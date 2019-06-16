set -eu

mkdir -p results
rm -f results/ecm_*


COUNT_PER=100

B1LIST=$(cat <<EOF
11e4 50e4 250e4 1e6 3e6 11e6 43e6 110e6 260e6 850e6 2900e6 7600e6 25e9
21905 24433 32918 64703 76620 155247 183849 245335 445657 643986 1305195
3071166 3784867 4572523 7982718 9267681 22025673 26345943 35158748 46919468
47862548 153319098 188949210 410593604 496041799 491130495 1067244762
1056677983 1328416470 1315263832 2858117139
EOF
)

for B1 in $B1LIST; do
  F="results/ecm_$B1"

  echo "B1: $B1"
  for n in $(cat test_numbers | grep '^[(1-9]' | shuf -n $COUNT_PER | sort); do
    echo "  n: $n"
    echo "$n" | timeout --foreground 0.1s  ecm -v $B1 >> "$F" || [[ $? == 124 ]]
  done

  count=$(grep -c 'Input' "$F")
  echo "  Numbers: $count"
  cat "$F" | grep -hi "Using B1=\|Df=" | sed 's#sigma=[0-9]:[0-9]\+#sigma=<S>#g' | sort | uniq -c | sort -n
  echo
done

for B1 in $B1LIST; do
  echo "B1: $B1"

  F="results/ecm_$B1"
  count=$(grep -c 'Input' "$F")
  echo "  Numbers: $count"
  cat "$F" | grep -hi "Using B1=\|Df=" | sed 's#sigma=[0-9]:[0-9]\+#sigma=<S>#g' | sort | uniq -c | sort -n
  echo
done

