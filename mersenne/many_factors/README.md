### Do additional TF on Mersenne numbers with many know factors
---


## Commands

```bash
FACTOR_FILE=gimpsfactors20181219.txt
time cat $FACTOR_FILE | cut -d, -f1 | uniq -c | awk '$1 >= 8' | tqdm | sort -n > 8_plus_factors
```



