#!/usr/bin/env python3
"""Read the failing init status from a qcpep8250 0x14E triage dump.

qcpep RVA 0x1db000 runs the PEP init steps and calls KeBugCheckEx(0x14E)
when one returns an error; the status is kept at [fp + 0x10] of that frame.
The frame is found as the frame record whose return address is qcpep+0x214fbc.
Prints the bugcheck, which call site fired (0x1db2f4: step 0x101558,
0x1db568: InitializePppFramework 0x115288) and the saved NTSTATUS.

Example:
    pep_dump_status.py pep.dmp
"""
import struct
import sys

b = open(sys.argv[1], "rb").read()
if b[:8] != b"PAGEDU64" or struct.unpack_from("<I", b, 0xF98)[0] != 4:
    sys.exit("not an ARM64 triage dump")
u = lambda o: struct.unpack_from("<I", b, o)[0]  # noqa: E731
q = lambda o: struct.unpack_from("<Q", b, o)[0]  # noqa: E731
ranges = [(q(0x2048), u(0x2028), u(0x202C))]
for i in range(u(0x207C)):
    p = u(0x2078) + 16 * i
    ranges.append((q(p), u(p + 8), u(p + 12)))


def rd(va, n):
    for base, off, size in ranges:
        if base <= va and va + n <= base + size:
            return b[off + va - base:off + va - base + n]
    return None


print(f"bugcheck {u(0x38):#x} params {[hex(q(0x40 + 8 * i)) for i in range(4)]}")
base, off, size = ranges[0]
records = {}
for o in range(0, size - 16, 8):
    prev, lr = struct.unpack_from("<QQ", b, off + o)
    records[base + o] = lr
for fp, lr in records.items():
    if lr & 0xFFFFF == 0x14FBC and fp - 0x20 in records:
        site = records[fp - 0x20] & 0xFFFFF
        status = struct.unpack("<I", rd(fp + 0x10, 4))[0]
        step = {0xDB2F4: "step 0x101558", 0xDB568: "InitializePppFramework 0x115288"}.get(
            site, f"return {site:#x}")
        print(f"0x1db000 frame fp {fp:#x}: failed in {step}, status {status:#010x}")
