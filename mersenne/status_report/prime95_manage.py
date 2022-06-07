#!/usr/bin/env python3

# Copyright (c) 2021 Seth Troisi
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, version 3.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.

"""
Manage backup files using json from status report
"""

import hashlib
import itertools
import json
import os
import sys

import prime95_status


def sha256_short(fn):
    with open(fn, "rb") as f:
        h = hashlib.sha256(f.read()).hexdigest()

    return h[:8]


def hash_name(fn):
    """Normalize name to <file>.bu.<SHA256(8)>"""

    assert os.path.isfile(fn), fn
    short_hash = sha256_short(fn)

    bare_fn = os.path.splitext(os.path.basename(fn))
    return f"{bare_fn}.bu.{short_hash}"


def hash_rename(files):
    """Renames to <file>{"", .bu, .buX} to <file>.bu.<SHA256>"""

    for fn in files:
        file_dir = os.path.dirname(fn)
        assert os.path.isdir(file_dir), file_dir

        new_name = hash_name(fn)
        new_fn = os.path.join(file_dir, new_name)
        print (f"{fn:35} renamed to {new_fn}")
        os.rename(fn, new_fn)


def rough_PM1_credit(exp, B1, B2):
    # See: https://github.com/sethtroisi/misc-scripts/blob/main/mersenne/pm1_prob/pm1.sage
    import pm1

    return pm1.credit(exp, B1, B2)


def core_minutes_to_GHz_days(minutes):
    """Rough approx of GHz-days for $minutes core minutes"""
    return 6 * (minutes / (24 * 60))


def is_same_exp(wu_a, wu_b):
    return all(wu_a["raw"][var] == wu_b["raw"][var] for var in ("k", "b", "n", "c"))


def compare_work_done(wu_a, wu_b):
    '''
    Returns if a has been complete to higher bounds than b

    Returns 0 if a == b
    Returns -1 if a < b
    Returns 1 if a > b
    '''

    assert is_same_exp(wu_a, wu_b), (wu_a, wu_b)

    # XXX: FIXME: TODO: verify this logic several times (and maybe with tests)

    # Tricky Cases:
    #   More done than before BUT in stage1 with a HUGE B1

    # MVP only accepts finished files
    a_done = wu_a["done"]
    b_done = wu_b["done"]
    UNFINISHED_DONE = (None, "stage0")
    assert not all(t in UNFINISHED_DONE for t in (a_done, b_done)), (wu_a, wu_b)

    if a_done in UNFINISHED_DONE:
        assert b_done not in UNFINISHED_DONE
        return -1

    # Stage1 at least is done for a
    if b_done in UNFINISHED_DONE
        return 1

    a_b1 = wu_a["B1_progress"]
    b_b1 = wu_b["B1_progress"]
    assert isinstance(a_b1, int) and isinstance(b_b1, int), (a_b1, b_b1)
    if wu_a["B1_progress"] > wu_b["B1_progress"]:
        return 1

    if wu_a["B1_progress"] == wu_b["B1_progress"]:
        # Check if B2 is more done on a or b
        a_b2 = wu_a.get("B2_progress", 0)
        b_b2 = wu_b.get("B2_progress", 0)
        if a_b2 > b_b2:
            return 1
        elif a_b2 == b_b2:
            return 0
        else:
            return -1


#### Utilities Above ^ ####
#### Features  below v ####


def trivial(parsed, small = 0.02):
    """list of files with less than $SMALL GHz-Days work done"""

    small_effort = []
    for name, wu in parsed.items():
        if name.startswith('m'):
            # P-1 results

            if "B1_guess" not in wu:
                continue

            B1 = wu["B1_guess"]
            if B1 == 0:
                print("B1 shouldn't be zero\n", wu)
                continue

            credit = rough_PM1_credit(wu["n"], B1, 0)

            # an hours work, not super important to save
            if credit < core_minutes_to_GHz_days(60):
                small_effort.append((credit, B1, name))

    if small_effort:
        print(len(small_effort), f"files with < {small:.3f} GHz-days work")
        for credit, B1, name in sorted(small_effort):
            status_line = prime95_status.one_line_status(name, parsed[name])
            remove = f"rm {name!r};"
            print(f"{remove:20} # {B1} | {status_line} => {credit:.2f} GHz-Days")


