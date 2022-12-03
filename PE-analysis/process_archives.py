#!/usr/bin/env python

"""
Process archives/archives_<page>.html to a csv=txt file
"""

import csv
import os
import re

from bs4 import BeautifulSoup

previously_handled = 0
processed = 0
for fn in sorted(os.listdir("archives")):
    if not fn.endswith(".html"):
        continue

    num = re.search("[0-9]+", fn).group()

    output_fn = f"archives/archives_{num}.txt"
    if os.path.exists(output_fn):
        previously_handled += 1
        continue

    print(f"Processing {num} = {fn!r}")
    with open(f"archives/{fn}", "r") as f:
        soup = BeautifulSoup(f, 'html.parser')

    results = []
    for i, row in enumerate(soup.select("#problems_table > tr")):
        children = list(row.children)

        ID = children[0].text
        if i == 0:
            assert ID == "ID"
            continue

        if "Pinned Problem" in ID:
            ID = ID.replace("Pinned Problem", "")

        name = children[1].text
        published = next(children[1].children)["title"]
        if published.startswith("Published on"):
            published = published[len("Published on "):]

        if int(ID) % 50 in (0, 1,2,3,5,10,20):
            print(f"\t{ID:3} {published:20} {name:20}")

        results.append((int(ID), published, name))

    if len(results) != 50:
        print(f"\tOnly {len(results)} results for archive page {num}")

    if results:
        processed += 1
        with open(output_fn, "w") as csv_file:
            writer = csv.writer(csv_file)
            for result in results:
                writer.writerow(result)

print(f"Processed {processed}, previously handled {previously_handled}")
