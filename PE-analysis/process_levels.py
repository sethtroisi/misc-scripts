#!/usr/bin/env python

"""
Process levels/level_NUM.html to a csv=txt file
"""

import csv
import os
import re

from bs4 import BeautifulSoup

previously_handled = 0
processed = 0
for fn in sorted(os.listdir("levels")):
    if not fn.endswith(".html"):
        continue

    num = re.search("[0-9]+", fn).group()

    output_fn = f"levels/level_{num}.txt"
    if os.path.exists(output_fn):
        previously_handled += 1
        continue

    print(f"Processing {num} = {fn!r}")
    with open(f"levels/{fn}", "r") as f:
        soup = BeautifulSoup(f, 'html.parser')

    results = []
    for i, row in enumerate(soup.select("#main_table > tr")):
        children = list(row.children)

        if i == 0:
            continue

        # Ugly hack to workaround <i>Username<i>
        name = list(children[3].select(".tooltip")[0].children)[0].string

        solved_column = row.select(".solved_column")
        assert len(solved_column) == 1
        solved = solved_column[0].text

        raw_html = row.decode_contents()
        is_team_member = ("admin" in raw_html) or ("dev_team" in raw_html)

        if i in (0,1,2,3,5,10,20,100) or is_team_member:
            print(f"\t{i:3} {solved:4} {name:20}{'*' if is_team_member else ''}")

        results.append((solved, name, is_team_member))

    print(f"\t{len(results)} results for level {num}")

    if results:
        processed += 1
        with open(output_fn, "w") as csv_file:
            writer = csv.writer(csv_file)
            for result in results:
                writer.writerow(result)

print(f"Processed {processed}, previously handled {previously_handled}")
