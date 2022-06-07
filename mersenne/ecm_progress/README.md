## Create ECM progress data for mersenne.ca

See https://www.mersenneforum.org/showpost.php?p=575452&postcount=595

Recompiled `ecm.c` with

```
-#define DIGITS_START 35
+#define DIGITS_START 20
```

Copied data from James in https://www.mersenneforum.org/showpost.php?p=575451&postcount=594 into `B1_B2.txt`

Then run

```
sort -n -k2 B1_B2.txt | awk '$6 ~ /^[0-9]+$/ && $6 > 100 { print $2, $4 }' | xargs -I{} sh -c 'echo {}; echo "2^31-1" | ~/Projects/gmp-ecm/ecm -v {} | grep -A2 "Expected number" | tail -n 2' | tee curves.txt
# or to run faster with parallel
awk '$6 ~ /^[0-9]+$/ && $6 > 100 { print $2, $4 }' B1_B2.txt | parallel 'echo {}; echo "2^31-1" | ecm -v {} | grep -A2 "Expected number" | tail -n 2' | tee curves.txt
```

join curves to B1/B2 with

```
cat curves.txt | grep -v '^20\s*25' | paste -sd ' \n' |  sort -n | tee curves_joined.txt
```

Convert to `curve_data` for `progress_v2` in `test2.py` with `process.py`

```
python process.py
```

then paste that into `test2.py`
