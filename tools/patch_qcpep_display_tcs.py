#!/usr/bin/env python3
"""Lower qcpep8250's display RSC TCS requirement to what SM8250 provides.

qcpep8250.sys 1.0.2140.0 (Kona BSP) keeps one 0x50-byte record per RPMh
controller at RVA 0x19ff10. During initialisation (RVA 0x111238) it reads
each controller's DRV CONFIG register and stops with bugcheck 0x14B when
the hardware TCS count is below record+0x24. For the display RSC (record
ID 9, base 0x0AF20000) that field is 4, but munch's display RSC reports 2
TCS on DRV0 (CONFIG 0x80000002, see docs/rpmh-config.md), as in the Linux
SM8250 device tree.

The same function accepts a TCS count equal to the controller's sleep/wake
base (2 for display) without dedicated active TCSs, so the record is set to
2. The init routine (RVA 0x111450) then assigns two sleep/wake slots and no
active slot. Whether active requests on the display controller work in that
mode is not established by reading the code; it needs a hardware test.

The output is a test copy: PE checksum recomputed, embedded Authenticode
signature removed (it no longer matches). Sign it with a test certificate
on the target, with test signing enabled.

--with-lmh also applies the earlier LMH diagnostic of the previous port: the
two BL calls to helper RVA 0x5c50 at RVA 0x1df358 and 0x21555c become NOPs
(the crash that followed it is the one this patch addresses).

--no-lmh-mmio turns the four functions that access the LMh blocks the driver
maps at 0x18350800 / 0x18358800 (layout of SM8150; munch's DT has no LMh
there) into a bare RET: RVA 0x5520 (status read, result unused), 0x5B20 and
0x5B88 (writes), 0x5C50 (the helper --with-lmh already bypasses at two call
sites). After PEP initialisation succeeded the system hung with
CLOCK_WATCHDOG_TIMEOUT, as the previous port did inside 0x5C50.

--tag-unsuccessful FILE gives every `orr wN, wzr, #0xC0000001` (STATUS_UNSUCCESSFUL)
between RVA 0x100000 and 0x130000 its own status value, still an error with
bit 31 set, and writes the value -> RVA map to FILE. A crash dump then shows
which site produced the failing status (tools/pep_dump_status.py --tags).

Examples:
    patch_qcpep_display_tcs.py qcpep8250.sys -o out/qcpep8250-disptcs.sys
    patch_qcpep_display_tcs.py qcpep8250.sys --with-lmh -o out/qcpep8250-lmh-disptcs.sys
"""
import argparse
import hashlib
import json
import struct
import sys

PINNED_SHA256 = "39fafcd60536c7d36dd95187dc9f51bfc4af661b614bce4a5e9ec0729fe24e01"
TABLE_RVA = 0x19FF10
RECORD_SIZE = 0x50
DISPLAY_INDEX = 1
# fields of the display record checked before patching: offset -> value
EXPECTED = {0x00: 9, 0x04: 9, 0x0C: 9, 0x24: 4, 0x28: 16, 0x30: 0x0AF20000}
APPS_EXPECTED = {0x00: 2, 0x24: 8, 0x28: 16, 0x30: 0x18220000}
TCS_FIELD = 0x24
NEW_TCS = 2
LMH_CALLS = (0x1DF358, 0x21555C)
LMH_TARGET = 0x5C50
NOP = bytes.fromhex("1f2003d5")
RET = bytes.fromhex("c0035fd6")
# function entry RVA -> expected first instruction
LMH_FUNCS = {0x5520: "fd7bbda9", 0x5B20: "fd7bbea9", 0x5B88: "fd7bbda9", 0x5C50: "fd7bbda9"}


def sections(data):
    pe = struct.unpack_from("<I", data, 0x3C)[0]
    count = struct.unpack_from("<H", data, pe + 6)[0]
    opt_size = struct.unpack_from("<H", data, pe + 20)[0]
    out = []
    for i in range(count):
        o = pe + 24 + opt_size + 40 * i
        vsize, va, rsize, raw = struct.unpack_from("<IIII", data, o + 8)
        out.append((va, max(vsize, rsize), raw))
    return pe, out


def rva_to_offset(secs, rva):
    for va, size, raw in secs:
        if va <= rva < va + size:
            return raw + rva - va
    sys.exit(f"RVA {rva:#x} is not in any section")


def bitmask_values():
    """32-bit ORR bitmask immediates with bit 31 set, other than 0xC0000001."""
    for ones in range(3, 31):
        for rot in range(1, ones):
            value = ((1 << ones) - 1)
            value = ((value >> rot) | (value << (32 - rot))) & 0xFFFFFFFF
            if value != 0xC0000001 and value >> 31:
                yield ones, rot, value


