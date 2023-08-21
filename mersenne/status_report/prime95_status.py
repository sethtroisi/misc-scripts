#!/usr/bin/env python3

# Copyright (c) 2021 Seth Troisi
# Copyright (c) 2023 Teal Dulcet
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

Teal Dulcet substantially extended the code.
  * Added support for Mlucus, GpuOwl, and CUDALucus.
  * Better work_unit class
  * Better argparsing
  * Better output (much more)

This was written looking at MPrime source code.
The relevant files for details are
  * commonc.c
    read_header / write_header
    read_X

  * ecm.c
    pm1_save
    calc_exp

See https://www.mersenneforum.org/showthread.php?t=25378 to understand version support.
"""

from __future__ import division, print_function, unicode_literals

import glob
import locale
import optparse
import os
import re
import struct
import sys
from datetime import datetime, timedelta

locale.setlocale(locale.LC_ALL, "")

# Prime95/MPrime constants

CERT_MAGICNUM = 0x8f729ab1
FACTOR_MAGICNUM = 0x1567234D
LL_MAGICNUM = 0x2c7330a8
PRP_MAGICNUM = 0x87f2a91b
ECM_MAGICNUM = 0x1725bcd9
PM1_MAGICNUM = 0x317a394b
PP1_MAGICNUM = 0x912a374a

CERT_VERSION = 1
FACTOR_VERSION = 1
LL_VERSION = 1
PRP_VERSION = 7
ECM_VERSION = 3
PM1_VERSION = 7
PP1_VERSION = 2

# Mlucas constants

TEST_TYPE_PRIMALITY = 1
TEST_TYPE_PRP = 2
TEST_TYPE_PM1 = 3

MODULUS_TYPE_MERSENNE = 1
MODULUS_TYPE_MERSMERS = 2
MODULUS_TYPE_FERMAT = 3
MODULUS_TYPE_GENFFTMUL = 4

# GpuOwl headers

# Exponent, iteration, 0, hash
# HEADER_v1 = "OWL LL 1 %u %u 0 %" SCNx64 "\n"
LL_v1_RE = re.compile(br"^OWL LL 1 (\d+) (\d+) 0 ([\da-f]+)$")

# # OWL 1 <exponent> <iteration> <width> <height> <sum> <nErrors>
# # HEADER = "OWL 1 %d %d %d %d %d %d\n"

# # OWL 2 <exponent> <iteration> <nErrors>
# # HEADER = "OWL 2 %d %d %d\n"

# # <exponent> <iteration> <nErrors> <check-step>
# # HEADER = "OWL 3 %d %d %d %d\n"
# # HEADER = "OWL 3 %u %u %d %u\n"

# # <exponent> <iteration> <nErrors> <check-step> <checksum>
# # HEADER = "OWL 4 %d %d %d %d %016llx\n"
# # HEADER = "OWL 4 %u %u %d %u %016llx\n"

# # HEADER_R = R"(OWL 5
# # Comment: %255[^
# # ]
# # Type: PRP
# # Exponent: %d
# # Iteration: %d
# # PRP-block-size: %d
# # Residue-64: 0x%016llx
# # Errors: %d
# # End-of-header:
# # \0)";
# # HEADER_R = R"(OWL 5
# # Comment: %255[^
# # ]
# # Type: PRP
# # Exponent: %u
# # Iteration: %u
# # PRP-block-size: %u
# # Residue-64: 0x%016llx
# # Errors: %d
# # End-of-header:
# # \0)";

# # Exponent, iteration, block-size, res64, nErrors.
# # HEADER = "OWL PRP 6 %u %u %u %016llx %d\n"
# # HEADER = "OWL PRP 6 %u %u %u %016llx %u\n"

# # E, k, B1, blockSize, res64
# # HEADER = "OWL PRPF 1 %u %u %u %u %016llx\n"

# # Exponent, iteration, B1, block-size, res64.
# # HEADER_v7 = "OWL PRP 7 %u %u %u %u %016llx\n"

# # Exponent, iteration, B1, block-size, res64, stage, nBitsBase
# # HEADER_v8 = "OWL PRP 8 %u %u %u %u %016llx %u %u\n"

# Exponent, iteration, block-size, res64
# HEADER_v9  = "OWL PRP 9 %u %u %u %016llx\n"
PRP_v9_RE = re.compile(br"^OWL PRP 9 (\d+) (\d+) (\d+) ([\da-f]{16})$")

# E, k, block-size, res64, nErrors
# PRP_v10 = "OWL PRP 10 %u %u %u %016" SCNx64 " %u\n"
PRP_v10_RE = re.compile(
    br"^OWL PRP 10 (\d+) (\d+) (\d+) ([\da-f]{16}) (\d+)$")

# Exponent, iteration, block-size, res64, nErrors
# HEADER_v11 = "OWL PRP 11 %u %u %u %016" SCNx64 " %u\n"
# Exponent, iteration, block-size, res64, nErrors, B1, nBits, start, nextK, crc
# PRP_v11 = "OWL PRP 11 %u %u %u %016" SCNx64 " %u %u %u %u %u %u\n"
PRP_v11_RE = re.compile(
    br"^OWL PRP 11 (\d+) (\d+) (\d+) ([\da-f]{16}) (\d+)(?: (\d+) (\d+) (\d+) (\d+) (\d+))?$")

# E, k, block-size, res64, nErrors, CRC
# PRP_v12 = "OWL PRP 12 %u %u %u %016" SCNx64 " %u %u\n"
PRP_v12_RE = re.compile(
    br"^OWL PRP 12 (\d+) (\d+) (\d+) ([\da-f]{16}) (\d+) (\d+)$")

# # Exponent, iteration, total-iterations, B1.
# # HEADER = "OWL PF 1 %u %u %u %u\n"

# # Exponent, iteration, B1.
# # HEADER = "OWL P-1 1 %u %u %u

# Exponent, B1, iteration, nBits
# HEADER_v1 = "OWL PM1 1 %u %u %u %u\n"
# HEADER_v1 = "OWL P1 1 %u %u %u %u\n"
P1_v1_RE = re.compile(br"^OWL PM?1 1 (\d+) (\d+) (\d+) (\d+)$")

# E, B1, k, nextK, CRC
# P1_v2 = "OWL P1 2 %u %u %u %u %u\n"
P1_v2_RE = re.compile(br"^OWL P1 2 (\d+) (\d+) (\d+) (\d+) (\d+)$")

# P1_v3 = "OWL P1 3 E=%u B1=%u k=%u block=%u\n"
# P1_v3 = "OWL P1 3 E=%u B1=%u k=%u\n"
P1_v3_RE = re.compile(
    br"^OWL P1 3 E=(\d+) B1=(\d+) k=(\d+)(?: block=(\d+))?$")

# E, B1, CRC
# P1Final_v1 = "OWL P1F 1 %u %u %u\n"
P1Final_v1_RE = re.compile(br"^OWL P1F 1 (\d+) (\d+) (\d+)$")

# Exponent, B1, B2, nWords, kDone
# HEADER_v1 = "OWL P2 1 %u %u %u %u 2880 %u\n"
P2_v1_RE = re.compile(br"^OWL P2 1 (\d+) (\d+) (\d+) (\d+) 2880 (\d+)$")

# E, B1, B2, CRC
# P2_v2 = "OWL P2 2 %u %u %u %u\n"
# E, B1, B2
# P2_v2 = "OWL P2 2 %u %u %u\n"
P2_v2_RE = re.compile(br"^OWL P2 2 (\d+) (\d+) (\d+)(?: (\d+))?$")

# E, B1, B2, D, nBuf, nextBlock
# P2_v3 = "OWL P2 3 %u %u %u %u %u %u\n"
P2_v3_RE = re.compile(br"^OWL P2 3 (\d+) (\d+) (\d+) (\d+) (\d+) (\d+)$")

# # Exponent, bitLo, classDone, classTotal.
# # HEADER = "OWL TF 1 %d %d %d %d\n"

# # Exponent, bitLo, bitHi, classDone, classTotal.
# # HEADER = "OWL TF 2 %d %d %d %d %d\n"
# # HEADER = "OWL TF 2 %u %d %d %d %d\n"
# # HEADER = "OWL TF 2 %u %u %u %u %u\n"
TF_v2_RE = re.compile(br"^OWL TF 2 (\d+) (\d+) (\d+) (\d+) (\d+)$")


PRIME95_RE = re.compile(
    r"^[cpefmn][0-9]+(?:_[0-9]+){0,2}(?:\.(?:[0-9]{3,}|(bu([0-9]*))))?$")
MLUCAS_RE = re.compile(
    r"^([pfq])([0-9]+)(?:\.(?:s([12])|([0-9]+)M|G))?$")
CUDALUCAS_RE = re.compile(r"^([ct])([0-9]+)$")
GPUOWL_RE = re.compile(os.path.join(
    r"(?:([0-9]+)", r"([0-9]+)(?:-([0-9]+)\.(?:prp|p1final|p2)|(?:-[0-9]+-([0-9]+))?\.p1|(-old)?\.(?:(?:ll|p[12])\.)?owl)|[0-9]+(-prev)?\.(?:tf\.)?owl)$"))

suffix_power_char = ["", "K", "M", "G", "T", "P", "E", "Z", "Y", "R", "Q"]

WORK_FACTOR = 0
WORK_TEST = 1
# WORK_DBLCHK = 2
# WORK_ADVANCEDTEST = 3
WORK_ECM = 4
WORK_PMINUS1 = 5
WORK_PPLUS1 = 6
# WORK_PFACTOR = 7
WORK_PRP = 10
WORK_CERT = 11

ECM_STATE_STAGE1_INIT = 0
ECM_STATE_STAGE1 = 1
ECM_STATE_MIDSTAGE = 2
ECM_STATE_STAGE2 = 3
ECM_STATE_GCD = 4

ECM = ["Stage 1 Init", "Stage 1", "Midstage", "Stage 2", "GCD"]

PM1_STATE_STAGE0 = 0
PM1_STATE_STAGE1 = 1
PM1_STATE_MIDSTAGE = 2
PM1_STATE_STAGE2 = 3
PM1_STATE_GCD = 4
PM1_STATE_DONE = 5

PM1 = ["Stage 0", "Stage 1", "Midstage", "Stage 2", "GCD", "Done"]

PP1_STATE_STAGE1 = 1
PP1_STATE_MIDSTAGE = 2
PP1_STATE_STAGE2 = 3
PP1_STATE_GCD = 4
PP1_STATE_DONE = 5

PP1 = ["", "Stage 1", "Midstage", "Stage 2", "GCD", "Done"]


class work_unit(object):

    __slots__ = (
        "work_type", "k", "b", "n", "c", "stage", "pct_complete", "fftlen",
        "nerr_roe", "nerr_gcheck", "error_count", "counter", "shift_count",
        "res64", "total_time", "factor_found", "bits", "apass", "test_bits",
        "prp_base", "residue_type", "L", "proof_power", "isProbablePrime",
        "res2048", "proof_power_mult", "proof_version", "curve", "state", "B",
        "stage1_prime", "C", "sigma", "D", "B2_start", "B_done", "interim_B",
        "C_done", "interim_C", "stage0_bitnum", "E", "numerator",
        "denominator")

    def __init__(self):
        # k*b^n+c
        self.k = 1.0
        self.b = 2
        self.n = 0
        self.c = -1
        self.fftlen = None
        self.nerr_roe = None
        self.nerr_gcheck = None
        self.error_count = None
        self.shift_count = 0
        self.res64 = None
        self.total_time = None

        # Factor
        self.factor_found = None
        self.test_bits = None

        # PRP
        self.prp_base = 3
        self.residue_type = None
        self.L = None
        self.proof_power = 0
        self.isProbablePrime = None
        self.proof_power_mult = 1
        self.proof_version = 1

        # ECM
        self.C = None
        self.B2_start = None

        # P-1
        self.B_done = None
        self.interim_B = None
        self.C_done = None
        self.interim_C = None
        self.stage0_bitnum = None
        self.E = None


def assignment_to_str(assignment):
    if not assignment.n:
        buf = "{0:.0f}".format(assignment.k + assignment.c)
    elif assignment.k != 1.0:
        buf = "{0.k:.0f}*{0.b}^{0.n}{0.c:+}".format(assignment)
    elif assignment.b == 2 and assignment.c == -1:
        buf = "M{0.n}".format(assignment)
    else:
        cnt = 0
        temp_n = assignment.n
        while not temp_n & 1:
            temp_n >>= 1
            cnt += 1
        if assignment.b == 2 and temp_n == 1 and assignment.c == 1:
            buf = "F{0}".format(cnt)
        else:
            buf = "{0.b}^{0.n}{0.c:+}".format(assignment)
    return buf


def output_table(rows):
    amax = max(len(row) for row in rows)
    for row in rows:
        row.extend("" for _ in range(amax - len(row)))
    lens = [max(len(v) for v in col) for col in zip(*rows)]
    aformat = "  ".join("{{:<{0}}}".format(alen) for alen in lens)
    print("\n".join(aformat.format(*row) for row in rows))


def outputunit(number, scale=False):
    scale_base = 1000 if scale else 1024

    power = 0
    while abs(number) >= scale_base:
        power += 1
        number /= scale_base

    anumber = abs(number)
    anumber += 0.0005 if anumber < 10 else 0.005 if anumber < 100 else 0.05 if anumber < 1000 else 0.5

    if number and anumber < 1000 and power > 0:
        strm = "{0:.{prec}g}".format(number, prec=sys.float_info.dig)

        length = 5 + (number < 0)
        if len(strm) > length:
            prec = 3 if anumber < 10 else 2 if anumber < 100 else 1
            strm = "{0:.{prec}f}".format(number, prec=prec)
    else:
        strm = "{0:.0f}".format(number)

    strm += suffix_power_char[power] if power < len(
        suffix_power_char) else "(error)"

    if not scale and power > 0:
        strm += "i"

    return strm


def from_bytes(abytes):
    return sum(b << i * 8 for i, b in enumerate(bytearray(abytes)))


def parse_work_unit_prime95(filename):
    wu = work_unit()

    try:
        with open(filename, "rb") as f:
            aformat = "<IIdIIi11sxdI"
            size = struct.calcsize(aformat)
            buffer = f.read(size)
            if len(buffer) != size:
                return None
            magicnum, version, wu.k, wu.b, wu.n, wu.c, stage, pct_complete, _sum = struct.unpack(
                aformat, buffer)

            wu.stage = stage.rstrip(b"\0").decode()
            wu.pct_complete = max(0, min(1, pct_complete))

            if magicnum == CERT_MAGICNUM:
                if version != CERT_VERSION:
                    print("Cert savefile with unsupported version = {0}".format(
                        version), file=sys.stderr)
                    return None

                wu.work_type = WORK_CERT

                aformat = "<III"
                size = struct.calcsize(aformat)
                buffer = f.read(size)
                wu.error_count, wu.counter, wu.shift_count = struct.unpack(
                    aformat, buffer)
            elif magicnum == FACTOR_MAGICNUM:
                if version != FACTOR_VERSION:
                    print("Factor with unsupported version = {0}".format(
                        version), file=sys.stderr)
                    return None

                wu.work_type = WORK_FACTOR

                aformat = "<IIIIIII"
                size = struct.calcsize(aformat)
                buffer = f.read(size)
                wu.factor_found, wu.bits, wu.apass, _fachsw, _facmsw, _endpthi, _endptlo = struct.unpack(
                    aformat, buffer)
            elif magicnum == LL_MAGICNUM:
                if version != LL_VERSION:
                    print("LL savefile with unsupported version = {0}".format(
                        version), file=sys.stderr)
                    return None

                wu.work_type = WORK_TEST

                aformat = "<III"
                size = struct.calcsize(aformat)
                buffer = f.read(size)
                wu.error_count, wu.counter, wu.shift_count = struct.unpack(
                    aformat, buffer)
            elif magicnum == PRP_MAGICNUM:
                if not 1 <= version <= PRP_VERSION:
                    print("PRP savefile with unsupported version = {0}".format(
                        version), file=sys.stderr)
                    return None

                wu.work_type = WORK_PRP

                aformat = "<II"
                size = struct.calcsize(aformat)
                buffer = f.read(size)
                wu.error_count, wu.counter = struct.unpack(aformat, buffer)

                if version >= 2:
                    aformat = "<III"
                    size = struct.calcsize(aformat)
                    buffer = f.read(size)
                    wu.prp_base, wu.shift_count, _two_power_opt = struct.unpack(
                        aformat, buffer)
                if version >= 3:
                    aformat = "<IIIIIIII"
                    size = struct.calcsize(aformat)
                    buffer = f.read(size)
                    wu.residue_type, _error_check_type, _state, _alt_shift_count, wu.L, _start_counter, _next_mul_counter, _end_counter = struct.unpack(
                        aformat, buffer)
                if version >= 5:
                    aformat = "<IIII512s16s"
                    size = struct.calcsize(aformat)
                    buffer = f.read(size)
                    wu.proof_power, _hashlen, wu.isProbablePrime, _have_res2048, wu.res2048, wu.res64 = struct.unpack(
                        aformat, buffer)
                    wu.res2048 = wu.res2048.rstrip(b"\0").decode()
                    wu.res64 = wu.res64.rstrip(b"\0").decode()
                if version >= 6:
                    aformat = "<II"
                    size = struct.calcsize(aformat)
                    buffer = f.read(size)
                    wu.proof_power_mult, _md5_residues = struct.unpack(
                        aformat, buffer)
                if version >= 7:
                    aformat = "<I"
                    size = struct.calcsize(aformat)
                    buffer = f.read(size)
                    wu.proof_version, = struct.unpack(aformat, buffer)
            elif magicnum == ECM_MAGICNUM:
                if not 1 <= version <= ECM_VERSION:
                    print("ECM savefile with unsupported version = {0}".format(
                        version), file=sys.stderr)
                    return None

                wu.work_type = WORK_ECM

                if version == 1:    # 25 - 30.6
                    aformat = "<IIdQQQ"
                    size = struct.calcsize(aformat)
                    buffer = f.read(size)
                    wu.state, wu.curve, wu.sigma, wu.B, wu.stage1_prime, _C_processed = struct.unpack(
                        aformat, buffer)
                else:
                    aformat = "<IQIdQQ"
                    size = struct.calcsize(aformat)
                    buffer = f.read(size)
                    wu.curve, _average_B2, wu.state, wu.sigma, wu.B, wu.C = struct.unpack(
                        aformat, buffer)

                    if wu.state == ECM_STATE_STAGE1:
                        aformat = "<Q"
                        size = struct.calcsize(aformat)
                        buffer = f.read(size)
                        wu.stage1_prime, = struct.unpack(aformat, buffer)
                    elif wu.state == ECM_STATE_MIDSTAGE:
                        pass
                    elif wu.state == ECM_STATE_STAGE2:
                        aformat = "<IIIIIIQQQQQQ"
                        size = struct.calcsize(aformat)
                        buffer = f.read(size)
                        _stage2_numvals, _totrels, wu.D, _E, _TWO_FFT_STAGE2, _pool_type, _first_relocatable, _last_relocatable, wu.B2_start, _C_done, _numDsections, _Dsection = struct.unpack(
                            aformat, buffer)
                    elif wu.state == ECM_STATE_GCD:
                        pass
            elif magicnum == PM1_MAGICNUM:
                if not 1 <= version <= PM1_VERSION:
                    print(
                        "P-1 savefile with unsupported version = {0}".format(version), file=sys.stderr)
                    return None

                wu.work_type = WORK_PMINUS1

                if version < 4:  # Version 25 through 30.3 save file
                    aformat = "<I"
                    size = struct.calcsize(aformat)
                    buffer = f.read(size)
                    state, = struct.unpack(aformat, buffer)

                    if version == 2:
                        _max_stage0_prime = 13333333
                    else:
                        aformat = "<I"
                        size = struct.calcsize(aformat)
                        buffer = f.read(size)
                        _max_stage0_prime, = struct.unpack(aformat, buffer)

                    aformat = "<QQQQQQIII"
                    size = struct.calcsize(aformat)
                    buffer = f.read(size)
                    wu.B_done, wu.interim_B, wu.C_done, _C_start, wu.interim_C, processed, wu.D, wu.E, _rels_done = struct.unpack(
                        aformat, buffer)

                    if state == 3:
                        wu.state = PM1_STATE_STAGE0
                        wu.stage0_bitnum = processed
                    elif state == 0:
                        wu.state = PM1_STATE_STAGE1
                        wu.stage1_prime = processed
                    elif state == 1:
                        wu.state = PM1_STATE_STAGE2
                    elif state == 2:
                        wu.state = PM1_STATE_DONE
                else:  # 4 <= version <= 7  # 30.4 to 30.7
                    aformat = "<I"
                    size = struct.calcsize(aformat)
                    buffer = f.read(size)
                    wu.state, = struct.unpack(aformat, buffer)

                    if wu.state == PM1_STATE_STAGE0:
                        aformat = "<Q" + ("II" if version <= 5 else "QQ")
                        size = struct.calcsize(aformat)
                        buffer = f.read(size)
                        wu.interim_B, _max_stage0_prime, wu.stage0_bitnum = struct.unpack(
                            aformat, buffer)
                    elif wu.state == PM1_STATE_STAGE1:
                        aformat = "<QQQ"
                        size = struct.calcsize(aformat)
                        buffer = f.read(size)
                        wu.B_done, wu.interim_B, wu.stage1_prime = struct.unpack(
                            aformat, buffer)
                    elif wu.state == PM1_STATE_MIDSTAGE:
                        aformat = "<QQ"
                        size = struct.calcsize(aformat)
                        buffer = f.read(size)
                        wu.B_done, wu.C_done = struct.unpack(aformat, buffer)
                    elif wu.state == PM1_STATE_STAGE2:
                        aformat = "<QQQIIIQQQQQ"
                        size = struct.calcsize(aformat)
                        buffer = f.read(size)
                        wu.B_done, wu.C_done, wu.interim_C, _stage2_type, wu.D, _numrels, wu.B2_start, _numDsections, _Dsection, _first_relocatable, _last_relocatable = struct.unpack(
                            aformat, buffer)
                    elif wu.state == PM1_STATE_GCD:
                        aformat = "<QQ"
                        size = struct.calcsize(aformat)
                        buffer = f.read(size)
                        wu.B_done, wu.C_done = struct.unpack(aformat, buffer)
                    elif wu.state == PM1_STATE_DONE:
                        aformat = "<QQ"
                        size = struct.calcsize(aformat)
                        buffer = f.read(size)
                        wu.B_done, wu.C_done = struct.unpack(aformat, buffer)
            elif magicnum == PP1_MAGICNUM:
                if not 1 <= version <= PP1_VERSION:
                    print(
                        "P+1 savefile with unsupported version = {0}".format(version), file=sys.stderr)
                    return None

                wu.work_type = WORK_PPLUS1

                aformat = "<III"
                size = struct.calcsize(aformat)
                buffer = f.read(size)
                wu.state, wu.numerator, wu.denominator = struct.unpack(
                    aformat, buffer)

                if wu.state == PP1_STATE_STAGE1:
                    aformat = "<QQQ"
                    size = struct.calcsize(aformat)
                    buffer = f.read(size)
                    wu.B_done, wu.interim_B, wu.stage1_prime = struct.unpack(
                        aformat, buffer)
                elif wu.state == PP1_STATE_MIDSTAGE:
                    aformat = "<QQ"
                    size = struct.calcsize(aformat)
                    buffer = f.read(size)
                    wu.B_done, wu.C_done = struct.unpack(aformat, buffer)
                elif wu.state == PP1_STATE_STAGE2:
                    aformat = "<QQQIIIQQQQQ"
                    size = struct.calcsize(aformat)
                    buffer = f.read(size)
                    wu.B_done, wu.C_done, wu.interim_C, _stage2_numvals, _totrels, _D, _first_relocatable, _last_relocatable, wu.B2_start, _numDsections, _Dsection = struct.unpack(
                        aformat, buffer)
                elif wu.state == PP1_STATE_GCD:
                    aformat = "<QQ"
                    size = struct.calcsize(aformat)
                    buffer = f.read(size)
                    wu.B_done, wu.C_done = struct.unpack(aformat, buffer)
                elif wu.state == PP1_STATE_DONE:
                    aformat = "<QQ"
                    size = struct.calcsize(aformat)
                    buffer = f.read(size)
                    wu.B_done, wu.C_done = struct.unpack(aformat, buffer)
            else:
                print("Error: savefile with unknown magicnum = {0:#x}".format(
                    magicnum), file=sys.stderr)
                return None
    except (IOError, OSError):
        print("Error reading {0!r} file.".format(filename), file=sys.stderr)
        return None

    return wu


def parse_work_unit_mlucas(filename, exponent, stage):
    wu = work_unit()

    try:
        with open(filename, "rb") as f:
            aformat = "<BB8s"
            size = struct.calcsize(aformat)
            buffer = f.read(size)
            if len(buffer) != size:
                return None
            t, m, tmp = struct.unpack(aformat, buffer)
            nsquares = from_bytes(tmp)

            p = 1 << exponent if m == MODULUS_TYPE_FERMAT else exponent

            nbytes = (p + 7) // 8 if m == MODULUS_TYPE_MERSENNE else (p >>
                                                                      3) + 1 if m == MODULUS_TYPE_FERMAT else 0
            f.seek(nbytes, 1)

            aformat = "<Q5s5s"
            size = struct.calcsize(aformat)
            buffer = f.read(size)
            res64, _res35m1, _res36m1 = struct.unpack(aformat, buffer)
            _res35m1 = from_bytes(_res35m1)
            _res36m1 = from_bytes(_res36m1)
            # print("{0:016X}".format(res64), "{0:010X}".format(res35m1), "{0:010X}".format(res36m1))

            aformat = "<3sQ"
            size = struct.calcsize(aformat)
            buffer = f.read(size)
            kblocks, res_shift = struct.unpack(aformat, buffer)
            kblocks = from_bytes(kblocks)

            if t == TEST_TYPE_PRP:
                aformat = "<I"
                size = struct.calcsize(aformat)
                buffer = f.read(size)
                prp_base, = struct.unpack(aformat, buffer)

                f.seek(nbytes, 1)

                aformat = "<Q5s5s"
                size = struct.calcsize(aformat)
                buffer = f.read(size)
                _i1, _i2, _i3 = struct.unpack(aformat, buffer)
                _i2 = from_bytes(_i2)
                _i3 = from_bytes(_i3)
                # print("{0:016X}".format(i1), "{0:010X}".format(i2), "{0:010X}".format(i3))

                aformat = "<Q"
                size = struct.calcsize(aformat)
                buffer = f.read(size)
                _gcheck_shift, = struct.unpack(aformat, buffer)

            aformat = "<II"
            size = struct.calcsize(aformat)
            buffer = f.read(size)
            nerr_roe = nerr_gcheck = None
            if len(buffer) == size:
                nerr_roe, nerr_gcheck = struct.unpack(aformat, buffer)

            if t == TEST_TYPE_PRIMALITY:
                if m == MODULUS_TYPE_MERSENNE:
                    wu.work_type = WORK_TEST

                    wu.counter = nsquares
                    wu.shift_count = res_shift

                    wu.stage = "LL"
                    wu.pct_complete = nsquares / (p - 2)
                elif m == MODULUS_TYPE_FERMAT:
                    wu.work_type = WORK_PRP  # No Pépin worktype

                    wu.counter = nsquares
                    wu.shift_count = res_shift

                    wu.stage = "Pépin"
                    wu.pct_complete = nsquares / (p - 1)
            elif t == TEST_TYPE_PRP:
                wu.work_type = WORK_PRP

                wu.counter = nsquares
                wu.shift_count = res_shift
                wu.prp_base = prp_base

                wu.stage = "PRP"
                wu.pct_complete = nsquares / p
            elif t == TEST_TYPE_PM1:
                wu.work_type = WORK_PMINUS1

                if stage == 1:
                    wu.state = PM1_STATE_STAGE1
                    wu.interim_B = nsquares
                elif stage == 2:
                    wu.state = PM1_STATE_STAGE2
                    wu.interim_C = from_bytes(tmp[:-1])
                    _psmall = from_bytes(tmp[-1:])
                wu.shift_count = res_shift

                wu.stage = "S{0}".format(stage)
                wu.pct_complete = None  # ?
            else:
                print("Error: savefile with unknown TEST_TYPE = {0}".format(
                    t), file=sys.stderr)
                return None

            if m == MODULUS_TYPE_MERSENNE:
                wu.n = p
            elif m == MODULUS_TYPE_FERMAT:
                wu.n = p
                wu.c = 1
            else:
                print("Error: savefile with unknown MODULUS_TYPE = {0}".format(
                    m), file=sys.stderr)
                return None

            wu.res64 = "{0:016X}".format(res64)
            wu.fftlen = kblocks << 10
            wu.nerr_roe = nerr_roe
            wu.nerr_gcheck = nerr_gcheck
    except (IOError, OSError):
        print("Error reading {0!r} file.".format(filename), file=sys.stderr)
        return None

    return wu


def parse_work_unit_cudalucas(filename, p):
    wu = work_unit()
    end = (p + 31) // 32

    try:
        with open(filename, "rb") as f:
            f.seek((end + 1) * 4)

            wu.work_type = WORK_TEST

            aformat = "=IIIIII"
            size = struct.calcsize(aformat)
            buffer = f.read(size)
            if len(buffer) != size:
                return None
            n, j, offset, total_time, _time_adj, _iter_adj = struct.unpack(
                aformat, buffer)
            total_time <<= 15
            _time_adj <<= 15

            wu.n = p
            wu.counter = j
            wu.shift_count = offset
            wu.fftlen = n
            wu.total_time = timedelta(microseconds=total_time)

            wu.stage = "LL"
            wu.pct_complete = j / (p - 2)
    except (IOError, OSError):
        print("Error reading {0!r} file.".format(filename), file=sys.stderr)
        return None

    return wu


def parse_work_unit_gpuowl(filename):
    wu = work_unit()

    try:
        with open(filename, "rb") as f:
            header = f.readline().rstrip()
    except (IOError, OSError):
        print("Error reading {0!r} file.".format(filename), file=sys.stderr)
        return None

    if not header.startswith(b"OWL "):
        return None

    if header.startswith(b"OWL LL "):
        ll_v1 = LL_v1_RE.match(header)

        wu.work_type = WORK_TEST

        if ll_v1:
            exponent, iteration, ahash = ll_v1.groups()
        else:
            print("LL savefile with unknown version: {0}".format(
                header), file=sys.stderr)
            return None

        wu.n = int(exponent)
        wu.counter = int(iteration)
        wu.shift_count = 0
        wu.res64 = ahash.decode().upper()

        wu.stage = "LL"
        wu.pct_complete = wu.counter / (wu.n - 2)
    elif header.startswith(b"OWL PRP "):
        prp_v9 = PRP_v9_RE.match(header)
        prp_v10 = PRP_v10_RE.match(header)
        prp_v11 = PRP_v11_RE.match(header)
        prp_v12 = PRP_v12_RE.match(header)

        wu.work_type = WORK_PRP
        nErrors = None

        if prp_v9:
            exponent, iteration, block_size, res64 = prp_v9.groups()
        elif prp_v10:
            exponent, iteration, block_size, res64, nErrors = prp_v10.groups()
        elif prp_v11:
            exponent, iteration, block_size, res64, nErrors, _B1, _nBits, _start, _nextK, _crc = prp_v11.groups()
        elif prp_v12:
            exponent, iteration, block_size, res64, nErrors, _crc = prp_v12.groups()
        else:
            print("PRP savefile with unknown version: {0}".format(
                header), file=sys.stderr)
            return None

        wu.n = int(exponent)
        wu.counter = int(iteration)
        wu.shift_count = 0
        wu.L = int(block_size)
        wu.res64 = res64.decode().upper()
        if nErrors is not None:
            wu.nerr_gcheck = int(nErrors)

        wu.stage = "PRP"
        wu.pct_complete = wu.counter / wu.n
    elif header.startswith((b"OWL PM1 ", b"OWL P1 ", b"OWL P1F ")):
        p1_v1 = P1_v1_RE.match(header)
        p1_v2 = P1_v2_RE.match(header)
        p1_v3 = P1_v3_RE.match(header)
        p1final_v1 = P1Final_v1_RE.match(header)

        wu.work_type = WORK_PMINUS1
        wu.pct_complete = None  # ?

        if p1_v1:
            exponent, B1, iteration, nBits = p1_v1.groups()
            wu.pct_complete = int(iteration) / int(nBits)
        elif p1_v2:
            exponent, B1, iteration, _nextK, _crc = p1_v2.groups()
        elif p1_v3:
            exponent, B1, iteration, _block = p1_v3.groups()
        elif p1final_v1:
            exponent, B1, _crc = p1final_v1.groups()
            wu.pct_complete = 1.0
        else:
            print(
                "P-1 stage 1 savefile with unknown version: {0}".format(header), file=sys.stderr)
            return None

        wu.state = PM1_STATE_STAGE1
        wu.n = int(exponent)
        wu.B_done = int(B1)

        wu.stage = "S1"
    elif header.startswith(b"OWL P2 "):
        p2_v1 = P2_v1_RE.match(header)
        p2_v2 = P2_v2_RE.match(header)
        p2_v3 = P2_v3_RE.match(header)

        wu.work_type = WORK_PMINUS1
        wu.pct_complete = None  # ?

        if p2_v1:
            exponent, B1, B2, _nWords, kDone = p2_v1.groups()
            wu.pct_complete = int(kDone) / 2880
        elif p2_v2:
            exponent, B1, B2, _crc = p2_v2.groups()
        elif p2_v3:
            exponent, B1, B2, D, _nBuf, nextBlock = p2_v3.groups()
            wu.D = int(D)
            if int(nextBlock) == (1 << 32) - 1:
                wu.pct_complete = 1.0
        else:
            print(
                "P-1 stage 2 savefile with unknown version: {0}".format(header), file=sys.stderr)
            return None

        wu.state = PM1_STATE_STAGE2
        wu.n = int(exponent)
        wu.B_done = int(B1)
        wu.C_done = int(B2)

        wu.stage = "S2"
    elif header.startswith(b"OWL TF "):
        tf_v2 = TF_v2_RE.match(header)

        wu.work_type = WORK_FACTOR

        if tf_v2:
            exponent, bitLo, bitHi, classDone, classTotal = tf_v2.groups()
        else:
            print("TF savefile with unknown version: {0}".format(
                header), file=sys.stderr)
            return None

        wu.n = int(exponent)
        wu.bits = int(bitLo)
        wu.test_bits = int(bitHi)

        wu.stage = "TF{0}".format(wu.bits)
        wu.pct_complete = int(classDone) / int(classTotal)
    else:
        print(
            "Error: Unknown save/checkpoint file header: {0}".format(header), file=sys.stderr)
        return None

    return wu


def one_line_status(file, num, index, wu):
    stage = None
    if wu.work_type == WORK_CERT:
        work_type_str = "Certify"
        temp = ["Iter: {0:n}".format(wu.counter)]
        if wu.shift_count is not None:
            temp.append("Shift: {0:n}".format(wu.shift_count))
    elif wu.work_type == WORK_FACTOR:
        work_type_str = "Factor"
        temp = ["Bits: {0}{1}".format(wu.bits, " to {0}".format(
            wu.test_bits) if wu.test_bits else "")]
        if wu.factor_found:
            temp.append("Factor found!")
    elif wu.work_type == WORK_TEST:
        # work_type_str = "Lucas-Lehmer"
        work_type_str = "LL"
        # temp = ["Iter: {0:n} / {1:n}".format(wu.counter, wu.n - 2)]
        temp = ["Iter: {0:n}".format(wu.counter)]
        if wu.shift_count is not None:
            temp.append("Shift: {0:n}".format(wu.shift_count))
        if wu.fftlen:
            temp.append("FFT: {0}".format(outputunit(wu.fftlen)))
        if wu.res64:
            temp.append("Residue: {0}".format(wu.res64))
        if wu.total_time:
            temp.append("Time: {0}".format(wu.total_time))
    elif wu.work_type == WORK_PRP:
        work_type_str = "PRP"
        # temp = ["Iter: {0:n} / {1:n}".format(wu.counter, wu.n)]
        temp = ["Iter: {0:n}".format(wu.counter)]
        if wu.shift_count is not None:
            temp.append("Shift: {0:n}".format(wu.shift_count))
        if wu.fftlen:
            temp.append("FFT: {0}".format(outputunit(wu.fftlen)))
        if wu.L:
            temp.append("Block Size: {0:n}".format(wu.L))
        if wu.prp_base != 3:
            temp.append("Base: {0}".format(wu.prp_base))
        if wu.residue_type and wu.residue_type != 1:
            temp.append("Residue Type: {0}".format(wu.residue_type))
        if wu.res64:
            temp.append("Residue: {0}".format(wu.res64))
        if wu.proof_power:
            temp.append("Proof Power: {0}{1}".format(wu.proof_power, "x{0}".format(
                wu.proof_power_mult) if wu.proof_power_mult > 1 else ""))
    elif wu.work_type == WORK_ECM:
        work_type_str = "ECM"
        stage = ECM[wu.state]
        temp = ["Curve #{0:n}, s={1:.0f}".format(
            wu.curve, wu.sigma), "B1={0}".format(wu.B)]
        if wu.C:
            temp.append("B2={0}".format(wu.C))
        if wu.B2_start:
            temp.append("B2_start={0}".format(wu.B2_start))
    elif wu.work_type == WORK_PMINUS1:
        work_type_str = "P-1"
        stage = PM1[wu.state]
        temp = ["E={0}".format(wu.E) if wu.E is not None and wu.E >= 2 else ""]
        B1 = wu.interim_B or wu.B_done or wu.stage0_bitnum
        if B1:
            temp.append("B1={0}".format(B1))
        B2 = wu.interim_C or wu.C_done
        # if B2 and B2 > B1:
        if B2:
            temp.append("B2={0}".format(B2))
        if wu.B2_start:
            temp.append("B2_start={0}".format(wu.B2_start))
        if wu.shift_count:
            temp.append("Shift: {0:n}".format(wu.shift_count))
        if wu.fftlen:
            temp.append("FFT: {0}".format(outputunit(wu.fftlen)))
        if wu.res64:
            temp.append("Residue: {0}".format(wu.res64))
    elif wu.work_type == WORK_PPLUS1:
        work_type_str = "P+1"
        stage = PP1[wu.state]
        B1 = wu.interim_B or wu.B_done
        temp = [
            "Start={0}/{1}".format(wu.numerator, wu.denominator), "B1={0}".format(B1)]
        B2 = wu.interim_C or wu.C_done
        # if B2 and B2 > B1:
        if B2:
            temp.append("B2={0}".format(B2))
        if wu.B2_start:
            temp.append("B2_start={0}".format(wu.B2_start))

    if wu.error_count:
        temp.append("Errors: {0:08X}".format(wu.error_count))
    if wu.nerr_roe:
        temp.append("ROEs: {0:n}".format(wu.nerr_roe))
    if wu.nerr_gcheck:
        temp.append("GEC errors: {0:n}".format(wu.nerr_gcheck))

    result = [assignment_to_str(wu) if not index else "", "{0:n}. {1}".format(
        num + 1, os.path.basename(file)) if num >= 0 else os.path.basename(file)]
    if options.long:
        mtime = os.path.getmtime(file)
        date = datetime.fromtimestamp(mtime)
        size = os.path.getsize(file)
        result += ["{0}B".format(outputunit(size)), "{0:%c}".format(date)]
    result += [work_type_str, "{0}, {1}".format(stage, wu.stage) if stage else "Stage: {0}".format(
        wu.stage), "?%" if wu.pct_complete is None else "{0:.4%}".format(wu.pct_complete)] + temp

    return result


def main(dirs):
    for i, adir in enumerate(dirs):
        if i:
            print()
        print("{0}:".format(adir))
        if options.prime95:
            if options.mlucas or options.cudalucas or options.gpuowl:
                print("\tPrime95/MPrime:")
            entries = {}
            for entry in glob.iglob(os.path.join(adir, "[cpefmn][0-9_]*")):
                filename = os.path.basename(entry)
                match = PRIME95_RE.match(filename)
                if match:
                    root, _ = os.path.splitext(filename)
                    if root not in entries:
                        entries[root] = []
                    entries[root].append((int(match.group(2)) if match.group(
                        2) else 1 if match.group(1) else 0, entry))
            rows = []
            for entry in entries.values():
                for j, (num, file) in enumerate(sorted(entry)):
                    result = parse_work_unit_prime95(file)
                    if result is not None:
                        rows.append(one_line_status(file, num, j, result))
                    else:
                        print(
                            "Error: unable to parse the {0!r} save/checkpoint file".format(file), file=sys.stderr)
            if rows:
                output_table(rows)
            else:
                print("\tNo save/checkpoint files found for Prime95/MPrime.")

        if options.mlucas:
            if options.prime95 or options.cudalucas or options.gpuowl:
                print("\tMlucas:")
            entries = {}
            for entry in glob.iglob(os.path.join(adir, "[pfq][0-9]*")):
                match = MLUCAS_RE.match(os.path.basename(entry))
                if match:
                    exponent = int(match.group(2))
                    if exponent not in entries:
                        entries[exponent] = []
                    stage = match.group(3) and int(match.group(3))
                    entries[exponent].append((-1 if match.group(4) else 0 if stage else 0 if match.group(
                        1) in {"p", "f"} else 1, 1 if stage is None else stage, entry))
            rows = []
            for exponent, entry in entries.items():
                for j, (num, stage, file) in enumerate(sorted(entry)):
                    result = parse_work_unit_mlucas(file, exponent, stage)
                    if result is not None:
                        rows.append(one_line_status(file, num, j, result))
                    else:
                        print(
                            "Error: unable to parse the {0!r} save/checkpoint file".format(file), file=sys.stderr)
            if rows:
                output_table(rows)
            else:
                print("\tNo save/checkpoint files found for Mlucas.")

        if options.cudalucas:
            if options.prime95 or options.mlucas or options.gpuowl:
                print("\tCUDALucas:")
            entries = {}
            for entry in glob.iglob(os.path.join(adir, "[ct][0-9]*")):
                match = CUDALUCAS_RE.match(os.path.basename(entry))
                if match:
                    exponent = int(match.group(2))
                    if exponent not in entries:
                        entries[exponent] = []
                    entries[exponent].append(
                        (0 if match.group(1) == "c" else 1, entry))
            rows = []
            for exponent, entry in entries.items():
                for j, (num, file) in enumerate(sorted(entry)):
                    result = parse_work_unit_cudalucas(file, exponent)
                    if result is not None:
                        rows.append(one_line_status(file, num, j, result))
                    else:
                        print(
                            "Error: unable to parse the {0!r} save/checkpoint file".format(file), file=sys.stderr)
            if rows:
                output_table(rows)
            else:
                print("\tNo save/checkpoint files found for CUDALucas.")

        if options.gpuowl:
            if options.prime95 or options.mlucas or options.cudalucas:
                print("\tGpuOwl:")
            entries = {}
            for entry in (aglob for globs in (os.path.join(
                    adir, "[0-9]*", "[0-9]*.*"), os.path.join(adir, "[0-9]*.owl")) for aglob in glob.iglob(globs)):
                match = GPUOWL_RE.search(entry)
                if match:
                    exponent = int(match.group(1))
                    if exponent not in entries:
                        entries[exponent] = []
                    entries[exponent].append(
                        (-1 if match.group(3) or match.group(4) else 1 if match.group(5) or match.group(6) else 0, entry))
            rows = []
            for entry in entries.values():
                for j, (num, file) in enumerate(sorted(entry)):
                    result = parse_work_unit_gpuowl(file)
                    if result is not None:
                        rows.append(one_line_status(file, num, j, result))
                    else:
                        print(
                            "Error: unable to parse the {0!r} save/checkpoint file".format(file), file=sys.stderr)
            if rows:
                output_table(rows)
            else:
                print("\tNo save/checkpoint files found for GpuOwl.")


if __name__ == "__main__":
    parser = optparse.OptionParser(
        version="%prog 1.0", description="Read Prime95/MPrime, Mlucas, GpuOwl and CUDALucas save/checkpoint files")
    parser.add_option("-w", "--workdir", dest="workdir", default=os.curdir,
                      help="Working directory, Default: %default (current directory)")
    # parser.add_option("-D", "--dir", action="append", dest="dirs", help="Directories with the save/checkpoint files. Provide once for each directory.")
    parser.add_option("-p", "--prime95", "--mprime", action="store_true",
                      dest="prime95", help="Look for Prime95/MPrime save/checkpoint files")
    parser.add_option("-m", "--mlucas", action="store_true",
                      dest="mlucas", help="Look for Mlucas save/checkpoint files")
    parser.add_option("-g", "--gpuowl", action="store_true",
                      dest="gpuowl", help="Look for GpuOwl save/checkpoint files")
    parser.add_option("-c", "--cudalucas", action="store_true",
                      dest="cudalucas", help="Look for CUDALucas save/checkpoint files")
    parser.add_option("-l", "--long", action="store_true", dest="long",
                      help="Output in long format with the file size and modification time")

    options, args = parser.parse_args()
    # if args:
    # parser.error("Unexpected arguments")

    workdir = os.path.expanduser(options.workdir)
    dirs = [os.path.join(workdir, adir)
            for adir in args] if args else [workdir]

    for adir in dirs:
        if not os.path.exists(adir) or not os.path.isdir(adir):
            parser.error("Directory {0!r} does not exist".format(adir))

    if not options.prime95 and not options.mlucas and not options.cudalucas and not options.gpuowl:
        parser.error(
            "Must select at least one GIMPS program to look for save/checkpoint files for")

    main(dirs)
