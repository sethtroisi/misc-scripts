#!/usr/bin/env bash

: '
Get list of members by level from https://projecteuler.net/level=<LEVEL>
 '
# Have to do this logged in
# Copy PHPSESSID
if [ -z "$PHPSESSID" ]; then
    echo "Must set PHPSESSID"
    exit 1
fi

cookie_str="cookie: PHPSESSID=$PHPSESSID"

# Download a new version of
# https://projecteuler.net/eulerians

# Slowly download the list of members by level
for lvl in {25..31}; do
    level_fn="levels/level_${lvl}.html"
    level_url="https://projecteuler.net/level=${lvl}"
    if [ ! -f "$level_fn" ]; then
        echo "$level_url -> $level_fn"
        curl -H "$cookie_str" "$level_url" -o "$level_fn"
        sleep 1;
    fi
done
