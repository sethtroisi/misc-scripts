# Timing GMP vs OpenPFGW
Testing performed on a i7-2600K as well as a generic Xeon

## Commands

```shell
g++ gmp-test.cpp -lgmp -o gmp-test && ./gmp-test primorial_tests_short.txt
Compiled with GMP 6.1.99
503# + -641 => composite (0.000369 seconds)
503# + -647 => composite (0.000347 seconds)
503# + -659 => prime (0.002239 seconds)
503# + 599 => composite (0.000227 seconds)
503# + 601 => composite (0.000199 seconds)
503# + 631 => prime (0.001390 seconds)
1009# + -2749 => composite (0.001250 seconds)
1009# + -2753 => composite (0.001232 seconds)
1009# + -2767 => prime (0.007550 seconds)
1009# + 1259 => composite (0.001230 seconds)
1009# + 1283 => composite (0.001255 seconds)
1009# + 1289 => prime (0.007069 seconds)
3001# + -3673 => composite (0.032229 seconds)
3001# + -3677 => composite (0.031984 seconds)
3001# + -3709 => prime (0.150622 seconds)
3001# + 4663 => composite (0.032593 seconds)
3001# + 4673 => composite (0.031775 seconds)
3001# + 4691 => prime (0.143035 seconds)
10007# + -12263 => composite (0.666864 seconds)
10007# + -12329 => composite (0.797205 seconds)
10007# + -12343 => prime (2.930432 seconds)
10007# + 15901 => composite (0.666613 seconds)
10007# + 15913 => composite (0.674733 seconds)
10007# + 15919 => prime (3.049916 seconds)

real	0m12.042s
user	0m12.042s
sys	0m0.000s

```

```shell
$pfgw64 primorial_tests_short.txt -lprimorial_tests_short.pfgw.log
PFGW Version 4.0.1.64BIT.20191203.x86_Dev [GWNUM 29.8]
503# -641 is composite: RES64: [D52471BF5F4DADE0] (0.0015s+0.0001s)
503# -647 is composite: RES64: [E4A9DD931E0AAB3E] (0.0013s+0.0001s)
503# -659 is 3-PRP! (0.0013s+0.0001s)
503# +599 is composite: RES64: [28E9B7BC9318BC48] (0.0013s+0.0001s)
503# +601 is composite: RES64: [6CCB12306CFFF317] (0.0014s+0.0001s)
503# +631 is 3-PRP! (0.0013s+0.0001s)
1009# -2749 is composite: RES64: [856DCF1302B477F2] (0.0034s+0.0001s)
1009# -2753 is composite: RES64: [93EDEECF6F4C7B91] (0.0032s+0.0001s)
1009# -2767 is 3-PRP! (0.0032s+0.0001s)
1009# +1259 is composite: RES64: [EF953107D1674167] (0.0033s+0.0001s)
1009# +1283 is composite: RES64: [767F6CDDD78B79A6] (0.0032s+0.0001s)
1009# +1289 is 3-PRP! (0.0031s+0.0001s)
3001# -3673 is composite: RES64: [F496AF3273D36CC0] (0.0213s+0.0001s)
3001# -3677 is composite: RES64: [060B1F5EE10E2917] (0.0232s+0.0001s)
3001# -3709 is 3-PRP! (0.0209s+0.0001s)
3001# +4663 is composite: RES64: [A2D797374D7B3AEA] (0.0214s+0.0002s)
3001# +4673 is composite: RES64: [73C6E58B779317A1] (0.0212s+0.0001s)
3001# +4691 is 3-PRP! (0.0242s+0.0001s)
10007# -12263 is composite: RES64: [FCB20090A7194757] (0.2668s+0.0003s)
10007# -12329 is composite: RES64: [6E0E0394016C32B3] (0.2596s+0.0003s)
10007# -12343 is 3-PRP! (0.2564s+0.0003s)
10007# +15901 is composite: RES64: [6288A3D7E661B970] (0.2601s+0.0003s)
10007# +15913 is composite: RES64: [B37E9DE5F5728E60] (0.2554s+0.0003s)
10007# +15919 is 3-PRP! (0.2545s+0.0003s)

real	0m2.917s
user	0m2.959s
sys	0m0.025s
```

## Primorial Numbers (P# + 1)

