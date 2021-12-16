#!/usr/bin/env python3

# Copyright (c) 2021 Seth Troisi
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, version 3.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.

"""
Read Prime95 backup files and display status on them

An attempt to merge this into Prime95's c code was made but there was little
interest and the code was verbose and difficult to maintain
See
  * https://www.mersenneforum.org/showthread.php?p=540022#post540022
  * https://github.com/sethtroisi/prime95/pull/1


This was written looking at 29.8 source code but the save file header are
likely to be fairly consistent and can be upgraded easily.
The relevant files for details are
  * commonc.c
    read_header / write_header
    read_X

  * ecm.c
    pm1_save
    calc_exp
"""

"""
ostensible the file format is
    u32             magic number  (different for ll, p-1, prp, tf, ecm)
    u32             version number
    double          k in k*b^n+c
    u32             b in k*b^n+c
    u32             n in k*b^n+c
    s32             c in k*b^n+c
    double          pct complete
    char(11)        stage
    char(1)         pad
    u32             checksum of all following data
"""

"""
This has been tested with
  * v29.8 build 6
  * v30.3 build 6
  * v30.7 build 9
  * v30.8 build 4 (partial)
"""

"""
TODO
  * Understand what finished B1 (without B2) looks like for P-1
"""

import argparse
import json
import os
import re
import struct
import sys


##### MAGIC NUMBERS USED BY PRIME95  #####

 #### $ grep '#define.*MAGICNUM' *.c #####
FACTOR_MAGICNUM         = 0x1567234D
LL_MAGICNUM             = 0x2c7330a8
PRP_MAGICNUM            = 0x87f2a91b
SPOOL_FILE_MAGICNUM     = 0x73d392ac
ECM_MAGICNUM            = 0x1725bcd9
PM1_MAGICNUM            = 0x317a394b
 #### $ grep '#define.*VERSION' *.c #####
 # Removed {ECM,PRP,PM1}_VERSION
FACTOR_VERSION          = 1
LL_VERSION              = 1
SPOOL_FILE_VERSION      = 1

##### END MAGIC NUMBERS             #####


MAX_BACKUP_FILES   = 100
BACKUP_CWD         = "Status of files in '%s'."
BACKUP_CWD_ERROR   = "Unable to read working directory."
BACKUP_STATUS      = "Backup %-16s | %s."
BACKUP_NONE        = "No Backup files (*.bu) were found in %s."
BACKUP_PARSE_ERROR = "Unable to parse (%s)."

BACKUP_PTN = re.compile("[emp][0-9A-Z]{0,3}[0-9]{5,}(_[0-9]+){0,2}(.bu[0-9]*)?$")



def get_arg_parser():
    parser = argparse.ArgumentParser(description="Parse prime95 status/backup files")

    parser.add_argument('dir', type=str, default=".",
        help="Directory for with status/backup files")

    parser.add_argument('--json', type=str, default="",
        help="Save JSON data in this file")

    parser.add_argument('--skip-failed', action="store_true",
        help="Don't output anything for failed files")

    return parser

def scan_directory(dir_name):
    names = []
    if not os.path.isdir(dir_name):
        sys.exit(f"{dir_name!r} does not exist")

    for filename in os.listdir(dir_name):
        if BACKUP_PTN.match(filename):
            names.append(filename)

    return names


def _read_bytes(f, count):
    f_bytes = f.read(count)
    if len(f_bytes) != count:
        sys.stderr.write(f"Not enough bytes! Read {len(f_bytes)} of {count} from {f.name!r}")
        return b"\0"
    return f_bytes

def _read_struct(f, count, struct_format):
    f_bytes = _read_bytes(f, count)
    tmp = struct.unpack(struct_format, f_bytes)
    assert len(tmp) == 1, tmp

    # TODO checksumming
    return tmp[0]


def read_long(f):
    """Read a uint32_t from [f]ile"""
    return _read_struct(f, 4, "I")

def read_slong(f):
    """Read a int32_t from [f]ile"""
    return _read_struct(f, 4, "i")

def read_uint64(f):
    """Read a uint64_t from [f]ile"""
    return _read_struct(f, 8, "Q")

