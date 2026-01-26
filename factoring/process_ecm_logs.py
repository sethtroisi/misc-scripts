#!/usr/bin/env python
"""Helper tool for reporting found factors to Studio Kamada."""

import argparse
import csv
import datetime
import json
import math
import os
import re
import sys
import time
import urllib.parse
import urllib.request

from collections import defaultdict, Counter

import sympy.ntheory

import ecm_resume


def get_argparser():
    parser = argparse.ArgumentParser(
            description='Process ECM logs for factors')

    parser.add_argument('-a', '--allcomp', help='allcomp.txt filename', required=True)
    parser.add_argument('-l', '--logs', help='list of log files', nargs='*')
    parser.add_argument('-d', '--factor-distribution',
            action='store_true',
            help='print distribution of found factor length')
    parser.add_argument('--split', help="Split allcomp.txt to runs", action='store_true')
    parser.add_argument('--rebatch',
            nargs="+",
            help="Load all residuals split to batches")
    parser.add_argument('--submit',
            action='store_true',
            help='if factors should be submitted to https://stdkmd.net/')
    return parser


def number_with_digits(n):
    return f"{n}<{len(str(n))}>"


def split_numbers_to_batches(numbers):
        # Breakpoints related to kernel sizes
        BREAK_POINTS = list(reversed([128 * k - 8 for k in (6, 8, 10, 12, 14, 16, 20)]))

        GROUP_SIZE = 1792

        groups = []
        current = []
        for number in numbers:
            assert 1 < number < 2 ** 2048

            bit_size = number.bit_length()
            if bit_size >= BREAK_POINTS[-1] or len(current) == GROUP_SIZE:
                if current:
                    print("new batch of {} {} to {} bits".format(
                        len(current),
                        current[0].bit_length(),
                        current[-1].bit_length()))
                    groups.append(current)
                    current = []

                while bit_size >= BREAK_POINTS[-1]:
                    print()
                    BREAK_POINTS.pop(-1)

            current.append(number)

        if current:
            print("new batch of {} {} to {} bits".format(
                len(current),
                current[0].bit_length(),
                current[-1].bit_length()))
            groups.append(current)
            current = []


        date = datetime.datetime.now().strftime("%Y%m%d")
        for i, group in enumerate(groups):
            max_bits = group[-1].bit_length()
            fn = f"pm1_stdkmd_{date}_batch_{i:02d}_{max_bits}.txt"
            print(f"Writing {len(group)} rows to {fn!r}")
            assert not os.path.exists(fn)
            with open(fn, "w") as f:
                for number in group:
                    f.write(str(number) + "\n")


def validate_residual(parsed):
    keys = ("METHOD", "N", "B1", "X", "X0")
    return all(key in parsed for key in keys)

def rebatch_residuals(args):
    """
    Load all residuals
        Drop all but largest B1
    Figure out for each N in residual if it has new factors
        N should appear in allcomp_2023.txt
        Get factors from newest allcomp_<DATE>.txt
    Split up residuals by batch size
        When B1 doesn't match ask for CPU eval?
    """

    loaded = 0
    residuals = {}

    print(args.rebatch)

    for fn in args.rebatch:
        with open(fn) as f:
            for i, line in enumerate(f):
                if not line:
                    continue

                loaded += 1
                parsed = ecm_resume.parse_resume(line)
                if not validate_residual(parsed):
                    print(f"Bad residual line {i} in {f}: {line[:40]}...")
                    exit(1)

                n = parsed['N']
                current = residuals.get(n)
                update = current is None
                if current:
                    update = parsed['B1'] > current[0]['B1']

                if update:
                    residuals[n] = (parsed, line)

    print(f"Loaded {loaded} residuals, {len(residuals)} unique")
    for B1, count in sorted(Counter(p['B1'] for p,l in residuals.values()).items()):
        print(f"\t{B1=:,} x {count}")

    for p, l in residuals.values():
        if p['B1'] == 1000000:
            print(p)


def load_allcomp(fn):
    numbers = []
    lookup = {}
    with open(fn) as f:
        reader = csv.DictReader(f)
        for row in reader:
            n = int(row["CompositeNumber"])
            lookup[n] = row
            numbers.append(n)

    numbers.sort()
    assert len(numbers) > 25000, len(numbers)
    return numbers, lookup


def get_logs(log_fns):
    log = []
    for fn in log_fns:
        with open(fn) as f:
            log.extend((l.strip() for l in f.readlines()))

    return log


def parse_logs(logs):
    """Parse logs into per-ECM output."""

    factors = defaultdict(list)

    # Regular Expression that indicate start of log
    starts = (
        re.compile('^Resuming ... residue'),
        re.compile('^Input number is'),
        re.compile('^GMP-ECM'),
        re.compile('^v{10}'),
    )
    ends = (
        re.compile('Step 2 took'),
        re.compile(r'^\^{10}'),
    )

    groups = []
    grouped = []
    for i, line in enumerate(logs):
        is_start = line.startswith(("R", "I", "G", "v")) and any(re.search(start, line) for start in starts)

        # First line should be start line
        assert len(grouped) > 0 or is_start, (grouped, line)

        # If new start, one of the recent lines should be an end
        if len(grouped) >= 5 and is_start or line.startswith('^^^^^^'):
            # DEBUG Truncated inputs
            if False:
                if not grouped[0].startswith("vvvvv"):
                    # Step 2 took, Factor found, Found Prime factor, cofactor
                    if not any(re.search(end, prev) for end in ends for prev in grouped[-4:]):
                        print("TRUNCATED INPUT")
                        for g in grouped:
                            out = g.replace("\t", "  ").strip()
                            print(f"\t|{out:81}|")
                        print("*" * 80)

            groups.append(grouped)
            grouped = []

        grouped.append(line)

    if grouped:
        groups.append(grouped)

    for group in groups:
        for line in group:
            match = re.search("Factor found in step .: ([0-9]+)$", line)
            if match:
                f = int(match.group(1))
                assert 2 <= f <= 10 ** 65, f
                factors[f].append(group)

    print("\t", len(groups), "ecm runs", sum(len(g) for g in groups), "lines")

    return factors


