#!/usr/bin/env python3

import gmpy2
import glob
import math
import os
import re
import sqlite3

from collections import Counter, defaultdict
from tqdm import tqdm


BASE_FOLDER = os.path.expanduser("~/Downloads/GIMPS/")
#RESULTS_FILE = os.path.join(BASE_FOLDER, "results/megaresults.txt")
RESULTS_FILES = ["past_1g/results.txt", "results.txt"]

FACTOR_FILES = glob.glob('/media/five/Sojourner/GIMPS/mersenneca_known_factors_3G*.txt')

STATUS_FILE="many_factor_progress_3G.txt"
MANY_THRESHOLD = 6

MIN_EXP = 2 ** 20 + 100

# TJAOI has checked everything less than 2^68, we start at [68,69],
MIN_TF = 64 + 1
# A large number
MAX_TF = 100

MAX_TIME = 20 * 60
GHZ_DAYS_PER_DAY = 1400     # Based on 1080ti with mfaktc


REPROCESS = False

def process():
    factors = defaultdict(list)
    factor_counts = Counter()

    for factor_fn in FACTOR_FILES:
      with open(factor_fn) as factor_f:
        cur_p = None
        cur_factors = []
        for line in factor_f:
            p, f = map(int, line.strip().split(","))
            if p != cur_p:
                count = len(cur_factors)
                if count >= MANY_THRESHOLD:
                    factors[cur_p] = [2 * cur_p * k + 1 for k in cur_factors]
                    factor_counts[count] += 1
                    if factor_counts[count] <= 20:
                        # Z exponents x 6 factors
                        counts = ", ".join("{1}x{0}".format(*p) for p in factor_counts.most_common())
                        print ("{}: {:50} M{}".format(len(factors), counts, p))
                cur_p = p
                cur_factors = []

            cur_factors.append(f)
    return factors


def work_time(M, tf):
    '''Approx time to TF M from 2^(tf-1) to 2^tf'''
    return 2 ** tf / M / 1.0e8 / GHZ_DAYS_PER_DAY


def format_time(time):
    if time < 1000:
        return f"{time:.1f}s"
    return f"{time/3600:.2f}h"


def save(factors):
    with open(STATUS_FILE, "w") as status_f:
        for m, factors in sorted(factors.items()):
            status_f.write("{}:{}\n".format(m, ",".join(map(str, factors))))


def load():
    factors = defaultdict(list)
    with open(STATUS_FILE) as status_f:
        for line in status_f:
            e, e_factors = line.split(":")
            e = int(e)
            factors[e] = list(map(int, e_factors.split(",")))
    return factors


def verify(factors):
    print ("Checking existing factors")
    for m, m_factors in tqdm(factors.items()):
        for f in m_factors:
            assert pow(2, m, f) == 1, (m, f)

    print ("Verifying factors up to 2^34")
    for m, m_factors in tqdm(factors.items()):
        # for really small m we want to avoid this as it takes a long time
        # we also can't use mfaktc so skip them.
        if m <= MIN_EXP:
            continue

        assert len(m_factors) == len(set(m_factors)), (m, m_factors)
        kmax = 2 ** 34 // (2 * m) + 1
        for k in range(1, kmax + 1):
            p = 2 * m * k + 1
            if pow(2, m, p) == 1:
                # Maybe a composite factor.
                t = p
                for f in m_factors:
                    while t % p == 0:
                        t //= p
                assert t == 1, (m, k, p, m_factors)


def generate_worktodo_ordered(factors, tf_data):
    prime_count = Counter({m:len(fs) for m, fs in factors.items() if fs and m > MIN_EXP})

    # Divide cost when we find this many primes
    value = {
        8:6,
        9:30,
        10:60,
        11:300,
    }

    count_missing = 0
    work = []
    for e, count in prime_count.items():
        # Handles if we accidentally get extra numbers added by megaresult.txt
        if count < MANY_THRESHOLD:
            continue

        # check if non-consecutive set
        if tf_data[e]:
            tf = tf_data[e]
            missing = set(range(MIN_TF, max(tf))) - set(tf)
            for bit in missing:
                count_missing += 1
                print ("Missing TF range {} for {} | {}".format(bit, e, sorted(tf_data[e])))

        for bit in range(MIN_TF, MAX_TF+1):
            if bit in tf_data[e]:
                continue

            cost = int(work_time(e, bit))
            priority = cost / value.get(count, 1)
            if priority > MAX_TIME:
                break

            work.append((priority, cost, e, bit))

    if count_missing:
        print ("\t{} missing exponents".format(count_missing))

    print ("{} exponents, {} work items, {:.1f}s to {:.1f}s".format(
        len(prime_count), len(work), min(work)[0], max(work)[0]))

    with open("worktodo.txt", "w") as todo:
        sum_cost = 0
        for i, (priority, cost, e, bits) in enumerate(sorted(work), 1):
            sum_cost += cost
            if i < 20 or i * 25 % len(work) < 25:
                todo.write(f"#{i}th,  TF {e},{bits} ~ {cost} seconds\n")
                print ("\t{:>5}th entry, {:10},{} | ({} factors) ~{}, total {}"
                    .format(i, e, bits, prime_count[e],
                            format_time(cost), format_time(sum_cost)))
            todo.write(f"Factor={e},{bits-1},{bits}\n")


