import re
import subprocess

from scipy import interpolate
from scipy.optimize import minimize, bisect

def load_B1_timing():
    """Load Step 1 timing"""
    # take as command line option
    return 4786 / 1000 / 1e5 / 1792

def load_B2_timing():
    """Load Step 2 timings at various B2 values"""

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
    process = subprocess.run(["ecm", "-v", str(B1), str(B2)], input=b"2^31-1", capture_output=True)
    #assert process.returncode == 8
    output = process.stdout.split(b"\n")
    CURVES_KEY = b'35\t40\t45\t50\t55\t60\t65\t70\t75\t80'
    assert CURVES_KEY in output, output
    digits = map(int, CURVES_KEY.split())
    expected_curves = map(float, output[output.index(CURVES_KEY) + 1].split())
    return {X: C for X, C in zip(digits, expected_curves)}


def optimize_t(digits, B1_B2_ratio):
    B1_timing = load_B1_timing()
    B2_timings = load_B2_timing()

    B1_time_func = lambda B1 : B1 * B1_timing
    B2_time_func = B2_timing_guess(B2_timings)

    def time_for_tX(B1, B2):
        curves = int(number_of_curves(B1, B2)[digits])
        return curves, curves * (B1_time_func(B1) + B2_time_func(B2))

    def optimize_B2(B1):
        """Find B2 that requires B1/B2 ratio time"""
        B1_t = B1_time_func(B1)
        B2_goal = B1_t * B1_B2_ratio
        #print (B1, "\t", B1_t, "\t", B2_goal, "\t", B2_time_func(B1), B2_time_func(2000*B1))
        def test(x):
            err = B2_time_func(x) - B2_goal
#            print(x, B2_time_func(x), B2_goal, err)
            return err

        #t = minimize(test, 3 * B1, bounds=[[2*B1, 2000*B1]], method="trust-constr")
        t = bisect(test, B1, 400*B1)
        return int(t) #int(t.x[0])


    B1_best = 10000
    _, timing = time_for_tX(B1_best, 100 * B1_best)

    # This is way less efficient than binary search but easier to code
    for i in range(100):
        # Try with 60% larger, 5% larger and 1% smaller B1
        for B1_test in (B1_best * 160 // 100, B1_best * 105 // 100, B1_best * 99 // 100):
            B2_test = optimize_B2(B1_test)
            curves_test, test_time = time_for_tX(B1_test, B2_test)
            is_better = bool(test_time < timing)
            if is_better:
                print ("\tB1={:<8} B2={:<10}  curves={:<6}\ttime(s): {:.1f}".format(
                    B1_test, B2_test, curves_test, test_time))
                B1_best = B1_test
                timing = test_time
                break
        else:
            break


    B2_best = optimize_B2(B1_best)
    B2_ratio = B2_best / B1_best
    curves, _ = time_for_tX(B1_test, B2_test)
    print ("B1={}, B2={:.1f}*B1   {} curves".format(B1_best, B2_ratio, curves))
    print ("Step 1 takes: {:.1f} seconds".format(curves * B1_time_func(B1_best)))
    return (B1_best, B2_best)

def optimize():
    #for digits in range(35, 81, 5):
    optimize_t(35, 4)

optimize()