def easy_finish(parsed, effort = 0.02):
    """list of files that can have stage 1 completed for minimal effort"""

    small_effort = []
    for name, wu in parsed.items():
        if name.startswith('m'):
            if wu["stage_guess"] != "B1":
                continue

            pct = wu["pct_complete"]
            if wu["stage_guess"] == "B1":
                B1 = max(wu["B_done"], wu["interim_B"])
                finished = wu["B1_guess"]
                test = finished / B1
                if B1 < finished or abs(test - pct) < 0.1:
                    print(f"pct mismatch: {pct:.2%} vs guess {test:.2%}\n", wu)
                    continue

                needed_credit = rough_PM1_credit(wu["n"], finished, 0)
                total_credit = rough_PM1_credit(wu["n"], B1, 0)
                remaining = total_credit - needed_credit

                # min pct depends on total_credit.
                min_pct = 0.9 - total_credit / 100

                if pct > min_pct or remaining < core_minutes_to_GHz_days(15):
                    small_effort.append((credit, B1, name))

    if small_effort:
        print(len(small_effort), f"files with < {small:.3f} GHz-days work")
        for credit, B1, name in sorted(small_effort):
            status_line = prime95_status.one_line_status(name, parsed[name])
            remove = f"rm {name!r};"
            print(f"{remove:20} # {B1} | {status_line} => {credit:.2f} GHz-Days")




def is_backup_of_finalized(parsed):
    """Find all <file>.bu[0-9]* where <file> is finished and bu is not needed"""

    exponents = list(itertools.groupby(parsed.keys(), lambda p: os.path.splitext(p)[0]))
    pm1_exponents = [n for n, _ in exponents if n.startswith('m')]

    new_is_same_or_better_done = []
    backwards_fix_suggestion = []

    for name, wu in parsed.items():
        short, ext = os.path.splitext(name)
        if not ext.startswith(".bu"):
            continue

        other = parsed.get(short)
        if not other:
            continue

        if name.startswith('m'):
            # P-1 results

            new_B1 = wu['B_done']
            new_B2 = wu.get('C_done', 0)

            old_B1 = other['B_done']
            old_B2 = other.get('C_done', 0)

            if short == "m0017747":
                print(name, short)
                print(new_B1, new_B2, old_B1, old_B2)
                print

            if other['stage_guess'] == 'DONE':
                if new_B1 <= new_B2 and old_B1 <= old_B2:
                    if (new_B1 < old_B1) or (new_B1 == old_B1 and new_B2 < old_B2):
                        print(f"Backwards progress {short} = {(new_B1, new_B2)} vs {name} = {(old_B1, old_B2)}")
                        # Swap names
                        backwards_fix_suggestion.append(
                            f"mv -n {name} {short}.temp.bu; "
                            f"mv -n {short} {name}; "
                            f"mv -n {short}.temp.bu {short}"
                        )
                        # Don't want to double modify (after or during rename)
                        continue

            if wu['stage_guess'] == 'DONE':
                if new_B1 >= old_B1 and new_B2 >= new_B1:
                    # Very safe to remove
                    new_is_same_or_better_done.append((name, short))

    print(f"Files({len(parsed)}) | Exponents({len(exponents)}) | P-1 exponents({len(pm1_exponents)})")

    if backwards_fix_suggestion:
        print()
        print(f"Suggest fixing {len(backwards_fix_suggestion)} backwards first files")
        for line in backwards_fix_suggestion:
            print(line)

    else:
        print("Newer is Done:", len(new_is_same_or_better_done))
        if new_is_same_or_better_done:
            #for name, better in sorted(new_is_same_or_better_done):
                #print(f"{name:15} not needed as {better} is better")
            print("rm -i", " ".join(n for n, _ in new_is_same_or_better_done))


if __name__ == "__main__":
    print("USE THIS SCRIPT AT YOUR OWN RISK")
    print("BACKUP YOUR FILES BEFORE USING THIS")
    print()

    json_fn = "test.json" if len(sys.argv) < 2 else sys.argv[1]

    with open(json_fn) as f:
        parsed = json.load(f)

    #is_backup_of_finalized(parsed)
    #trivial(parsed)
    #easy_finish(parsed)

    files = sorted(set(wu["path"] for wu in parsed.values()))
    hash_rename(files)
