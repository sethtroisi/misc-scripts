# Process results in directory into Markdown tables.

import os
import re
import gmpy2

POWER_RE = re.compile(r"(10\^([0-9]+)\s*[+-]\s*([0-9]+))")
PRIMORIAL_RE = re.compile(r"(([0-9]+)#\s*[+-]\s*([0-9]+))")

TIME_RE = re.compile(r"[0-9]+\.[0-9]+(?= *s)")

filenames = os.listdir()

for fn in filenames:
    base, ext = os.path.splitext(fn)
    if ext == ".txt":
        pfgw_fn = min([fn2 for fn2 in filenames if fn2.startswith(base) and '.pfgw' in fn2], default="")
        gmp_fn = min([fn2 for fn2 in filenames if fn2.startswith(base) and '.gmp' in fn2], default="")
        print (f"{base:25} | pfgw: {pfgw_fn:33} gmp: {gmp_fn}")

        if gmp_fn and pfgw_fn:
            with open(fn) as bf:
                blines = list(map(str.strip, bf.readlines()))

            with open(gmp_fn) as gf:
                glines = list(map(str.strip, gf.readlines()))

            with open(pfgw_fn) as pf:
                plines = list(map(str.strip, pf.readlines()))

            columns   = "| {:15} | {:<6} | {:9} | {:10} | {:10} | {:5} |"
            header    = columns.format("Number", "Bits", "Prime", "PFGW", "GMP 6.2", "Ratio")
            seperator = "|-----------------|--------|-----------|------------|------------|-------|"

            rows = []
            for line in blines:
                match = POWER_RE.search(line)
                match = match or PRIMORIAL_RE.search(line)
                assert match, line

                number, part, add = match.groups()

                g_line = min([g for g in glines if number in g], default="")
                p_line = min([p for p in plines if number in p], default="")

                if not g_line or not p_line:
                    break

                g_s = TIME_RE.search(g_line).group(0)
                p_s = TIME_RE.search(p_line).group(0)

                prime = "prime" if "prime" in g_line else "composite"

                print (number)
                print (g_line)
                print (p_line)
                print (g_s, p_s)

                bits = round(gmpy2.log2(10 ** int(part) if '10^' in number else gmpy2.primorial(int(part))))
                ratio = round(float(g_s) / (float(p_s) + 1e-4), 1)

                rows.append((number, bits, prime, p_s, g_s, ratio))

            print(header)
            print(seperator)
            for row in rows:
                print(columns.format(*row))
            print()
