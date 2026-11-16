#!/usr/bin/env python3
"""Extract UEFI firmware volumes from a Qualcomm XBL (xbl.img / xbl.elf).

Finds volumes by their _FVH signature, unpacks LZMA/gzip sections and nested
volumes, and lays files out as <UI name or GUID>/ directories holding the
sections: *.efi (PE32), *.depex, *.raw, *.te. No external dependencies.

Example:
    xbl_fv_extract.py xbl.img -o out/xbl-fv
"""
import argparse
import gzip
import lzma
import os
import struct
import sys
import uuid

LZMA_GUID = uuid.UUID("ee4e5898-3914-4259-9d6e-dc7bd79403cf")
# Qualcomm compresses the main DXE volume with gzip under its own GUID
GZIP_GUID = uuid.UUID("1d301fe9-be79-4353-91c2-d23bc959ae0c")
FFS_TYPES = {1: "RAW", 2: "FREEFORM", 3: "SEC", 4: "PEI_CORE", 5: "DXE_CORE",
             6: "PEIM", 7: "DRIVER", 8: "COMBINED", 9: "APPLICATION",
             0xB: "FV_IMAGE", 0xF0: "PAD"}
SEC_EXT = {0x10: "efi", 0x12: "te", 0x13: "depex", 0x19: "raw", 0x1B: "depex",
           0x11: "pic", 0x14: "ver"}


def guid_at(buf, off):
    return uuid.UUID(bytes_le=bytes(buf[off:off + 16]))


def size24(buf, off):
    return buf[off] | buf[off + 1] << 8 | buf[off + 2] << 16


def walk_sections(buf, sink, depth):
    """Call sink(kind, payload) for every leaf section."""
    off, end = 0, len(buf)
    while off + 4 <= end:
        size, stype = size24(buf, off), buf[off + 3]
        hdr = 4
        if size == 0xFFFFFF:
            size = struct.unpack_from("<I", buf, off + 4)[0]
            hdr = 8
        if size < hdr or off + size > end:
            break
        body = buf[off + hdr:off + size]
        if stype == 0x02:  # GUID defined
            guid = guid_at(body, 0)
            data_off = struct.unpack_from("<H", body, 16)[0] - hdr
            inner = bytes(body[data_off:])
            if guid == LZMA_GUID:
                inner = lzma.decompress(inner, format=lzma.FORMAT_ALONE)
            elif guid == GZIP_GUID:
                inner = gzip.decompress(inner)
            walk_sections(memoryview(inner), sink, depth)
        elif stype == 0x01:  # compression section
            ctype = body[4]
            if ctype == 0:
                walk_sections(body[5:], sink, depth)
            else:
                sink("compressed", bytes(body[5:]))
        elif stype == 0x17:  # nested firmware volume
            sink("fv", bytes(body))
        elif stype == 0x15:  # UI
            sink("ui", bytes(body).decode("utf-16le").rstrip("\0"))
        elif stype in SEC_EXT:
            sink(SEC_EXT[stype], bytes(body))
        off += (size + 3) & ~3


def parse_fv(buf, out_dir, depth, index):
    fv_len = struct.unpack_from("<Q", buf, 32)[0]
    hdr_len = struct.unpack_from("<H", buf, 48)[0]
    ext_off = struct.unpack_from("<H", buf, 52)[0]
    erase = 0xFF if struct.unpack_from("<I", buf, 44)[0] & 0x800 else 0x00
    off = hdr_len
    if ext_off:
        ext_size = struct.unpack_from("<I", buf, ext_off + 16)[0]
        off = (ext_off + ext_size + 7) & ~7
    fv_len = min(fv_len, len(buf))
    while off + 24 <= fv_len:
        if bytes(buf[off:off + 24]) == bytes([erase]) * 24:
            break
        guid = guid_at(buf, off)
        ftype, attrs = buf[off + 18], buf[off + 19]
        size, hdr = size24(buf, off + 20), 24
        if attrs & 0x01:  # FFS_ATTRIB_LARGE_FILE
            size = struct.unpack_from("<Q", buf, off + 24)[0]
            hdr = 32
        if size < hdr or off + size > fv_len:
            break
        body = buf[off + hdr:off + size]
        if ftype != 0xF0:
            emit_file(guid, ftype, body, out_dir, depth, index)
        off = (off + size + 7) & ~7


def emit_file(guid, ftype, body, out_dir, depth, index):
    parts, name, nested = [], [None], []

    def sink(kind, payload):
        if kind == "ui":
            name[0] = payload
        elif kind == "fv":
            nested.append(payload)
        else:
            parts.append((kind, payload))

    if ftype == 1:  # RAW file: no sections
        parts.append(("raw", bytes(body)))
    else:
        walk_sections(body, sink, depth)
    for fv in nested:
        parse_fv(memoryview(fv), out_dir, depth + 1, index)
    if not parts:
        return
    label = name[0] or str(guid).upper()
    safe = label.replace("/", "_").replace("\\", "_")
    target = os.path.join(out_dir, safe)
    os.makedirs(target, exist_ok=True)
    counts = {}
    for kind, payload in parts:
        n = counts.get(kind, 0)
        counts[kind] = n + 1
        fname = f"{safe}{'' if n == 0 else '.' + str(n)}.{kind}"
        with open(os.path.join(target, fname), "wb") as f:
            f.write(payload)
    index.append((str(guid).upper(), FFS_TYPES.get(ftype, hex(ftype)), label,
                  ",".join(f"{k}:{len(p)}" for k, p in parts)))


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("image")
    ap.add_argument("-o", "--out", default="out/xbl-fv")
    args = ap.parse_args()

    data = memoryview(open(args.image, "rb").read())
    raw = bytes(data)
    index, pos, found = [], 0, 0
    while True:
        sig = raw.find(b"_FVH", pos)
        if sig < 0:
            break
        start = sig - 40
        pos = sig + 4
        if start < 0:
            continue
        fv_len = struct.unpack_from("<Q", raw, start + 32)[0]
        if not 0x48 <= fv_len <= len(raw) - start:
            continue
        found += 1
        print(f"FV @ 0x{start:x}, size 0x{fv_len:x}", file=sys.stderr)
        parse_fv(data[start:start + fv_len], args.out, 0, index)
        pos = start + fv_len
    if not found:
        sys.exit("no UEFI firmware volumes found")
    with open(os.path.join(args.out, "INDEX.tsv"), "w") as f:
        f.write("guid\ttype\tname\tsections\n")
        for row in index:
            f.write("\t".join(row) + "\n")
    print(f"files: {len(index)} -> {args.out}", file=sys.stderr)


if __name__ == "__main__":
    main()