def get_contribution_parameters(classification, logs):
    """
    Get URL params for submitting to https://stdkmd.net/nrr/c.cgi

    Params:
        classification: number label e.g. "94447_297"
        logs: logs as a list
    """

    assert isinstance(logs, (list, tuple)), logs
    results = "".join(l.strip() + "\n" for l in logs)
    return {
        "q": classification,
        "mode": "submit",
        "results": results,
        "software": "GMP-ECM 7.0.6, ecm-db 0.1",
        "environment": "1080 Ti for PM1 stage1",
        "name": "Seth Troisi",
        "mail": "braintwo@gmail.com",
    }


def handle_factor(f, n, submit, row, log):
    assert n % f == 0
    expr = row["Expression"]
    label = row['#"Label"']
    power = row["N"]
    classification = f"{label}_{power}"
    contribute_url = f"https://stdkmd.net/nrr/c.cgi?q={classification}"
    details_url = f"https://stdkmd.net/nrr/cont/{label[0]}/{label}.htm#N{power}"
    factors = sorted(sympy.ntheory.factorint(f-1).items())
    minB2 = max(p for p, e in factors)
    minB1 = max(p ** e for p, e in factors if p != minB2)
    print(f"\t{f} divides {expr}")
    print(f"\t{contribute_url:45} {details_url}")
    print("\tP-1 =", " * ".join(f"{p}" if e == 1 else f"{p}^{e}" for p, e in factors))
    print("\tRequires: B1 >= {:9,} B2 >= {:9,} || B1 >= 1e{}, B2 >= 1e{}".format(
        minB1, minB2, len(str(minB1)), len(str(minB2))))

    # Small remaining composite number, suitable for GNFS
    cf = n // f
    if len(str(cf)) < 145 and not sympy.isprime(cf):
        print(f"\t{len(str(cf))}-digit composite remaining")
        print("\t\t", cf)
    print()

    # Submit numbers
    if submit:
        time.sleep(0.1)
        page = urllib.request.urlopen(contribute_url)
        assert page.code == 200, page.code
        data = page.read().decode()
        assert len(data) > 2000, len(data)

        if str(f) in data or "This number has been factored." in data:
            print("ALREADY KNOWN")
            return
        if "Please wait until the factor table" in data:
            print("WAITING ON factor table UPDATE")
            return

        print("-"*80)
        for line in log[0]:
            print(line.strip())
        print("-"*80)

        if input("Submit [N]:").lower() in ("y", "yes"):
            print("Submitting")
            params = get_contribution_parameters(classification, log[0])
            form_data = urllib.parse.urlencode(params).encode()

            req = urllib.request.Request(contribute_url, data=form_data, method='POST')
            with urllib.request.urlopen(req) as f:
                data = f.read().decode()
                received = "Contribution was received" in data
                print("\tResponse:", f.code, "Contribution received:", received)
                assert f.code == 200 and received, data
    print()


def main(args):
    numbers, lookup = load_allcomp(args.allcomp)

    if args.split:
        split_numbers_to_batches(numbers)
        return

    if args.rebatch:
        rebatch_residuals(args)
        return

    assert args.logs, "No log filenames specified"
    logs = get_logs(args.logs)
    assert logs, "No logs found"
    print(f"{len(args.logs)} log files contained {len(logs)} lines\n")

    factors = parse_logs(logs)

    # TODO something better here
    extra_factors = [
    ]
    '''
    Composite factor
33696225345898595418519136300455807677197161879159983273906152538118480634518675311038180741771055825530494319368895712771779857659506133711
Reservation key is 9366?
    '''

    for f in extra_factors:
        if f not in factors:
            print(f, "Not in any log file!")
            factors[f].append([])

    print(f"\n\nFound {len(factors)} unique factors!\n\n")

    # Factor length distribution
    if args.factor_distribution:
        assert factors
        print(min(factors), "to", max(factors))
        print()
        sizes = [len(str(f)) for f in sorted(factors)]
        for digits in range(sizes[0], sizes[-1] + 1):
            count = sizes.count(digits)
            print(f'{digits:2d} | {count:3d} {"*" * count}')
        print()
        exit()

    # Factor info
    if True:
        new = 0
        for f, log in sorted(factors.items()):
            found = [n for n in lookup if n % f == 0]
            if not found:
                # Number has already been submitted.
                print (f"\n{number_with_digits(f)} already submitted")
                continue

            log_lines = sum(len(l) for l in log)
            print (f"\n{number_with_digits(f)} with {log_lines} log lines")
            new += 1

            assert len(found) == 1, f"{f} divides {len(found)} numbers"
            for n in found:
                handle_factor(f, n, args.submit, lookup[n], log)

        print(new, "factors not yet in allcomp.txt")


if __name__ == "__main__":
    parser = get_argparser()
    args = parser.parse_args()

    main(args)
