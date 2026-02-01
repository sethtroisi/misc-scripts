#!/usr/bin/env bash

set -eux

if [ "$#" -ne 2 -a "$#" -ne 3 ]; then
    set +x
    echo "Usage: $0 \"RESUME_FN\" B1_LIMIT"
    exit 1
fi

RESUME_DIR="$(dirname $1)"
BATCH_FN="$(basename $1)"
LIM=$2
START=$3

if [ "$START" -ge "$LIM" ]; then
    echo "Bad LIM=$LIM or START=$START"
    exit 1
fi

cd "$RESUME_DIR"

test -f "$BATCH_FN"

RESUME_FN=$(echo "$BATCH_FN" | sed -E 's/^pm1_stdkmd_(batch_[0-9]+_[0-9]+).resume.txt$/\1/')
RESUME_FN=$(echo "$RESUME_FN" | sed -E 's/(batch[_0-9]+)\.[0-9]+e[7-9].txt/\1/')

[ "$RESUME_FN" != "$BATCH_FN" ] || (echo "ERROR: RESUME_FN = BATCH_FN" && exit 1)

LAST_FN="$BATCH_FN"
for B1 in $(seq $START $LIM); do
    NEW_FN="$RESUME_FN.${B1}e8.txt"

    ./ecm -v -gpu -pm1 -resume "$LAST_FN" -save "$NEW_FN" "${B1}e8" 0 | tee -a "$NEW_FN.log"
    [ $((${PIPESTATUS[0]} % 2)) -eq 0 ] # Check if ecm had error (low bit)

    LAST_FN="$NEW_FN"
    sleep 5;
done

# runpodctl stop pod $RUNPOD_POD_ID
