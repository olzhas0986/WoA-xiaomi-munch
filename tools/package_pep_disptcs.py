#!/usr/bin/env python3
"""Repackage the previous port's PEP LMH test with the display TCS fix.

Takes munch-pep-lmh-test.zip from the previous port (its MunchPepLmh scripts
sign the diagnostic qcpep copy on the phone and start it once, traced) and
swaps in the driver produced by

    tools/patch_qcpep_display_tcs.py qcpep8250.sys --with-lmh -o <sys>

Everything else in the package is kept byte-for-byte. Checks:
  * the input package carries the expected LMH driver (sha256 pinned);
  * the new driver differs from it only in the PE checksum and in the display
    record's TCS field (file offset 0x19DD84: 4 -> 2);
  * test.ps1 accepts an SSDT up to 4 MiB instead of 64 KiB;
  * patch.json gets the new unsigned hash and the extra change; SHA256.json
    is regenerated for the files it lists.

Example:
    package_pep_disptcs.py munch-pep-lmh-test.zip out/qcpep/qcpep8250-lmh-disptcs.sys \\
        -o out/qcpep/munch-pep-lmh-disptcs-test.zip
"""
import argparse
import hashlib
import json
import sys
import zipfile

PREFIX = "MunchPepLmh/"
SYS_NAME = PREFIX + "qcpep-lmh-unsigned.sys"
LMH_SHA256 = "2e1c7ac1c076626f6b9ba54871b7bd6de53f057c7d5caf3e66818af9e9b10f39"
CHECKSUM = range(0x150, 0x154)
TCS_OFFSET = 0x19DD84
TCS_RVA = 0x19FF84
# file offsets of RVA 0x5520, 0x5B20, 0x5B88, 0x5C50 (.text: RVA 0x1000 at 0x400)
LMH_RET_OFFSETS = (0x4920, 0x4F20, 0x4F88, 0x5050)
NOTE = """# Display TCS variant

This package is the previous port's MunchPepLmh test with one more change in
the diagnostic driver: the display RSC record of qcpep8250 (RVA 0x19FF60,
field +0x24 at RVA 0x19FF84, file offset 0x19DD84) requires 2 TCS instead of
4. munch's display RSC reports 2 TCS (DRV CONFIG 0x80000002), which made
the driver stop with bugcheck 0x14B. The two LMH NOPs are unchanged.

Workflow, scripts and rollback are the same as in README.md.
"""


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("package")
    ap.add_argument("driver")
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--no-lmh-mmio", action="store_true",
                    help="also allow the four LMh function entries patched to RET")
    ap.add_argument("--tags", metavar="JSON",
                    help="also allow the STATUS_UNSUCCESSFUL tag patches listed in this map")
    args = ap.parse_args()

    with zipfile.ZipFile(args.package) as z:
        files = {i.filename: z.read(i) for i in z.infolist() if not i.is_dir()}
    old = files.get(SYS_NAME)
    if old is None or sha(old) != LMH_SHA256:
        sys.exit("input package does not carry the expected LMH driver")
    new = open(args.driver, "rb").read()
    if len(new) != len(old):
        sys.exit("driver sizes differ")
    diff = [i for i in range(len(new)) if new[i] != old[i]]
    tagged = set()
    if args.tags:
        for t in json.load(open(args.tags)).values():
            tagged.update(range(t["offset"], t["offset"] + 4))
    if args.no_lmh_mmio:
        for off in LMH_RET_OFFSETS:
            if new[off:off + 4] != bytes.fromhex("c0035fd6"):
                sys.exit(f"driver has no RET at file offset {off:#x}")
            tagged.update(range(off, off + 4))
    unexpected = [i for i in diff if i not in CHECKSUM and i != TCS_OFFSET and i not in tagged]
    if unexpected or TCS_OFFSET not in diff or (old[TCS_OFFSET], new[TCS_OFFSET]) != (4, 2):
        sys.exit(f"driver differs from the LMH copy in unexpected places: {[hex(i) for i in unexpected]}")

    patch = json.loads(files[PREFIX + "patch.json"])
    patch["unsigned_sha256"] = sha(new)
    patch["changes"].append({"rva": TCS_RVA, "offset": TCS_OFFSET, "before": "04000000",
                             "after": "02000000",
                             "field": "display RSC record +0x24 (TCS required)"})
    patch["purpose"] += (" Also lowers the display RSC TCS requirement from 4 to 2 to match "
                         "the hardware (DRV CONFIG 0x80000002).")
    files[SYS_NAME] = new
    files[PREFIX + "patch.json"] = (json.dumps(patch, indent=2) + "\n").encode()
    files[PREFIX + "README-disptcs.md"] = NOTE.encode()
    # test.ps1 reads the SSDT only if it is <= 64 KiB; the PEP0 configuration
    # imported from pipa makes it ~267 KiB
    test = files[PREFIX + "test.ps1"].decode("latin-1")
    old_limit = 'n>65536)throw new Exception("Cannot read SSDT")'
    if test.count(old_limit) != 1:
        sys.exit("test.ps1: SSDT size check not found")
    files[PREFIX + "test.ps1"] = test.replace(
        old_limit, 'n>4194304)throw new Exception("Cannot read SSDT")').encode("latin-1")
    listing = json.loads(files[PREFIX + "SHA256.json"])
    for name in listing:
        listing[name] = sha(files[PREFIX + name])
    files[PREFIX + "SHA256.json"] = (json.dumps(listing, indent=2) + "\n").encode()

    with zipfile.ZipFile(args.out, "w", zipfile.ZIP_DEFLATED) as z:
        for name in sorted(files):
            z.writestr(name, files[name])
    print(f"driver {sha(new)}")
    print(f"{args.out}: {sha(open(args.out, 'rb').read())}")


if __name__ == "__main__":
    main()
