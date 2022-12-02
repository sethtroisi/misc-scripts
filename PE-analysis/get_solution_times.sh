#!/usr/bin/env bash

: '
Get solution times from https://github.com/luckytoilet/projecteuler-solutions

1. Get final Solutions.md
2. Find first commit timestamp that "<NUM>. <SOULTION>" appears in file

$ git clone https://github.com/luckytoilet/projecteuler-solutions
$ cat Solutions.md
"801. 63812" (truncated)

$ git log -G "^801. 63812"
commit ac7a795bfca770ec7c87220ae53936c8d8ef711f
Date:   Wed Sep 7 11:30:02 2022 -0700
...

$ git log --format="format:%h %at | %ai" -G "^801. 63812"
ac7a795 1662575402 | 2022-09-07 11:30:02 -0700

Shell magic again
$ for p in {600..820}; do echo "$p $(git log --format="format:%h %at | %ai" -G "^$p. [0-9]" | wc -w)"; done | grep -v " 6$"
(spot check)
$ for p in {400..820}; do echo "$p $(git log --format="format:%h %at | %ai" -G "^$p. [0-9]")"; done
 '

for p in {400..820}; do echo "$p $(git log --format="format:%h %at | %ai" -G "^$p. [0-9]")"; done | tee solution_times.txt
