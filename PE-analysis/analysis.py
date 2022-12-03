#!/usr/bin/env python

"""
Process fastest/fastest_NUM.html to a csv=txt file
"""

import csv
import datetime
import os
import re

from collections import Counter

import dateutil.parser
import dateutil.tz


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

# fastest_solvers[problem] = [list]
fastest_solvers_map = {}

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
        row[2] = (row[2] == "True")
    members.sort(reverse=True)

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

        if row[0] not in fastest_solvers_map:
            fastest_solvers_map[row[0]] = []
        fastest_solvers_map[row[0]].append(row)


    for num, times in solution_postings.items():
        ts = datetime.datetime.fromtimestamp(times[0], tz=dateutil.tz.tzutc())
        #parsed = dateutil.parser.parse(times[1])
        #assert ts - parsed == 0, (ts - parsed)
        solution_postings[num] = ts

data_cleanup()

print(f"Found {len(problems)} problems")
print(f"Found {len(members)} members with >= {min(m[0] for m in members)} problems solved")
print(f"Found {len(fastest_solvers)} fastests solver results (only considering problems > 600)")
print(f"Found {len(solution_postings)} solution posting time")
print()


def compare_timings():
    # Have to be at least this much faster than the published time

    MIN_FASTER = 1 * 60
    # Figure out when during the top 100 a solution was published

    count_fasters = Counter()
    deltas = []

    # Assuming the answer are checked (e.g. submitted), these people are sus
    ranked_answers = 0
    before_answer = Counter()
    count_slower  = Counter()

    #print()
    for num, posted, name in sorted(problems):
        solution_time = solution_postings.get(num)

        if solution_time:
            delta = solution_time - posted
            delta_secs = delta.total_seconds()
        else:
            delta_secs = 86400

        # Fastest Solvers for this problem
        fast_solvers = fastest_solvers_map.get(num)
        if not fast_solvers:
            continue

        fasters = [row for row in fast_solvers if row[3] + MIN_FASTER < delta_secs]
        for faster in fasters:
            count_fasters[faster[2]] += 1

        if solution_time and len(fasters) < 100:
            ranked_answers += 1
            for row in fast_solvers:
                if row[3] - 60 < delta_secs:
                    before_answer[row[2]] += 1

            # For solvers after
            for row in fast_solvers:
                if row[3] > delta_secs:
                    count_slower[row[2]] += 1

#        if solution_time:
#            print("\t", num, posted, solution_time, delta)

        deltas.append((delta, num, len(fasters)))

    print()
    print("Times when github solutions were fast (<12 hr) or top 100")
    deltas.sort()
    for d, num, faster in deltas:
        if d < datetime.timedelta(hours=12) or faster < 100:
            print(f"\t{num:3} solved after {d!s:20} ~ {faster:<3} users solved before posting")

    print()
    print("Users that show up in fastest the most")
    for i, (name, count) in enumerate(count_fasters.most_common()):
        if i < 10 or i in (20, 30, 40, 50, 75, 100, 150, 200, 300) or "Seth" in name:
            print(f"\t{i:3},      {name:25} Solved {count} faster than published timings")

    print()
    print("Users by number of problems solve           | Top 100 finishes above GitHub solutions")
    results = []
    last_solved = 800
    for rank_i, (solved, name, is_team_member) in enumerate(members, 1):
        if solved < last_solved:
            rank = rank_i
            last_solved = solved

        if rank_i < 10 or rank_i in (20, 30, 40, 50, 75, 100, 150, 200, 300) or "Seth" in name:
            mark = "*" if is_team_member else ""
            print(f"\t{rank:3}, {solved:3}, {name+mark:25} |", count_fasters[name])

        # Admins and Project Euler team members probably don't race.
        if count_fasters[name] < 2 and (not is_team_member):
            results.append((name, rank, solved, count_fasters[name]))

    print()
    print("Suspect behaviors")
    print("-----------------")
    print()
    print("Users with lots of solves, but very few faster than GitHub solutions")
    for name, rank, solved, faster in results:
        print(f"\t{rank:3}, {solved:3}, {name:25} |", count_fasters[name])

    number_solved = {name: solved for solved, name, is_team_member in members if not is_team_member}

    print()
    print(f"From the {ranked_answers} problem where GitHub is top 100, before the solution is posted")
    for name, count in before_answer.most_common():

        # Want people who are only fast on these problems
        other_fasts = count_fasters[name]
        if other_fasts > 15:
            continue

        solved = number_solved.get(name, "???")
        print(f"\t{name:25} {solved} | {count}/{other_fasts} = {count/other_fasts:.0%}")
        if count < 5:
            break

    print()
    print(f"From the {ranked_answers} problem where GitHub is top 100, after the solution is posted")
    for name, count in count_slower.most_common():
        # Want people who are only fast when a solution is known
        other_fasts = count_fasters[name]
        if other_fasts > 10:
            continue

        solved = number_solved.get(name, "???")
        print(f"\t{name:25} {solved} | {count}/{other_fasts+count} = {(count)/(other_fasts+count):.0%}")
        if count < 5:
            break



compare_timings()
