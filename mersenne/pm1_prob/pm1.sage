# Adaption of GpuOwl's pm1.cpp
# https://github.com/preda/gpuowl/blob/master/pm1/pm1.cpp
# Copyright: GPL v3

# Adjustments
# 1. Use Sage dickman_rho() instead of precomputed table
# 2. Eval integral at more points
#

# Preda's code makes use of a table and linear interpolation to compute rho
# in sage we have direct access to dickman_rho

from fft import fft_timing_data, fft_size_data


def prob_stage1(alpha):
    '''
    Probability of finding factor in first stage

    This is the probability that the largest factor is < alpha
    '''
    return dickman_rho(alpha)


def prob_stage2(alpha, beta):
    '''
    Probability of finding factor in 1st (alpha) or 2nd stage (beta)

    See "Some Integer Factorization Algorithms using Elliptic Curves", R. P. Brent, page 3.
    https://maths-people.anu.edu.au/~brent/pd/rpb102.pdf
    Also "Speeding up Integer Multiplication and Factorization", A. Kruppa, chapter 5.3.3 (page 102).
    '''

    # alpha = M_bits / log(B1)
    # beta  = M_bits / log(B2)
    # B1 > B2   =>  alpha > beta
    assert alpha >= beta

    # See https://www.mersenneforum.org/showthread.php?p=553516
    def f(x):
        return dickman_rho(alpha - x) / x

    # Ratio of B2 / B1
    return numerical_integral(f, 1, alpha / beta)[0]


def prob_pm1(exponent, cleared, B1, B2):
    '''Probability of factor > cleared (e.g. 2^70, 10^20) for M<exp> = 2^exponent-1'''

    # Mersenne factors have a special form 2*k*p+1 for M<p>
    # so a factor of size F is actually a factor of size F/(2*p)

    sum_prob_s1 = 0
    sum_prob = 0

    factor_start = log(cleared)
    factor_end = log(2 ** 150)
    slices = 200
    log_per_slice = ((factor_end - factor_start) / slices).n()

    # Integrate over size of found factor F in 300 slices
    for i in range(slices):
        # Interval is [sta, end] with mid (logarithmically) of mid
        sta = exp(factor_start + i * log_per_slice).n()
        mid   = exp(factor_start + (i + 0.5) * log_per_slice).n()
        end   = exp(factor_start + (i + 1) * log_per_slice).n()

        # Probability of finding a factor in this interval
        # See: Merten's 2nd Theorem
        prob_factor = log(log(end)) - log(log(sta))
        # 1/alpha, 1/beta for dickman_rho
        alpha = (log(mid/2/exponent) / log(B1)).n()
        beta  = (log(mid/2/exponent) / log(B2)).n()
        p1 = prob_stage1(alpha)       * prob_factor
        p2 = prob_stage2(alpha, beta) * prob_factor

        sum_prob_s1 += p1 * (1 - sum_prob_s1)
        sum_prob    += (p1 + p2) * (1 - sum_prob)

    return float(sum_prob_s1), float(sum_prob)


def n_primes_between(B1, B2):
    # Sage has a very fast PrimePi
    if B2 <= B1:
        return 0
    return prime_pi(B2) - prime_pi(B1)


def get_FFT_size(exponent):
    '''Find appropriate length for FFT'''
    for max_exp, size in fft_size_data:
        if max_exp > exponent:
            return size
    assert False, exponent

def get_FFT_timing(exponent):
    '''Find FFT timing

    Uses a minimized version of James data
    See: https://www.mersenneforum.org/showpost.php?p=593701&postcount=707
    '''
    fftlen = get_FFT_size(exponent)
    best = fft_timing_data[0][1]
    for size, timing in fft_timing_data:
        if size >= fftlen:
            best = timing
        else:
            break
    return best


def credit(exponent, B1, B2):
    '''GIMPS CPU Credit (GHz-Days) for a P-1 assignment

    See: https://mersenneforum.org/showpost.php?p=152280&postcount=204
    and https://www.mersenneforum.org/showthread.php?t=10937
    '''
    timing = get_FFT_timing(exponent)
    credit = 1.45 * B1 + 0.079 * (B2 - B1)
    return float(timing * credit / 86400)


def test():
    # TODO add more test cases
    clear = 2 ** 70
    M  = 1000000
    B1 = 150000
    B2 = 20 * B1
    prob = prob_pm1(M, clear, B1, B2)
    #print(f"prob({M:,}, B1={B1:,}, B2={B2:,}, {clear:.1e}) = {prob[0]:.3%} {prob[1]:.3%}")
    assert abs(prob[0] - 0.666/100) < 1e-2
    assert abs(prob[1] - 1.977/100) < 1e-2

    w = credit(M, B1, B2)
    assert abs(w - 0.01312) < 1e-4

test()

