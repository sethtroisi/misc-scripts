import math
import csv


def factor_small(n):
    f = []
    while n % 2 == 0:
        f.append(2)
        n //= 2

    p = 3
    while p*p <= n:
        t, m = divmod(n, p)
        if m == 0:
            f.append(p)
            n = t
            continue
        p += 2

    if n != 1:
        f.append(n)

    return f


numbers = []
lookup = {}
with open("allcomp_og.txt") as f:
    reader = csv.DictReader(f)
    for row in reader:
        n = int(row["CompositeNumber"])
        lookup[n] = row
        numbers.append(n)

numbers.sort()
assert len(numbers) > 25000, len(numbers)


if True:
    import sympy.ntheory

    factors = [
            # From Joint 4e9, 2e15
            750312983689932225218814887475111451601,
            124129135622883824443968581830853501992780885741743617,
            80109470430049789177721628776680081527006382183194621913,


            # Stage 1 - 1e9
            7404060493192154517976641971746184393,
            7777800721604298444684388066053521389,
            432907204073232239655094010983227828959,
            984071418255729449467097147936590104643,
            72458227323361926380559281101094317478857,
            100041158794537080621316545277272786390523,
            324056793105934811802507610294993868559907,
            9422874245679805615653964935544972525496307319501,

            # Stage 2 - 2e14? 1e14?
            783984926776744932096181,
            1737289679429356608967591065359233,
            533207814245750437450966092477273317,
            2740742913581000832172011297905045089,
            6726045540270866626004863821670631059,
            128739369927123555536268836166387312613,
            627795208702324914458880001562791774793,
            1902068621034637535136848863748058513163,
            11993271422864609744246017402556166679877,
            22566885831388782728020298599939374665537,
            30358272040796046695304182622100286336771,
            173747322858833823449035200391059471151231,
            105559399884185903125590647759216386183633,
            3201761828353602683921687606701662392893519,
            6431134460830201783330609859249466216840691,
            15128501764661440151241120518617120431834631,
            254806665113499030259608186919038899558422081,
            3200897927486857171340190506371922210663972329,
            11899031169717085153622203077029727954826905253,
            42030665822347104252278349560778956058421034800651,

            # Stage 1 4e9
            #11993271422864609744246017402556166679877,

            # Stage 2 - 2e14
            149511525976835907680657617153619689331657,
            8336880910593090283874013013669704282193103,
    ]

    if len(factors) != len(set(factors)):
        assert False, ("DUPLICATES:", [f for f in factors if factors.count(f) > 1])

    found = []
    for f in factors:
        print (f"{len(str(f))} digits: {f}")
        for n, row in lookup.items():
            if n % f == 0:
                found.append(n)
                expr = row["Expression"]
                label = row['#"Label"']
                power = row["N"]
                print("\t", f, expr)
                #print(f"\thttps://stdkmd.net/nrr/{label[0]}/{label}.htm#N{power}")
                print(f"\thttps://stdkmd.net/nrr/c.cgi?q={label}_{power}")
                factors = sorted(sympy.ntheory.factorint(f-1).items())
                print("\t", " * ".join(f"{p}" if e == 1 else f"{p}^{e}" for p, e in factors))
                minB2 = max(p for p, e in factors)
                minB1 = max(p ** e for p, e in factors if p != minB2)
                print("\t Requires: B1 >= {:9,} B2 >= {:9,} || B1 >= 1e{}, B2 >= 1e{}".format(
                    minB1, minB2, len(str(minB1)), len(str(minB2))))
                print("\n")
                break
        else:
            print("No factor???")

    print("\n")
    for f in sorted(found):
        print(f)

    print("\n")
    starts = "|".join([str(f)[:10] for f in found])
    print(f"sed -E -i '/(^|\")({starts})/d'")


if False:
    # Breakpoints at 760 and 1016 bits
    END_GROUP = [760, 1016, 2048]

    GROUP_SIZE = 1792

    groups = []
    current = []
    for number in numbers:
        assert 1 < number < 2 ** 2048

        bit_size = number.bit_length()
        if bit_size >= END_GROUP[0] or len(current) == GROUP_SIZE:
            if current:
                print("new batch of {} {} to {} bits".format(
                    len(current),
                    current[0].bit_length(),
                    current[-1].bit_length()))
                groups.append(current)
                current = []

            while bit_size >= END_GROUP[0]:
                print()
                END_GROUP.pop(0)

        current.append(number)

    if current:
        print("new batch of {} {} to {} bits".format(
            len(current),
            current[0].bit_length(),
            current[-1].bit_length()))
        groups.append(current)
        current = []


    for i, group in enumerate(groups):
        max_bits = group[-1].bit_length()
        fn = f"pm1_stdkmd_batch_{i}_{max_bits}.txt"
        print(f"Writing {len(group)} rows to {fn!r}")
        with open(fn, "w") as f:
            for number in group:
                f.write(str(number) + "\n")