def read_double(f):
    """Read a double from [f]ile"""
    return _read_struct(f, 8, "d")

def read_int(f):
    """Read a slong then convert to int[32]"""
    return read_slong(f) & 0xFFFFFFFF

def read_array(f, length):
    b = _read_bytes(f, length)
    # TODO checksumming
    return b

def read_header(f, wu):
    # read_header normally validates k,b,n,c which we don't do

    wu["version"] = read_long(f)
    wu["k"] = read_double(f)
    wu["b"] = read_long(f)
    wu["n"] = read_long(f)
    wu["c"] = read_slong(f)
    wu["stage"] = list(read_array(f, 11))
    wu["pad"] = list(read_array(f, 1))
    wu["pct_complete"] = read_double(f)

    wu["checksum"] = read_long(f)

    wu["stage"][10] = 0
    wu["pct_complete"] = max(0, min(1, wu["pct_complete"]))

    return True


def parse_work_unit_from_file(filename):
    """
    Read a file and parse out the metadata

    # for PRP, LLR
    wu = {
        "work_type": "PRP" or "LLR"
        "version": 1

        "n": 123456

        "iterations": X,
        "errors": Y,
        "raw": {"E": Y, "C": X}
    }

    # for ECM / PRP wu are more complicated, most of these fields
    # should be present
    wu = {
        "work_type": "ECM" or "PM1"
        "version": 1

        "n": 123456

        "done": None, "B1", "B2", "DONE"

        "B1_progess": X
        "B1_bound": X

        "B2_progress": X
        "B2_bound": X

        "raw": {header: value, ...}}
    }
    """

    raw = {}
    wu = {"raw": raw}
    wu["work_type"] = None

    with open(filename, "rb") as f:
        raw["magicnumber"] = magic = read_long(f)

        # Common file header
        read_header(f, raw)
        version = raw["version"]
        wu["version"] = version
        wu["n"] = raw["n"]

        if magic == LL_MAGICNUM:
            if version != LL_VERSION:
                sys.exit(f"LL({magic}) with version {version}!")

            # See commonb.c readLLSaveFile (minus reading data)
            raw["E"] = read_long(f)  # error_count
            raw["C"] = read_long(f)  # counter (iterations)

            wu["work_type"] = "TEST"
            wu["iterations"] = raw["C"]
            wu["errors"] = raw["E"]

        elif magic == PRP_MAGICNUM:
            if version > 7:
                sys.stderr.write(f"PRP with version {version} {filename!r}\n")
                return None

            # See commonb.c readPRPSaveFile
            raw["E"] = read_long(f)  # error_count
            raw["C"] = read_long(f)  # counter (iterations)

            wu["work_type"] = "PRP"
            wu["iterations"] = raw["C"]
            wu["errors"] = raw["E"]

        elif magic == FACTOR_MAGICNUM:
            if version != FACTOR_MAGICNUM:
                sys.exit(f"FACTOR({magic}) with version {version}!")

            raw["work_type"] = "FACTOR"
            # TODO: implement FACTOR report

        elif magic == ECM_MAGICNUM:
            wu["work_type"] = "ECM"

            if version == 1:    # 25 - 30.4
                raw["state"] = read_long(f)
                raw["curve"] = read_long(f)    # 'curves_to_go' in older code
                raw["sigma"] = read_double(f)  # 'curve' in older code

                raw["B"] = read_uint64(f)
                raw["stage1_prime"] = read_uint64(f)
                raw["C_processed"] = read_uint64(f)

                wu["curve"] = raw["curve"]
                wu["B1_bound"] = raw["B"]
                wu["B1_progress"] = raw["stage1_prime"]
                wu["B2_progress"] = raw["C_processed"]
                # "Old save files did not store B2"

                if raw["state"] == 1:
                    wu["done"] = "B1"
                    # "Old ECM save file was in stage 2.  Restarting stage 2 from scratch."

            elif version > 1:
                raw["curve"] = read_long(f)
                raw["average_B2"] = read_uint64(f)
                state = read_int(f)
                raw["state"] = state

                raw["sigma"] = read_double(f)
                raw["B"] = read_uint64(f)
                raw["C"] = read_uint64(f)

                wu["curve"] = raw["curve"]
                wu["B1_bound"] = raw["B"]
                wu["B2_bound"] = raw["C"]

                #define ECM_STATE_STAGE1_INIT       0   /* Selecting sigma for curve */
                #define ECM_STATE_STAGE1        1   /* In middle of stage 1 */
                #define ECM_STATE_MIDSTAGE      2   /* Stage 2 initialization for the first time */
                #define ECM_STATE_STAGE2        3   /* In middle of stage 2 (processing a pairmap) */
                #define ECM_STATE_GCD           4   /* Stage 2 GCD */

                if state == 1:    # ECM_STATE_STAGE1
                    raw["stage1_prime"] = read_uint64(f)
                    wu["B1_progress"] = raw["stage1_prime"]
                elif state == 2:  # ECM_STATE_MIDSTAGE
                    wu["done"] = "B1"
                    wu["B1_progress"] = raw["B"]
                elif state == 3:  # ECM_STATE_STAGE2
                    # A bunch of unused (by this program values)
                    # read 6 ints (stage2_numvals, totrels, D, E, two_fft_stage2), pool_type)
                    # read 2 uint64 (first_relocatable, last_relocatable)
                    for i in range(6):
                        read_int(f)
                    for i in range(2):
                        read_uint64(f)

                    raw["B2_start"] = read_uint64(f)
                    raw["C_done"] = read_uint64(f)

                    wu["done"] = "B1"
                    wu["B1_progress"] = raw["B"]
                    wu["B2_progress"] = raw["C_done"]

                elif state == 4:  # ECM_STATE_CGD
                    wu["done"] = "B2"
                    wu["B1_progress"] = raw["B"]
                    wu["B2_progress"] = raw["C"]
            else:
                sys.stderr.write(f"ECM with version {version} {filename!r}\n")
                return None

        elif magic == PM1_MAGICNUM:
            wu["work_type"] = "PM1"
            wu["n"] = raw["n"]

            if 4 <= version <= 7:    # 30.4 to 30.7
                #define PM1_STATE_STAGE0	0	/* In stage 1, computing 3^exp using a precomputed mpz exp */
                #define PM1_STATE_STAGE1	1	/* In stage 1, processing larger primes */
                #define PM1_STATE_MIDSTAGE	2	/* Between stage 1 and stage 2 */
                #define PM1_STATE_STAGE2	3	/* In middle of stage 2 (processing a pairmap) */
                #define PM1_STATE_GCD		4	/* Stage 2 GCD */
                #define PM1_STATE_DONE		5	/* P-1 job complete */

                state = read_int(f)
                raw["state"] = state

                if state == 0:    # PM1_STATE_STAGE0
                    raw["interim_B"] = read_uint64(f)
                    raw["max_stage0_prime"] = read_long(f)
                    raw["stage0_bitnum"] = read_long(f)

                    if version >= 6:
                        # TODO verify this after 30.8 stable
                        # probably change a read_long to read_uint64()
                        assert raw["stage0_bitnum"] == 0, (
                                "Please contact Seth and provide this: " + repr(wu))
                        raw["stage0_bitnum"] = read_long(f)

                    wu["B1_bound"] = raw["interim_B"]
                    # Annoyingly this can move backwards after stage0 is done
                    wu["B1_progress"] = min(wu["B1_bound"], raw["stage0_bitnum"])

                elif state == 1:  # PM1_STATE_STAGE1
                    raw["B_done"] = read_uint64(f)
                    raw["interim_B"] = read_uint64(f)
                    raw["stage1_prime"] = read_uint64(f)

                    bound = raw["interim_B"]
                    # stage1_prime can be slightly larger than bound (e.g. the next prime)
                    wu["B1_progress"] = min(bound, max(raw["stage1_prime"], raw["B_done"]))
                    wu["B1_bound"] = bound
                    wu["done"] = "stage0"

                elif state == 2:  # PM1_STATE_MIDSTAGE
                    raw["B_done"] = read_uint64(f)
                    raw["C_done"] = read_uint64(f)

                    wu["done"] = "B1"
                    wu["B1_progress"] = wu["B1_bound"] = raw["B_done"]
                    wu["B2_progress"] = wu["B2_bound"] = raw["C_done"]

                elif state == 3:  # PM1_STATE_STAGE2
                    raw["B_done"] = read_uint64(f)
                    raw["C_done"] = read_uint64(f)
                    raw["interim_C"] = read_uint64(f)

                    wu["done"] = "B1"
                    wu["B1_progress"] = wu["B1_bound"] = raw["B_done"]
                    wu["B2_progress"] = raw["C_done"]
                    wu["B2_bound"] = raw["interim_C"]

                elif state == 4:  # PM1_STATE_GCD
                    raw["B_done"] = read_uint64(f)
                    raw["C_done"] = read_uint64(f)

                    print(f"\t{filename} is in PM1_STATE_GCD please finish it")

                    wu["done"] = "B2"
                    wu["B1_progress"] = wu["B1_bound"] = raw["B_done"]
                    wu["B2_progress"] = wu["B2_bound"] = raw["C_done"]

                elif state == 5:  # PM1_STATE_DONE
                    raw["B_done"] = read_uint64(f)
                    raw["C_done"] = read_uint64(f)

                    wu["done"] = "DONE"
                    wu["B1_progress"] = wu["B1_bound"] = raw["B_done"]
                    wu["B2_progress"] = wu["B2_bound"] = raw["C_done"]

            elif 1 <= version < 4:  # Version 25 through 30.3 save file
                state = read_long(f)
                raw["state"] = state

                raw["max_stage0_prime"] = 13333333 if version == 2 else read_long(f)

                # /* Read the first part of the save file, much will be ignored
                #    but must be read for backward compatibility */

                raw["B_done"]  = read_uint64(f)
                raw["B"]       = read_uint64(f)
                raw["C_done"]  = read_uint64(f)

                raw["C_start_unused"] = read_uint64(f)
                raw["C_unused"]       = read_uint64(f)  # C_done in source code, but I think this is C actually

                # "Processed" is number of bits in state 0, number of primes in state 1
                raw["processed"] = read_uint64(f)

                raw["D"]       = read_long(f)
                raw["E"]       = read_long(f)
                raw["rels_done"] = read_long(f)

                # /* Depending on the state, some of the values read above are not meaningful. */
                # /* In stage 0, only B and processed (bit number) are meaningful. */
                # /* In stage 1, only B_done, B, and processed (prime) are meaningful. */
                # /* In stage 2, only B_done is useful.  We cannot continue an old stage 2. */
                # /* When done, only B_done and C_done are meaningful. */
                if state == 3:     # PM1_STATE_STAGE0
                    b1 = raw["B"]
                    processed = raw["processed"]
                    max_prime = raw["max_stage0_prime"]
                    wu["B1_bound"] = b1

                    # Hard to map 'bit' backwards to a prime.
                    progress = min(processed, max_prime, b1 - 1)
                    wu["B1_progress"] = progress
                    if version == 1:
                        # 29.4 build 7 changed the calc_exp algorithm and invalidates this savefile
                        wu["B1_progress"] = 0

                    assert b1 > 0 and b1 >= progress, (
                            "Please contact Seth and provide this: " + repr(wu), b1, progress)

                elif state == 0:  # PM1_STATE_STAGE1
                    processed = raw["processed"]
                    b_done = raw["B_done"]

                    wu["done"] = "stage0"
                    wu["B1_progress"] = max(b_done, processed)
                    # Prime95 get's B1_bound from worktodo.txt

                    assert processed == 0 or b_done <= processed, (
                            "Please contact Seth and provide this: " + repr(wu))

                elif state == 1:  # PM1_STATE_STAGE2
                    # // Current stage 2 code is incompatible with older save file
                    # Doesn't really matter what the B2 bound/progress was (C_done)
                    wu["done"] = "B1"
                    wu["B1_progress"] = wu["B1_bound"] = raw["B_done"]

                elif state == 2:  # PM1_STATE_DONE
                    wu["done"] = "DONE"
                    wu["B1_progress"] = wu["B1_bound"] = raw["B_done"]
                    wu["B2_progress"] = wu["B2_bound"] = raw["C_done"]

            else:
                sys.stderr.write(f"P-1 with version {version} {filename!r}\n")
                return None

        else:
            sys.stderr.write(f"Unknown type magicnum = {magic}\n")
            return None

    return wu


