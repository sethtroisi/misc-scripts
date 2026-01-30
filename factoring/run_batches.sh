#!/usr/bin/env bash

set -eux

RESUME_DIR="$1"
BATCH_FN="$2"
LIM=$3

cd "$RESUME_DIR"

test -f "$BATCH_FN"

RESUME_FN=$(echo "$BATCH_FN" | sed -E 's/^pm1_stdkmd_(batch_[0-9]+_[0-9]+).resume.txt$/\1/')

[ "$RESUME_FN" != "$BATCH_FN" ]

LAST_FN="$BATCH_FN"
for B1 in $(seq 2 $LIM); do
    NEW_FN="$RESUME_FN.${B1}e9.txt"
    echo ../ecm -v -gpu -pm1 -resume "$LAST_FN" -save "$NEW_FN" "${B1}e9" 0
    LAST_FN="$NEW_FN"
    sleep 5;
done
