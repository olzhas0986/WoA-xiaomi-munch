#!/usr/bin/env python3
"""Merge Windows registry transaction logs into a dirty hive (for reading).

After a forced power-off the primary hive file lags behind: recent changes
are only in <hive>.LOG1/.LOG2. This applies the log entries (Windows 8.1+
"HvLE" format) to a copy of the primary so the result can be inspected.

Entries from both logs are applied in sequence order, starting at the
primary's second sequence number and stopping at the first gap. Entry
hashes (Marvin32) are not verified, so the output is meant for diagnostics,
not for writing back to a Windows installation.

Layout used (all little-endian):
  hive base block: 0x04 seq1, 0x08 seq2, 0x28 hive bins data size; bins at 0x1000
  log file: base block in the first 512 bytes, entries from 0x200
  entry: 'HvLE', size, flags, seq, bins size, dirty page count, hash1, hash2,
         then count x (offset, size) references, then the page data

Example:
    hive_recover.py SYSTEM SYSTEM.LOG1 SYSTEM.LOG2 -o SYSTEM.recovered
"""
import argparse
import struct
import sys


def log_entries(path):
    data = open(path, "rb").read()
    if data[:4] != b"regf":
        return []
    entries, off = [], 0x200
    while off + 40 <= len(data) and data[off:off + 4] == b"HvLE":
        size, flags, seq, bins_size, count = struct.unpack_from("<IIIII", data, off + 4)
        if size < 40 or off + size > len(data) or size % 512:
            break
        refs = [struct.unpack_from("<II", data, off + 40 + 8 * i) for i in range(count)]
        pos, pages = off + 40 + 8 * count, []
        for poff, psize in refs:
            pages.append((poff, data[pos:pos + psize]))
            pos += psize
        entries.append({"seq": seq, "bins_size": bins_size, "pages": pages, "src": path})
        off += size
    return entries


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("hive")
    ap.add_argument("logs", nargs="+")
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--from-logs", action="store_true",
                    help="start at the earliest log entry when the logs do not reach back "
                         "to the primary's sequence (diagnostics only)")
    args = ap.parse_args()

    hive = bytearray(open(args.hive, "rb").read())
    seq1, seq2 = struct.unpack_from("<II", hive, 4)
    print(f"primary: seq {seq1}/{seq2}, bins {struct.unpack_from('<I', hive, 0x28)[0]:#x} bytes")
    by_seq = {}
    for path in args.logs:
        ents = log_entries(path)
        print(f"{path}: {len(ents)} entries"
              + (f", seq {ents[0]['seq']}..{ents[-1]['seq']}" if ents else ""))
        for e in ents:
            by_seq.setdefault(e["seq"], e)

    seq, applied = seq2, 0
    if seq not in by_seq and args.from_logs and by_seq:
        seq = min(by_seq)
        print(f"logs start at {seq}, primary is at {seq2}: entries {seq2}..{seq - 1} "
              "are lost, applying from the logs anyway")
    while seq in by_seq:
        e = by_seq[seq]
        need = 0x1000 + e["bins_size"]
        if len(hive) < need:
            hive.extend(b"\0" * (need - len(hive)))
        for poff, page in e["pages"]:
            hive[0x1000 + poff:0x1000 + poff + len(page)] = page
        struct.pack_into("<I", hive, 0x28, e["bins_size"])
        applied += 1
        seq += 1
    struct.pack_into("<II", hive, 4, seq, seq)
    open(args.out, "wb").write(hive)
    print(f"applied {applied} entries (up to seq {seq - 1}) -> {args.out}")
    if applied == 0 and seq1 != seq2:
        sys.exit("hive is dirty but no matching log entries were found")


if __name__ == "__main__":
    main()
