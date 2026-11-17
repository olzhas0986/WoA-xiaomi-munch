#!/usr/bin/env python3
"""Name the qcpep8250 fatal-error call site behind a patched stop code.

qcpep8250 stops through one helper (RVA 0x101E80) that calls
KeBugCheckEx(0x14B SOC_SUBSYSTEM_FAILURE) with a details block holding the
message passed in x0. It has about 350 callers. When crash dumps cannot be
written, the test driver replaces the stop code with

    (return address - runtime address of RVA 0x101F20) mod 2^32

(see docs/previous-port-pep.md, "site code"), which is independent of the
load address. This tool lists, for a stop code read off the screen, the
call site and the message string loaded into x0 before the call.

Example:
    pep_fatal_site.py qcpep8250.sys 0x000D964C
    pep_fatal_site.py qcpep8250.sys --all
"""
import argparse
import re
import struct
import subprocess
import sys

HELPER = 0x101E80
ANCHOR = 0x101F20
IMAGE_BASE = 0x140000000


def sections(data):
    pe = struct.unpack_from("<I", data, 0x3C)[0]
    count = struct.unpack_from("<H", data, pe + 6)[0]
    opt = struct.unpack_from("<H", data, pe + 20)[0]
    return [struct.unpack_from("<IIII", data, pe + 24 + opt + 40 * i + 8) for i in range(count)]


def cstring(data, secs, rva):
    for vsize, va, rsize, raw in secs:
        if va <= rva < va + max(vsize, rsize):
            s = data[raw + rva - va:raw + rva - va + 200].split(b"\0")[0]
            return s.decode("latin-1")
    return None


def call_sites(path):
    out = subprocess.run(["llvm-objdump", "-d", "--no-show-raw-insn", path],
                         capture_output=True, text=True, check=True).stdout
    pat = re.compile(r"\s*(14[0-9a-f]+):\s+(\S+)\s*(.*)")
    window = []
    for line in out.splitlines():
        m = pat.match(line)
        if not m:
            continue
        addr, op, args = int(m.group(1), 16) - IMAGE_BASE, m.group(2), m.group(3)
        window = (window + [(addr, op, args)])[-8:]
        if op == "bl" and args.startswith(f"{IMAGE_BASE + HELPER:#x}"):
            yield addr, window


def message(data, secs, window):
    pages = {}
    for _, op, args in window:
        m = re.match(r"(x\d+), (0x[0-9a-f]+)", args)
        if op == "adrp" and m:
            pages[m.group(1)] = int(m.group(2), 16) - IMAGE_BASE
        m = re.match(r"x0, (x\d+), #0x([0-9a-f]+)$", args)
        if op == "add" and m and m.group(1) in pages:
            return cstring(data, secs, pages[m.group(1)] + int(m.group(2), 16))
    return None


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("sys_file")
    ap.add_argument("code", nargs="?", help="stop code shown on screen (hex)")
    ap.add_argument("--all", action="store_true", help="list every site and its code")
    args = ap.parse_args()
    data = open(args.sys_file, "rb").read()
    secs = sections(data)
    want = int(args.code, 16) if args.code else None
    found = False
    for site, window in call_sites(args.sys_file):
        code = (site + 4 - ANCHOR) & 0xFFFFFFFF
        if args.all or code == want:
            found = True
            print(f"code {code:#010x}  call at RVA {site:#x}  message {message(data, secs, window)!r}")
    if not found and not args.all:
        sys.exit("no call site with that code")


if __name__ == "__main__":
    main()
