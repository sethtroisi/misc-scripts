// g++ gmp-test.cpp -l gmp -o gmp-test
// ./gmp-test power_primes.txt

#include <cassert>
#include <chrono>
#include <cstdio>
#include <fstream>

#include <gmp.h>

using namespace std::chrono;


int main(int argc, char* argv[]) {
    printf("Compiled with GMP %d.%d.%d\n",
        __GNU_MP_VERSION, __GNU_MP_VERSION_MINOR, __GNU_MP_VERSION_PATCHLEVEL);

    assert(argc == 2);

    mpz_t ptest;
    mpz_init(ptest);

    std::ifstream prime_file (argv[1], std::ios::in);
    while (prime_file.good() && !prime_file.eof()) {
        int base, exp, add;
        std::string delim;
        char exp_sign;

        prime_file >> base;
        prime_file >> exp_sign;
        if (exp_sign == '^') {
            // Lines are of the form "10^60 + 7"
            prime_file >> exp;
            prime_file >> delim;
            prime_file >> add;

            mpz_ui_pow_ui(ptest, base, exp);
            mpz_add_ui(ptest, ptest, add);
        } else if (exp_sign == '#') {
            // Lines are of the form "31#+1"
            prime_file >> add;

            mpz_primorial_ui(ptest, base + 1);
            if (add >= 0)
                mpz_add_ui(ptest, ptest, add);
            else
                mpz_sub_ui(ptest, ptest, -add);

        } else {
            printf("What: %d | %c\n", base, exp_sign);
            assert( false );
        }

        if (prime_file.eof()) break;

        auto   start_t = high_resolution_clock::now();
        int is_prime = mpz_probab_prime_p(ptest, 25);
        auto   stop_t = high_resolution_clock::now();
        double secs = duration<double>(stop_t - start_t).count();

        if (exp_sign == '^') {
            printf("%d^%d + %d", base, exp, add);
        } else {
            printf("%d# + %d", base, add);
        }

        printf(" => %8s (%f seconds)\n",
            is_prime == 0 ? "composite": "prime",
            secs);
    }

    mpz_clear(ptest);
}

