#!/usr/bin/env python3

import gmpy2
import math
import os
import re
import sqlite3

from collections import Counter, defaultdict
from tqdm import tqdm


BASE_FOLDER = os.path.expanduser("~/Downloads/GIMPS/")

FACTOR_FILE = os.path.join(BASE_FOLDER, "gimps-klist20181219.txt")
TF_DB_FILE = os.path.join(BASE_FOLDER, "mersenne_tf_limits.db")
RESULTS_FILE = os.path.join(BASE_FOLDER, "results/megaresults.txt")

STATUS_FILE="many_factor_progress.txt"
MANY_THRESHOLD = 9

MIN_EXP = 2 ** 20 + 100

# TJAOI has checked everything less than 2^66, this is the first bitlevel we would check
MIN_TF = 67
# A large number
MAX_TF = 100

MAX_TIME = 20 * 60
GHZ_DAYS_PER_DAY = 1400     # Based on 1080ti with mfaktc


REPROCESS = False

def process():
    factors = defaultdict(list)
    factor_counts = Counter()

    with open(FACTOR_FILE) as factor_f:
        cur_p = None
        cur_factors = []
        for line in factor_f:
            p, f = map(int, line.strip().split(","))
            if p != cur_p:
                count = len(cur_factors)
                if count >= MANY_THRESHOLD:
                    factors[cur_p] = cur_factors
                    factor_counts[count] += 1
                    if factor_counts[count] <= 20:
                        # Z expontents x 6 factors
                        counts = ", ".join("{1}x{0}".format(*p) for p in factor_counts.most_common())
                        print ("{}: {:50} M{}".format(len(factors), counts, p))
                cur_p = p
                cur_factors = []

            cur_factors.append(f)
    return factors


def process_results_file(filename):
    factor_results = defaultdict(set)
    found_factor_results = {}
    no_factor_results = defaultdict(list)

    assert os.path.isfile(filename), filename
    with open(filename) as results_file:
        for result_line in results_file:
            result_line = result_line.strip()
            key_match = re.search("for M([0-9]*) from 2\^(..) to 2\^(..)", result_line)

            # Correctly reported
            match = re.match("no factor for M([0-9]*)", result_line)
            if match:
                assert key_match, result_line
                e, low, high = map(int, key_match.groups())
                no_factor_results[e].append((low, high, result_line))

            match = re.match("found ([0-9]*) factors?", result_line)
            if match:
                assert key_match, result_line
                count = int(match.group(1))
                e, low, high = map(int, key_match.groups())
                key = (e, low, high, result_line)
                assert found_factor_results.get(key) in (None, count)
                found_factor_results[key] = count


            match = re.match("M([0-9]*) has a factor: ([0-9]*)", result_line)
            if match:
                e, factor = map(int, match.groups())
                # Assert that mfaktc was not run with StopAfterFactor=2
                assert '*' not in result_line
                factor_results[e].add(factor)

    return factor_results, found_factor_results, no_factor_results


def generate_no_results_for_combosite_factors(known_factors, results_filename):
    '''Generate no factor for M... when the only factor is composite'''
    factor_results, found_factor_results, _ = process_results_file(results_filename)

    i = 0
    for (e, low, high, result_line), count in found_factor_results.items():
        # Weirdness with 67.0002 bit factor
        if e == 960477823 and high == 67: continue

        factors = [f for f in factor_results[e] if low < math.log2(f) < high]
        primes = [f for f in factors if gmpy2.is_prime(f)]
        assert count == len(factors), (e, low, high, count, factors, factor_results[e])

        if len(primes) == 0:
            known = known_factors[e]
            # These are clearly known.
            for test in [2 * e * k+ 1 for k in range(1000)]:
                if test not in known and gmpy2.is_prime(test):
                    known.append(test)

            # all factors should be composite
            for f in factors:
                known = [f_old for f_old in known_factors[e] if f % f_old == 0]
                assert len(known) == 2, (e, f, known, known_factors[e])

            i += 1
            #print (f"[{i}] Actually found {count} composite factor(s) for {e} from 2^{low} to 2^{high}")
            new_result_line = result_line.replace(f"found {count} factor" + "s" * (count > 1), "no factor")
            assert new_result_line != result_line, (result_line)
            if i % 100 == 0:
                print ("\t", i)
            print (new_result_line)


