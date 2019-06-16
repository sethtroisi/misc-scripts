### Do additional TF on Mersenne numbers with many know factors
---


## Commands

```bash
FACTOR_FILE=gimpsfactors20181219.txt
time cat $FACTOR_FILE | cut -d, -f1 | uniq -c | awk '$1 >= 8' | tqdm | sort -n > 8_plus_factors
```

Download TF limits from James' Wonderful [mersenne.ca/export/](https://www.mersenne.ca/export/)

```bash
wget https://www.mersenne.ca/export/mersenneca_prime_numbers_0.sql.xz
unxz -v2 mersenneca_prime_numbers_0.sql.xz
```

I want a sqlite db not MySQL so I convert the MySQL dump to sqlite with this ugly regex

```bash
cat mersenneca_prime_numbers_0.sql | tqdm | sed \
    -e 's# auto_increment##'       \
    -e 's#[UN]*LOCK TABLES.*##'    \
    -e 's# \w*int([0-9]*) \(unsigned \)*# integer #' \
    -e 's#^\s*KEY .*##'            \
    -e 's#\(PRIMARY KEY .*\),#\1#' \
    -e 's#) ENGINE=.*#)#' | sqlite3 mersenne_tf_limits.db
```

Sadly TF_limits = 1 for all primes with known factors.
