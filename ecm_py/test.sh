#!/usr/bin/bash

set -eu


die() { echo "$*"; exit 1; }

printf "Starting some tests\n-----\n\n"

export ECM_PATH=${1:-./}
export LOGNAME="ecm_py_tests.log"

# Cleanup any resume from previous tests
rm -f "resume_job_2_499_t35_curves32-txt_finished.txt"
rm -f "$LOGNAME"

# Help should exit with non-zero status
python ecm.py && die "zero exit status for help"

printf "\n-----\n"
printf "Testing 'B1' 'B2' (~6 seconds)\n\n"

# XXX: minB2-maxB2 unsupported

echo "2^5897-1" | python ecm.py -pollfiles 2 -c 1 -sigma 1:10526 5000 800e3 || die "non-zero exit status with prime factor"
grep "Found prime factor of 28 digits: 2970583620693002864570235337" "$LOGNAME" || die "P28 factor not found"

echo "2^2791-1" | python ecm.py -pollfiles 2 -c 1 -sigma 1:1781 7e3 19000 || die "non-zero exit status with prime factor"
grep "Found prime factor of 23 digits: 5870360861285190747049" "$LOGNAME" || die "P23 factor not found"

printf "\n-----\n"
printf "Testing '-param' and '-sigma', should find P12 then P22 then P33 (~5 seconds)\n\n"

# combined param/sigma
echo "2^401-1" | python ecm.py -pollfiles 2 -c 1 -sigma 1:1127 150 || die "non-zero exit status with prime factor"
grep "Found prime factor of 12 digits: 856971565399" "$LOGNAME" || die "P12 factor not found"

echo "(2^401-1)/856971565399" | python ecm.py -pollfiles 2 -c 1 -param 2 -sigma 1047 50000 || die "non-zero exit status with composite factor"
grep "Found prime factor of 22 digits: 2136958965524920285681" "$LOGNAME" || die "P22 factor not found"

echo "(2^401-1)/856971565399" | python ecm.py -pollfiles 2 -c 1 -param 3 -sigma 10441 8e5 || die "non-zero exit status with composite factor"
grep "Found prime factor of 33 digits: 594538100848945223169882301931953" "$LOGNAME" || die "P33 factor not found"

printf "\n-----\n"
printf "Testing '-resume', should find 34 digit prime (~20 seconds)\n\n"

# Should find P34 at sigma=3890 (requires B1=638,527, B2=1,850,969)
# generated with: $ echo "(2^499-1)/20959" | ecm -v -gpu -gpucurves 32 -sigma 3:3870 -save test_data/2_499_t35_curves32.txt 7e5 0
python ecm.py -pollfiles 2 -threads 3 -resume test_data/2_499_t35_curves32.txt || echo "ecm.py -resume failed"
grep "Found prime factor of 34 digits: 1998447222711143545931606352264121" "$LOGNAME" || die "P34 factor not found"

# TODO: p95 resume with B1
# TODO: p95 resume with minB1-maxB1

printf "\n-----\n"
printf "Testing -c | -c 10000, -c 0 with and without factor (11 seconds)\n\n"

# Found factor after ~30 curves (should stop despite very large curve count)
echo "2^733-1" | timeout 10 python ecm.py -pollfiles 2 -threads 2 -c 100000 1000 3000 || die "didn't find factor(c=10000)!"
grep "Found prime factor of 12 digits: 694653525743" "$LOGNAME" || die "P12 factor not found (with many curves)"

# Should also work with -c 0
echo "2^733-1" | timeout 10 python ecm.py -pollfiles 2 -threads 2 -c 0 1000 3000 || die "didn't find factor (c=0)!"
grep "Found prime factor of 12 digits: 694653525743" "$LOGNAME" || die "P12 factor not found (with many curves)"

echo "2^127-1" | timeout 11 python ecm.py -pollfiles 1 -c 0 5000 500000 || STATUS=$?; echo
if [ $STATUS -ne 124 ]; then
  die "Found a factor???"
fi
# ecm.py messes with the cursor and isn't happy about timeout
printf "\n\n"

printf "\n-----\n"
printf "Testing ECM on multiple numbers (11 seconds)\n\n"

# All have a single 10-15 digit factors
rm "$LOGNAME"
printf "2^379-1\n2^421-1\n(2^443-1)/887\n(2^577-1)/3463\n" | python ecm.py -pollfiles 1 -c 0 5000
COUNT=`grep --count "Found prime factor" "$LOGNAME"`
echo "Found $COUNT/4 factors"
if [ $COUNT -ne 4 ]; then
  die "Didn't find factors for all 4 numbers"
fi

# TODO
# test accepting multiple numbers
# test errors for some parameters
# test find_one_factor_and_stop
#   with several factors in a row
#     $ echo "(2^653-1)/78557207" | python ecm.py -pollfiles 1 -threads 4 -c 1000 140000
#   with multiple numbers as input?

green=`tput setaf 2`
reset=`tput sgr0`
printf "\n${green}Tests passed!${reset}\n"

rm -f "resume_job_2_499_t35_curves32-txt_finished.txt"
rm -f "$LOGNAME"
