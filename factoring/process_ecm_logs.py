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


def _get_argparser():
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
    parser.add_argument('--submit', default=False,
            action='store_true',
            help='if factors should be submitted to https://stdkmd.net/')
    parser.add_argument('-i', '--ignore', default=[], type=int, nargs='*',
            help='Factors to ignore')

    return parser


def number_with_digits(n):
    return f"{n}<{len(str(n))}>"


def split_to_batches(numbers):
    # Breakpoints related to kernel sizes
    BREAK_POINTS = list(reversed([128 * k - 8 for k in (10, 12, 14, 16, 20)]))

    BATCH_SIZE = 8192

    groups = []
    current = []
    for number in sorted(numbers):
        assert 1 < number < 2 ** 2048

        bit_size = number.bit_length()
        if bit_size >= BREAK_POINTS[-1] or len(current) == BATCH_SIZE:
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

    return groups


def _split_numbers_and_output_batches(numbers):
    groups = split_to_batches(numbers)

    date = datetime.datetime.now().strftime("%Y%m%d")
    for i, group in enumerate(groups):
        max_bits = group[-1].bit_length()
        fn = f"pm1_stdkmd_{date}_batch_{i:02d}_{max_bits}.txt"
        print(f"Writing {len(group)} rows to {fn!r}")
        assert not os.path.exists(fn)
        with open(fn, "w") as f:
            for number in group:
                f.write(str(number) + "\n")


def _validate_residual(parsed):
    keys = ("METHOD", "N", "B1", "X", "X0", "CHECKSUM")
    return all(key in parsed for key in keys)


def update_resume(parsed, line, factor):

    def assert_replaced(s, old, new):
        assert old in s
        temp = s.replace(old, new)
        assert new in temp
        return temp

    """Update resume line with a found factor."""
    old_n = parsed["N"]
    n, mod = divmod(old_n, factor)
    assert mod == 0, (old_n, factor)

    # Replace N with n
    line = assert_replaced(
            line, f"N={old_n};", f"N={n};")

    # Replace X, X0 with mod (N//factor)
    assert parsed["X0"] < n
    old_x = parsed["X"]
    line = assert_replaced(
            line, f"X={old_x:#x};", f"X={old_x % n:#x};")

    # Remove checksum so ecm will resume these lines.
    checksum = parsed["CHECKSUM"]
    line = assert_replaced(line, f"CHECKSUM={checksum};", f"")

    return line


