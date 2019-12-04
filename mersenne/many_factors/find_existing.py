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
MANY_THRESHOLD = 6

MIN_EXP = 2 ** 20 + 100

# TJAOI has checked everything less than 2^66, this is the first bitlevel we would check
MIN_TF = 67
# A large number
MAX_TF = 100

MAX_TIME = 10 * 60
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


def work_time(M, tf):
    '''Approx time to TF M from 2^(tf-1) to 2^tf'''
    return 2 ** tf / M / 5.0e7 / GHZ_DAYS_PER_DAY


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
        5:1, 6:1, 7:1,
        8:4, 9:6,
        10:2, 11:3,
    }

    work = []
    for e, count in prime_count.items():
        assert count >= MANY_THRESHOLD
        next_tf = tf_data.get(e, MIN_TF-1)+1

        for bits in range(next_tf, MAX_TF+1):
            cost = int(work_time(e, bits))
            priority = cost / value[count]
            if cost > MAX_TIME:
                break
            work.append((priority, cost, e, bits))

    print ("{} exponents, {} work items, {:.1f}s to {:.1f}s".format(
        len(prime_count), len(work), min(work)[0], max(work)[0]))

    with open("worktodo.txt", "w") as todo:
        sum_cost = 0
        for i, (priority, cost, e, bits) in enumerate(sorted(work), 1):
            sum_cost += cost / 3600
            if i < 20 or i * 25 % len(work) < 25:
                todo.write(f"#{i}th,  TF {e},{bits} ~ {cost} seconds\n")
                print ("\t{:>5}th entry, {:10},{} | ({} factors) ~{}s, total {:.1f}h"
                    .format(i, e, bits, prime_count[e], cost, sum_cost))
            todo.write(f"Factor={e},{bits},{bits+1}\n")


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


def add_new_results(factors):
    tf_level = defaultdict(int)

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
                tf_level[M] = max(tf_level[M], upper_tf)

            match = re.match("M([0-9]*) has a factor: ([0-9]*).*TF:..:([0-9]{2})", result)
            if match:
                M, factor, upper_tf = map(int, match.groups())
                # Assumes that mfaktc was run with StopAfterFactor=0
                tf_level[M] = max(tf_level[M], upper_tf)
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

        if new_count >= 8:
            tf_next = tf_level[M] + 1
            cost_next = work_time(M, tf_next)
            for new_prime in new_primes:
                prime_len = len(str(new_prime))
                print ("M{:<9}: {:23}<{}>, {} => {} factors, cost({}): ~{:.2f}s".format(
                    M, new_prime, prime_len, count_f, new_count, tf_next, cost_next))

    print ()
    print ("{} no factor, {} compsite factors found, {} prime factors found".format(
        no_factor, len(composite), len(new_factors)))
    print ()
    deltas = Counter([(len(factors[M]), len(added)) for M, added in new_factors.items()])
    for (orig, added), count in deltas.most_common():
        print (f"\tHad {orig} factors + {added} = {orig + added} x{count}")
    print ()

    return tf_level


if REPROCESS:
    factors = process()
    verify(factors)
    save(factors)
else:
    factors = load()

# Used to verify the db & local results

# Used if you've been running and have new local results
tf_data = add_new_results(factors)

# Used if you want to generate worktodo in effort order.
generate_worktodo_ordered(factors, tf_data)

# Used to generate worktodo with lines that should all find factors.
#generate_doublecheck(factors)
