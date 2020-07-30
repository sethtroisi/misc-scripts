# 2020-05-08 version 1.3

import re
import os
import sys

def merge(int96):
    return int96[0] + (int96[1] << 32) + (int96[2] << 64)

def res96(residual):
    mask = (1 << 32) - 1

    parts = [(residual >> (32 * i)) & mask for i in range(3)]
#    bits = [part if part >= 0 else ((1 << 32) - part) for part in parts]
    bits = parts

    return parts, bits[0] | bits[1] | bits[2]

def test96(line):
    '''Used for debugging GPU math'''

    parts = line.replace(",", " ").replace(")", "").replace("(", "").split(" ")
    n = list(map(int, reversed(parts[3:6])))
    nn = list(map(int, reversed(parts[7:10])))
    q = list(map(int, reversed(parts[11:14])))
    #print (parts[15])
    qi = int(parts[15])

    N = merge(n)
    NN = merge(nn)
    Q = merge(q)

    #print (line)
    #print ("N:", n, "\t", N)
    #print ("NN:", nn, "\t", NN)
    assert (NN-1) % N == 0, (NN % N)

    #print ("Q:", q, "\t", Q)
    div = Q // N
    #print ("Q/N:", (qi, div))
    assert qi in (div, div+1)

    res = list(map(int, reversed(parts[17:20])))
    #print (res, [bin(r) for r in res])

    #res_parts = [(a - b) if a >= b else (a - b + (1 << 32)) for a, b in zip(q, nn)]
    #print (res_parts, [bin(r) for r in res_parts])

    residual = (Q - NN)
    parts, res_comb = res96(residual)
    #print ("Res:", residual, "\t", parts, "\t", res_comb)
    #print ("\t", [bin(part) for part in res])
    assert res == parts


def validate96(P, F):
    res = pow(2, P, F)

    for test in [res - 1, F - res + 1]:
        parts, res_comb = res96(test)
        if parts[0] != 0:
        #    print (f"Bad res_low res={res}, test={test}")
            continue

        #print (parts)
        res_mid = parts[1]
        # Check how many trailing zeros
        ffs = bin(res_mid)[::-1].index("1") + 32
        #print (f"Validate({P}, {F}) = {ffs} {bin(test)}")
        return ffs

    assert False

def validate72(P, F):
    res = pow(2, P, F)

    # log2(F) - log(res)
    num_bits_f = len(bin(F)[2:])
    num_bits_r = len(bin(res)[2:])
    bits = num_bits_f - num_bits_r
    #print (f"Validate({P}, {F}) = {res} = {num_bits_f} - {num_bits_r} = {bits}")
    return bits


def validate(line):
    assert "proof(" in line, line
    match = re.match("^M([0-9]*) proof\(([0-9]*)\): ([0-9]*) difficulty.* ([a-z0-9_]*)]$", line)
    assert match, "Line didn't match: " + line
    m, f, b, kern = match.groups()
    m, f, b = map(int, (m, f, b))

    assert (f - 1) % m == 0, "F not for this exp: " + line

    if kern.startswith("75bit_mul32"):
        test = validate72(m, f)
    elif kern.startswith("barrett76_mul32"):
        test = validate96(m, f)
    else:
        assert False, "Unknown kernel please post to thread: " + line

    assert test == b, ("INVALID: {} does not match {}".format(test, line))
    return test

def process(lines):
    validated = 0
    for line in lines:
        if "proof(" in line:
            validate(line)
            validated += 1
    print (f"Validated {validated} proof results")

def selfcheck():
    test96("mod check 96bit(0): 810,2164837051,2578483143 | 2431,2199543858,3440482134 | 2717,1736090066,3440482134 | 3 | (285,3831513504,0), 3831513533 | 37 |")
    assert 37 == validate("M65551973 proof(14951160604042529376199): 37 difficulty [TF:73:74:mfaktc 0.21 barrett76_mul32_gs]")

    test96("mod check 96bit(0): 3,2474647416,1153253353 | 10,3128974952,3459760060 | 9,1404931144,3459760060 | 3 | (4294967294,2570923488,0), 4294967294 | 37 |")
    assert 37 == validate("M7320589 proof(65968761943132815337): 37 difficulty [TF:65:66:mfaktc 0.21 barrett76_mul32_gs]")
    assert 39 == validate("M7320589 proof(40375826991742863287): 39 difficulty [TF:65:66:mfaktc 0.21 barrett76_mul32_gs]")

    assert 30 == validate("M5500021 proof(316584655634160743): 30 difficulty [TF:58:60:mfaktc 0.21 75bit_mul32_gs]")
    assert 37 == validate("M5500021 proof(1138447911504519841): 37 difficulty [TF:58:60:mfaktc 0.21 75bit_mul32_gs]")

    assert 30 == validate("M6050039 proof(1011729923350931969): 30 difficulty [TF:58:60:mfaktc 0.21 75bit_mul32_gs]")
    assert 34 == validate("M6050039 proof(1283581832785931719): 34 difficulty [TF:60:62:mfaktc 0.21 75bit_mul32_gs]")

if __name__ == "__main__":
    print ("TF proof verifaction")

    selfcheck()

    if len(sys.argv) == 1:
        print ("Pass log line or results.txt file")
        sys.exit(1)

    # check if arg looks like a file
    if os.path.isfile(sys.argv[1]):
        with open(sys.argv[1]) as f:
            process(f.readlines())

    else:
        process(sys.argv[1:])
