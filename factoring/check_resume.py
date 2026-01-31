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
import multiprocessing
import os
import random
import re
import subprocess
import sys
import time


parser = argparse.ArgumentParser(description='ecm resume files testing and spot verification')

parser.add_argument('resume_files', type=str, nargs="+")

parser.add_argument('-n', '--count', type=int, default=3,
    help='Number of results to verify')

parser.add_argument('--ecm_cmd', type=str, default="ecm",
    help='which ecm (e.g. ecm, ./ecm) to run')

parser.add_argument('--seed', type=int, default=1,
    help='Random seed')

parser.add_argument('--threads', type=int, default=4,
    help="Number of simultanious process to run for spot checking")

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


def read_and_parse_resume_file(fn):
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

            yield p, line


def diff_resume_files(args, fn_a, fn_b):
    """Compare the results in two files."""

    def abbr(line, n=30):
        return line if len(line) <= n + 3 else (line[:n] + "...")

    def read_and_parse(fn):
        lines = {}
        for p, line in read_and_parse_resume_file(fn):
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
        print(f"{matching} lines matched. Files had {len(a)} and {len(b)} lines")

    if mismatches:
        print(f"ERROR: files had {mismatches} mismatches")

    return mismatches


def _run_cmd(command):
    print("\t", command, "&")
    subprocess.check_call(
            command,
            stderr=subprocess.STDOUT,
            shell=True)

def spot_check(args):
    """Read a resume file, select a set of lines to try and verify, run ecm, verify."""

    fn = args.resume_files[0]
    assert os.path.isfile(fn), fn
    lines = list(read_and_parse_resume_file(fn))
    if args.verbose:
        print(f"Found {len(lines)} lines in {fn!r}")

    N = min(args.count, len(lines))
    assert N > 0

    # First, (N-2) random, Last
    samples = [lines[0]]
    if N > 2:
        indexes = sorted(random.sample(range(1, len(lines)-1), N-2))
        for line_i in indexes:
            samples.append(lines[line_i])
    if N > 1:
        samples.append(lines[-1])

    assert len(samples) == N, (len(samples), N)

    ecm = args.ecm_cmd
    ts = int(time.time())
    save_fn = f"verify_{ts}_{os.path.basename(fn)}"
    if not save_fn.endswith(".txt"):
        save_fn += ".txt"

    commands = []
    for parsed, line in samples:
        method = {"P-1": "-pm1", "P+1": "pp1", "ECM": ""}[parsed['METHOD']]
        B1 = parsed["B1"]
        X0 = parsed["X0"]
        N = parsed["N"]
        cmd = f'echo "{N}" | {ecm} {method} -savea "{save_fn}" -x0 {X0} {B1} 0'
        commands.append(cmd)

    with multiprocessing.Pool(processes=args.threads) as pool:
            results = pool.map(_run_cmd, commands)

    if args.verbose:
        print()
        print("Testing output (can be rerun with):")
        print("\t", f'python {sys.argv[0]} {fn!r} {save_fn!r}')
        print()

    diff_resume_files(args, fn, save_fn)



if __name__ == '__main__':
    args = parser.parse_args()

    seed = args.seed
    if seed is None:
        args.seed = random.randrange(2 ^ 32)

    if len(args.resume_files) == 1:
        spot_check(args)
    elif len(args.resume_files) == 2:
        mismatches = diff_resume_files(args, *args.resume_files)
        exit(0 if mismatches == 0 else 1)
    else:
        print("Not sure what to do with", len(args.resume_files), "files")
        exit(1)
