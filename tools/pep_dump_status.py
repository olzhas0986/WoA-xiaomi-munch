#!/usr/bin/env python3
"""Read the failing init status from a qcpep8250 0x14E triage dump.

qcpep RVA 0x1db000 runs the PEP init steps and calls KeBugCheckEx(0x14E)
when one returns an error; the status is kept at [fp + 0x10] of that frame.
The frame is found as the frame record whose return address is qcpep+0x214fbc.
Prints the bugcheck, which call site fired (0x1db2f4: step 0x101558,
0x1db568: InitializePppFramework 0x115288) and the saved NTSTATUS.

Example:
    pep_dump_status.py pep.dmp [--tags=out/qcpep/unsuccessful-tags.json]
"""
import json
import struct
import sys

args = [a for a in sys.argv[1:] if not a.startswith("--tags=")]
tags = {}
for a in sys.argv[1:]:
    if a.startswith("--tags="):
        tags = {int(k, 16): v for k, v in json.load(open(a[7:])).items()}
b = open(args[0], "rb").read()
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
stack = {base + o: struct.unpack_from("<Q", b, off + o)[0] for o in range(0, size - 8, 8)}
values = set(stack.values())
# driver base: the value that makes both known return addresses appear on the stack
image = None
for v in values:
    cand = v - 0x214FBC
    if cand & 0xFFF == 0 and cand + 0x1DB568 in values or cand + 0x1DB2F4 in values and cand & 0xFFF == 0:
        image = cand
        break
if image is None:
    sys.exit("qcpep init frame (return to +0x214fbc) not found on the captured stack")
print(f"qcpep loaded at {image:#x}")
for addr, v in stack.items():
    if v == image + 0x214FBC and stack.get(addr - 8) is not None and addr - 8 > base:
        fp = addr - 8          # frame record: [fp] = previous fp, [fp+8] = return address
        callee_lr = stack.get(fp - 0x20 + 8)
        site = (callee_lr - image) if callee_lr else None
        step = {0x1DB2F4: "step 0x101558", 0x1DB568: "InitializePppFramework 0x115288"}.get(
            site, f"return {site:#x}" if site is not None else "unknown")
        status = struct.unpack("<I", rd(fp + 0x10, 4))[0]
        print(f"init frame fp {fp:#x}: failed in {step}, status {status:#010x}")
        if status in tags:
            print(f"  tagged STATUS_UNSUCCESSFUL site: RVA {tags[status]['rva']} ({tags[status]['reg']})")
