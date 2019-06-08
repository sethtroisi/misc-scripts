#!/bin/bash

processes="$(($(cat /proc/cpuinfo  | grep proces | wc -l)/8 + 1))"
server="$1"

cd_dir="cd Math/cado-nfs"
run_cado="./cado-nfs-client.py --override t 8 --bindir=build/\$(hostname) --server=$server"

echo "screen -S cado-nfs-client -t cado -d -m"
echo "screen -S cado-nfs-client -p 0 -X stuff \"htop^M\""

for i in `seq 1 $processes`; do
    echo "screen -S cado-nfs-client -X screen -t cado-$i"
    echo "screen -S cado-nfs-client -p $i -X stuff \"$cd_dir; time $run_cado^M\""
done
