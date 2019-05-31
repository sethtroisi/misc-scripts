#!/bin/sh

echo "Hi"

echo "Instances:"
#gcloud compute instances list

echo
echo "Creating instances command:"
echo gcloud compute instances create \
    gmp-ecm-maxmem-test-{1..9} \
    --zone us-west1-b \
    --machine-type n1-highmem-4 \
    --preemptible \
    --scopes storage-rw

echo
echo "Cleanup:"
echo "gsutil rm gs://cloudy-go/ecm-maxmem/*"

echo
echo "SSH:"
echo
echo "screen -S maxmem -t 0 -d -m"

for i in `seq 1 8`; do
    prime=$(cat primes.txt | sed -n "${i}p")
    echo $prime > "prime_$i.txt"
    echo gcloud compute scp --zone "us-west1-b" client.sh prime_$i.txt "gmp-ecm-maxmem-test-"$i:~/
    echo "screen -S maxmem -X screen -t $i"
    echo "screen -S maxmem -p $i -X stuff $'gcloud compute ssh --zone "us-west1-b" "gmp-ecm-maxmem-test-"$i\\\r'"
    echo "screen -S maxmem -p $i -X stuff $'time ./client.sh\\\r'"
done

echo
echo "Stats:"
echo
echo "mkdir -p results"
echo "gsutil -m rsync -d gs://cloudy-go/ecm-maxmem/ results/"
echo 'grep --color=always "Using B1=\|Step . took\|Peak memory" $(find results/*.log | sort -t_ -n -k2.2,2.4 -k3 -k5) | awk -F: '\''{$1 = sprintf("%-65s", $1); print}'\'