def one_line_status(fn, wu, name_pad=15):
    buf = ""

    if True:
        k,b,n,c = [wu['raw'][k] for k in 'kbnc']
        buf = "{} ^ {}".format(b, n)
        if k != 1:
            buf = f"{k} * {buf}"
        if c > 0:
            buf += f" + {c}"
        else:
            buf += f" - {-c}"

        buf = buf.ljust(16) + " | "

    work = wu.get("work_type")
    pct = wu["raw"].get("pct_complete")

    if work == "ECM":
        # TODO print bounds?
        stage = {"B2": "GCD", "B1": "B2", None: "B1"}[wu.get("done")]
        buf += "ECM | Curve {} | Stage {} ({:.1%})".format(wu["curve"], stage, pct)
    elif work == "PM1":
        done = wu.get("done")
        if done is None:
            # Stage 1, processed = bit_number
            buf += "P-1 | Stage 1 ({:.1%}) B1 <= {:d}".format(
                    pct, wu["B1_progress"])
            assert pct < 1, wu
        elif done == "stage0":
            # Stage 1 after small primes
            if pct == 1:
                buf += "P-1 | B1={:d} complete".format(wu["B1_progress"])
            else:
                buf += "P-1 | Stage 1 ({:.1%}) B1 @ {:d}".format(
                    pct, wu["B1_progress"])
        elif done == "B1":
            # Stage 2
            buf += "P-1 | B1={}, B2={} Stage 2 ({:.1%})".format(
                    wu["B1_progress"], wu["B2_progress"], pct)
        elif done == "B2":
            # Stage 2
            buf += "P-1 | B1={}, B2={} in GCD ({:.1%})".format(
                    wu["B1_progress"], wu["B2_progress"], pct)
        elif done == "DONE":
            # P-1 done
            buf += "P-1 | B1={}".format(wu["B1_progress"])
            if wu["B2_progress"] > wu["B1_progress"]:
                buf += ", B2={}".format(wu["B2_progress"])
                if wu.get("E", 0) >= 2:
                    buf += ", E={}".format(wu["E"])
            buf += " complete"
        else:
            buf += "UNKNOWN STAGE={:d}".format(stage)

    elif work == "TEST":
        buf += "LL  | Iteration {}/{} [{:0.2%}]".format(wu["iterations"], wu["n"], pct)

    elif work == "PRP":
        buf += "PRP | Iteration {}/{} [{:0.2%}]".format(wu["iterations"], wu["n"], pct)

    elif work == "FACTOR":
        buf += "FACTOR | *unhandled*"

    else:
        buf += "UNKNOWN work={} | {}".format(work, wu)

    return fn.ljust(name_pad) + " | " + buf


def main(args):
    names = sorted(scan_directory(args.dir))

    parsed = {}
    failed = []
    for name in names:
        result = parse_work_unit_from_file(os.path.join(args.dir, name))
        if result is not None:
            parsed[name] = result
        else:
            failed.append(name)

    if failed and not args.skip_failed:
        print()
        print(f"FAILED ({len(failed)}):")
        for i, name in enumerate(failed):
            if i < 10 or (i < 100 and i % 10 == 0) or i % 100 == 0: print(f"\t{i} {name}")
        print()

    longest_name = min(20, max(map(len, parsed.keys()), default=0))
    print(f"Found {len(names)} backup files in {args.dir!r}")
    for name in sorted(parsed):
        print(one_line_status(name, parsed[name], longest_name))

    if args.json:
        print(f"Writing json data to {args.json!r}")

        # stage clutters json so pop it
        for wu in parsed.values():
            wu["raw"].pop("stage", None)
            wu["raw"].pop("pad", None)

        with open(args.json, "w") as f:
            json.dump(parsed, f, indent=4)



if __name__ == "__main__":
    parser = get_arg_parser()
    args = parser.parse_args()

    main(args)
