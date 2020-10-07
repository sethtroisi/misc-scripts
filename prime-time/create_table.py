# Process results in directory into Markdown tables.

import math
import os
import re

import gmpy2

POWER_RE = re.compile(r"(10\^([0-9]+)\s*[+-]\s*([0-9]+))")
PRIMORIAL_RE = re.compile(r"(([0-9]+)#\s*[+-]\s*([0-9]+))")

TIME_RE = re.compile(r"[0-9]+\.[0-9]+(?= *s)")

columns   = "| {:15} | {:<6} | {:9} | {:10} | {:10} | {:5} |"
header    = columns.format("Number", "Bits", "Prime", "PFGW", "GMP 6.2", "Ratio")
seperator = "|-----------------|--------|-----------|------------|------------|-------|"

filenames = os.listdir()

# For polyfit of composite
composite_timings = []

for fn in filenames:
    base, ext = os.path.splitext(fn)
    if ext == ".txt":
        pfgw_fn = min([fn2 for fn2 in filenames if fn2.startswith(base) and '.pfgw' in fn2], default="")
        gmp_fn = min([fn2 for fn2 in filenames if fn2.startswith(base) and '.gmp' in fn2], default="")
        print()
        print (f"{fn:25} | pfgw: {pfgw_fn:33} gmp: {gmp_fn}")

        if gmp_fn and pfgw_fn:
            with open(fn) as bf:
                blines = list(map(str.strip, bf.readlines()))

            with open(gmp_fn) as gf:
                glines = list(map(str.strip, gf.readlines()))

            with open(pfgw_fn) as pf:
                plines = list(map(str.strip, pf.readlines()))

            rows = []
            for line in blines:
                if not line: continue

                match = POWER_RE.search(line)
                match = match or PRIMORIAL_RE.search(line)
                assert match, line
                number, part, add = match.groups()

                alt_number = number.replace("# +", "# + ").replace("# -", "# + -")

                g_line = min([g for g in glines if number in g or alt_number in g], default="")
                p_line = min([p for p in plines if number in p], default="")
                if not g_line or not p_line:
                    print (number, "NOT FOUND")
                    break
                g_s = TIME_RE.search(g_line).group(0)
                p_s = TIME_RE.search(p_line).group(0)
                prime = "prime" if "prime" in g_line else "composite"

                #print (number)
                #print (g_line)
                #print (p_line)
                #print (g_s, p_s)

                bits = round(gmpy2.log2(10 ** int(part) if '10^' in number else gmpy2.primorial(int(part))))
                ratio = round(float(g_s) / (float(p_s) + 1e-4), 1)

                rows.append((number, bits, prime, p_s, g_s, ratio))

                if prime == "composite" and bits in range(400, 50000):
                    composite_timings.append((float(bits * math.log(2)), float(g_s)))

            print()
            print(header)
            print(seperator)
            for row in rows:
                print(columns.format(*row))
            print()


if True:
    import numpy as np

    # Fit Polynomial
    log, timings = zip(*sorted(composite_timings))
    print ("N:", len(log), len(timings))
    for row in sorted(composite_timings):
        print (row)
    polyfit = np.polyfit(x=log, y=timings, deg=4)
    #equation = " + ".join("{:.4e} * pow(K_log, {})".format(coef, p) for p, coef in enumerate(polyfit))
    equation = " + ".join("{:.4e}{}".format(coef, p * " * K_log") for p, coef in enumerate(polyfit[::-1]))
    print()
    print (f"Polyfit coefs: {polyfit}")
    print (f"Polyfit eqn: {equation}")

    import matplotlib.pyplot as plt
    plt.scatter(log, timings)
    plt.plot(log, np.polyval(polyfit, log))
    plt.xlabel('ln(n)')
    plt.xscale('log')
    plt.ylabel('Seconds')
    plt.yscale('log')
    plt.show()