def generate_doublecheck(factors):
    count = 0
    num_factors = 0
    double_check = []
    for M, e_factors in factors.items():
        bits = sorted(len(bin(factor)) - 2 for factor in e_factors)
        bits = [b for b in bits if b > MIN_TF]
        bits = [b for b in bits if work_time(M, b) <= 120]

        num_factors += len(bits)
        for b in set(bits):
            time_guess = work_time(M, b)
            double_check.append((time_guess, f"Factor={M},{b-1},{b}\n"))
            count += 1


    with open("worktodo.txt.doublecheck", "w") as todo:
        for t, line in sorted(double_check):
            todo.write(line)

    print (f"Wrote {count} lines should find {num_factors} factors")


def add_manual_tf_data(tf_data):
    # Manual tf data
    manual = """
        1938317, 1,76 # Thanks Kriesel (~8000 GHz-days!)
        5977753, 1,74 # Thanks ATH & BloodERazor
        7508981, 1,77 # Thanks M. Miller & Kriesel
        9100919, 1,75 # Thanks ATH
        9325159, 1,75 # Thanks ATH
        27366961, 1,76 # Thanks ATH
        28035701, 1,76 # Thanks ATH
        31866377, 1,76 # Thanks Ducho_YYZ & ATH
        60593041, 1,77 # Thanks ATH
        458703437, 1,82 # Thanks Kriesel & Ramgeis
        566448359, 1,83 # Thanks ATH & M. Miller
        940572491, 1,81 # Thanks Kriesel
        566448359, 1,83 # Thanks Matthew M. and ATH
    """
    for row in manual.strip().split("\n"):
        exp, low, high = row.split(",")
        assert low.strip() == "1"
        high = int(high.split(" ")[0].strip())
        assert high in range(70, 90), high
        tf_data[int(exp)].update(set(range(1, high+1)))

    mersenne_ca_data = """
M7,508,981	11	495.94	80.00	0.0066046380%	263	267	278
M9,100,919	11	521.51	80.16	0.0057302472%	264	268	278
M3,930,621,659	11	591.06	82.34	0.0000150374%	288	292	287
M110,393,069	10	514.10	91.06	0.0004656972%	272	276	281
M566,448,359	10	450.67	64.23	0.0000795615%	279	283	283
M726,064,763	10	550.41	78.70	0.0000758077%	280	284	282
M1,708,426,297	10	503.69	72.86	0.0000294827%	284	288	282
M2,612,650,693	10	542.98	79.88	0.0000207828%	286	290	283
M2,621,856,541	10	516.40	78.96	0.0000196960%	286	290	283
M2,680,080,503	10	493.96	72.07	0.0000184309%	286	290	285
M3,273,488,573	10	508.38	78.04	0.0000155302%	287	291	284
M3,356,318,939	10	528.37	82.65	0.0000157424%	287	291	283
M27,366,961	9	414.30	78.45	0.0015138683%	266	270	276
M28,035,701	9	409.77	60.86	0.0014615905%	266	270	276
M31,866,377	9	429.36	61.16	0.0013473915%	267	271	277
M38,197,477	9	429.48	71.01	0.0011243575%	267	271	277
M60,593,041	9	417.80	65.27	0.0006895233%	269	273	278
M113,644,673	9	392.87	63.84	0.0003457043%	272	276	280
M160,062,671	9	427.79	68.74	0.0002672618%	274	278	279
M210,313,553	9	433.48	71.75	0.0002061135%	275	279	278
M308,616,443	9	470.93	71.08	0.0001525936%	276	280	280
M426,357,143	9	461.58	74.65	0.0001082612%	278	282	279
M448,785,217	9	472.23	72.88	0.0001052241%	278	282	279
M453,966,731	9	453.46	67.45	0.0000998878%	278	282	279
M458,703,437	9	426.03	67.50	0.0000928772%	278	282	277
M475,403,087	9	450.08	72.59	0.0000946739%	278	282	279
M619,272,859	9	481.68	74.42	0.0000777813%	280	284	279
M630,486,799	9	388.05	56.11	0.0000615472%	280	284	280
M639,698,243	9	422.96	71.43	0.0000661191%	280	284	280
M736,098,431	9	444.14	76.85	0.0000603370%	280	284	280
M736,647,071	9	463.95	72.47	0.0000629816%	280	284	280
M809,682,121	9	451.78	69.39	0.0000557968%	281	285	280
M889,672,331	9	485.21	75.03	0.0000545378%	281	285	280
M894,182,719	9	550.35	75.01	0.0000615482%	281	285	280
M940,572,491	9	430.10	67.95	0.0000457275%	281	285	281
M1,030,187,299	9	464.78	67.70	0.0000451163%	282	286	281
M1,240,557,103	9	476.69	76.07	0.0000384252%	283	287	281
M1,253,228,947	9	479.56	70.47	0.0000382661%	283	287	281
M1,277,494,103	9	464.43	69.76	0.0000363546%	283	287	281
M1,512,382,493	9	430.77	72.94	0.0000284830%	284	288	281
M1,540,324,403	9	471.31	70.20	0.0000305981%	284	288	281
M1,541,784,557	9	423.31	73.29	0.0000274556%	284	288	281
M1,689,848,561	9	435.79	77.88	0.0000257884%	284	288	281
M1,702,917,103	9	459.90	72.90	0.0000270068%	284	288	281
M1,797,253,079	9	447.72	71.66	0.0000249115%	284	288	281
M1,956,651,017	9	447.40	66.25	0.0000228656%	285	289	281
M2,444,875,883	9	472.38	79.57	0.0000193211%	286	290	282
M2,568,758,321	9	408.94	70.40	0.0000159197%	286	290	283
M2,578,897,001	9	462.26	77.17	0.0000179246%	286	290	282
M2,622,903,683	9	480.28	73.43	0.0000183110%	286	290	282
M2,698,453,873	9	425.99	73.03	0.0000157863%	286	290	282
M2,877,506,711	9	434.64	77.84	0.0000151046%	286	290	282
M3,250,525,121	9	444.80	75.89	0.0000136841%	287	291	283
M3,278,329,211	9	489.54	75.16	0.0000149327%	287	291	283
M4,057,374,691	9	416.46	60.43	0.0000102644%	288	292	284
M4,121,105,419	9	478.16	71.90	0.0000116027%	288	292	284
M4,152,954,881	9	506.06	79.91	0.0000121855%	288	292	284
M1,156,807	8	426.55	83.70	0.0368734801%	256	260	268
M1,313,363	8	324.70	69.42	0.0247228904%	256	260	269
M1,330,223	8	374.69	79.06	0.0281671399%	256	260	269
M1,557,623	8	408.97	74.76	0.0262560934%	257	261	267
M2,171,159	8	302.73	56.59	0.0139432487%	258	262	269
M2,329,081	8	308.41	74.59	0.0132416266%	258	262	269
M2,346,191	8	333.26	70.35	0.0142041116%	258	262	267
M2,761,567	8	386.07	78.00	0.0139800506%	259	263	267
M3,206,429	8	409.86	70.72	0.0127824325%	260	264	273
M3,379,501	8	388.21	93.07	0.0114870924%	260	264	273
M3,544,741	8	367.94	98.40	0.0103798674%	260	264	267
M3,658,283	8	357.04	75.43	0.0097598940%	260	264	270
M3,774,409	8	422.52	86.88	0.0111942034%	260	264	267
M5,049,959	8	294.99	52.51	0.0058415276%	261	265	271
M5,491,303	8	416.37	84.54	0.0075823653%	262	266	268
M5,837,719	8	346.32	83.43	0.0059323918%	262	266	268
M7,788,259	8	331.41	58.65	0.0042552815%	263	267	271
M8,490,563	8	380.06	80.91	0.0044762191%	264	268	271
M9,194,659	8	342.37	57.49	0.0037236192%	264	268	271
M9,971,147	8	332.23	62.45	0.0033318706%	264	268	272
M10,172,717	8	364.15	62.91	0.0035796576%	264	268	272
M10,397,537	8	403.43	80.89	0.0038800866%	264	268	269
M12,732,431	8	355.76	67.96	0.0027941369%	264	268	273
M18,261,863	8	351.44	62.00	0.0019244464%	265	269	272
M20,848,559	8	362.54	63.11	0.0017389136%	265	269	273
M20,882,179	8	366.71	62.60	0.0017560980%	265	269	273
M23,110,567	8	357.38	58.73	0.0015463827%	265	269	273
M24,165,809	8	372.77	63.77	0.0015425349%	266	270	272
M25,434,463	8	363.75	58.47	0.0014301363%	266	270	273
M28,070,071	8	331.72	57.23	0.0011817742%	266	270	273
M36,397,093	8	365.74	69.74	0.0010048681%	267	271	273
M38,043,283	8	380.00	66.03	0.0009988522%	267	271	275
M38,118,737	8	334.30	70.52	0.0008769887%	267	271	274
M39,183,121	8	290.40	47.81	0.0007411270%	268	272	274
M39,905,519	8	359.45	55.76	0.0009007536%	268	272	274
M41,087,467	8	392.50	66.02	0.0009552856%	268	272	274
M43,588,297	8	371.74	67.37	0.0008528325%	268	272	274
M46,520,977	8	384.96	69.86	0.0008275012%	268	272	274
M47,872,439	8	361.53	68.63	0.0007551887%	268	272	274
M50,570,297	8	356.98	59.02	0.0007059135%	269	273	274
M52,238,653	8	388.54	69.06	0.0007437863%	269	273	274
M67,696,859	8	343.49	65.44	0.0005073977%	270	274	274
M68,073,283	8	358.49	65.67	0.0005266169%	270	274	274
M70,044,503	8	373.19	66.41	0.0005327964%	270	274	274
M70,737,091	8	444.49	67.00	0.0006283670%	270	274	274
M74,520,007	8	409.59	70.02	0.0005496386%	270	274	274
M75,846,209	8	392.65	67.01	0.0005176915%	270	274	277
M78,343,891	8	425.39	71.34	0.0005429740%	271	275	275
M81,609,779	8	364.44	67.81	0.0004465668%	271	275	275
M85,270,477	8	390.81	69.58	0.0004583191%	271	275	275
M97,951,751	8	347.83	70.83	0.0003551000%	272	276	275
M100,046,857	8	363.06	73.94	0.0003628898%	272	276	280
M102,998,939	8	348.87	65.45	0.0003387125%	272	276	275
M106,843,769	8	403.23	69.66	0.0003774041%	272	276	275
M113,880,131	8	364.53	61.96	0.0003200965%	272	276	275
M120,853,517	8	378.19	69.46	0.0003129303%	273	277	275
M130,546,981	8	430.93	71.16	0.0003300920%	273	277	275
M141,263,609	8	351.82	67.91	0.0002490530%	273	277	275
M145,813,891	8	366.64	63.45	0.0002514447%	273	277	275
M154,669,811	8	347.28	73.17	0.0002245295%	274	278	276
M158,249,669	8	338.87	68.75	0.0002141388%	274	278	276
M159,267,131	8	415.66	71.14	0.0002609811%	274	278	276
M172,088,801	8	439.44	65.62	0.0002553580%	274	278	276
M177,504,629	8	335.73	53.85	0.0001891365%	274	278	276
M179,939,807	8	354.98	52.54	0.0001972797%	274	278	276
M180,820,751	8	412.43	68.17	0.0002280865%	274	278	276
M181,801,751	8	334.43	64.76	0.0001839527%	274	278	276
M184,038,061	8	389.16	71.84	0.0002114566%	274	278	276
M184,074,089	8	439.10	65.28	0.0002385469%	274	278	276
M195,927,911	8	389.62	60.04	0.0001988566%	274	278	275
M197,141,057	8	399.93	67.99	0.0002028631%	274	278	275
M202,528,981	8	369.48	63.81	0.0001824341%	275	279	278
M202,800,413	8	349.00	65.45	0.0001720917%	275	279	276
M203,113,067	8	435.57	63.68	0.0002144485%	275	279	276
M212,889,239	8	408.50	71.31	0.0001918837%	275	279	276
M224,357,201	8	370.37	62.67	0.0001650817%	275	279	276
M225,827,509	8	378.12	69.43	0.0001674369%	275	279	276
M226,315,151	8	374.80	64.45	0.0001656104%	275	279	276
M228,590,017	8	326.58	63.74	0.0001428688%	275	279	276
M231,618,197	8	319.96	64.26	0.0001381397%	275	279	276
M237,432,137	8	338.63	55.68	0.0001426217%	275	279	276
M241,588,889	8	379.87	67.53	0.0001572384%	275	279	276
M250,862,839	8	377.57	63.47	0.0001505095%	275	279	276
M252,674,011	8	321.83	48.63	0.0001273678%	275	279	276
M263,126,389	8	353.17	57.90	0.0001342190%	276	280	276
M265,581,077	8	342.28	60.19	0.0001288803%	276	280	276
M272,702,657	8	394.59	68.70	0.0001446956%	276	280	276
M273,313,889	8	387.28	68.93	0.0001416967%	276	280	276
M277,777,589	8	385.76	60.98	0.0001388726%	276	280	276
M277,949,501	8	346.95	65.26	0.0001248238%	276	280	276
M280,379,107	8	354.32	62.27	0.0001263735%	276	280	276
M284,376,839	8	355.74	57.53	0.0001250939%	276	280	276
M286,991,179	8	429.78	70.56	0.0001497539%	276	280	276
M297,850,321	8	391.22	69.01	0.0001313494%	276	280	276
M299,602,489	8	379.20	62.91	0.0001265672%	276	280	276
M303,821,657	8	368.17	67.36	0.0001211791%	276	280	277
M306,785,449	8	385.56	62.46	0.0001256785%	276	280	277
M310,993,811	8	406.89	73.71	0.0001308362%	276	280	277
M314,993,407	8	412.76	69.33	0.0001310390%	276	280	277
M320,024,891	8	416.19	69.75	0.0001300497%	276	280	277
M334,965,083	8	316.93	56.33	0.0000946171%	277	281	277
M340,011,179	8	381.94	72.85	0.0001123303%	277	281	277
M361,688,023	8	407.29	70.11	0.0001126085%	277	281	277
M363,432,539	8	347.56	62.91	0.0000956316%	277	281	277
M369,370,907	8	416.14	67.99	0.0001126630%	277	281	277
M371,827,327	8	412.91	72.73	0.0001110500%	277	281	277
M372,611,747	8	381.97	69.32	0.0001025110%	277	281	277
M380,058,167	8	350.73	57.77	0.0000922832%	277	281	277
M381,930,767	8	425.08	72.76	0.0001112989%	277	281	277
M382,066,457	8	323.39	55.64	0.0000846426%	277	281	277
M383,741,207	8	383.38	58.19	0.0000999064%	277	281	276
M395,962,993	8	425.07	67.55	0.0001073513%	277	281	276
M409,785,557	8	423.21	73.36	0.0001032769%	278	282	277
M412,867,883	8	385.47	66.01	0.0000933639%	278	282	277
M420,171,607	8	443.11	73.32	0.0001054587%	278	282	277
M420,755,459	8	420.95	72.83	0.0001000467%	278	282	277
M422,475,617	8	366.37	73.10	0.0000867203%	278	282	277
M423,007,391	8	374.81	66.25	0.0000886071%	278	282	277
M423,213,799	8	407.99	68.10	0.0000964020%	278	282	277
M432,187,571	8	361.98	72.30	0.0000837542%	278	282	277
M434,809,201	8	413.99	66.19	0.0000952113%	278	282	276
M440,057,161	8	438.67	66.74	0.0000996852%	278	282	277
M448,522,007	8	379.28	57.70	0.0000845630%	278	282	277
M448,751,297	8	402.46	69.02	0.0000896853%	278	282	277
M451,006,597	8	380.88	65.16	0.0000844516%	278	282	277
M452,551,637	8	378.59	59.45	0.0000836575%	278	282	277
M457,461,611	8	350.09	61.20	0.0000765282%	278	282	277
M458,315,773	8	395.82	71.41	0.0000863633%	278	282	277
M459,150,047	8	379.12	63.15	0.0000825702%	278	282	277
M461,972,339	8	380.79	65.81	0.0000824267%	278	282	277
M464,369,153	8	425.52	72.11	0.0000916343%	278	282	277
M468,468,551	8	313.70	60.12	0.0000669629%	278	282	277
M475,048,687	8	390.38	67.74	0.0000821765%	278	282	277
M478,060,897	8	375.37	59.23	0.0000785201%	278	282	277
M481,061,527	8	345.34	64.45	0.0000717865%	278	282	277
M487,740,151	8	358.13	70.93	0.0000734268%	278	282	277
M500,362,039	8	376.21	68.88	0.0000751879%	278	282	277
M503,640,083	8	337.84	51.68	0.0000670805%	278	282	277
M509,342,371	8	359.40	68.86	0.0000705625%	278	282	277
M509,465,833	8	374.69	58.08	0.0000735463%	278	282	277
M513,826,991	8	375.99	72.96	0.0000731744%	278	282	277
M517,152,673	8	411.90	66.34	0.0000796483%	279	283	277
M523,082,363	8	344.69	58.92	0.0000658956%	279	283	277
M533,500,991	8	399.20	68.43	0.0000748274%	279	283	277
M540,571,313	8	372.88	72.82	0.0000689792%	279	283	277
M559,776,103	8	395.00	68.27	0.0000705633%	279	283	277
M566,455,751	8	412.68	71.09	0.0000728528%	279	283	277
M568,034,227	8	461.09	68.03	0.0000811730%	279	283	277
M569,342,773	8	441.91	72.53	0.0000776170%	279	283	277
M573,474,563	8	378.75	54.92	0.0000660450%	279	283	277
M575,363,099	8	373.28	53.10	0.0000648769%	279	283	277
M586,704,773	8	409.23	70.88	0.0000697512%	279	283	277
M590,815,129	8	396.53	65.25	0.0000671159%	279	283	277
M594,136,619	8	370.22	74.50	0.0000623116%	279	283	277
M595,608,899	8	345.59	63.00	0.0000580234%	279	283	277
M602,840,713	8	365.90	58.93	0.0000606956%	279	283	278
M607,247,177	8	395.92	72.21	0.0000651999%	280	284	278
M610,533,241	8	380.57	69.89	0.0000623344%	280	284	278
M615,229,739	8	435.82	69.20	0.0000708389%	280	284	278
M618,256,843	8	389.94	59.34	0.0000630701%	280	284	278
M622,817,563	8	438.59	67.52	0.0000704200%	280	284	277
M623,712,301	8	382.45	69.75	0.0000613185%	280	284	278
M631,734,823	8	413.58	60.69	0.0000654670%	280	284	278
M651,771,359	8	371.38	71.06	0.0000569795%	280	284	278
M670,032,659	8	341.01	58.42	0.0000508941%	280	284	278
M671,941,763	8	353.18	51.20	0.0000525612%	280	284	278
M676,716,871	8	391.77	60.76	0.0000578935%	280	284	278
M678,140,429	8	363.82	60.72	0.0000536499%	280	284	278
M681,674,879	8	406.60	70.49	0.0000596471%	280	284	278
M699,860,699	8	400.91	74.98	0.0000572846%	280	284	278
M700,467,563	8	423.25	70.74	0.0000604240%	280	284	278
M705,767,677	8	389.94	69.99	0.0000552499%	280	284	278
M710,809,481	8	376.20	61.76	0.0000529257%	280	284	278
M711,082,637	8	477.79	72.52	0.0000671920%	280	284	278
M719,092,651	8	350.02	56.88	0.0000486748%	280	284	278
M730,612,811	8	422.61	68.10	0.0000578429%	280	284	278
M749,122,813	8	463.30	72.47	0.0000618462%	280	284	278
M778,105,151	8	368.93	67.18	0.0000474137%	281	285	278
M778,477,471	8	437.92	70.77	0.0000562528%	281	285	277
M778,778,191	8	421.04	71.34	0.0000540642%	281	285	278
M791,785,619	8	390.66	71.84	0.0000493392%	281	285	277
M791,868,503	8	371.00	66.95	0.0000468509%	281	285	278
M795,079,541	8	371.92	68.24	0.0000467772%	281	285	278
M798,612,761	8	357.79	56.48	0.0000448010%	281	285	278
M803,037,563	8	383.02	58.79	0.0000476960%	281	285	278
M831,946,651	8	405.10	62.61	0.0000486934%	281	285	278
M832,787,089	8	398.99	68.18	0.0000479108%	281	285	278
M836,556,181	8	413.65	68.21	0.0000494471%	281	285	278
M839,211,959	8	404.05	73.50	0.0000481468%	281	285	278
M841,166,219	8	381.37	71.01	0.0000453381%	281	285	275
M841,722,223	8	424.78	70.63	0.0000504656%	281	285	278
M841,881,899	8	402.94	70.73	0.0000478615%	281	285	278
M844,354,151	8	397.56	72.65	0.0000470845%	281	285	278
M873,694,637	8	383.92	73.14	0.0000439424%	281	285	278
M874,331,593	8	436.80	69.70	0.0000499580%	281	285	278
M875,741,341	8	398.94	65.62	0.0000455543%	281	285	278
M882,277,057	8	404.00	62.34	0.0000457905%	281	285	278
M884,515,217	8	350.77	58.57	0.0000396570%	281	285	278
M889,750,231	8	414.33	73.48	0.0000465675%	281	285	278
M908,233,259	8	400.20	72.13	0.0000440640%	281	285	278
M915,044,653	8	360.31	67.24	0.0000393760%	281	285	278
M932,721,121	8	351.84	60.84	0.0000377216%	281	285	278
M944,699,633	8	367.60	60.79	0.0000389120%	281	285	278
M952,345,063	8	415.82	74.62	0.0000436625%	281	285	278
M968,370,979	8	423.47	72.16	0.0000437302%	282	286	278
M996,522,251	8	373.31	67.77	0.0000374614%	282	286	278
M997,361,143	8	419.79	68.98	0.0000420903%	282	286	278
M1,010,224,739	8	409.17	66.13	0.0000405029%	282	286	279
M1,022,630,831	8	399.27	59.37	0.0000390432%	282	286	280
M1,035,151,891	8	373.68	75.61	0.0000360994%	282	286	279
M1,046,606,993	8	394.97	61.48	0.0000377378%	282	286	279
M1,072,395,223	8	412.06	67.35	0.0000384240%	282	286	277
M1,081,515,899	8	394.99	67.91	0.0000365219%	282	286	277
M1,090,101,119	8	376.23	68.37	0.0000345129%	282	286	279
M1,098,591,911	8	424.21	67.63	0.0000386139%	282	286	277
M1,104,012,757	8	410.19	64.52	0.0000371544%	282	286	279
M1,112,452,927	8	385.67	66.43	0.0000346684%	282	286	279
M1,125,916,439	8	340.77	62.72	0.0000302658%	282	286	279
M1,130,831,699	8	312.35	50.35	0.0000276215%	282	286	279
M1,135,449,163	8	429.00	67.55	0.0000377822%	282	286	277
M1,138,710,401	8	362.28	63.84	0.0000318146%	282	286	279
M1,165,039,181	8	399.96	63.00	0.0000343298%	282	286	277
M1,194,833,881	8	337.85	55.64	0.0000282761%	282	286	279
M1,198,059,451	8	404.93	65.71	0.0000337989%	282	286	279
M1,228,533,209	8	399.09	62.04	0.0000324852%	283	287	277
M1,245,292,709	8	349.37	55.56	0.0000280551%	283	287	279
M1,271,104,651	8	413.06	65.56	0.0000324964%	283	287	277
M1,294,129,237	8	376.59	60.38	0.0000291002%	283	287	279
M1,314,530,521	8	372.15	57.78	0.0000283104%	283	287	279
M1,320,554,437	8	405.69	66.36	0.0000307214%	283	287	276
M1,322,825,729	8	355.75	66.05	0.0000268928%	283	287	279
M1,329,692,167	8	381.05	59.30	0.0000286570%	283	287	279
M1,337,537,603	8	348.38	55.32	0.0000260461%	283	287	279
M1,361,685,599	8	334.90	51.71	0.0000245942%	283	287	279
M1,394,304,239	8	367.04	65.99	0.0000263240%	283	287	279
M1,403,425,711	8	394.87	63.64	0.0000281362%	283	287	279
M1,411,291,103	8	392.05	67.52	0.0000277797%	283	287	276
M1,426,177,853	8	357.40	67.10	0.0000250602%	283	287	279
M1,433,736,677	8	356.53	59.83	0.0000248674%	283	287	279
M1,454,134,811	8	320.40	45.99	0.0000220335%	283	287	279
M1,490,728,763	8	394.80	59.72	0.0000264836%	283	287	276
M1,511,087,321	8	367.58	68.05	0.0000243256%	284	288	279
M1,553,324,219	8	358.90	64.05	0.0000231053%	284	288	279
M1,577,212,517	8	357.99	67.34	0.0000226976%	284	288	279
M1,579,522,519	8	414.50	62.50	0.0000262422%	284	288	276
M1,590,737,723	8	364.92	63.91	0.0000229404%	284	288	279
M1,605,909,497	8	387.88	74.12	0.0000241533%	284	288	279
M1,611,629,839	8	431.57	65.05	0.0000267788%	284	288	276
M1,662,169,583	8	348.46	58.47	0.0000209643%	284	288	279
M1,708,815,373	8	418.93	67.68	0.0000245158%	284	288	279
M1,710,754,033	8	374.72	62.74	0.0000219038%	284	288	279
M1,732,479,779	8	446.84	67.84	0.0000257917%	284	288	276
M1,846,064,351	8	369.81	64.03	0.0000200326%	284	288	279
M1,860,014,927	8	372.83	65.30	0.0000200446%	284	288	279
M1,882,759,259	8	364.02	67.51	0.0000193342%	285	289	279
M1,895,310,959	8	377.95	61.74	0.0000199414%	285	289	279
M1,920,075,869	8	404.85	65.41	0.0000210853%	285	289	279
M1,935,123,007	8	386.54	59.35	0.0000199752%	285	289	279
M1,940,351,999	8	337.53	54.43	0.0000173955%	285	289	279
M1,953,768,749	8	385.31	60.43	0.0000197216%	285	289	279
M1,953,861,911	8	388.91	65.44	0.0000199045%	285	289	276
M1,956,140,617	8	391.12	66.14	0.0000199942%	285	289	279
M2,017,930,643	8	358.37	54.50	0.0000177593%	285	289	279
M2,036,715,743	8	354.26	66.23	0.0000173935%	285	289	279
M2,050,413,689	8	363.92	57.50	0.0000177485%	285	289	279
M2,050,651,151	8	376.87	61.66	0.0000183779%	285	289	279
M2,058,883,031	8	370.39	76.53	0.0000179900%	285	289	279
M2,072,099,591	8	353.20	57.07	0.0000170454%	285	289	279
M2,107,330,133	8	407.19	67.15	0.0000193225%	285	289	276
M2,114,715,269	8	370.59	58.62	0.0000175243%	285	289	279
M2,202,860,819	8	454.43	65.92	0.0000206290%	285	289	268
M2,240,227,289	8	406.52	61.58	0.0000181463%	285	289	276
M2,301,076,651	8	394.74	62.00	0.0000171546%	285	289	276
M2,321,945,123	8	326.17	49.78	0.0000140474%	285	289	274
M2,326,793,471	8	404.97	65.15	0.0000174047%	286	290	274
M2,353,828,859	8	349.68	63.19	0.0000148558%	286	290	274
M2,360,761,163	8	365.15	58.60	0.0000154673%	286	290	274
M2,466,579,431	8	355.84	63.46	0.0000144264%	286	290	274
M2,546,831,879	8	379.44	66.67	0.0000148984%	286	290	274
M2,549,304,937	8	401.67	59.14	0.0000157560%	286	290	274
M2,640,012,233	8	413.02	73.45	0.0000156447%	286	290	279
M2,672,005,751	8	390.85	73.47	0.0000146277%	286	290	279
M2,678,109,521	8	398.10	66.77	0.0000148648%	286	290	274
M2,693,913,437	8	391.81	65.30	0.0000145442%	286	290	274
M2,702,509,559	8	398.02	61.47	0.0000147279%	286	290	274
M2,753,170,087	8	391.03	60.77	0.0000142030%	286	290	274
M2,792,002,751	8	387.24	58.57	0.0000138695%	286	290	274
M2,794,936,723	8	359.84	58.60	0.0000128745%	286	290	274
M2,826,530,591	8	361.03	57.96	0.0000127730%	286	290	274
M2,827,868,339	8	384.85	72.82	0.0000136092%	286	290	274
M2,871,074,029	8	439.45	68.34	0.0000153060%	286	290	276
M2,915,101,603	8	409.27	67.50	0.0000140396%	287	291	276
M2,924,906,143	8	377.58	66.07	0.0000129091%	287	291	279
M2,928,695,813	8	428.20	69.32	0.0000146210%	287	291	283
M2,946,546,283	8	456.90	70.49	0.0000155062%	287	291	274
M2,950,621,391	8	441.03	65.81	0.0000149469%	287	291	276
M2,955,334,619	8	388.32	69.30	0.0000131395%	287	291	276
M2,955,999,251	8	385.01	60.43	0.0000130248%	287	291	274
M2,956,453,427	8	461.45	64.03	0.0000156082%	287	291	276
M2,957,834,963	8	384.99	64.91	0.0000130161%	287	291	274
M2,976,682,277	8	432.25	63.45	0.0000145213%	287	291	276
M3,073,154,351	8	380.41	56.75	0.0000123786%	287	291	274
M3,074,150,777	8	401.98	63.28	0.0000130761%	287	291	274
M3,146,823,257	8	363.01	73.12	0.0000115356%	287	291	274
M3,156,771,763	8	389.24	57.76	0.0000123303%	287	291	274
M3,175,219,679	8	402.12	65.87	0.0000126643%	287	291	274
M3,187,947,071	8	358.55	63.49	0.0000112469%	287	291	274
M3,245,423,009	8	396.36	71.27	0.0000122129%	287	291	274
M3,272,118,833	8	387.23	66.24	0.0000118341%	287	291	274
M3,274,234,031	8	403.61	74.65	0.0000123269%	287	291	274
M3,320,176,439	8	366.37	58.09	0.0000110346%	287	291	274
M3,332,438,953	8	396.44	63.60	0.0000118964%	287	291	276
M3,346,616,711	8	394.15	71.83	0.0000117777%	287	291	274
M3,369,333,371	8	372.03	60.02	0.0000110418%	287	291	274
M3,371,640,709	8	380.57	59.91	0.0000112875%	287	291	274
M3,383,353,331	8	398.31	74.48	0.0000117728%	287	291	274
M3,396,244,391	8	364.62	68.98	0.0000107358%	287	291	274
M3,428,023,883	8	379.34	64.53	0.0000110660%	287	291	274
M3,432,770,657	8	363.13	59.10	0.0000105783%	287	291	274
M3,453,838,403	8	350.23	54.13	0.0000101403%	287	291	274
M3,467,209,799	8	414.67	71.34	0.0000119598%	287	291	274
M3,482,470,903	8	388.45	67.64	0.0000111543%	287	291	274
M3,506,403,479	8	419.55	64.14	0.0000119651%	287	291	274
M3,529,560,899	8	369.34	64.29	0.0000104642%	287	291	274
M3,563,727,239	8	418.63	72.80	0.0000117470%	287	291	279
M3,613,076,231	8	369.59	71.73	0.0000102291%	288	292	274
M3,643,718,633	8	400.93	64.06	0.0000110032%	288	292	274
M3,765,940,169	8	414.53	70.11	0.0000110074%	288	292	281
M3,778,813,447	8	384.34	67.24	0.0000101709%	288	292	280
M3,850,688,869	8	408.47	72.47	0.0000106078%	288	292	279
M3,862,210,409	8	408.08	74.34	0.0000105660%	288	292	279
M3,863,918,893	8	387.02	66.35	0.0000100162%	288	292	280
M3,868,963,481	8	443.64	75.09	0.0000114666%	288	292	279
M3,884,348,183	8	383.01	69.20	0.0000098604%	288	292	280
M3,889,591,729	8	420.03	75.72	0.0000107989%	288	292	279
M3,937,403,039	8	402.05	63.34	0.0000102110%	288	292	282
M3,971,468,009	8	400.77	67.72	0.0000100913%	288	292	276
M4,002,960,967	8	390.01	60.52	0.0000097431%	288	292	280
    """
    for row in mersenne_ca_data.strip().split("\n"):
        data = row.split("\t")
        assert data[0][0] == "M" and data[7][0] == "2", data
        exp = int(data[0][1:].replace(",", ""))
        actual = int(data[7][1:])
        assert actual in range(66, 90), row

        tf_data[int(exp)].update(set(range(1, actual+1)))

