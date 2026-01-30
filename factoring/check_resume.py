# Script to manually check resume lines.
#
# Use this to verify GPU results or something.
#
# to diff two resume files
#  $ python check_resume.py full.resume.txt partial.resume.txt
#
# to test 10 numbers
#  $ python check_resume.py --samples 10
#
# to see all options
#  $ python check_resume.py -h
#
# On error, will exit with return code 1 and stdout
#    'Wrong result for <fn>:<line>: LINE'

import argparse
import random
import re
import subprocess

parser = argparse.ArgumentParser(description='ecm resume files testing and spot verification')

parser.add_argument('resume_files', type=str, nargs="+")

parser.add_argument('--ecm_cmd', type=str, default="ecm",
    help='which ecm (e.g. ecm, ./ecm) to run')

parser.add_argument('--seed', type=int, default=1,
    help='Random seed')

parser.add_argument('--verbose', '-v', action='count', default=1,
    help='Print more output (pass -v -v for even more)')
parser.add_argument('--quiet', '-q',
    action='store_const', const=0, dest='verbose',
    help='Suppress most output')



def parse_resume(line):
    """Parse an ECM resume line."""
    IGNORE = ["PROGRAM", "WHO", "TIME"]
    INT = ["N", "B1", "X", "Y", "X0", "Y0", "CHECKSUM"]

    parsed = {}
    for part in line.split(";"):
        part = part.strip()
        if not part:
            continue

        key, value = part.split("=", 1)
        if key in IGNORE:
            continue

        if key in INT:
            if value.startswith("0x"):
                value = int(value, 16)
            else:
                value = int(value)

        assert key not in parsed, f"Duplicate key: {key}"
        parsed[key] = value

    return parsed

def entries_match(e_a, e_b):
    """Check if two entries (parsed_resume lines) match."""
    # Use dict so order is preserved
    keys = list(dict.fromkeys(list(e_a.keys()) + list(e_b.keys())))

    for k in keys:
        v_a = e_a.get(k)
        v_b = e_b.get(k)
        if v_a == v_b:
            continue

        if k in ("COMMENT", ):
            continue

        # missing zeros is probably fine for these fields
        if k in ("X", "Y", "X0", "Y0") and v_a in (0, None) and v_b in (0, None):
            continue

        return False, (k, v_a, v_b)

    return True, None


def diff_resume_files(args, fn_a, fn_b):
    """Compare the results in two files."""

    def abbr(line, n=30):
        return line if len(line) <= n + 3 else (line[:n] + "...")

    def read_and_parse(fn):
        lines = {}
        with open(fn) as f:
            for i, line in enumerate(f):
                line = line.strip()
                if not line:
                    continue

                p = parse_resume(line)
                keys = ("METHOD", "N", "B1", "CHECKSUM")
                if any(key not in p for key in keys):
                    print("BAD Resume line {i} in {fn}: {abbr(line)}")
                    continue

                key = p["METHOD"] + "_" + str(p["N"])
                if key in lines:
                    print("Ignoring duplicate entry for", key)
                    continue

                lines[key] = (p, line)
        return lines

    if args.verbose:
        print(f"Comparing resume files: {fn_a!r} and {fn_b!r}")

    a = read_and_parse(fn_a)
    b = read_and_parse(fn_b)

    if len(b) > len(a):
        a, b = b, a
        fn_a, fn_b = fn_b, fn_a

    is_superset = a.keys() >= b.keys()

    matching = 0
    mismatches = 0
    for k, (p_a, a_line) in a.items():
        if k in b:
            match, diff = entries_match(p_a, b[k][0])
            if match:
                matching += 1
            else:
                mismatches += 1
                print(f"\tMISMATCH {mismatches}: {diff} | {k}")

        if not is_superset:
            print("\tPresent only in {fn_a}: {abbr(a_line, 50)}")
            continue

    if not is_superset:
        for k, e in b.items():
            if k not in a:
                print("\tPresent only in {fn_b}: {abbr(a_line, 50)}")
                continue

    if args.verbose:
        print(f"{matching} of lines matched. Files had {len(a)} and {len(b)} lines")

    if mismatches:
        print(f"ERROR: files had {mismatches} mismatches")

    return mismatches


def spot_check(fn):
    """TODO"""
    pass




if __name__ == '__main__':
    args = parser.parse_args()

    seed = args.seed
    if seed is None:
        args.seed = random.randrange(2 ^ 32)

    if len(args.resume_files) == 2:
        diff_resume_files(args, *args.resume_files)
