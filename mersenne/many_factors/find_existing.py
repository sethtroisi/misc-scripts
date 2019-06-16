#!/usr/bin/env python3

import gmpy2
import re
import sqlite3

from collections import Counter
from tqdm import tqdm


FACTOR_FILE="/home/eights/Downloads/GIMPS/gimps-klist20181219.txt"
TF_DB_FILE="/home/eights/Downloads/GIMPS/mersenne_tf_limits.db"

STATUS_FILE="many_factor_progress.txt"
MANY_THRESHOLD = 6

REPROCESS = False

def process():
    many = []
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
                    many.append((int(cur_p), cur_factors))
                    many_counts[count] += 1
                    if many_counts[count] <= 50:
                        counts = ", ".join("{}x{}".format(*p) for p in sorted(many_counts.items()))
                        print ("{}: {:50} M{}".format(len(many), counts, many[-1][0]))
                cur_p = p
                cur_factors = []

            cur_factors.append(f)
    return many


def save(many):
    with open(STATUS_FILE, "w") as status_f:
        for m, factors in many:
            status_f.write("{}:{}\n".format(m, ",".join(map(str, factors))))


def load():
    many = []
    with open(STATUS_FILE) as status_f:
        for line in status_f:
            m, factors = line.split(":")
            m = int(m)
            factors = list(map(int, factors.split(",")))
            factors = [2 * m * f + 1 for f in factors]
            many.append((m, factors))
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
                todo.write(f"Factor=,{e},{bits},{bits+1}\n")


if REPROCESS:
    many = process()
    save(many)
else:
    many = load()

#verify(many)
generate_worktodo(many)

#tf_data = load_tf_db(many)
#for m, tf in tf_data:
#    if tf > 1:
#        print (m)

