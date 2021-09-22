#include <cassert>
#include <cmath>
#include <cstdio>
#include <cstdint>
#include <vector>

using std::vector;

/**
 * p has [32, 33.8] bits
 * m is  [50, 64] bits (and should be prime)
 */
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

int main(int argc, char** argv) {
    assert(argc == 2);
    uint64_t M = atol(argv[1]);
    printf("Testing M%lu\n", M);

    uint64_t BITS = 60;
    uint64_t INTERVALS = 20;
    uint64_t max_k;
    {
        __uint128_t k = 1;
        k <<= BITS;
        k /= 2 * M;
        max_k = k + 1;
    }

    uint64_t t = 1;
    uint64_t inc = 2 * M;
    uint64_t k = 0;

    vector<uint8_t> small_primes = {
        3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41, 43, 47, 53, 59, 61, 67, 71, 73, 79, 83, 89, 97,
        101, 103, 107, 109, 113, 127, 131, 137, 139, 149, 151, 157, 163, 167, 173, 179, 181, 191, 193,
        197, 199, 211, 223, 227, 229, 233, 239, 241, 251
    };

    // i such that (2 * M * i + 1) % p == 0;
    vector<uint8_t> next_i(small_primes.size(), 0);
    for (size_t pi = 0; pi < small_primes.size(); pi++) {
        uint16_t p = small_primes[pi];
        uint16_t step = inc % p;
        uint16_t rem = 1;
        uint8_t i = 0;
        while (rem != 0) {
            i++;
            rem += step;
            if (rem >= p)
                rem -= p;
        }
        assert( (inc * i + 1) % p == 0 );
        next_i[pi] = i;
    }


    size_t tested = 0;
    size_t interval = 0;

    while (k < max_k) {
        uint64_t first = interval * max_k / INTERVALS;
        uint64_t last =  (interval + 1) * max_k / INTERVALS;

        if (k > first) {
            printf(" [%lu, %lu) (%.2f, %.2f) bits %ld tests\n", first, last, log2(2*first*M+1), log2(2*(last-1)*M+1), tested);
            interval += 1;
        }

        size_t SIEVE_SIZE = (1 << 16);
        char sieve[SIEVE_SIZE] = {};
        for (size_t pi = 0; pi < small_primes.size(); pi++) {
            uint16_t p = small_primes[pi];
            uint32_t i = next_i[pi];
            //assert( (inc * (k + i) + 1) % p == 0 );
            for (; i < SIEVE_SIZE; i += p)
                sieve[i] = 1;
            next_i[pi] = i - SIEVE_SIZE;
        }

        size_t I = std::min(SIEVE_SIZE, max_k - k);
        for (size_t i = 0; i < I; i++, t += inc) {
            if (sieve[i] == 0) {
                tested += 1;
                if (powMod(2, M, t) == 1)
                    printf("\tFactor %lu\n", t);
            }
        }
        k += I;
    }
}
