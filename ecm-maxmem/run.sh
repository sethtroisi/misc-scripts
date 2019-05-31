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
echo "SSH:"
echo
echo "screen -S maxmem -t 0 -d -m"

for i in `seq 1 8`; do
    echo "screen -S maxmem -X screen -t $i"
#    echo "screen -S maxmem -p $i -X stuff $'gcloud compute --project "cloudy-go" ssh --zone "us-west1-b" "gmp-ecm-maxmem-test-"$i\\\r'"
    prime=$(cat primes.txt | sed -n "${i}p")
    echo $prime > "prime_$i.txt"
    echo gcloud compute scp --zone "us-west1-b" client.sh prime_$i.txt "gmp-ecm-maxmem-test-"$i:~/
    echo "screen -S maxmem -p $i -X stuff $'gcloud compute ssh --zone "us-west1-b" "gmp-ecm-maxmem-test-"$i\\\r'"
done

echo
