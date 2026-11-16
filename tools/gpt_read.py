#!/usr/bin/env python3
"""Decode a GPT from a raw dump of the start of a disk.

Take the dump from recovery (read-only):

    adb exec-out "dd if=/dev/block/sda bs=4096 count=6 2>/dev/null" > out/sda-gpt.bin

The logical sector size is detected from where the "EFI PART" header sits
(4096 on UFS, 512 elsewhere). The primary header CRC and the partition array
CRC are verified.

Examples:
    gpt_read.py out/sda-gpt.bin
    gpt_read.py out/sda-gpt.bin --json
"""
import argparse
import json
import struct
import sys
import uuid
import zlib

HEADER = struct.Struct("<8sIIIIQQQQ16sQIII")


def parse(data):
    for sector in (4096, 512):
        if data[sector:sector + 8] == b"EFI PART":
            break
    else:
        sys.exit("no GPT header at LBA1 for sector sizes 4096 or 512")

    (sig, rev, hsize, hcrc, _, my_lba, alt_lba, first_usable, last_usable,
     disk_guid, entries_lba, n_entries, entry_size, entries_crc) = HEADER.unpack_from(data, sector)
    header = bytearray(data[sector:sector + hsize])
    header[16:20] = b"\0\0\0\0"
    if zlib.crc32(header) != hcrc:
        sys.exit("GPT header CRC mismatch")
    start = entries_lba * sector
    table = data[start:start + n_entries * entry_size]
    if len(table) < n_entries * entry_size:
        sys.exit(f"dump too short: need {(start + n_entries * entry_size + sector - 1) // sector}"
                 f" sectors of {sector} bytes")
    if zlib.crc32(table) != entries_crc:
        sys.exit("GPT partition array CRC mismatch")

    parts = []
    for i in range(n_entries):
        e = table[i * entry_size:(i + 1) * entry_size]
        ptype = uuid.UUID(bytes_le=e[0:16])
        if ptype.int == 0:
            continue
        first, last, attrs = struct.unpack_from("<QQQ", e, 32)
        parts.append({
            "number": i + 1,
            "name": e[56:128].decode("utf-16le").rstrip("\0"),
            "first_lba": first,
            "last_lba": last,
            "size_bytes": (last - first + 1) * sector,
            "type_guid": str(ptype).upper(),
            "part_guid": str(uuid.UUID(bytes_le=e[16:32])).upper(),
            "attributes": attrs,
        })
    return {
        "sector_size": sector,
        "disk_guid": str(uuid.UUID(bytes_le=disk_guid)).upper(),
        "first_usable_lba": first_usable,
        "last_usable_lba": last_usable,
        "alternate_lba": alt_lba,
        "entries": n_entries,
        "partitions": parts,
    }


def human(n):
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if n < 1024 or unit == "TiB":
            return f"{n:.1f} {unit}" if unit != "B" else f"{n} B"
        n /= 1024


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("dump")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    gpt = parse(open(args.dump, "rb").read())
    if args.json:
        json.dump(gpt, sys.stdout, indent=2)
        print()
        return
    print(f"disk GUID {gpt['disk_guid']}, sector {gpt['sector_size']}, "
          f"usable LBA {gpt['first_usable_lba']}..{gpt['last_usable_lba']}")
    print(f"{'#':>3}  {'name':<20} {'first':>10} {'last':>10} {'size':>10}  type")
    for p in gpt["partitions"]:
        print(f"{p['number']:>3}  {p['name']:<20} {p['first_lba']:>10} {p['last_lba']:>10} "
              f"{human(p['size_bytes']):>10}  {p['type_guid']}")
    used = sorted((p["first_lba"], p["last_lba"]) for p in gpt["partitions"])
    cursor = gpt["first_usable_lba"]
    for first, last in used + [(gpt["last_usable_lba"] + 1, 0)]:
        if first > cursor and (first - cursor) * gpt["sector_size"] >= 1 << 20:
            print(f"     {'<free>':<20} {cursor:>10} {first - 1:>10} "
                  f"{human((first - cursor) * gpt['sector_size']):>10}")
        cursor = max(cursor, last + 1)


if __name__ == "__main__":
    main()
