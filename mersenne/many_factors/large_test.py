import math

# Given that M is constant, could conceivable construct a more optimal addition-chain
# timing in pypy shows same addition chain as pow(...) is 50% slower, so this is unlikely to help
# From http://koclab.cs.ucsb.edu/teaching/cren/project/2018/Schibler.pdf
# optimal chain is no more than 50% faster

M = 9114263003

BITS = 60
INTERVALS = 100
max_k = 2 ** BITS // (2*M) + 1

for interval in range(INTERVALS):
    first = interval * max_k // INTERVALS
    last =  (interval + 1) * max_k // INTERVALS
    print(first, last, math.log2(2*first*M+1), math.log2(2*(last-1)*M+1))
    for k in range(first, last):
        t = 2*k*M+1
        if (t % 3 == 0 or t % 5 == 0 or t % 7 == 0 or t % 11 == 0 or t % 13 == 0 or t % 17 == 0 or
                t % 23 == 0 or t % 27 == 0):
            continue

        if pow(2, M, t) == 1:
            print("\tFactor", t)