def work_time(M, tf):
    '''Approx time to TF M from 2^(tf-1) to 2^tf'''
    return 2 ** tf / M / 1.0e8 / GHZ_DAYS_PER_DAY


def format_time(time):
    if time < 1000:
        return f"{time:.1f}s"
    return f"{time/3600:.2f}h"


def save(factors):
    with open(STATUS_FILE, "w") as status_f:
        for m, factors in sorted(factors.items()):
            status_f.write("{}:{}\n".format(m, ",".join(map(str, factors))))


def load():
    factors = defaultdict(list)
    with open(STATUS_FILE) as status_f:
        for line in status_f:
            e, k_factors = line.split(":")
            e = int(e)
            factors[e] = [2 * e * int(k) + 1 for k in k_factors.split(",")]
    return factors


def verify(factors):
    print ("Checking existing factors")
    for m, m_factors in tqdm(factors.items()):
        for f in m_factors:
            assert pow(2, m, f) == 1, (m, f)

    print ("Verifying factors up to 2^34")
    for m, m_factors in tqdm(factors.items()):
        # for really small m we want to avoid this as it takes a long time
        # we also can't use mfaktc so skip them.
        if m <= MIN_EXP:
            continue

        assert len(m_factors) == len(set(m_factors)), (m, m_factors)
        kmax = 2 ** 34 // (2 * m) + 1
        for k in range(1, kmax + 1):
            p = 2 * m * k + 1
            if pow(2, m, p) == 1:
                # Maybe a composite factor.
                t = p
                for f in m_factors:
                    while t % p == 0:
                        t //= p
                assert t == 1, (m, k, p, m_factors)


def generate_worktodo_ordered(factors, tf_data):
    prime_count = Counter({m:len(fs) for m, fs in factors.items() if fs and m > MIN_EXP})

    # Divide cost when we find this many primes
    value = {
        8:6,
        9:30,
        10:60,
        11:300,
    }

    count_missing = 0
    work = []
    for e, count in prime_count.items():
        # Handles if we accidentally get extra numbers added by megaresult.txt
        if count < MANY_THRESHOLD:
            continue

        # check if none consecutive set
        if tf_data[e]:
            tf = tf_data[e]
            missing = set(range(MIN_TF, max(tf))) - set(tf)
            for bit in missing:
                count_missing += 1
                print ("Missing TF range {} for {} | {}".format(bit, e, sorted(tf_data[e])))

        for bits in range(MIN_TF, MAX_TF+1):
            if bits in tf_data[e]:
                continue

            cost = int(work_time(e, bits))
            priority = cost / value.get(count, 1)
            if priority > MAX_TIME:
                break

            work.append((priority, cost, e, bits))

    if count_missing:
        print ("\t{} missing exponents".format(count_missing))

    print ("{} exponents, {} work items, {:.1f}s to {:.1f}s".format(
        len(prime_count), len(work), min(work)[0], max(work)[0]))

    with open("worktodo.txt", "w") as todo:
        sum_cost = 0
        for i, (priority, cost, e, bits) in enumerate(sorted(work), 1):
            sum_cost += cost
            if i < 20 or i * 25 % len(work) < 25:
                todo.write(f"#{i}th,  TF {e},{bits} ~ {cost} seconds\n")
                print ("\t{:>5}th entry, {:10},{} | ({} factors) ~{}, total {}"
                    .format(i, e, bits, prime_count[e],
                            format_time(cost), format_time(sum_cost)))
            todo.write(f"Factor={e},{bits-1},{bits}\n")


def generate_doublecheck(factors):
    count = 0
    num_factors = 0
    double_check = []
    for M, e_factors in factors.items():
        bits = sorted(len(bin(factor)) - 2 for factor in e_factors)
        bits = [b for b in bits if b > MIN_TF]
        bits = [b for b in bits if work_time(M, b) <= 120]

        num_factors += len(bits)
        for b in set(bits):
            time_guess = work_time(M, b)
            double_check.append((time_guess, f"Factor={M},{b-1},{b}\n"))
            count += 1


    with open("worktodo.txt.doublecheck", "w") as todo:
        for t, line in sorted(double_check):
            todo.write(line)

    print (f"Wrote {count} lines should find {num_factors} factors")


