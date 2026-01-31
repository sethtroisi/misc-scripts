apt update
apt install -y autoconf automake libtool
apt install -y screen htop vim
apt install -y libgmp-dev

cd /workspace

git clone https://github.com/sethtroisi/gmp-ecm.git
git clone https://github.com/NVlabs/CGBN.git

cd gmp-ecm
git checkout -b cgbn_pm1_attempt2 origin/cgbn_pm1_attempt2

autoreconf -i
# Have to modify acinclude.m4 for this.
# 61 for 1080, 89 for 4090
./configure --enable-gpu=89 --with-cgbn-include=../CGBN/include/cgbn --with-cuda=/usr/local/cuda --enable-openmp CC=gcc

make -j

# scp files
#scp -P<P> resumes_20260130/* "root@<MACHINE>:~/resumes_20260130/"

./run_batches.sh resumes_20260130/ pm1_stdkmd_batch_01_799.resume.txt 4
