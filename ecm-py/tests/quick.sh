#!/bin/sh

set -u

ecm -c 10 -one 5e5 < M433
ret=$?
if [ $ret -ne 6 ]; then
  echo "Didn't find factor in M433"
fi

ecm -c 10 -one 1e5 < 11_265P
ret=$?
if [ $ret -ne 6 ]; then
  echo "Didn't find factor in 11_265P"
fi

set -e

rm -f M647.info
python3 ../ecm.py -c 10 -v -threads 4 -out M647.info 1e6 < M647

