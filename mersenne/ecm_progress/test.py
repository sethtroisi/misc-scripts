# Try to convert list of <B1, B2, number_of_curves> to
# t40, t45, t50 progress


# References:
# https://members.loria.fr/PZimmermann/records/ecm/params.html
# https://www.rieselprime.de/ziki/Elliptic_curve_method
# https://www.mersenne.org/report_ecm/

def process(curves):
    # https://www.mersenne.org/report_ecm/
    expected_effort = {
            20: (11000, 100),
            25: (50000, 280),
            30: (250000, 640),
            35: (1000000, 1580),
            40: (3000000, 4700),
            45: (11000000, 9700),
            50: (44000000, 17100),
            55: (110000000, 46500),
            60: (260000000, 112000),
            65: (800000000, 360000),
    }

    completed = []
    for digits, (min_B1, needed) in expected_effort.items():
        complete = 0.0
        for B1, B2, count in curves:
            if B1 >= min_B1 and B2 >= 20 * min_B1:
                complete += count / needed

        if complete > 0.001:
            completed.append((digits, complete))

    status = []
    for digits, effort in completed:
        status.append("t{} x {}".format(digits, round(effort, 3)))

    print (" ".join(status))
    return completed


# Simple cases t20 x 1, t25 x 2, t35 x 0.5
answer = process([(11000, 11000 * 100, 100)])
assert answer[0] == (20, 1.0), answer
# t20 x 1.0

answer = process([(50000, 50000 * 82, 200), (50001, 50000 * 85, 80)])
assert answer[1] == (25, 1.0), answer
# t20 x 2.8 t25 x 1.0

answer = process([(10 ** 6, 10 ** 9, 700), (10 ** 7, 10 ** 9, 90)])
assert answer[3] == (35, 0.5), answer
assert answer[4] == (40, 90 / 4700), answer
# t20 x 7.9 t25 x 2.821 t30 x 1.234 t35 x 0.5 t40 x 0.019

# B1=B2 doesn't qualify as t45 (or t35)
answer = process([(11000000, 11000000, 9700)])
assert answer[2] == (30, 9700 / 640)
assert len(answer) == 3
# t20 x 97.0 t25 x 34.643 t30 x 15.156

