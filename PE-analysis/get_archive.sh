#!/usr/bin/env bash

: '
Get problem posting times from https://projecteuler.net/archives;page=<PAGE>
 '

for p in {1..14}; do
    archive_fn="archives/archives_$p.html"
    if [ ! -f "$archive_fn" ]; then
        echo "Downloading page $p -> \"$archive_fn\""
        curl "https://projecteuler.net/archives;page=$p" -o "$archive_fn"
        sleep 2
    fi
done