def add_manual_tf_data(tf_data):
    # Manual tf data
    tf_data[1938317].update(set(range(1,76+1)))     # Thanks Kriesel (~8000 GHz-days!)
    tf_data[5977753].update(set(range(1,74+1)))     # Thanks ATH & BloodERazor
    tf_data[7508981].update(set(range(1,77+1)))     # Thanks M. Miller & Kriesel
    tf_data[9100919].update(set(range(1,75+1)))     # Thanks ATH
    tf_data[9325159].update(set(range(1,75+1)))     # Thanks ATH
    tf_data[27366961].update(set(range(1,76+1)))    # Thanks ATH
    tf_data[28035701].update(set(range(1,76+1)))    # Thanks ATH
    tf_data[31866377].update(set(range(1,76+1)))    # Thanks Ducho_YYZ & ATH
    tf_data[60593041].update(set(range(1,77+1)))    # Thanks ATH
    tf_data[458703437].update(set(range(1,82+1)))   # Thanks Kriesel & Ramgeis
    tf_data[566448359].update(set(range(1,83+1)))   # Thanks ATH & M. Miller
    tf_data[940572491].update(set(range(1,81+1)))   # Thanks Kriesel
    tf_data[566448359].update(set(range(1,83+1)))   # Thanks Matthew M. and ATH


def add_new_results(factors):
    tf_level = defaultdict(set)

    no_factor = 0
    known_prime = 0
    composite = set()
    new_factors = defaultdict(set)

    assert os.path.isfile(RESULTS_FILE), RESULTS_FILE
    with open(RESULTS_FILE) as results_file:
        for result in results_file:
            match = re.match("no factor for M([0-9]*) from 2\^.. to 2\^(..)", result)
            if match:
                no_factor += 1
                M, upper_tf = map(int, match.groups())
                tf_level[M].add(upper_tf)

            match = re.match("M([0-9]*) has a factor: ([0-9]*).*TF:..:([0-9]{2})", result)
            if match:
                M, factor, upper_tf = map(int, match.groups())
                # Assumes that mfaktc was run with StopAfterFactor=0
                tf_level[M].add(upper_tf)
                if gmpy2.is_prime(factor):
                    if factor in factors[M]:
                        known_prime += 1
                    else:
                        new_factors[M].add(factor)
                else:
                    composite.add((M, factor))

    for M, new_primes in sorted(new_factors.items()):
        for f1 in new_primes:
            for f2 in factors[M]:
                assert f1 % f2 != 0 and f2 % f1 != 0, (M, f1, f2)

        count_f = len(factors[M])
        new_count = count_f + len(new_primes)

        for new_prime in new_primes:
            factors[M].append(new_prime)

        if new_count >= 9:
            tf_next = max(tf_level[M]) + 1
            cost_next = work_time(M, tf_next)
            for i, new_prime in enumerate(sorted(new_primes)):
                lead = "M{:<9}:".format(M) if i == 0 else " " * 11
                prime_len = len(str(new_prime))
                cost_time = "%" % cost_next if cost_next < 1000 else "%.2h"
                print ("{} {:23}<{}>, {} => {} factors, cost({}): ~{}".format(
                    lead, new_prime, prime_len, count_f, new_count,
                    tf_next, format_time(cost_next)))

    print ()
    print ("{} no factor, {} compsite factors found, {} prime factors found".format(
        no_factor, len(composite), len(new_factors)))
    print ()
    deltas = Counter([(len(factors[M]), len(added)) for M, added in new_factors.items()])
    for (new, added), count in deltas.most_common():
        if new == added: continue
        print (f"\tHad {new-added} factors + {added} = {new:2} x{count}")
    print ()

    return tf_level


if __name__ == "__main__":
    if REPROCESS:
        factors = process()
        verify(factors)
        save(factors)
    else:
        factors = load()


    #generate_no_results_for_combosite_factors(factors, RESULTS_FILE)

    # Used to verify the db & local results

    # Used if you've been running and have new local results
    tf_data = add_new_results(factors)
    add_manual_tf_data(tf_data)

    # Used if you want to generate worktodo in effort order.
    generate_worktodo_ordered(factors, tf_data)

    # Used to generate worktodo with lines that should all find factors.
    #generate_doublecheck(factors)