def _rebatch_residuals(args, lookup):
    """
    1. Load all residuals
        Drop all but largest B1
    2. Figure out for each N in residual if it has new factors
        N should appear in allcomp_2023.txt
        Get factors from newest allcomp_<DATE>.txt
    3. Split up residuals by batch size
        When B1 doesn't match ask for CPU eval?
    """

    # 1. Load all residuals
    loaded = 0
    residuals = {}

    for fn in args.rebatch:
        with open(fn) as f:
            for i, line in enumerate(f):
                line = line.strip()
                if not line:
                    continue

                loaded += 1
                parsed = ecm_resume.parse_resume(line)
                if not _validate_residual(parsed):
                    print(f"Bad residual line {i} in {fn}: {line[:40]}...")
                    exit(1)

                n = parsed['N']

                # This likely happens when a stage 1 factor was found.
                # Maybe the number still needs to be factored.
                if parsed['X'] == 0:
                    # Not sure why this happened but need to drop
                    print(f"\tDropping line {i} in {fn}: X=0 N={str(n)[:10]}...")
                    continue

                current = residuals.get(n)
                update = current is None
                if current:
                    update = parsed['B1'] > current[0]['B1']

                if update:
                    residuals[n] = (parsed, line)

    print()
    print(f"Loaded {loaded} residuals, {len(residuals)} unique")

    # 2. Load old and newer allcomp.txt
    OG_ALLCOMP = "allcomp_2023.txt"
    assert args.allcomp != OG_ALLCOMP
    _, og_lookup = load_allcomp(OG_ALLCOMP)
    print(f"Allcomp was {len(og_lookup)} is now {len(lookup)}")
    print()

    if False:
        for B1, count in sorted(Counter(p['B1'] for p,l in residuals.values()).items()):
            print(f"\t{B1=:,} x {count}")

    LABEL_KEY = '#"Label"'

    # reindex lookup and og_lookup by "Label"+"N"
    def new_label(row):
        return row[LABEL_KEY].replace('"', '') + "_" + row["N"]

    lookup_label = {new_label(row): row for row in lookup.values()}
    og_lookup_label = {new_label(row): row for row in og_lookup.values()}

    to_run = []

    # Present in lookup
    same = 0

    # present in og_lookup, label not present in lookup
    factored_completely = 0
    # Present in og_lookup, label present in lookup (as smaller n)
    factored_partial = 0
    # Not Present in either, will have to do a search or something
    missing = 0

    add_residuals = {}

    # Update residuals, possibly removing a factor or dismissing if factored.
    for n, (parsed, line) in residuals.items():
        if n in lookup:
            same += 1
            to_run.append(n)
            continue

        if n in og_lookup:
            # Lookup label and check if factored partially or completely
            label = new_label(og_lookup[n])
            if label not in lookup_label:
                factored_completely += 1
                continue
            else:
                factored_partial += 1
                n_new = int(lookup_label[label]["CompositeNumber"])
                f, mod = divmod(n, n_new)
                assert mod == 0, (label, n)

                # Update resume line removing factor of f.
                new_line = update_resume(parsed, line, f)
                new_parsed = ecm_resume.parse_resume(new_line)
                assert new_parsed["N"] == n_new
                assert 1 < new_parsed["X"] < n_new

                assert n_new in lookup
                if n_new in residuals:
                    # Residuals for both the old and new number have to merge
                    if residuals[n_new][0]['B1'] < parsed['B1']:
                        # More P-1 complete for old number, Merge
                        residuals[n_new] = (new_parsed, new_line)
                else:
                    # Technically we might need to merge again but very few numbers.
                    add_residuals[n_new] = (new_parsed, new_line)
                    to_run.append(n_new)


    # Add any residuals which had a factored removed
    for k, v in add_residuals.items():
        residuals[k] = v
    del add_residuals

    if True:
        print("Wanted residuals by B1 level")
        B1_to_run = Counter(residuals[n][0]["B1"] for n in to_run)
        for B1, count in sorted(B1_to_run.items()):
            print(f"\t{B1=:,} x {count}")

        # select all the same B1 so that all B1 in resume match.
        SELECT_B1 = 4 * 10 ** 9
        print(f"Selecting only residuals with B1={SELECT_B1:,}")
        to_run = [n for n in to_run if residuals[n][0]["B1"] == SELECT_B1]

        print(f"B1 of needed residuals")
        for B1, count in sorted(Counter(residuals[n][0]["B1"] for n in to_run).items()):
            print(f"\t{B1=:,} x {count}")

    print()
    print(f"Comparing with {OG_ALLCOMP!r}")
    print("\t{} the same, {} with a new factor, {} completely factored".format(
        same, factored_partial, factored_completely))

    print()
    print(f"{len(to_run)} numbers with residuals")

    if False:
        # Present in lookup, no existing residual
        new_allcomp_n = set(lookup.keys())
        for n in to_run:
            assert n in new_allcomp_n
            new_allcomp_n.remove(n)

        if len(new_allcomp_n) > 0:
            print(f"{len(new_allcomp_n)} numbers from {args.allcomp} don't yet have residuals")

            # These sequences got extended with new terms I would have tried
            EXTENSIONS = ("37771", "51115", "83336", "53335", "53333", "49992", "54444", "39991", "88878")
            new_allcomp_n = [n for n in new_allcomp_n if lookup[n][LABEL_KEY] not in EXTENSIONS]
            print(f"\tMissing {len(new_allcomp_n)} numbers after filtering known extensions")
            new_allcomp_n = [n for n in new_allcomp_n if n.bit_length() < 1020]
            print(f"\tMissing {len(new_allcomp_n)} numbers after filtering < 1020 bits")

            # Seems like these numbers are extensions / large numbers with new factors.
            # TODO can manual ecm them and add to the queue

            if False:
                # By Digit Length
                digit_counter = Counter(len(str(n)) for n in new_allcomp_n)
                for digits, count in sorted(digit_counter.items()):
                    min_bits = int(math.log2(10) * digits) + 1
                    print(f"\tMissing {count} x {digits} numbers (bits: {min_bits})")
            if False:
                # By Label
                label_counter = Counter(lookup[n][LABEL_KEY] for n in new_allcomp_n)
                for label, count in label_counter.most_common():
                    print(f"\tMissing {count} from {label}")

            if False:
                for i, n in enumerate(sorted(new_allcomp_n)):
                    print(i, lookup[n])
                    if i > 10:
                        break


    # 3. Split to_run by batch
    groups = split_to_batches(to_run)

    date = datetime.datetime.now().strftime("%Y%m%d")
    folder = f"resumes_{date}"
    if args.submit:
        assert not os.path.exists(folder)
        os.mkdir(folder)

    for i, group in enumerate(groups):
        max_bits = group[-1].bit_length()
        path = os.path.join(folder, f"pm1_stdkmd_batch_{i:02d}_{max_bits}.resume.txt")
        if not args.submit:
            print(f"Would write {len(group)} rows to {path!r} (with --submit)")
        else:
            print(f"Writing {len(group)} rows to {path!r}")
            assert not os.path.exists(path)
            with open(path, "w") as f:
                for number in group:
                    f.write(residuals[number][1])
                    f.write("\n")



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
    logs = {}
    for fn in log_fns:
        with open(fn) as f:
            file_logs = [l.strip() for l in f.readlines()]
        if file_logs:
            logs[fn] = file_logs

    return logs


