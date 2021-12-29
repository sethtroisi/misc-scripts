#!/usr/bin/env python

# twok => two below two thousand unfactored candidates

import math
import heapq
from collections import Counter
from functools import lru_cache

import primesieve
import pm1

# Roughly (GPU TF GHz-day / CPU P-1 GHz-day)
GPU_MULT = 50

# Roughly optimal B2/B1 ratio
B2_RATIO = 100

# Ranges above 100M are supposed to be handled by default
# and TF is very easy there so likely will have no very
# hard ranges
STOP = 30 * 10 ** 6

# (head -n 6000000 mersenneca_known_factors_0G.txt && cat mersenneca_known_factors_0G_30day.txt) | sort -u -n -t',' -k1,1 | sponge mersenneca_known_factors_100M.txt
# wc mersenneca_known_factors_100M.txt

factor_fn = "mersenneca_known_factors_100M.txt"
tf_limits_fn = "mersenneca_tf_pm1_bounds_0G.txt"

# the OG project is looking at ranges of .1M = 100,000
SIZE = 100000
rem_threshold = 2 * (SIZE // 100) - 1
extra_threshold = 40

# [0, SIZE], [SIZE, 2*SIZE], [2*SIZE, 3*SIZE]
# don't have to work about overlap with ] and [ because SIZE is composite
counts = [[0, 0] for _ in range(0, STOP, SIZE)]

# I want this to contain all primes without factors
# Ideally we'd do something in two passes, or one combined pass
# to avoid adding then removing all primes but that's hard to write.
unfactored = [set() for _ in range(0, STOP, SIZE)]

for prime in primesieve.primes(0, STOP):
    interval = prime // SIZE
    counts[interval][0] += 1
    unfactored[interval].add(prime)

##### Handle Numbers with factors (and mersenne primes) #####

with open(factor_fn) as f:
    last_m = 0
    for line in f:
        raw = line.split(",")
        m, k = int(raw[0]), int(raw[1])
        if m > STOP:
            break

        assert pow(2, m, 2 * m * k + 1) == 1
        if last_m == m:
            continue

        # First factor of m
        counts[m // SIZE][1] += 1
        last_m = m
        unfactored[m // SIZE].remove(m)

MP = [
    2, 3, 5, 7, 13, 17, 19, 31, 61, 89, 107, 127, 521, 607, 1279, 2203,
    2281, 3217, 4253, 4423, 9689, 9941, 11213, 19937, 21701, 23209, 44497,
    86243, 110503, 132049, 216091, 756839, 859433, 1257787, 1398269, 2976221,
    3021377, 6972593, 13466917, 20996011, 24036583, 25964951, 30402457,
    32582657, 37156667, 42643801, 43112609, 57885161, 74207281, 77232917,
    82589933
]
for m in MP:
    if m < STOP:
        counts[m // SIZE][1] += 1
        unfactored[m // SIZE].remove(m)

#####

unfactored_per = Counter()
for start in range(0, STOP, SIZE):
    c = counts[start // SIZE]
    rem = c[0] - c[1]
    nf = len(unfactored[start // SIZE])
    assert rem == nf, (start, c, rem, nf)
    if rem > (rem_threshold + extra_threshold):
        print(f"{start:8}  factored {c[1]} / {c[0]} => {rem} unfactored")
        unfactored_per[start] = rem - rem_threshold

print()
print(f"Ranges with large remaining work: {len(unfactored_per)}")
print(f"Those ranges need {sum(unfactored_per.values())} factors")
worst = unfactored_per.most_common(1)[0]
print(f"Most needed {worst[1]} for {worst[0]}")
print()

##### Get TF work done on remaining ranges

tf_limits = {interval: Counter() for interval in unfactored_per}
pm1_limits = {interval: Counter() for interval in unfactored_per}

with open(tf_limits_fn) as f:
    headers = f.readline()
    assert "exponent\tfactored\ttfnf\tb1\tb2\tpm1_prob\n" == headers, list(headers)
    for line in f:
        raw = line.split()
        m = int(raw[0])
        if m > STOP:
            break

        interval = (m // SIZE)
        bottom = interval * SIZE
        if bottom in unfactored_per:
            if m in unfactored[interval]:
                if raw[1] == "1":
                    # actually is factored
                    unfactored[interval].remove(m)
                    counts[m // SIZE][1] += 1
                    continue

                tf = int(raw[2])
                pm1_bounds = (int(raw[3]), int(raw[4]))
                tf_limits[bottom][tf] += 1
                pm1_limits[bottom][pm1_bounds] += 1

##### Work calculation

def tf_work(M, tf):
    '''Approx GHz-Days to TF M from 2^(tf-1) to 2^tf'''
    return 2 ** tf / M / 0.9875e13


@lru_cache(maxsize=100000)
def pm1_stats(e, cleared, B1, B2, e_prob, inc=1):
    B1 *= inc
    B2 *= inc

    prob = pm1.prob_pm1(e, cleared, B1, B2)[1]
    work = pm1.credit(e, B1, B2)
    return (prob - e_prob) / (1 - e_prob), work, B1, B2


def format_bounds(count, cur_B1, cur_B2, new_B1, new_B2):
    cur = f"B1={cur_B1/1e1:5.0f}, B2={cur_B2/1e3:3.0f}K"
    new = f"B1={new_B1/1e1:5.0f}, B2={new_B2/1e3:3.0f}K"
    return f"\t\t{count:3}x  {cur}  =>  {new}"


def pm1_strategy(start, cleared, needed):
    '''Approx GHz-Days needed to find <needed> factors using P-1'''

    debug = (start == 6900000)

    # Doesn't account for TF removing some factors
    # Doesn't account for new TF limit
    # Doesn't account for what TF each exp has
    # Doesn't estimate optimal B2/B1 (or compute work correctly for new 30.8 prime95)

    exponents = sorted(unfactored[start // SIZE])
    first_e = min(exponents)

    if start in pm1_limits:
        # average B1/B2 already complete to this level
        B1, B2 = list(map(lambda e: sum(e) / n, zip(*pm1_limits[start].elements())))
        prob = pm1.prob_pm1(first_e, cleared, B1, B2)[1]
        if debug:
            print(f"\tExisting P-1 for interval, avg B1={B1/1e3:5.0f}K, B2={B2/1e6:3.0f}M => {prob:.1%}")
    else:
        assert False, f"No P-1 Bounds for {start}"

    # Simple solution is to add them to a pqueue (heapq)
    # 1. Take the item with the highest marginal yield (derivative of rate=prob/credit)
    # 2. Increase B1/B2 slightly, add back to pqueue

    # TODO include tf per group. This increases prob estimates, but takes more time
    local_pm1_limits = Counter()
    extra = [0, 0, 0]  # count, sum(B1), sum(B2)
    for (B1, B2), count in pm1_limits[start].items():
        if count > 50:
            local_pm1_limits[(B1, B2)] += count
        else:
            extra[0] += count
            extra[1] += B1
            extra[2] += B2

    if extra[0] > 0:
        avg_B1 = int(extra[1] / extra[0] // 10000) * 10000
        avg_B2 = int(extra[2] / extra[0] // 10000) * 10000
        local_pm1_limits[(avg_B1, avg_B2)] = extra[0]

    # priority queue of
    #   (yield derivative,
    #    incremental probability,
    #    incremental work,
    #    probability at new bounds,
    #    work at new bounds,
    #    B1 of new work,
    #    B2 of new work,
    #    probability of initial bounds,
    #    count of exponents at these bounds)
    queue = []

    for (B1, B2), count in local_pm1_limits.items():
        # Prob / Work is u shaped (increases as B1 > B1_existing, decreases at some point)
        e_prob = pm1.prob_pm1(first_e, cleared, B1, B2)[1]
        best = (0, 1, B1, B2)
        best_rate = 0

        for exp in range(1, 20):
            mult = math.exp(exp / 8)
            prob, work, *_, = test = pm1_stats(first_e, cleared, B1, B2_RATIO * B1, e_prob, inc=mult)
            if prob < 0:
                continue

            rate = prob / work
            if rate < best_rate:
                break
            best = test
            best_rate = rate

        prob, work, opt_B1, opt_B2 = best
        if debug:
            print(f"\tP-1 optimized at {prob:.2%} for {work:.2f} GHz-Days = {1/best_rate:.1f} GHz-Days/Factor")
            print(format_bounds(count, B1, B2, opt_B1, opt_B2))

        # First "derivative" is a little weird as efficency increases over a small window
        # (as you have to do a lot of work to get to existing B1). so the derivative
        # is instead taken over the whole "optimal" P-1.
        marginal_yield = prob / work

        # Add to priority queue with yield derivative
        assert marginal_yield > 0
        heapq.heappush(queue, (-marginal_yield, prob, work, prob, work, opt_B1, opt_B2, e_prob, count))

    if debug:
        print("\t----")

    # How much incremental probability via increasing limits
    remaining = needed
    sum_work = 0

    # To help with the degenerate case where not all exponents are tested items
    # in the queue aren't part of the solution set. Only items when they are popped.
    while remaining > 0:
        # The best work we can do is to include up to these bounds.
        _, inc_prob, inc_work, prob, work, B1, B2, e_prob, count = queue[0]

        # Increase bounds
        inc = 1.2 if (remaining / count / prob) < 2 else 1.8
        new_prob, new_work, new_B1, new_B2 = pm1_stats(first_e, cleared, B1, B2, e_prob, inc=inc)

        # Remove new incremental probability
        remaining -= inc_prob * count
        # Add new incremental work
        sum_work += inc_work * count

        # Compute new derivatives
        new_inc_prob = new_prob - prob
        new_inc_work = new_work - work
        marginal = new_inc_prob / new_inc_work
        new = (-marginal, new_inc_prob, new_inc_work, new_prob, new_work, new_B1, new_B2, e_prob, count)
        heapq.heapreplace(queue, new)

        if debug:
            print(format_bounds(count, B1, B2, new_B1, new_B2))

    if debug:
        print(f"\tLast P-1 {count} x {prob:.1%} @ B1={B1/1e3:5.0f}K B2={B2/1e6:5.0f}M")
    return sum_work, len(exponents), int(B1), int(B2)


def work_to_clear(start, threshold):
    total_needed = rem = unfactored_per[start]
    limits = Counter(tf_limits[start])
    # GPU only strategy
    gpu_work = 0
    tfs = 0

    best_combined = 10 ** 1000

    output = ["\n"]
    while rem > 1e-4:
        bit = min(limits)

        # Never going to print, never going to improve best_combined
        if best_combined < threshold and best_combined < gpu_work / GPU_MULT:
            break

        # Find rem factors with P-1
        cpu_work, pm1s, B1, B2 = pm1_strategy(start, 2 ** bit, rem)
        ratio = gpu_work / max(cpu_work, 0.1)
        g_factors = total_needed - rem
        g_rate = gpu_work / max(g_factors, 0.1)
        c_rate = cpu_work / max(rem, 0.1)
        rate_str = f"GHz-Days/factor  GPU: {g_rate:.1f}  CPU: {c_rate:.1f} | {ratio:.1f}x GPU/CPU"
        tf_work_str  = f"factors/tests {g_factors:.1f}/{tfs} TF"
        pm1_work_str = f"{rem:.1f}/{pm1s} P-1 @ B1={B1/1e3:5.0f}K B2={B2/1e6:5.0f}M"
        output.append(f"\t{gpu_work:.0f} GPU({bit}) + {cpu_work:.1f} CPU | {rate_str}")
        output.append(f"\t{tf_work_str} {pm1_work_str}\n")

        combined = gpu_work / GPU_MULT + cpu_work
        if combined < best_combined:
            best_combined = combined

        # Better to spend CPU than 150x GPU
        if ratio > 150:
            break

        # Move the lowest bit level to the next level
        # expect to find a little less than ~(1 / bit) factors
        bit = min(limits)
        count = limits[bit]
        success = 1 / (bit + 5)  # adjust for some P-1 already done
        to_tf = min(count, int(math.ceil(rem / success)))
        expected = to_tf * success

        rem -= expected
        gpu_work += to_tf * tf_work(start + SIZE/2, bit)
        tfs += to_tf

        if to_tf == count:
            # zero and remove key
            assert limits.pop(bit) == to_tf
        else:
            limits[bit] -= to_tf

        limits[bit+1] += to_tf - int(expected)

    if gpu_work / 50 < best_combined:
        best_combined = gpu_work / 50

    if rem < 1e-4:
        output.append(f"\t{gpu_work:.0f} GPU({to_tf} x {bit + 1}) + 0 CPU | {total_needed}/{tfs} TF\n")

    return best_combined, output




# For each interval determine work to clear using only TF
total = 0
most_work = 0
for start, rem in unfactored_per.most_common():
    n = sum(tf_limits[start].values())
    tf_str = " + ".join(f"{c} x {b}" for b, c in tf_limits[start].most_common())
    avg_pm1 = list(map(lambda e: sum(e) / n, zip(*pm1_limits[start].elements())))
    pm1_str = f"avg B1={avg_pm1[0]/1e3:.0f}K B2={avg_pm1[1]/1e6:.0f}M"
    print()
    work, output = work_to_clear(start, 0.5 * most_work)
    total += work
    print(f"{start:8}  {rem} needed | P-1 {pm1_str:20}  TF {tf_str}")
    print(f"\tCombined Work: {work:.0f} GHz-Days")
    if work >= 0.5 * most_work:
        print("\n".join(output))

    if work > most_work:
        most_work = work
        print(f"\tTakes ~ {work:.0f} GHz-Days Combined work (GPU/{GPU_MULT} + CPU)!")
        print("\n\n")


print(f"Total Combined (CPU + GPU/{GPU_MULT}) Work  {total:.0f} GHz-Days = {total/365.25:.0f} GHz-Years")

