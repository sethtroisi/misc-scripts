#!/usr/bin/env python

# Factoring Beyond First doesn't work with > 1G
# Improvise with
# 1. Load manyfactors.php filtered to > 1G
# 2. For each M<NUMBER> load it's page
# 3. Pull all factors and all bitranges
# 4. Queue 1-70 (fast)
# 5. Queue any missing bitranges

import os
import re
import requests
import time

from collections import defaultdict

import gmpy2

from bs4 import BeautifulSoup

from find_existing import process_results_file


GHZ_DAYS_PER_DAY = 1400
DIR = "past_1g/"
RESULTS_FILE = os.path.join(DIR, "results.txt")


def work_time(M, tf):
    '''Approx time(seconds) to TF M from 2^(tf-1) to 2^tf'''
    return 2 ** tf / M / 1.0e8 / GHZ_DAYS_PER_DAY


def load_cached_or_refresh(url, filename, max_age=12 * 3600):
    # Load filename is "fresh" else load page and save overfilename
    if os.path.exists(filename) and (time.time() - os.stat(filename).st_mtime) < max_age:
        with open(filename) as f:
            return f.read()
    else:
        print(f"\tRequesting: {url}")
        r = requests.get(url)
        assert r.status_code == 200
        with open(filename, "wb") as f:
            f.write(r.content)
        return r.content.decode()


def load_many():
    URL = "https://www.mersenne.ca/manyfactors.php"
    PARAMS = "?s=n&o=d&exp_min=1000000000&exp_max=9999999967&fac_min=5&fac_max=20&pct_min=0.000000&pct_max=100.000000"

    raw_page = load_cached_or_refresh(URL + PARAMS, os.path.join(DIR, "many_1g.html"))
    print("len(page):", len(raw_page))

    soup = BeautifulSoup(raw_page, "html.parser")
    for row in soup.find_all("tr"):
        exponent = row.find("a")
        if not exponent:
            continue
        text = exponent.text
        if text and re.match("^M[1-9][0-9,]*$", text):
            yield text[1:].replace(",", "")


def load_exponent(exponent):
    URL = "https://www.mersenne.ca/exponent/"
    raw_page = load_cached_or_refresh(URL + exponent, os.path.join(DIR, exponent + ".html"))

    M = int(exponent)
    factors = set()

    # Just grab everything that looks like a factor and check with 2*k*p+1
    for number in map(int, re.findall("[1-9][0-9]{9,}", raw_page)):
        if (number - 1) % (2 * M) == 0:
            assert pow(2, M, number) == 1
            if gmpy2.is_prime(number):
                factors.add(number)

    BITRANGE_RE = re.compile("^2[1-9][0-9]{0,2}$")

    soup = BeautifulSoup(raw_page, "html.parser")
    bitranges = set()
    for row in soup.find_all("tr"):
        if len(row.contents) == 11:
            fourth = row.contents[3].getText()
            fifth = row.contents[4].getText()
            if BITRANGE_RE.match(fourth) and BITRANGE_RE.match(fifth):
                a = fourth[1:]
                b = fifth[1:]
                #print(f"\t {a} to {b}")
                for bit_finished in range(int(a), int(b)):
                    bitranges.add(bit_finished)

    return factors, bitranges


if __name__ == "__main__":
    found_factors, found_factor_results, no_factor_results = process_results_file(RESULTS_FILE)
    tested = defaultdict(set)
    for M, low, high, _ in found_factor_results:
        for bit in range(low, high):
            tested[M].add(bit)
    for M, values in no_factor_results.items():
        for low, high in values:
            for bit in range(low, high):
                tested[M].add(bit)

    total_tested = sum(len(bits) for bits in tested.values())
    print("Found", total_tested, "ranges")

    lines = 0
    with open("past_1g/worktodo.txt", "w") as f:
        for exponent in load_many():
            # Let's do 1-70 for all of these:
            factors, bits = load_exponent(exponent)
            M = int(exponent)
            factors = sorted(factors)
            print("\t", M, "\t", len(factors), factors[:3], "...", factors[-2:])

            for found in found_factors[M]:
                if found not in factors and gmpy2.is_prime(found):
                    print("Found new factor!")
                    print(M, found)

            todo = []
            if any(bit not in tested[M] for bit in range(1,72)):
                f.write(f"Factor={exponent},1,72\n")
                todo.append("[1,72)")
                lines += 1

            for bit in range(72, 80):
                if bit not in bits and bit not in tested[M]:
                    if work_time(int(exponent), bit) < 120:
                        f.write(f"Factor={exponent},{bit},{bit+1}\n")
                        lines += 1
                        todo.append(str(bit))

            if todo:
                print("\t",", ".join(todo))

            print()

    print("Wrote", lines, "worktodo entries")
