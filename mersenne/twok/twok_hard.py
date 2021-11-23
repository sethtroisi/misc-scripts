#!/usr/bin/env python

# twok => two below two thousand unfactored candidates

import math
import heapq
from collections import Counter
from functools import lru_cache

import primesieve
import pm1

# Ranges above 100M are supposed to be handled by default
# and TF is very easy there so likely will have no very
# hard ranges
STOP = 20 * 10 ** 6

factor_fn = "mersenneca_known_factors_0G.txt"
tf_limits_fn = "tf_limits_0g"

# the OG project is looking at ranges of .1M = 100,000
size = 100000
rem_threshold = 2 * (size // 100) - 1

# [0, size], [size, 2*size], [2*size, 3*size]
# don't have to work about overlap with ] and [ because size is composite
counts = [[0, 0] for _ in range(size, STOP+1, size)]

# I want this to contain all primes without factors
# Ideally we'd do something in two passes, or one combined pass
# to avoid adding then removing all primes but that's hard to write.
unfactored = [set() for _ in range(size, STOP+1, size)]

for prime in primesieve.primes(0, STOP):
    counts[prime // size][0] += 1
    unfactored[prime // size].add(prime)

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
        counts[m // size][1] += 1
        last_m = m
        unfactored[m // size].remove(m)

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
        unfactored[m // size].remove(m)

#####

unfactored_per = Counter()
for end in range(size, STOP+1, size):
    c = counts[end // size - 1]
    rem = c[0] - c[1]
    if rem > (rem_threshold + 10):
        print(f"[{end-size:8},{end:8}] {c[1]} / {c[0]} => {rem}")
        unfactored_per[end] = rem - rem_threshold

print()
print(f"Ranges with large remaining work: {len(unfactored_per)}")
print(f"Those ranges need {sum(unfactored_per.values())} factors")
worst = unfactored_per.most_common(1)[0]
print(f"Most needed {worst[1] - rem_threshold} for {worst[0]-size}")
print()

##### Get TF work done on remaining ranges

tf_limits = {interval: Counter() for interval in unfactored_per}
with open(tf_limits_fn) as f:
    for line in f:
        raw = line.split(",")
        m = int(raw[0])
        if m > STOP:
            break

        interval = (m // size)
        top = interval * size + size
        if top in unfactored_per:
            if m in unfactored[interval]:
                limit = int(raw[1])
#                assert raw[1] + "\n" == raw[2], raw
                tf_limits[top][limit] += 1


##### Work calculation

def tf_work(M, tf):
    '''Approx GHz-Days to TF M from 2^(tf-1) to 2^tf'''
    return 2 ** tf / M / 0.9875e13


@lru_cache(maxsize=100000)
def pm1_stats(e, cleared, B1, B2, inc=1):
    B1 *= inc
    B2 *= inc
    prob = pm1.prob_pm1(e, cleared, B1, B2)[1]
    work = pm1.credit(e, B1, B2)
    return (prob, work, B1, B2)

def pm1_strategy(end, min_tf, needed):
    '''Approx GHz-Days needed to find <needed> factors using P-1'''

    # Doesn't account for TF removing some factors
    # Doesn't account for new TF limit
    # Doesn't account for existing B1/B2 limits (or what TF each exp has)

    # Assume P-1 to 2% has been done (with B1 = 20 * B2)
    # This is generally very optimistic (High P-1 has probably been done)

    exponents = sorted(unfactored[end // size - 1])
    first_e = min(exponents)


    for B1_exp in range(40, 120):
        # Steps of 30%
        B1 = math.exp(B1_exp / 4)
        B2 = 20 * B1
        prob = pm1.prob_pm1(first_e, 2 ** min_tf, B1, B2)[1]
        if prob > 0.02:
            break

    print(f"\tFor M{first_e:,} {prob:.1%} P-1:  B1={B1:.0f}  B2={B2:.0f}")

    # Prob / Work is u shaped (increases as B1 > B1_existing, decreases at some point)
    existing = (B1, B2)
    e_prob = prob

    best = (0, 1, B1, B2)
    best_rate = 0

    for exp in range(1, 20):
        mult = math.exp(exp / 8)
        prob, work, *_, = test = pm1_stats(first_e, 2 ** min_tf, B1, B2, inc=mult)
        rate = (prob - e_prob) / work
        #print(f"\t{mult:.1f}x\t => {e_prob:.1%} -> {prob:.1%} For {rate:.2f} GHz-Days ({work:.3f})")
        if rate < best_rate:
            break

        best = test
        best_rate = rate


    prob, work, B1, B2 = best
    print(f"\tP-1 optimized at {prob:.2%} for {work:.2f} GHz-Days = {1/best_rate:.1f} GHz-Days/Factor (B1={B1:.0f} B2={B2:0.7})")

    gain = prob - e_prob
    expected = gain * len(exponents)
    cost = len(exponents) * work
    print(f"\t{len(exponents)} x +{gain:.2%} = +{expected:.1f} factors for {cost:.1f} GHz-Days")

    # If optimal (best yield for CPU time)
    if expected > needed:
        # This assumes we have enough exponents that len(exponents)
        count = needed / gain
        return count * work, count, B1, B2

    # If we had a bag of B1/B2 limits this would be harder
    # But the simple solution is to add them to a pqueue (heapq)
    # 1. Take the item with the highest marginal yield (derivative of rate=prob/credit)
    # 2. Increase B1/B2 slightly, add back to pqueue

    # TODO also keep tf cleared per group
    pm1_limits = Counter({(B1, B2): len(exponents)})

    # priority queue of (yield derivative, prob, work, B1, B2, count exponents)
    queue = []
    for (B1, B2), count in pm1_limits.items():
        prob_1, work_1, *_ = pm1_stats(first_e, 2 ** min_tf, B1, B2)
        prob_2, work_2, *_ = pm1_stats(first_e, 2 ** min_tf, B1, B2, inc=1.05)
        marginal_yield = (prob_2 - prob_1) / (work_2 - work_1)
        assert marginal_yield > 0
        heapq.heappush(queue, (-marginal_yield, prob_1, work_1, B1, B2, count))


    # How much incremental probability via increasing limits
    remaining = needed - expected
    sum_work = cost

    while remaining > 0:
        _, old_prob, old_work, _, _, count = queue[0]

        # Increase bounds slightly
        prob, work, B1, B2 = pm1_stats(first_e, 2 ** min_tf, B1, B2, inc=1.2)

        # Remove new expected probability
        remaining -= (prob - old_prob) * count
        sum_work += (work - old_work) * count

        # Compute new stats
        marginal = (prob - old_prob) / (work - old_work)
        new = (-marginal, prob, work, B1, B2, count)

        heapq.heapreplace(queue, new)

    avgB1 = int(sum(s[3] * s[-1] for s in queue) / len(exponents))
    avgB2 = int(sum(s[4] * s[-1] for s in queue) / len(exponents))

    return sum_work, len(exponents), avgB1, avgB2


def work_to_clear(end):
    total_needed = rem = unfactored_per[end]
    limits = Counter(tf_limits[end])
    # GPU only strategy
    gpu_work = 0
    tfs = 0

    print()
    while rem > 1e-4:
        # Finish with PM1
        cpu_work, pm1s, B1, B2 = pm1_strategy(end, min(limits), rem)
        ratio = gpu_work / max(cpu_work, 0.1)
        g_rate = gpu_work / max(total_needed - rem, 0.1)
        c_rate = cpu_work / max(rem, 0.1)
        rate_str = f"GHz-Days/factor  GPU: {g_rate:.1f}  CPU: {c_rate:.1f} | {ratio:.1f}x GPU/CPU"
        work_str = f"{tfs} TF + {pm1s} P-1 @ B1={B1} B2={B2}"
        print(f"\t{gpu_work:.0f} GPU + {cpu_work:.1f} CPU | {rate_str} | {work_str}")
        print()

        # Move the lowest bit level to the next level
        # expect to find a little less than ~(1 / bit) factors
        bit = min(limits)
        count = limits[bit]
        success = 1 / (bit + 5)  # adjust for some P-1 already done
        to_tf = min(count, rem / success)
        rem -= to_tf * success
        # TODO could look at actualy primes but meh, average is good enough
        gpu_work += to_tf * tf_work(end - size/2, bit)
        tfs += to_tf
        if to_tf == count:
            # zero and remove key
            assert limits.pop(bit) == to_tf
        else:
            limits[bit] -= to_tf
        limits[bit+1] += to_tf

    print(f"\t{gpu_work:.0f} GPU + 0 CPU | {tfs} TF")
    print()

    return gpu_work




# For each interval determine work to clear using only TF
most_work = 0
for end, rem in unfactored_per.most_common():
    print()
    print(f"[{end-size},{end}] {rem} => {tf_limits[end].items()}")
    work = work_to_clear(end)
    if work >= most_work:
        most_work = work

