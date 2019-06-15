set -eux

mkdir -p results

for B1 in 11e4 50e4 250e4 1e6 3e6 11e6 43e6 110e6 260e6 850e6 2900e6 76e6 25e6; do
  echo shuf -n20 test_numbers | ecm -v $B1 | tee "ecm_$B1"
done
