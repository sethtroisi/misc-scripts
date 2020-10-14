# Process results in directory into Markdown tables.

import math
import os
import re

from collections import defaultdict

import gmpy2


POWER_RE = re.compile(r"(10\^([0-9]+)\s*[+-]\s*([0-9]+))")
PRIMORIAL_RE = re.compile(r"(([0-9]+)#\s*[+-]\s*([0-9]+))")

TIME_RE = re.compile(r"[0-9]+\.[0-9]+(?= *s)")

columns   = "| {:15} | {:<6} | {:9} | {:10} | {:10} | {:5} |"
header    = columns.format("Number", "Bits", "Prime", "PFGW", "GMP 6.2", "Ratio")
seperator = "|-----------------|--------|-----------|------------|------------|-------|"


def parse_and_print(filenames):
  # For polyfit of composite, prime
  timings = defaultdict(list)

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
                  status = "prime" if "prime" in g_line else "composite"

                  #print (number)
                  #print (g_line)
                  #print (p_line)
                  #print (g_s, p_s)

                  bits = round(gmpy2.log2(10 ** int(part) if '10^' in number else gmpy2.primorial(int(part))))
                  ratio = round(float(g_s) / (float(p_s) + 1e-4), 1)

                  rows.append((number, bits, status, p_s, g_s, ratio))

                  timings["gmp_" + status].append((float(bits * math.log(2)), float(g_s)))
                  timings["pfgw_" + status].append((float(bits * math.log(2)), float(p_s)))

              print()
              print(header)
              print(seperator)
              for row in rows:
                  print(columns.format(*row))
              print()
  return timings

def run():
    import numpy as np

    filenames = os.listdir()
    result_timings = parse_and_print(filenames)

    import matplotlib.pyplot as plt
    plt.figure(figsize=(15,8))

    for c, (result, timings) in zip("rgbm", result_timings.items()):
        timings.sort()

        # Fit Polynomial
        log, times = zip(*timings)
        print (result, "N:", len(log), len(times),  len(timings))

        # Only look at values with time > 0.01
        l, t = zip(*[v for v in timings if v[1] > 0.01])
        polyfit = np.polyfit(x=l, y=np.log(t), deg=5)
        poly_vals = np.exp(np.polyval(polyfit, l))

        #equation = " + ".join("{:.4e} * pow(K_log, {})".format(coef, p) for p, coef in enumerate(polyfit))
        #equation = " + ".join("{:.4e}{}".format(coef, p * " * K_log") for p, coef in enumerate(polyfit[::-1]))
        print (f"Polyfit coefs: {polyfit}")
        #print (f"Polyfit eqn: {equation}")
        print ()

        plt.scatter(log, times, label=result, color=c)

        plt.plot(l, poly_vals, color=c)

    plt.xlabel('ln(n)')
    plt.ylabel('Seconds')
    plt.xscale("log")
    plt.yscale("log")
    plt.legend(loc='upper left')

    plt.tight_layout()
    plt.savefig("timing.png")
    plt.show()


if __name__ == "__main__":
    run()

