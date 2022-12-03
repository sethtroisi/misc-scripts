#!/usr/bin/env python

"""
Process fastest/fastest_NUM.html to a csv=txt file
"""

import csv
import os
import re

from bs4 import BeautifulSoup

previously_handled = 0
processed = 0
for fn in sorted(os.listdir("fastest")):
    if not fn.endswith(".html"):
        continue

    num = re.search("[0-9]+", fn).group()

    output_fn = f"fastest/fastest_{num}.txt"
    if os.path.exists(output_fn):
        previously_handled += 1
        continue

    print(f"Processing {num} = {fn!r}")
    with open(f"fastest/{fn}", "r") as f:
        soup = BeautifulSoup(f, 'html.parser')

    results = []
    for i, row in enumerate(soup.select("table.grid tr")):
        children = list(row.children)

        # Work around a bug in project euler html
        if i == 0:
            assert children[1].text == "User"
            assert len(children) > 50
            continue

        place = children[1].text
        user  = children[2].text
        time  = children[5].text

        if int(place[:-2]) in (1,2,3,5,10,20,100):
            print(f"\t{num:3} {place:4} {user:20} {time}")

        results.append((num, place, user, time))

    if len(results) != 100:
        print(f"\tOnly {len(results)} results for problem {num}")
        continue

    if results:
        processed += 1
        with open(output_fn, "w") as csv_file:
            writer = csv.writer(csv_file)
            for result in results:
                writer.writerow(result)

print(f"Processed {processed}, previously handled {previously_handled}")
