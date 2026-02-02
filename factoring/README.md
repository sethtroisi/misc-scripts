# Near Repdigit Numbers

From [Studio Kamada's](https://stdkmd.net/nrr/) NRR project.

List of all composites: https://stdkmd.net/nrr/allcomp.txt

## Current Limits

In 2023 using a 1080ti I ran P-1 up to B1=1e9 (some numbers 4e9) and B2=1.34e16

In 2026 I'm resuming the P-1 from 2023 up to B1=1e10

## Misc commands

```shell

for fn in pm1_stdkmd_batch_{16..17}*; do printf "$fn\n"; ~/Projects/gmp-ecm/ecm_attempt2 -inp "$fn" -save "resume.${fn%.*}.pm1.1e10.txt" -x0 12 -cgbn -pm1 -v 1e10 0; done

ecm -resume resume.pm1_stdkmd_batch_14_866.pm1.1e9.txt 1e9 1e12
scp "four:~/Projects/ecm-db/client/log.batch_14.1e16.log" .
python ecm_runner.py -b ../../gmp-ecm/ecm --resume ~/Downloads/pm1/small_run/resume.pm1_stdkmd_batch_17_1015.pm1.1e10.txt --B1 10000000000 -B2 1e16 -t 5 --log_name log.batch_17.txt -- -maxmem 8400

# Original rebatch
python process_ecm_logs.py --rebatch backups/pm1/small_run_v0/resume.pm1_stdkmd_batch*.txt 20260126/manual_cpu.1e9.txt --allcomp allcomp_20260126.txt

# Rebatched after 4e9
clear && python process_ecm_logs.py -a allcomp_20260126.txt --rebatch 202305/pm1/small_run_v0/resume.pm1_stdkmd_batch*.txt 20260127/manual_cpu.1e9.txt runpod/resumes_20260130/batch_*9.txt runpod/1080ti/batch_00_1015.4e9.txt runpod/resumes_20260131/batch_*40e8.txt

# Used to setup a VM
./instance_setup.sh

# Used to run <RESUME_FN> in 1B increments up to <LIM>
./run_batches <RESUME_DIR> <RESUME_FN>

# Used to watch progress
while true; do echo "$(date +'%Y%m%d-%H%M%S') | $(cat batch_*.txt | wc -l) |  $(nvidia-smi | grep MiB | awk '{print $3, $4,   $5, $6, $7, $13}')"; sleep 30; done

# Used checking for found factors in early batches
python process_ecm_logs.py -a allcomp_20260126.txt -l runpod/resumes_20260130/batch_00_703.4e9.1e14.txt
```

## Misc Timing

Ryzen 3900X P-1 Stage 2 timing

`OMP_NUM_THREADS` | Digits | B2 | Time per P-1
24 threads (2/core) | 138 | 1.3e16 | 120-130 seconds
12 threads (1/core) | 138 | 1.3e16 | 120-130 seconds
6 threads           | 138 | 1.3e16 | 140-160 seconds
4 threads           | 138 | 1.3e16 | 194-210 seconds
3 threads           | 138 | 1.3e16 | 237-248 seconds