def tag_unsuccessful(data, secs):
    tags, values = {}, bitmask_values()
    for rva in range(0x100000, 0x130000, 4):
        off = rva_to_offset(secs, rva)
        insn = struct.unpack_from("<I", data, off)[0]
        if insn & ~0x1F != 0x32020BE0:      # orr wN, wzr, #0xC0000001
            continue
        ones, rot, value = next(values)
        new = 0x32000000 | (rot << 16) | ((ones - 1) << 10) | (31 << 5) | (insn & 0x1F)
        struct.pack_into("<I", data, off, new)
        tags[f"{value:#010x}"] = {"rva": f"{rva:#x}", "offset": off, "reg": f"w{insn & 0x1F}"}
    return tags


def pe_checksum(data, checksum_offset):
    total = 0
    for i in range(0, len(data) - len(data) % 2, 2):
        if checksum_offset <= i < checksum_offset + 4:
            continue
        total += struct.unpack_from("<H", data, i)[0]
        total = (total & 0xFFFF) + (total >> 16)
    if len(data) % 2:
        total += data[-1]
        total = (total & 0xFFFF) + (total >> 16)
    total = (total & 0xFFFF) + (total >> 16)
    return (total + len(data)) & 0xFFFFFFFF


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("sys_file")
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--tag-unsuccessful", metavar="JSON",
                    help="give each STATUS_UNSUCCESSFUL site a unique status; write the map")
    ap.add_argument("--no-lmh-mmio", action="store_true",
                    help="make the four LMh register functions return immediately")
    ap.add_argument("--with-lmh", action="store_true",
                    help="also NOP the two LMH helper calls (previous port's diagnostic)")
    args = ap.parse_args()

    data = bytearray(open(args.sys_file, "rb").read())
    digest = hashlib.sha256(data).hexdigest()
    if digest != PINNED_SHA256:
        sys.exit(f"unexpected qcpep8250.sys ({digest}); this patch is for 1.0.2140.0 only")

    pe, secs = sections(data)
    apps = rva_to_offset(secs, TABLE_RVA)
    disp = rva_to_offset(secs, TABLE_RVA + DISPLAY_INDEX * RECORD_SIZE)
    for base, expected, name in ((apps, APPS_EXPECTED, "apps"), (disp, EXPECTED, "display")):
        for off, want in expected.items():
            got = struct.unpack_from("<I", data, base + off)[0]
            if got != want:
                sys.exit(f"{name} record +{off:#x} is {got:#x}, expected {want:#x}")

    struct.pack_into("<I", data, disp + TCS_FIELD, NEW_TCS)
    print(f"display record (RVA {TABLE_RVA + RECORD_SIZE:#x}) +0x24: 4 -> {NEW_TCS} "
          f"(file offset {disp + TCS_FIELD:#x})")

    if args.with_lmh:
        for rva in LMH_CALLS:
            off = rva_to_offset(secs, rva)
            insn = struct.unpack_from("<I", data, off)[0]
            imm = insn & 0x3FFFFFF
            if imm & (1 << 25):
                imm -= 1 << 26
            if insn >> 26 != 0b100101 or rva + imm * 4 != LMH_TARGET:
                sys.exit(f"RVA {rva:#x} is not BL {LMH_TARGET:#x}")
            data[off:off + 4] = NOP
            print(f"LMH: BL {LMH_TARGET:#x} at RVA {rva:#x} -> NOP")

    if args.no_lmh_mmio:
        for rva, want in LMH_FUNCS.items():
            off = rva_to_offset(secs, rva)
            got = data[off:off + 4].hex()
            if got != want:
                sys.exit(f"RVA {rva:#x} starts with {got}, expected {want}")
            data[off:off + 4] = RET
            print(f"LMh: RVA {rva:#x} -> RET (file offset {off:#x})")

    if args.tag_unsuccessful:
        tags = tag_unsuccessful(data, secs)
        with open(args.tag_unsuccessful, "w") as f:
            json.dump(tags, f, indent=2)
        print(f"tagged {len(tags)} STATUS_UNSUCCESSFUL sites -> {args.tag_unsuccessful}")

    # drop the Authenticode signature: security directory is data directory 4
    opt = pe + 24
    magic = struct.unpack_from("<H", data, opt)[0]
    dd = opt + (96 if magic == 0x10B else 112)
    sec_off, sec_size = struct.unpack_from("<II", data, dd + 4 * 8)
    if sec_off and sec_off + sec_size == len(data):
        del data[sec_off:]
        print(f"removed embedded signature ({sec_size} bytes)")
    struct.pack_into("<II", data, dd + 4 * 8, 0, 0)

    checksum_offset = opt + 64
    struct.pack_into("<I", data, checksum_offset, pe_checksum(data, checksum_offset))
    open(args.out, "wb").write(data)
    print(f"{args.out}: sha256 {hashlib.sha256(data).hexdigest()}")


if __name__ == "__main__":
    main()
