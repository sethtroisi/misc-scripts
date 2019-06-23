#!/usr/bin/env python3

import math
import gmpy2
import re
import sqlite3

from collections import Counter, defaultdict
from tqdm import tqdm


FACTOR_FILE="/home/eights/Downloads/GIMPS/gimps-klist20181219.txt"
TF_DB_FILE="/home/eights/Downloads/GIMPS/mersenne_tf_limits.db"
RESULTS_FILE="/home/eights/Downloads/megaresults.txt"

STATUS_FILE="many_factor_progress.txt"
MANY_THRESHOLD = 6

REPROCESS = False


def process():
    many = {}
    many_counts = Counter()

    with open(FACTOR_FILE) as factor_f:
        cur_p = None
        cur_factors = []
        for line in factor_f:
            p, f = line.strip().split(",")
            if p != cur_p:
                count = len(cur_factors)
                if count >= MANY_THRESHOLD:
                    cur_factors = sorted(map(int, cur_factors))
                    many[int(cur_p)] = cur_factors
                    many_counts[count] += 1
                    if many_counts[count] <= 50:
                        counts = ", ".join("{}x{}".format(*p) for p in sorted(many_counts.items()))
                        print ("{}: {:50} M{}".format(len(many), counts, many[-1][0]))
                cur_p = p
                cur_factors = []

            cur_factors.append(f)
    return many


def work_time(M, tf):
    '''Approx time to TF M from 2^(tf-1) to 2^tf on 1080ti'''
    return 2 ** tf / M / 1.4e12


def save(many):
    with open(STATUS_FILE, "w") as status_f:
        for m, factors in sorted(many.items()):
            status_f.write("{}:{}\n".format(m, ",".join(map(str, factors))))


def load():
    many = {}
    with open(STATUS_FILE) as status_f:
        for line in status_f:
            M, factors = line.split(":")
            M = int(M)
            factors = list(map(int, factors.split(",")))
            factors = [2 * M * f + 1 for f in factors]
            many[M] = factors
    return many

def load_tf_db(many):
    with sqlite3.connect(TF_DB_FILE) as conn:
        conn.row_factory = sqlite3.Row

        cur = conn.cursor()

        # Create a temp table so we can join on it to retrieve all exponents.
        cur.execute("CREATE TEMP TABLE lookup_exp (e integer)")

        exponents = [(e,) for e, factors in many]
        cur.executemany('INSERT INTO temp.lookup_exp VALUES (?)', exponents)

        cur.execute('SELECT exponent, tf from prime_numbers_0 '
                    'INNER JOIN lookup_exp on exponent = e ')
        rows = list(map(tuple, cur.fetchall()))
        cur.close()
    return rows


def verify(many):
    print ("Checking existing factors")
    for m, factors in tqdm(many):
        for f in factors:
            assert pow(2, m, f) == 1, (m, f)

    print ("Verifying factors up to 2^34")
    for m, factors in tqdm(many):
        # for really small m we want to avoid this as it takes a long time
        # we also can't use mfaktc so skip them.
        if m <= 1e6:
            continue

        assert len(factors) == len(set(factors)), (m, factors)

        kmax = 2 ** 34 // (2 * m) + 1

        for k in range(1, kmax + 1):
            p = 2 * m * k + 1
            if pow(2, m, p) == 1:
                # Maybe a composite factor.
                t = p
                for f in factors:
                    while t % p == 0:
                        t //= p
                assert t == 1, (m, k, p, factors)


def generate_worktodo(many):
    exps = sorted([m for m, factors in many], reverse=True)
    exps = [e for e in exps if e > 1e6]

    with open("worktodo.txt", "w") as todo:
        for bits in range(66, 75):
            for e in exps:
                todo.write(f"Factor={e},{bits},{bits+1}\n")

def generate_doublecheck(many):
    # min tf
    min_tf = 65 # TJAI has checked everything less than this.

    count = 0
    num_factors = 0
    double_check = []
    for M, factors in many.items():
        bits = sorted(len(bin(factor)) - 2 for factor in factors)
        bits = [b for b in bits if b > min_tf]
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


def add_new_results(many):
    tf_level = defaultdict(int)

    no_factor = 0
    composite = set()
    known_prime = 0
    new_primes = Counter()

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
                if gmpy2.is_prime(factor):
                    if factor in many.get(M, []):
                        known_prime += 1
                    else:
                        new_primes[(M, factor)] += 1
                        tf_level[M] = max(tf_level[M], upper_tf)
#                        print(result.strip())
                else:
                    composite.add((M, factor))
    print()

    ''' These were all known (discovered after, logs lost...)
    not_found_twice = 0
    for (M, f), count in new_primes.most_common():
        if count != 2:
            bits = math.log2(f)
            if bits <= 65 or work_time(M, int(bits+1)) > 120:
                continue
            print (count, M, "\t", f, math.log2(f))
            print (f"M{M} has a factor: {f}")

            not_found_twice += 1
    print (not_found_twice, "were not found twice")
    print ()
    '''


    new_primes = sorted(new_primes)
    original = {}
    delta = Counter()
    for M, test in new_primes:
        factors = many.get(M, [])
        for f in factors:
            assert test % f != 0, (M, test, f)

        if M not in original:
            original[M] = len(factors)
        factors.append(test)
        count_f = len(factors)
        delta[(original[M], len(factors) - original[M])] += 1
        if count_f >= 8:
            tf_next = tf_level[M]
            cost_next = work_time(M, tf_next)
            print ("M{}: factor {}<{}>, +{} to {} total factors, cost next({}): ~{:.2f}s".format(
                M, test, len(str(test)), count_f - original[M], count_f, tf_next, cost_next))

    print ()
    print ("{} no factor, {} compsite factors found, {} prime factors found".format(
        no_factor, len(composite), len(new_primes)))
    print ()
    for (orig, new), instances in delta.most_common():
        print (f"\tHad {orig} factors + {new} = {orig + new} x{instances}")
    print ()

if REPROCESS:
    many = process()
    save(many)
else:
    many = load()

add_new_results(many)

#verify(many)
#generate_worktodo(many)
#generate_doublecheck(many)

#tf_data = load_tf_db(many)
#for m, tf in tf_data:
#    if tf > 1:
#        print (m)

