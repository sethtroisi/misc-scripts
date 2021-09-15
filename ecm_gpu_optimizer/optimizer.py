import math
import re
import subprocess

from scipy import interpolate
from scipy.optimize import minimize, bisect

def load_B1_timing():
    """Load CPU Step 1 timing"""
    # take as command line option
    return 1075 / 1000 / 1e6

def load_B2_timing():
    """Load CPU Step 2 timings at various B2 values"""

    # (B2, time(ms))
    B2_timing = []

    # TODO add more values to the log or something
    with open("B2_timing.log") as f:
        B2 = None
        for line in f:
            match = re.match("Using B1=[0-9]*, B2=([1-9][0-9]*), ", line)
            if match:
                B2 = int(match.group(1))
                #print (B2, "\t", line.strip())

            match = re.match("Step 2 took ([0-9]+)ms", line)
            if match:
                assert B2
                timing = int(match.group(1)) / 1000
                #print (timing, B2, "\t", line.strip())
                B2_timing.append((B2, timing))
                B2 = None

    return sorted(B2_timing)

def B2_timing_guess(timings):
    """Take an educated guess at B2 timing based on interpolation between values"""

    x, y = tuple(zip(*timings))
    f = interpolate.interp1d(x, y)
    '''
    import matplotlib.pyplot as plt
    import numpy as np
    new_x = np.linspace(min(x), max(x), num=100, endpoint=False)
    plt.plot(x, y)
    plt.plot(new_x, f(new_x))
    plt.xscale("log")
    plt.yscale("log")
    plt.show()
    '''
    return f

def number_of_curves(B1, B2):
    # ECM should finish rho / dickman calculation quickly
    process = subprocess.run(["timeout", "0.2", "ecm", "-v", "-param", "3", str(B1), str(B2)], input=b"2^31-1", capture_output=True)
    output = process.stdout.split(b"\n")
    CURVES_KEY = b'35\t40\t45\t50\t55\t60\t65\t70\t75\t80'
    # This will fail if you haven't applied https://gitlab.inria.fr/zimmerma/ecm/-/merge_requests/13
    # You may also need to change "ecm" to "../gmp-ecm/ecm" or some other local path
    assert CURVES_KEY in output, (output, "see comment above about zimmerma/ecm/#13")
    digits = map(int, CURVES_KEY.split())
    expected_curves = map(float, output[output.index(CURVES_KEY) + 1].split())
    return {X: C for X, C in zip(digits, expected_curves)}


def optimize_t(digits, GPU_SPEEDUP, CPU_CORES):
    B1_timing = load_B1_timing()
    B2_timings = load_B2_timing()

    B1_time_func = lambda B1 : B1 * B1_timing
    B2_time_func = B2_timing_guess(B2_timings)

    def time_for_tX(B1, B2):
        curves = int(number_of_curves(B1, B2)[digits])
        B1_time = B1_time_func(B1) / GPU_SPEEDUP
        B2_time = B2_time_func(B2) - B2_time_func(B1)
        return curves, curves * (B1_time + B2_time), curves * max(B1_time, B2_time / CPU_CORES)

    def optimize_B2(B1):
        """Find B2 that takes B1 / B1_speedup time"""
        B1_t = B1_time_func(B1) / GPU_SPEEDUP * CPU_CORES
        B2_goal = B1_t
        #print (B1, "\t", B1_t, "\t", B2_goal, "\t", B2_time_func(B1), B2_time_func(2000*B1))
        def test(x):
            err = (B2_time_func(x) - B2_time_func(B1)) - B2_goal
            return err

        #t = minimize(test, 3 * B1, bounds=[[2*B1, 2000*B1]], method="trust-constr")
        MAX_B1 = 10 ** 14
        if test(MAX_B1) < 0:
            return MAX_B1

        t = bisect(test, 2 * B1, MAX_B1)
        return int(t) #int(t.x[0])


    # Good, but a little low, initial guess
    B1_best = int(math.exp(digits / 4 + 4))
    _, _, timing = time_for_tX(B1_best, 100 * B1_best)

    # This is way less efficient than binary search but easier to code
    for i in range(100):
        one_pct = B1_best // 100
        # Try with 40% larger, 3% larger, 2% smaller and 1% smaller B1
        for B1_test in (one_pct * 140, one_pct * 103, one_pct * 98, one_pct * 99):
            B2_test = optimize_B2(B1_test)
            curves_test, _, test_time = time_for_tX(B1_test, B2_test)
            if test_time < timing:
#                print ("\tB1={:<8} B2={:4.0f}*B1={:<4.2e}  curves={:<6}\ttime(s): {:.1f}".format(
#                    B1_test, B2_test / B1_test, B2_test, curves_test, test_time))
                B1_best = B1_test
                B2_best = B2_test
                timing = test_time
                break
        else:
            break

    B2_ratio = B2_best / B1_best
    curves, _, _ = time_for_tX(B1_best, B2_best)
    B1_time = int(curves * B1_time_func(B1_best) / GPU_SPEEDUP)
    B2_time = int(curves * (B2_time_func(B2_best) - B2_time_func(B1_best)))
    if False:
        print ("B1={}, B2={:.1f}*B1   {} curves".format(B1_best, B2_ratio, curves))
        print ("Step 1 takes: {} seconds".format(B1_time))
        print ("Step 2 takes: {} seconds".format(B2_time))
        print ("Running on GPU + {} cores: {} seconds".format(CPU_CORES, max(B1_time, B2_time / CPU_CORES)))
    else:
        print ("| {:>2}/{:<17}| {:<4} | {:11,} | {:15,} | {:9.0f} | {:13} |".format(
            GPU_SPEEDUP, CPU_CORES, digits, B1_best, B2_best, B2_ratio, curves))

    return (B1_best, B2_best)


def optimize():
#    for digits in range(35, 61, 5):
#        optimize_t(digits, 1, 1)

    for GPU_SPEEDUP in (20, 30, 40, 50):
        for CPU_CORES in (1, 4, 8, 12):
            label = "{} GPU + {} cores".format(
                ["Slow", "Medium", "Fast", "Extreme"][(GPU_SPEEDUP - 20) // 10], CPU_CORES)
            print ("| {:19} | {:4} | {:11} | {:15} | {:9} | {:13} |".format(
                label, *(("",) * 5)))
            for digits in range(35, 61, 5):
                optimize_t(digits, GPU_SPEEDUP, CPU_CORES)

optimize()