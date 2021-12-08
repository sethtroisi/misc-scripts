# Status Report for Prime95 save/restore/backup files
---

This show you the status of Prime95 backup (.bu) files.

This can be very helpful if you want to extend previous P-1 runs and need to
know what bounds were used before or if you want to cleanup old saved files.

```
$ ./prime95_status.py <DIR> [--json test.json]

Found 12 backup files in 'v308'
e0014009         | ECM | Curve 1 | Stage 1 (12.1%)
e0014243         | ECM | Curve 4 | Stage 1 (0.7%)
e0150089         | ECM | Curve 1 | Stage 2 (18.5%)
m0002237         | P-1 | Stage 1 (0.0%) B1 <= 0
m0002267         | P-1 | Stage 1 (25.5%) B1 <= 0
m0013009         | P-1 | B1=100000 complete
m0013217         | P-1 | B1=100000, B2=3115132020 complete
m0150107         | P-1 | B1=100000, B2=58149630 complete
p0700001         | PRP | Iteration 22035/700001 [3.15%]
p46157_698207    | PRP | Iteration 59878/698207 [8.58%]
p46157_698207.bu | PRP | Iteration 15/698207 [0.00%]
p6_71299_7       | PRP | Iteration 75799/71299 [32.00%]

$ head -n 20 test.json
{
    "e0014009": {
        "work_type": "WORK_ECM",
        "magicnumber": 388349145,
        "version": 3,
        "k": 1.0,
        "b": 2,
        "n": 14009,
        "c": -1,
        "pct_complete": 0.1234855,
        "checksum": 425552135,
        "curve": 1,
        "average_B2": 0,
        "state": 1,
        "sigma": 2079734188444047.0,
        "B": 2000000,
        "C": 200000000,
        "stage_guess": 1,
        "stage1_prime": 246971
    },
```

### Test Data

Data from 29.8, 30.3, and 30.7 and 30.8 is included

```shell
$ unzip 'v*.zip'
$ for ver in v[0-9]*; do echo $ver; ./prime95_status.py $ver; done
```
