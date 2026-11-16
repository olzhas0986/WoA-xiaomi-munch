#!/usr/bin/env python3
"""Minimal Android OTA payload.bin extractor with no external dependencies.

Supports full (non-delta) OTAs: REPLACE, REPLACE_BZ, REPLACE_XZ and ZERO
operations. The manifest protobuf is decoded by hand so python-protobuf is
not needed.

Examples:
    payload_extract.py payload.bin --list
    payload_extract.py payload.bin -o out/crdroid -p abl,xbl,xbl_config,boot,dtbo
"""
import argparse
import bz2
import hashlib
import lzma
import os
import struct
import sys

OP_REPLACE, OP_REPLACE_BZ, OP_ZERO, OP_REPLACE_XZ = 0, 1, 6, 8
OP_NAMES = {0: "REPLACE", 1: "REPLACE_BZ", 6: "ZERO", 8: "REPLACE_XZ"}


def varint(buf, pos):
    result = shift = 0
    while True:
        b = buf[pos]
        pos += 1
        result |= (b & 0x7F) << shift
        if not b & 0x80:
            return result, pos
        shift += 7


def fields(buf):
    """Yield (field_number, wire_type, value) for a protobuf message."""
    pos, end = 0, len(buf)
    while pos < end:
        key, pos = varint(buf, pos)
        num, wt = key >> 3, key & 7
        if wt == 0:
            val, pos = varint(buf, pos)
        elif wt == 1:
            val = buf[pos:pos + 8]
            pos += 8
        elif wt == 2:
            ln, pos = varint(buf, pos)
            val = buf[pos:pos + ln]
            pos += ln
        elif wt == 5:
            val = buf[pos:pos + 4]
            pos += 4
        else:
            raise ValueError(f"unsupported wire type {wt}")
        yield num, wt, val


def parse_extent(buf):
    start = count = 0
    for num, _, val in fields(buf):
        if num == 1:
            start = val
        elif num == 2:
            count = val
    return start, count


def parse_operation(buf):
    op = {"type": 0, "offset": 0, "length": 0, "dst": [], "sha256": None}
    for num, _, val in fields(buf):
        if num == 1:
            op["type"] = val
        elif num == 2:
            op["offset"] = val
        elif num == 3:
            op["length"] = val
        elif num == 6:
            op["dst"].append(parse_extent(val))
        elif num == 8:
            op["sha256"] = bytes(val)
    return op


def parse_partition(buf):
    part = {"name": "", "ops": [], "size": 0, "hash": None}
    for num, _, val in fields(buf):
        if num == 1:
            part["name"] = bytes(val).decode()
        elif num == 8:
            part["ops"].append(parse_operation(val))
        elif num == 7:
            for n2, _, v2 in fields(val):
                if n2 == 1:
                    part["size"] = v2
                elif n2 == 2:
                    part["hash"] = bytes(v2)
    return part


def read_manifest(f):
    if f.read(4) != b"CrAU":
        sys.exit("not a payload.bin (missing CrAU magic)")
    version, manifest_size = struct.unpack(">QQ", f.read(16))
    if version != 2:
        sys.exit(f"unsupported payload version: {version}")
    (sig_size,) = struct.unpack(">I", f.read(4))
    manifest = memoryview(f.read(manifest_size))
    data_start = 24 + manifest_size + sig_size
    block_size, parts = 4096, []
    for num, _, val in fields(manifest):
        if num == 3:
            block_size = val
        elif num == 13:
            parts.append(parse_partition(val))
    return block_size, parts, data_start


def extract(f, part, block_size, data_start, out_path, verify=True):
    with open(out_path, "wb") as out:
        for op in part["ops"]:
            kind = op["type"]
            if kind == OP_ZERO:
                data = None
            else:
                f.seek(data_start + op["offset"])
                raw = f.read(op["length"])
                if verify and op["sha256"] and hashlib.sha256(raw).digest() != op["sha256"]:
                    sys.exit(f"{part['name']}: corrupted operation data")
                if kind == OP_REPLACE:
                    data = raw
                elif kind == OP_REPLACE_BZ:
                    data = bz2.decompress(raw)
                elif kind == OP_REPLACE_XZ:
                    data = lzma.decompress(raw)
                else:
                    sys.exit(f"{part['name']}: operation {kind} is not supported "
                             "(delta OTA?)")
            pos = 0
            for start, count in op["dst"]:
                out.seek(start * block_size)
                size = count * block_size
                if data is None:
                    out.write(b"\0" * size)
                else:
                    out.write(data[pos:pos + size])
                    pos += size
        out.truncate(part["size"])
    if verify and part["hash"]:
        h = hashlib.sha256()
        with open(out_path, "rb") as chk:
            for chunk in iter(lambda: chk.read(1 << 20), b""):
                h.update(chunk)
        if h.digest() != part["hash"]:
            sys.exit(f"{part['name']}: partition sha256 mismatch")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("payload")
    ap.add_argument("-o", "--out", default="out")
    ap.add_argument("-p", "--partitions", help="comma-separated list (default: all)")
    ap.add_argument("-l", "--list", action="store_true", help="only list partitions")
    ap.add_argument("--no-verify", action="store_true")
    args = ap.parse_args()

    with open(args.payload, "rb") as f:
        block_size, parts, data_start = read_manifest(f)
        if args.list:
            for p in parts:
                kinds = sorted({OP_NAMES.get(o["type"], str(o["type"])) for o in p["ops"]})
                digest = p["hash"].hex() if p["hash"] else "-"
                print(f"{p['name']:<16}{p['size']:>12}  {digest}  {','.join(kinds)}")
            return
        wanted = set(args.partitions.split(",")) if args.partitions else None
        missing = (wanted or set()) - {p["name"] for p in parts}
        if missing:
            sys.exit(f"no such partitions: {', '.join(sorted(missing))}")
        os.makedirs(args.out, exist_ok=True)
        for p in parts:
            if wanted and p["name"] not in wanted:
                continue
            path = os.path.join(args.out, p["name"] + ".img")
            extract(f, p, block_size, data_start, path, not args.no_verify)
            print(f"{p['name']:<16}{p['size']:>12}  -> {path}")


if __name__ == "__main__":
    main()
