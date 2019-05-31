#!/bin/bash

sudo apt install -y gmp-ecm

function run_and_log() {
    method=$1
    b1=$2
    maxmem=$3
    log_file=$4

    echo "time ecm -v $method -maxmem=$maxmem $b1 > \"prime_$i.txt\""
    time ecm -v $method -maxmem $maxmem $b1 < "prime_$i.txt" |& tee -a $log_file

    gsutil cp $log_file gs://cloudy-go/ecm-maxmem
}

for i in `seq 1 8`; do
    [[ -f "prime_$i.txt" ]] || continue

    psize=$(($(cat "prime_$i.txt" | wc -c)-1))

    for b1 in 100e6 300e6; do #1e9 3e9; do
        log_file="ecm_p${psize}_${b1}_maxmem"

        run_and_log "-pm1" "$b1" 16000 "${log_file}_0.log"

        # Run with less memory
        usage=$(grep 'Peak memory usage:' $log_file | grep -o '[0-9]\+')
        for d in 2 3 5 10 20; do
            memory=$(( (usage + 10) / d ))

            run_and_log "-pm1" "$b1" "$memory" "${log_file}_${memory}MB.log"
        done
    done
done
