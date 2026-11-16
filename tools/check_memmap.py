#!/usr/bin/env python3
"""Check the port's MemoryMapLib.c against uefiplat.cfg from the XBL and the device DTB.

Checks:
  1. regions do not overlap;
  2. every region named as in uefiplat.cfg matches its base/size;
  3. every register region from the XBL [RegisterMap] is present;
  4. UEFI FD and stack match munch.toml / munch.dsc;
  5. no-map regions from the DTB reserved-memory do not fall into memory
     that UEFI hands out as free (Conv).

Example:
    check_memmap.py --cfg out/xbl-fv/uefiplat.cfg/uefiplat.cfg.raw --dtb munch-live.dtb
"""
import argparse
import os
import re
import subprocess
import sys
import tomllib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENTRY = re.compile(r'\{\s*"([^"]+)",\s*(0x[0-9A-Fa-f]+),\s*(0x[0-9A-Fa-f]+),\s*(\w+),'
                   r'\s*(\w+),\s*(\w+),\s*(\w+),\s*(\w+)\s*\}')
CFG_LINE = re.compile(r'^(0x[0-9A-Fa-f]+),\s*(0x[0-9A-Fa-f]+),\s*"([^"]+)",\s*(\w+),'
                      r'\s*(\w+),\s*(\w+),\s*(\w+),\s*(\w+)')
# Regions named differently in the port and in the XBL
ALIASES = {"TZApps": "TZApps Reserved"}


def parse_lib(path):
    return [(m[1], int(m[2], 16), int(m[3], 16), m[7])
            for m in ENTRY.finditer(open(path).read())]


def parse_cfg(path):
    section, out = None, {"MemoryMap": {}, "RegisterMap": {}}
    for line in open(path, errors="replace"):
        line = line.strip()
        if line.startswith("["):
            section = line.strip("[]")
        m = CFG_LINE.match(line)
        if m and section in out:
            out[section][m[3]] = (int(m[1], 16), int(m[2], 16), m[7])
    return out


def dtb_nomap(path):
    dts = subprocess.run(["dtc", "-I", "dtb", "-O", "dts", path],
                         capture_output=True, text=True).stdout
    start = dts.find("reserved-memory {")
    regions = []
    for m in re.finditer(r"\n\t\t(?:\w+: )?([\w,@-]+) \{(.*?)\n\t\t\};", dts[start:], re.S):
        reg = re.search(r"\breg = <([^>]+)>", m[2])
        if reg and "no-map" in m[2]:
            v = [int(x, 16) for x in reg[1].split()]
            regions.append((m[1], (v[0] << 32) | v[1], (v[2] << 32) | v[3]))
    return regions


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--lib", default=os.path.join(
        ROOT, "port/munchPkg/Library/MemoryMapLib/MemoryMapLib.c"))
    ap.add_argument("--cfg", required=True, help="uefiplat.cfg from the XBL")
    ap.add_argument("--dtb", help="device DTB (live or from vendor_boot)")
    args = ap.parse_args()

    regions, cfg, errors = parse_lib(args.lib), parse_cfg(args.cfg), []
    if not regions:
        sys.exit("no regions found in MemoryMapLib.c")

    ordered = sorted(regions, key=lambda r: r[1])
    for (n1, b1, s1, _), (n2, b2, _, _) in zip(ordered, ordered[1:]):
        if b1 + s1 > b2 and n1 != "IMEM Base":  # IMEM Cookie sits inside IMEM Base in the XBL too
            errors.append(f"overlap: {n1} [{b1:#x}+{s1:#x}] and {n2} [{b2:#x}]")

    xbl = {**cfg["MemoryMap"], **cfg["RegisterMap"]}
    for name, base, size, _ in regions:
        ref = xbl.get(ALIASES.get(name, name))
        if ref and (ref[0], ref[1]) != (base, size):
            errors.append(f"{name}: port has {base:#x}+{size:#x}, XBL has {ref[0]:#x}+{ref[1]:#x}")
    have = {r[0] for r in regions}
    for name in cfg["RegisterMap"]:
        if name not in have:
            errors.append(f"register region {name} from the XBL is missing in the port")

    by_name = {r[0]: r for r in regions}
    with open(os.path.join(ROOT, "port/Resources/Configs/munch.toml"), "rb") as f:
        fd = tomllib.load(f)["uefi_fd"]
    if (fd["base"], fd["size"]) != by_name["UEFI FD"][1:3]:
        errors.append("uefi_fd in munch.toml does not match the UEFI FD region")
    dsc = open(os.path.join(ROOT, "port/munchPkg/munch.dsc")).read()
    stack = int(re.search(r"PcdCPUCoresStackBase\|(0x[0-9A-Fa-f]+)", dsc)[1], 16)
    stack_size = int(re.search(r"PcdCPUCorePrimaryStackSize\|(0x[0-9A-Fa-f]+)", dsc)[1], 16)
    if (stack, stack_size) != by_name["UEFI Stack"][1:3]:
        errors.append("stack in munch.dsc does not match the UEFI Stack region")

    if args.dtb:
        conv = [(n, b, s) for n, b, s, t in regions if t == "Conv" and b >= 0x80000000]
        for name, base, size in dtb_nomap(args.dtb):
            for cn, cb, cs in conv:
                if base < cb + cs and cb < base + size:
                    errors.append(f"DTB no-map region {name} [{base:#x}+{size:#x}] "
                                  f"falls into free region {cn}")

    for name, base, size, mtype in ordered:
        print(f"  {base:#012x} {size:#011x} {mtype:<7} {name}")
    if errors:
        print("\nERRORS:")
        for e in errors:
            print("  -", e)
        sys.exit(1)
    print(f"\nmemory map consistent: {len(regions)} regions")


if __name__ == "__main__":
    main()
