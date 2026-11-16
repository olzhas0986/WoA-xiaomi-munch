#!/usr/bin/env python3
"""Prepare the DTB that is appended to the "kernel" in the UEFI boot.img.

For sibling devices Mu-Silicium keeps a snapshot of /sys/firmware/fdt from a
running Android in Resources/DTBs: already merged with dtbo and carrying the
msm-id/board-id that ABL uses to pick a tree. This tool strips per-unit data
from such a snapshot (serial number, cpuid, panel calibration in bootargs);
ABL rewrites /chosen on every boot anyway.

Example:
    prepare_dtb.py munch-live.dtb -o out/munch.dtb --dts dts/munch.dts
"""
import argparse
import re
import subprocess
import sys

EXPECT_MODEL = "xiaomi munch"
EXPECT_BOARD_ID = "<0x32 0x00>"


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("dtb")
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--dts", help="also write the cleaned-up source")
    args = ap.parse_args()

    res = subprocess.run(["dtc", "-q", "-I", "dtb", "-O", "dts", args.dtb],
                         capture_output=True, text=True)
    if res.returncode:
        sys.exit(res.stderr)
    dts = res.stdout
    if EXPECT_MODEL not in dts or f"qcom,board-id = {EXPECT_BOARD_ID}" not in dts:
        sys.exit("not a munch DTB (model/board-id mismatch)")

    dts, n = re.subn(r'(\n\t\tbootargs = )"[^"]*";', r'\1"";', dts)
    if n != 1:
        sys.exit("/chosen/bootargs not found")
    # initrd address and random seeds also belong to a single boot
    dts = re.sub(r"\n\t\t(linux,initrd-(start|end)|kaslr-seed|rng-seed) = [^;]*;", "", dts)

    if args.dts:
        with open(args.dts, "w") as f:
            f.write(dts)
    res = subprocess.run(["dtc", "-q", "-I", "dts", "-O", "dtb", "-o", args.out, "-"],
                         input=dts, capture_output=True, text=True)
    if res.returncode:
        sys.exit(res.stderr)
    print(f"{args.out}: done")


if __name__ == "__main__":
    main()
