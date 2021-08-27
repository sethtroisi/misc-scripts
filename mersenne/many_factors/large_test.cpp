#include <cassert>
#include <cmath>
#include <cstdio>
#include <cstdint>

uint64_t powMod(uint64_t b, uint64_t p, uint64_t m)
{

    // Initialize answer
    uint64_t res = 1;

    // Check till the number becomes zero
    while (p)
    {
        // If p is odd, multiply b with result
        if (p & 1 == 1) {
            __uint128_t temp = res;
            temp *= b;
            res = temp % m;
        }

        p >>= 1;

        // Change b to b^2
        __uint128_t temp = b;
        temp *= b;
        b = temp % m;
    }
    return res;
}

// This code is contributed by yaswanth0412

int main(int argc, char** argv) {
    assert(argc == 2);
    uint64_t M = atol(argv[1]);
    printf("Testing M%lu\n", M);

    uint64_t BITS = 64;
    uint64_t INTERVALS = 100;
    uint64_t max_k;
    {
        __uint128_t k = 1;
        k <<= BITS;
        k /= 2 * M;
        max_k = k + 1;
    }

    uint64_t t = 1;
    uint64_t inc = 2 * M;

    for (uint64_t interval = 0; interval < INTERVALS; interval++) {
        uint64_t first = interval * max_k / INTERVALS;
        uint64_t last =  (interval + 1) * max_k / INTERVALS;
        printf(" [%lu, %lu) (%.2f, %.2f) bits\n", first, last, log2(2*first*M+1), log2(2*(last-1)*M+1));

        for (uint64_t k = first; k < last; k++) {
            t += inc;
            //t = 2 * k * M + 1;
            if (t % 3 == 0 or t % 5 == 0 or t % 7 == 0 or t % 11 == 0 or t % 13 == 0 or t % 17 == 0 or
                    t % 23 == 0 or t % 27 == 0)
                continue;

            if (powMod(2, M, t) == 1)
                printf("\tFactor %lu\n", t);
        }
    }
}