def add_new_results(factors):
    tf_level = defaultdict(set)

    no_factor = 0
    known_prime = 0
    composite = set()
    new_factors = defaultdict(set)

    for fn in RESULTS_FILES:
      assert os.path.isfile(fn), fn
      with open(fn) as results_file:
        for result in results_file:
            match = re.search("no factor for M([0-9]*) from 2\^.. to 2\^(..)", result)
            if match:
                no_factor += 1
                M, upper_tf = map(int, match.groups())
                tf_level[M].add(upper_tf)

            match = re.search("M([0-9]*) has a factor: ([0-9]*).*TF:..:([0-9]{2})", result)
            if match:
                M, factor, upper_tf = map(int, match.groups())
                # Assumes that mfaktc was run with StopAfterFactor=0
                tf_level[M].add(upper_tf)
                if gmpy2.is_prime(factor):
                    if factor in factors[M]:
                        known_prime += 1
                    else:
                        if factor not in factors[M]:
                            new_factors[M].add(factor)
                else:
                    composite.add((M, factor))

    for M, new_primes in sorted(new_factors.items()):
        for f1 in new_primes:
            for f2 in factors[M]:
                assert f1 % f2 != 0 and f2 % f1 != 0, (M, f1, f2)

        count_f = len(factors[M])
        new_count = count_f + len(new_primes)

        for new_prime in new_primes:
            factors[M].append(new_prime)

        if new_count >= 7:
            tf_next = max(tf_level[M]) + 1
            cost_next = work_time(M, tf_next)
            for i, new_prime in enumerate(sorted(new_primes)):
                lead = "M{:<9}:".format(M) if i == 0 else " " * 11
                prime_len = len(str(new_prime))
                cost_time = "%.1s" % cost_next if cost_next < 1000 else "%.2h"
                print ("{} {:23}<{}>, {} => {} factors, cost({}): ~{}".format(
                    lead, new_prime, prime_len, count_f, new_count,
                    tf_next, format_time(cost_next)))

    print ()
    print ("{} no factor, {} composite factors found, {} prime factors found".format(
        no_factor, len(composite), len(new_factors)))
    print ()
    deltas = Counter([(len(factors[M]), len(added)) for M, added in new_factors.items()])
    for (new, added), count in deltas.most_common():
        if new == added: continue
        print (f"\tHad {new-added} factors + {added} = {new:2} x{count}")
    print ()

    return tf_level


if __name__ == "__main__":
    if REPROCESS:
        factors = process()
        verify(factors)
        save(factors)
    else:
        factors = load()


    # Used to verify the db & local results

    # Used if you've been running and have new local results
    tf_data = add_new_results(factors)
    add_manual_tf_data(tf_data)

    # Used if you want to generate worktodo in effort order.
    generate_worktodo_ordered(factors, tf_data)

    # Used to generate worktodo with lines that should all find factors.
    #generate_doublecheck(factors)
