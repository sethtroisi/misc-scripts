#!/usr/bin/bash

set -u

die() { echo "$*"; exit 1; }

echo -e "Starting some tests\n-----\n"

export ECM_PATH=${1:-./}
export LOGNAME="ecm_py_tests.log"

# Cleanup any resume from previous tests
rm -f "resume_job_2_499_t35_curves32-txt_finished.txt"
rm -f "$LOGNAME"

# Help should exit with non-zero status
python ecm.py && die "zero exit status for help"

echo -e "\n-----"
echo -e "Testing '-param' and '-sigma', should find P12 then P22 then P33 (~20 seconds)\n"

echo "2^401-1" | python ecm.py -c 1 -param 2 -sigma 1012 11000 || die "non-zero exit status with prime factor"
grep "Found prime factor of 12 digits: 856971565399" "$LOGNAME" || die "P12 factor not found"

echo "(2^401-1)/856971565399" | python ecm.py -c 1 -param 2 -sigma 1047 50000 || die "non-zero exit status with composite factor"
grep "Found prime factor of 22 digits: 2136958965524920285681" "$LOGNAME" || die "P22 factor not found"

echo "(2^401-1)/856971565399" | python ecm.py -c 1 -param 3 -sigma 10441 1e6 || die "non-zero exit status with composite factor"
grep "Found prime factor of 33 digits: 594538100848945223169882301931953" "$LOGNAME" || die "P33 factor not found"

echo -e "\n-----"
echo -e "Testing '-resume', should find 34 digit prime (~20 seconds)\n"

# Should find P34 at sigma=3890
# generated with: $ echo "(2^499-1)/20959" | ecm -v -gpu -gpucurves 32 -sigma 3:3870 -save 2_499_t35_curves32.txt 1e6 0
python ecm.py -resume 2_499_t35_curves32.txt || echo "ecm.py -resume failed"
grep "Found prime factor of 34 digits: 1998447222711143545931606352264121" "$LOGNAME" || die "P34 factor not found"


green=`tput setaf 2`
reset=`tput sgr0`
echo -e "\n${green}Tests passed!${reset}"