def parse_json_logs(logs):
    """Parse logs from ecm-db."""
    return [json.loads(line) for line in logs if not line.isspace()]

def parse_logs(all_logs):
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
    for fn, logs in all_logs.items():
        if fn.endswith("json.log"):
            groups.extend(parse_json_logs(logs))
            continue

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

    total_lines = 0
    for group in groups:
        if len(group) == 2 and isinstance(group[0], dict):
            # json log.
            wu, result = group
            for f in result['factors']:
                factors[f].append(group)
            total_lines += result['output'].count('\n')
        else:
            total_lines += len(group)
            for line in group:
                match = re.search("Factor found in step .: ([0-9]+)$", line)
                if match:
                    f = int(match.group(1))
                    assert 2 <= f <= 10 ** 65, f
                    factors[f].append(group)

    print("\t", len(groups), "ecm runs", total_lines, "lines")

    return factors


def _get_contribution_parameters(classification, logs):
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
        "software": "GMP-ECM 7.0.7, ecm-db 0.12",
        "environment": "GPU PM1 stage1",
        "name": "Seth Troisi",
        "mail": "braintwo@gmail.com",
    }


def _handle_factor(f, n, submit, row, log):
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
            params = _get_contribution_parameters(classification, log[0])
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
        _split_numbers_and_output_batches(numbers)
        return

    if args.rebatch:
        _rebatch_residuals(args, lookup)
        return

    assert args.logs, "No log filenames specified"
    logs = get_logs(args.logs)
    assert logs, "No logs found"
    total_lines = sum(len(l) for l in logs.values())
    print(f"{len(args.logs)} log files contained {total_lines} lines\n")

    factors = parse_logs(logs)

    # TODO something better here
    extra_factors = [
    ]

    for f in extra_factors:
        if f not in factors:
            print(f, "Not in any log file!")
            factors[f] = [[]]

    ignored = 0
    for f in args.ignore:
        if f in factors:
            factors.pop(f)
            ignored += 1

    if ignored:
        print(f"\n\nFound {len(factors)} unique factors!")
        print(f"Plus {ignored} ignored factors!\n\n")
    else:
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
                _handle_factor(f, n, args.submit, lookup[n], log)

        print(new, "factors not yet in allcomp.txt")


if __name__ == "__main__":
    parser = _get_argparser()
    args = parser.parse_args()

    main(args)