| Primorial | Prime     | PFGW   | GMP 6.2  | Ratio |
|-----------|-----------|--------|----------|-------|
| 503       | composite | 0.0016 | 0.000214 | 0.13  |
| 503       | composite | 0.0013 | 0.000216 | 0.17  |
| 503       | prime     | 0.0013 | 0.001428 | 1.10  |
| 503       | composite | 0.0013 | 0.000188 | 0.14  |
| 503       | composite | 0.0013 | 0.000186 | 0.14  |
| 503       | prime     | 0.0013 | 0.001962 | 1.51  |
| 1009      | composite | 0.0036 | 0.00219  | 0.61  |
| 1009      | composite | 0.0041 | 0.00140  | 0.34  |
| 1009      | prime     | 0.0035 | 0.00682  | 1.95  |
| 1009      | composite | 0.0033 | 0.00128  | 0.39  |
| 1009      | composite | 0.0031 | 0.00123  | 0.40  |
| 1009      | prime     | 0.0034 | 0.00717  | 2.11  |
| 3001      | composite | 0.0226 | 0.0292   | 1.29  |
| 3001      | composite | 0.0215 | 0.0298   | 1.39  |
| 3001      | prime     | 0.0212 | 0.1334   | 6.29  |
| 3001      | composite | 0.0211 | 0.0331   | 1.57  |
| 3001      | composite | 0.0210 | 0.0310   | 1.47  |
| 3001      | prime     | 0.0212 | 0.1321   | 6.23  |
| 10007     | composite | 0.2561 | 0.649    | 2.53  |
| 10007     | composite | 0.2917 | 0.615    | 2.11  |
| 10007     | prime     | 0.2894 | 2.785    | 9.62  |
| 10007     | composite | 0.2578 | 0.621    | 2.41  |
| 10007     | composite | 0.2757 | 0.639    | 2.32  |
| 10007     | prime     | 0.2569 | 2.894    | 11.27 |
| 20011     | composite | 1.1491 | 3.532    | 3.07  |
| 20011     | composite | 1.1583 | 3.617    | 3.12  |
| 20011     | prime     | 1.1706 | 16.743   | 14.30 |
| 20011     | composite | 1.1309 | 3.517    | 3.11  |
| 20011     | composite | 1.1385 | 3.578    | 3.14  |
| 20011     | prime     | 1.1401 | 17.233   | 15.12 |

## Power Numbers (10^P + {3,7,9})

| Power | Prime     | PFGW   | GMP 6.2  | Ratio |
|-------|-----------|--------|----------|-------|
| 48    | composite | 0.0003 | 0.000038 | 0.13  |
| 116   | composite | 0.0001 | 0.000062 | 0.62  |
| 204   | composite | 0.0039 | 0.000194 | 0.05  |
| 424   | composite | 0.0037 | 0.001359 | 0.37  |
| 960   | composite | 0.0161 | 0.0126   | 0.78  |
| 1370  | composite | 0.0291 | 0.0328   | 1.13  |
| 2645  | composite | 0.1006 | 0.1760   | 1.75  |
| 4590  | composite | 0.2709 | 0.7088   | 2.62  |
| 5499  | composite | 0.4242 | 1.103    | 2.60  |
| 7639  | composite | 0.8399 | 2.563    | 3.05  |
| 10488 | composite | 1.87   | 5.472    | 2.92  |
| 14592 | composite | 3.46   | 11.88    | 3.43  |
| 17922 | composite | 5.60   | 19.95    | 3.56  |
| 21070 | composite | 8.68   | 29.88    | 3.44  |
| 27031 | composite | 14.24  | 53.75    | 3.77  |
| 31546 | composite | 17.74  | 78.33    | 4.41  |
| 43309 | composite | 36.63  | 162.0    | 4.42  |
| 50340 | composite | 46.67  | 234.2    | 5.02  |
| 60    | composite | 0.0001 | 0.000171 | 1.71  |
| 110   | prime     | 0.0001 | 0.000359 | 3.59  |
| 134   | prime     | 0.0001 | 0.000499 | 4.99  |
| 222   | prime     | 0.0017 | 0.001496 | 0.88  |
| 412   | prime     | 0.0033 | 0.006193 | 1.88  |
| 700   | prime     | 0.0076 | 0.0273   | 3.59  |
| 999   | prime     | 0.0128 | 0.0718   | 5.61  |
| 1383  | prime     | 0.0256 | 0.146    | 5.72  |
| 2607  | prime     | 0.0975 | 0.751    | 7.70  |
| 2730  | prime     | 0.1032 | 0.883    | 8.56  |
| 2841  | prime     | 0.1081 | 0.989    | 9.15  |
| 4562  | prime     | 0.2699 | 3.310    | 12.26 |
| 5076  | prime     | 0.3893 | 4.118    | 10.58 |
| 5543  | prime     | 0.4233 | 5.030    | 11.88 |
| 6344  | prime     | 0.4955 | 7.222    | 14.58 |
| 7668  | prime     | 0.8508 | 11.69    | 13.74 |
| 10470 | prime     | 1.867  | 24.81    | 13.29 |
| 11021 | prime     | 1.969  | 28.98    | 14.72 |
| 14600 | prime     | 3.478  | 57.02    | 16.39 |
| 15093 | prime     | 3.573  | 59.95    | 16.78 |
| 17753 | prime     | 5.583  | 90.79    | 16.26 |
| 21717 | prime     | 8.893  | 146.9    | 16.52 |
| 23636 | prime     | 10.61  | 184.9    | 17.42 |
| 26927 | prime     | 14.67  | 260.0    | 17.72 |
| 30221 | prime     | 16.04  | 349.4    | 21.78 |
| 31810 | prime     | 18.17  | 406.3    | 22.36 |
| 43186 | prime     | 38.61  | 844.5    | 21.87 |
| 48109 | prime     | 44.58  | 1119.7   | 25.11 |
| 50711 | prime     | 49.55  | 1160.1   | 23.41 |

