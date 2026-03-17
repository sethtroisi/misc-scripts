"""Find newest checkpoint file and resume"""

import datetime
import os
import re
import sys
from pathlib import Path


def find_max_checkpoint(file_prefix):
    reB1 = re.compile(r"B1=(\d+);")
    reDate = re.compile(r"_(20\d{6}_\d{6}).txt")

    folder = Path(file_prefix).parent
    fn_prefix = Path(file_prefix).name

    found = []

    # Iterate through files starting with the prefix
    for fn in folder.glob(f"{fn_prefix}*.txt"):
        if not fn.is_file():
            continue

        with open(fn, 'r') as f:
            first_line = f.readline()
            if not first_line:
                continue

            date = reDate.search(fn.name)
            assert date, f"Bad filename {fn!r}"

            # Search for the B1 pattern
            b1 = reB1.search(first_line)
            if not b1:
                print("B1= not found in {fn!r}")
                continue

            B1 = int(b1.group(1))
            day = date.group(1)
            print("\tMatch:", B1, day, fn.name)
            found.append((B1, day, fn))

    print(f"\tFound {len(found)} matches for {fn_prefix!r}")
    return found


def resume_cmd(file_prefix):
    found = find_max_checkpoint(file_prefix)
    if not found:
        print("No matches!")
        exit(1)

    b1, date, fn = max(found)
    fn = str(fn)
    print(f"Resuming {fn!r} B1={b1} Date={date}")

    new_date = datetime.datetime.today().strftime("%Y%m%d_%H%M%S")
    chkpnt_fn = file_prefix + "_" + new_date + ".txt"
    final = file_prefix + "_final.txt"
    print(f"./ecm -gpu -pm1 -v -v -resume {fn!r} -chkpnt {chkpnt_fn} -save {final} 100e9 0 | tee {chkpnt_fn}.log")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <RESUME_FILE_PREFIX>")
        exit(1)

    assert not os.path.isfile(sys.argv[1] + "_final.txt")

    resume_cmd(sys.argv[1])
