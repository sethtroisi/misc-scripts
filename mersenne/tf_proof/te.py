import gmpy2

exp = 5000000

while exp <= 250000000:
    exp = gmpy2.next_prime(exp)

    base = "Factor=N/A,{},".format(exp)

    for bits in ((58,60), (60,62),
                 (65,67), (70,71),
                 73,74), (75,76)):
        ghz =  2 ** bits[1] / exp / 1.0e8 / 86400
        if ghz <= 25:
            print (base + "{},{}".format(*bits))

    exp = int(exp * 1.1)
