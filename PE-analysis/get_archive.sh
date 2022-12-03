#!/usr/bin/env bash

: '
Get problem posting times from https://projecteuler.net/archives;page=<PAGE>
 '

if [ -z "$PHPSESSID" ]; then
    echo "Must set PHPSESSID"
    exit 1
fi

cookie_str="cookie: PHPSESSID=$PHPSESSID"

for p in {1..17}; do
    archive_fn="archives/archives_$p.html"
    if [ ! -f "$archive_fn" ]; then
        echo "Downloading page $p -> \"$archive_fn\""
        # I think I need the cache-control to get local tz info?
        curl -H "$cookie_str" -H 'cache-control: max-age=0' "https://projecteuler.net/archives;page=$p" -o "$archive_fn"
        sleep 2
    fi
done
