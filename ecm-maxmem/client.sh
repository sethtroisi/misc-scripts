#!/bin/bash

sudo apt install -y gmp-ecm

function() run_and_log() {
    method=$1
    b1=$2
    maxmem=$3
    log_file=$4

    echo "time ecm -v $method -maxmem=$maxmem $b1 << \"prime_$i.txt\""
    time ecm -v $method -maxmem $maxmem $b1 < "prime_$i.txt" |& tee -a $log_file

    gsutil cp $log_file gs://cloudy-go/ecm-maxmem
}

for i in `seq 1 8`; do
    [[ -f "prime_$i.txt" ]] || continue
    for b1 in 100e6 1e9 10e9; do
        log_file="ecm_${i}_${b1}_maxmem_0.log"

        run_and_log "-pm1" "$b1" 16000 "$log_file"

        # Run with less memory
        usage=$(grep 'Peak memory usage:' $log_file | grep -o '[0-9]\+')
        for d in 2 3 5 10 20; do
            memory=$(( (usage + 10) / d ))
            log_file="ecm_${i}_${b1}_maxmem_${d}_${memory}MB.log"

            run_and_log "-pm1" "$b1" "$memory" "$log_file"
        done
    done
done
