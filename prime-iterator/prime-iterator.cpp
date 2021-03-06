#include <algorithm>
#include <cassert>
#include <cmath>
#include <cstring>
#include <functional>
#include <iostream>
#include <locale>
#include <vector>

using std::cout;
using std::endl;
using std::vector;

vector<uint32_t> get_sieve_primes(uint32_t n) {
    vector<uint32_t> primes = {2};
    vector<bool> is_prime(n, true);
    for (uint64_t p = 3; p*p <= n; p += 2) {
        if (is_prime[p]) {
            primes.push_back(p);
            for (uint64_t m = p*p; m <= n; m += 2*p)
                is_prime[m] = false;
        }
    }
    for (uint32_t p = primes.back() + 2; p <= n; p += 2) {
        if (is_prime[p])
            primes.push_back(p);
    }
    return primes;
}

// Faster because of better memory access patterns
vector<uint64_t> get_sieve_primes_segmented(uint64_t n) {
    assert( n > 10'000 );
    uint64_t sqrt_n = sqrt(n);
    while (sqrt_n * sqrt_n <= n) sqrt_n++;

    const vector<uint32_t> small_primes = get_sieve_primes(sqrt_n);

    // First number in next block that primes[pi] divides.
    vector<int32_t> next_mod(small_primes.size(), 0);

    // Large enough to be fast and still fit in L1/L2 cache.
    uint32_t BLOCKSIZE = 1 << 16;
    uint32_t ODD_BLOCKSIZE = BLOCKSIZE >> 1;
    vector<char> is_prime(ODD_BLOCKSIZE, true);

    vector<uint64_t> primes = {2};

    uint32_t max_pi = 0;
    for (uint64_t B = 0; B < n; B += BLOCKSIZE) {
        uint64_t B_END = B + BLOCKSIZE - 1;
        if (B_END > n) {
            BLOCKSIZE = (n - B);
            ODD_BLOCKSIZE = (n - B + 1) >> 1;
            B_END = n;
        }

        while (max_pi < small_primes.size()) {
            uint64_t p2 = small_primes[max_pi];
            p2 = p2 * p2;
            if (p2 > B_END) break;
            next_mod[max_pi] = (p2 - B) >> 1;
            max_pi += 1;
        }

        // reset is_prime
        std::fill(is_prime.begin(), is_prime.end(), true);
        if (B == 0) is_prime[0] = 0; // Skip 1

        // Can skip some large pi up to certain B (would have to set next_mod correctly)
        for (uint32_t pi = 1; pi < max_pi; pi++) {
            const uint32_t prime = small_primes[pi];
            uint32_t first = next_mod[pi];
            for (; first < ODD_BLOCKSIZE; first += prime){
                is_prime[first] = false;
            }
            next_mod[pi] = first - ODD_BLOCKSIZE;
        }
        for (uint32_t prime = 0; prime < ODD_BLOCKSIZE; prime++) {
            if (is_prime[prime]) {
                primes.push_back(B + 2 * prime + 1);
            }
        }
    }

    return primes;
}

bool isprime_brute(uint32_t n) {
    if ((n & 1) == 0)
        return false;
    for (uint32_t p = 3; p * p <= n; p += 2)
        if (n % p == 0)
            return false;
    return true;
}

void get_sieve_primes_segmented_lambda(uint64_t n, std::function<void (uint64_t)> lambda) {
    // Large enough to be fast and still fit in L1/L2 cache.
    uint32_t BLOCKSIZE = 1 << 16;
    uint32_t ODD_BLOCKSIZE = BLOCKSIZE >> 1;
    vector<char> is_prime(ODD_BLOCKSIZE, true);

    lambda(2L);

    vector<int32_t> primes = {3};
    // First number in next block that primes[pi] divides.
    vector<int32_t> next_mod = {9 >> 1};

    uint32_t p_lim = 5;
    uint64_t p2_lim = p_lim * p_lim;

    for (uint64_t B = 0; B < n; B += BLOCKSIZE) {
        uint64_t B_END = B + BLOCKSIZE - 1;
        if (B_END > n) {
            BLOCKSIZE = (n - B);
            ODD_BLOCKSIZE = (n - B + 1) >> 1;
            B_END = n;
        }

        while (p2_lim <= B_END) {
            if (isprime_brute(p_lim)) {
                primes.push_back(p_lim);
                assert( p2_lim >= B );
                next_mod.push_back((p2_lim - B) >> 1);
            }
            p2_lim += 4 * p_lim + 4;
            p_lim += 2;
            //assert( p_lim * p_lim == p2_lim );
        }

        // reset is_prime
        std::fill(is_prime.begin(), is_prime.end(), true);
        if (B == 0) is_prime[0] = 0; // Skip 1

        // Can skip some large pi up to certain B (would have to set next_mod correctly)
        for (uint32_t pi = 0; pi < primes.size(); pi++) {
            const uint32_t prime = primes[pi];
            uint32_t first = next_mod[pi];
            for (; first < ODD_BLOCKSIZE; first += prime) {
                is_prime[first] = false;
            }
            next_mod[pi] = first - ODD_BLOCKSIZE;
        }
        for (uint32_t prime = 0; prime < ODD_BLOCKSIZE; prime++) {
            if (is_prime[prime]) {
                lambda(B + 2 * prime + 1);
            }
        }
    }
}


class PrimeIterator {
    class PrimeIter {
        public:
            PrimeIter(uint64_t start, bool update) {
                if (update) {
                    first_prime = start;
                    B = (start / BLOCKSIZE) * BLOCKSIZE;

                    is_prime.resize(PrimeIter::ODD_BLOCKSIZE);
                    nextPrime();
                } else {
                    first_prime = B = start;
                }
            }

            PrimeIter operator++() {
                nextPrime();
                return *this;
            }

            bool operator!=(const PrimeIter & other) const {
                uint64_t comp = B;
                if (current_primes.size()) {
                    comp = current_primes.front();
                }
                return comp < other.B;
            }

            const vector<uint64_t>& operator*() const { return current_primes; }

        private:
            void nextPrime() {
                uint64_t B_END = B + BLOCKSIZE - 1;
                while (true) {
                    uint64_t lastp = primes.empty() ? 0 : primes.back();
                    if (lastp * lastp > B_END) break;

                    // Find a next prime via brute force.
                    uint64_t nextp = lastp == 0 ? 3 : lastp + 2;
                    for (; ; nextp += 2) {
                        bool isp = true;
                        for (uint32_t p : primes) {
                            if (nextp % p == 0) {
                                isp = false;
                                break;
                            }
                        }
                        if (isp) break;
                    }

                    primes.push_back(nextp);
                    if (B == 0) {
                        next_mod.push_back(nextp * nextp >> 1);
                    } else {
                        // Next odd multiple of nextp >= B
                        uint64_t mult = (B-1) / nextp + 1;
                        uint64_t first = (mult | 1) * nextp;
                        assert( first >= B );
                        assert( first / nextp % 2 == 1 );
                        first -= B;
                        next_mod.push_back(first >> 1);
                    }
                }

                std::fill(is_prime.begin(), is_prime.end(), true);
                if (B == 0) is_prime[0] = 0; // Skip 1

                for (uint32_t pi = 0; pi < primes.size(); pi++) {
                    const uint32_t prime = primes[pi];
                    uint32_t first = next_mod[pi];
                    for (; first < ODD_BLOCKSIZE; first += prime){
                        is_prime[first] = false;
                    }
                    next_mod[pi] = first - ODD_BLOCKSIZE;
                }

                current_primes.clear();
                if (B == 0 && first_prime <= 2) {
                    current_primes.push_back(2);
                }

                // deal with start > B
                size_t p = 0;
                if (first_prime > B) {
                    p = (first_prime - B) / 2;
                }

                for (; p < ODD_BLOCKSIZE; p++) {
                    if (is_prime[p]) {
                        current_primes.push_back(B + 2 * p + 1);
                    }
                }
                B += BLOCKSIZE;
            }

            uint64_t first_prime;
            vector<uint64_t> current_primes;

            // Large enough to be fast and still fit in L1/L2 cache.
            const uint64_t BLOCKSIZE = 1 << 16;
            const uint64_t ODD_BLOCKSIZE = BLOCKSIZE >> 1;

            uint64_t is_prime_i = BLOCKSIZE;
            uint64_t B = 0;
            vector<char> is_prime;

            vector<uint32_t> primes;

            // First number in next block that primes[pi] divides.
            vector<int32_t> next_mod;
    };

    private:
        uint64_t first_prime;
        uint64_t last;

    public:
        PrimeIterator(uint64_t n) {
            first_prime = 0;
            last = n;
        }

        PrimeIterator(uint64_t a, uint64_t b) {
            first_prime = a;
            last = b;
        }

        PrimeIter begin() const { return PrimeIter(first_prime, true); }
        PrimeIter end()   const { return PrimeIter(last + 1,    false); }
};




int main(int argc, char** argv)
{
    uint64_t limit = argc >= 2 ? std::atoll(argv[1]) : 1e9;

    // For commas in numbers.
    std::cout.imbue(std::locale(""));

    if (argc == 2) {
        uint64_t count = 0;
        uint64_t sum = 0;
        // /*
        get_sieve_primes_segmented_lambda(
            limit,
            [&count, &sum](uint64_t p) { count += 1; sum += p; return; }
        );
        // */
        /*
        auto primes = get_sieve_primes_segmented(limit);
        count = primes.size();
        for (auto prime : primes) {
            sum += prime;
        }
        // */
        cout << "Found " << count << " Primes <= " << limit << endl;
        cout << "  Sum " << sum << endl;
        return 0;
    }

    uint64_t start = std::atoll(argv[2]);

    int z = 0;
    size_t count = 0;
    uint64_t sum = 0;
    for (auto primes : PrimeIterator(start, limit)) {
        if (primes.size() && primes.back() > limit) {
            for (auto p : primes) {
                count += p <= limit;
                sum   += (p <= limit) * p;
            }
        } else {
            count += primes.size();
            for (auto p : primes) {
                sum += p;
            }
        }

        z += 1;
        if (primes.size() && (z < 6 || z % (100 * (1<<4)) == 0))
            cout << count << " : " << primes.size() << " "
                << primes[0] << " to " << primes.back() << endl;
    }
    cout << "Found " << count << " Primes <= " << limit << endl;
    cout << "  Sum " << sum << endl;
    return 0;
}
