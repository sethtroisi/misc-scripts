#!/usr/bin/env python
"""Helper tool for reporting found factors to Studio Kamada."""

import csv
import json
import math
import re
import sys
import time
import urllib.parse
import urllib.request

from collections import defaultdict

import sympy.ntheory


def split_numbers_to_batches(numbers):
        # Breakpoints related to kernel sizes
        BREAK_POINTS = [256 * k - 8 for k in (3, 4, 6)]

        GROUP_SIZE = 1792

        groups = []
        current = []
        for number in numbers:
            assert 1 < number < 2 ** 2048

            bit_size = number.bit_length()
            if bit_size >= BREAK_POINTS[0] or len(current) == GROUP_SIZE:
                if current:
                    print("new batch of {} {} to {} bits".format(
                        len(current),
                        current[0].bit_length(),
                        current[-1].bit_length()))
                    groups.append(current)
                    current = []

                while bit_size >= BREAK_POINTS[0]:
                    print()
                    BREAK_POINTS.pop(0)

            current.append(number)

        if current:
            print("new batch of {} {} to {} bits".format(
                len(current),
                current[0].bit_length(),
                current[-1].bit_length()))
            groups.append(current)
            current = []


        for i, group in enumerate(groups):
            max_bits = group[-1].bit_length()
            fn = f"pm1_stdkmd_batch_{i:2d}_{max_bits}.txt"
            print(f"Writing {len(group)} rows to {fn!r}")
            if True:
                print("dry run")
            else:
                with open(fn, "w") as f:
                    for number in group:
                        f.write(str(number) + "\n")


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
        re.compile('^Resuming.*residue'),
        re.compile('^Input number is'),
        re.compile('^GMP-ECM'),
        re.compile('^v{10}'),
    )
    ends = (
        re.compile('Step 2 took'),
        re.compile('^\^{10}'),
    )

    groups = []
    grouped = []
    for i, line in enumerate(logs):
        is_start = any(re.search(start, line) for start in starts)

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


def print_factor_info(f, n, row, log):
    assert n % f == 0
    expr = row["Expression"]
    label = row['#"Label"']
    power = row["N"]
    classification = f"{label}_{power}"
    contribute_url = f"\thttps://stdkmd.net/nrr/c.cgi?q={classification}"
    print(f"\t{f} divides {expr}")
    print(contribute_url)
    print(f"\thttps://stdkmd.net/nrr/cont/{label[0]}/{label}.htm#N{power}")
    factors = sorted(sympy.ntheory.factorint(f-1).items())
    print("\tP-1 =", " * ".join(f"{p}" if e == 1 else f"{p}^{e}" for p, e in factors))
    minB2 = max(p for p, e in factors)
    minB1 = max(p ** e for p, e in factors if p != minB2)
    print("\tRequires: B1 >= {:9,} B2 >= {:9,} || B1 >= 1e{}, B2 >= 1e{}".format(
        minB1, minB2, len(str(minB1)), len(str(minB2))))

    # Small remaining composite number, suitable for GNFS
    cf = n // f
    if len(str(cf)) < 145 and not sympy.isprime(cf):
        print(f"\t{len(str(cf))}-digit composite remaining")
        print("\t\t", cf)
    print()

    # Submit numbers
    if False:
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


def main(allcomp_fn, log_fns):
    numbers, lookup = load_allcomp(allcomp_fn)

    logs = get_logs(log_fns)
    assert logs, "No logs found"
    print(f"{len(log_fns)} log files contained {len(logs)} lines\n")

    factors = parse_logs(logs)

    # TODO something better here
    extra_factors = [
            1124454316097622336388524874701151785403,
            1758894179568848098592692044560871267130300898981,
            135007364014709592091635360212683657437974511161,
            77584963804370623318377261901492932182167057,

            244873247732029431528427679518897269211061263,
            121547489614908980531274700026144404942094229,
            6074450236085204945666461485763132838606015443,

            31734041227814641692974565848888870878622696731,
            897438063383371813207119041644261263103457,
            92699495662649251267496033462225436898037,
            777681778665587298011461383504803404249,
            820609099557622784987305420015539988393763,
            42555595286255615516481485542800355199237,
            30125829040214338235380675150762029118875538347077,
            9607225096023100803198937141644381008255180711,
            4233482583905114491215398986607349712163,
            25878125464895606953511092966790890207517,
            6503872670596251761784245131633913,
            850351135326050148821427820675652246449,
    ]
    '''
    Composite factor
33696225345898595418519136300455807677197161879159983273906152538118480634518675311038180741771055825530494319368895712771779857659506133711
Reservation key is 9366?
    '''
    extra_factors = []

    for f in extra_factors:
        if f not in factors:
            factors[f].append([])

    print(f"\n\nFound {len(factors)} unique factors!\n\n")

    # Factor length distribution
    if False and factors:
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
        for f, log in factors.items():
            print (f"\n{len(str(f))} digits: {f}")
            found = [n for n in lookup if n % f == 0]
            assert len(found) == 1, f"{factor} divides {len(found)} numbers"

            for n in found:
                print_factor_info(f, n, lookup[n], log)



if __name__ == "__main__":
    # TODO also pass in log files and find stuff
    if len(sys.argv) < 3:
        print(f"{sys.argv[0]} takes two arg [allcomp path] [log files]+")
        exit(1)

    allcomp_fn = sys.argv[1]
    log_fns = sys.argv[2:]

    main(allcomp_fn, log_fns)
