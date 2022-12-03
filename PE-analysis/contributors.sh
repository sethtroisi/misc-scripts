#!/usr/bin/env bash

# Have to do this logged in
# Copy PHPSESSID
test -n "$PHPSESSID" || (echo "Must set PHPSESSID"; exit 1)

cookie_str="cookie: PHPSESSID=$PHPSESSID"

# Download a new version of
# https://projecteuler.net/eulerians

eulerians_fn="eulerians_$(date --iso)"
echo "$eulerians_fn"
test -f "$eulerians_fn" || curl -H "$cookie_str" "https://projecteuler.net/eulerians" -o "$eulerians_fn"

# Slowly download the list of fastest solvers
for p in {500..815}; do
    fastest_fn="fastest/fastest_${p}.html"
    fastest_url="https://projecteuler.net/fastest=${p}"
    if [ ! -f "$fastest_fn" ]; then
        echo "$fastest_url -> $fastest_fn"
        curl -H "$cookie_str" "$fastest_url" -o "$fastest_fn"
        sleep 1;
    fi
done

