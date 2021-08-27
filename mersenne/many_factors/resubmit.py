#!/usr/bin/env python3

import os
import re

from collections import defaultdict

import gmpy2

RESULTS_FILE = "results/megaresults.txt"


def find_composite():
    """
    Historically the mersenne.org manual results didn't mark as complete
    ranges that included a composite result.
    e.g. https://www.mersenne.org/report_exponent/?exp_lo=113644673&full=1

    Search for any result that contained 1 or more composite factor and save
        <factor>
        <factor>
        found <x> factor for M<z> from 2^72 to 2^73 [mfaktc 0.21 barrett76_mul32_gs]
    """

    # results[exp][bitlevel] = []
    results = defaultdict(lambda: defaultdict(list))

    # set of (exp, bitlevels) that will need to be resubmitted
    composite = set()

    assert os.path.isfile(RESULTS_FILE), RESULTS_FILE
    with open(RESULTS_FILE) as results_file:
        for result in results_file:
            match = re.match("M([0-9]*) has a factor: ([0-9]*).*TF:..:([0-9]{2})", result)
            if match:
                M, factor, upper_tf = map(int, match.groups())
                # Wonky factor, see https://www.mersenneforum.org/showthread.php?p=585014#post585014
                if factor == 147602823780943516039:
                    continue

                # Composite factor
                if not gmpy2.is_prime(factor):
                    results[M][upper_tf].append(result)
                    log2 = gmpy2.log2(factor)
                    assert (upper_tf - 1) < log2 < upper_tf, (factor, log2, upper_tf)
                    composite.add( (M, upper_tf) )

            match = re.match("found [1-9]+ factors? for M([0-9]+) from 2\^([0-9]+) to 2\^([0-9]+)", result)
            if match:
                # Assumes that mfaktc was run with StopAfterFactor=0 (which is was
                M, low, high = map(int, match.groups())
                results[M][high].append(result)

    print ()
    print ("{} compsite factors found, {} exponents {} bit levels".format(
        len(composite), len(results), sum(map(len, results.values()))))
    print ()

    for M, high in sorted(composite):
        if high <= 68:
            continue
        #print (f"\t# M{M} 2^{high-1} to 2^{high}")
        for result in results[M][high]:
            print (result.strip())
        #print ()


if __name__ == "__main__":
    find_composite()
