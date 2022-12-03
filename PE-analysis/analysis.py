#!/usr/bin/env python

"""
Process fastest/fastest_NUM.html to a csv=txt file
"""

import csv
import datetime
import dateutil.parser
import dateutil.tz
import os
import re


def get_csv_results(directory):
    results = []
    for fn in sorted(os.listdir(directory)):
        if not fn.endswith(".txt"):
            continue

        with open(os.path.join(directory, fn), "r") as csv_file:
            reader = csv.reader(csv_file)
            for row in reader:
                results.append(row)

    return results


def get_solution_posted_times():
    solution_times = {}
    with open("solution_times.txt") as f:
        for row in f:
            parts = row.strip().split(" ", 4)
            if len(parts) > 1:
                solution_times[int(parts[0])] = (int(parts[2]), parts[4])

    return solution_times

problems = get_csv_results("archives")
members = get_csv_results("levels")
fastest_solvers = get_csv_results("fastest")
solution_postings = get_solution_posted_times()

def data_cleanup():
    # Data munging
    for row in problems:
        row[0] = int(row[0])
        # "Saturday, 1st February 2020, 01:00 pm"
        # I believe this is in my local timezone
        # and that this is the default for parse
        #row[1] = dateutil.parser.parse(row[1])

        # This would make 686 (and many others)
        # have negative solve time, checking UTC
        row[1] = dateutil.parser.parse(row[1] + " UTC")

    problems.sort()

    for row in members:
        row[0] = int(row[0].replace('+', ''))

    for row in fastest_solvers:
        row[0] = int(row[0])
        assert row[1][-2:] in ("st", "nd", "rd", "th"), row[1]
        row[1] = int(row[1][:-2])

        total_time = 0
        for unit, seconds in (("day", 86400), ("hour", 3600), ("minute", 60), ("second", 1)):
            match = re.search("([0-9]+)\s+" + unit, row[3])
            if match:
                total_time += int(match.group(1)) * seconds
        assert 59 < total_time < 200 * 86400, (row, total_time)
        row[3] = total_time

    for num, times in solution_postings.items():
        ts = datetime.datetime.fromtimestamp(times[0], tz=dateutil.tz.tzutc())
        #parsed = dateutil.parser.parse(times[1])
        #assert ts - parsed == 0, (ts - parsed)
        solution_postings[num] = ts

data_cleanup()

print(f"Found {len(problems)} problems")
print(f"Found {len(members)} members with >= {min(p for p, _ in members)} problems solved")
print(f"Found {len(fastest_solvers)} fastests solver results")
print(f"Found {len(solution_postings)} solution posting time")
print()


def compare_timings():
    # Figure out when during the top 100 a solution was published

    deltas = []

    for num, posted, name in sorted(problems):
        solution_time = solution_postings.get(num)
        if not solution_time:
            continue

        delta = solution_time - posted
        if delta < datetime.timedelta(days=10):
            print(num, name)
            print("\t", posted, solution_time, delta)
            print()

            deltas.append((delta, num))

    deltas.sort()
    for d, num in deltas:
        print(num, "solved after", d)


compare_timings()
