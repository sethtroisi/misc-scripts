#!/bin/bash

sudo apt install -y gmp-ecm

function run_and_log() {
    method=$1
    b1=$2
    maxmem=$3
    log=$4

    echo "Starting: $log"
    echo "time ecm -v $method -maxmem=$maxmem $b1" > "$log"
    time ecm -v $method -maxmem $maxmem $b1 < "prime_$i.txt" |& tee -a "$log"

    gsutil cp "$log" gs://cloudy-go/ecm-maxmem/
}

for i in `seq 1 8`; do
    [[ -f "prime_$i.txt" ]] || continue

    psize=$(($(cat "prime_$i.txt" | wc -c)-1))

    for b1 in 100e6 300e6 1e9 3e9; do
        log_prefix="ecm_p${psize}_${b1}_maxmem"
        log_file="${log_prefix}_0.log"

        run_and_log "-pm1" "$b1" 16000 "$log_file"

        # Run with less memory
        usage=$(grep 'Peak memory usage:' $log_file | grep -o '[0-9]\+')
        for d in 2 3 5 10 20; do
            memory=$(( (usage + 10) / d ))
            log_file_mem="${log_prefix}_${d}_${memory}MB.log"

            run_and_log "-pm1" "$b1" "$memory" "$log_file_mem"
        done
    done
done
