#!/usr/bin/env python3
"""Validate/stage a munch Android A650 ZAP dump; never access phone partitions."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import struct


def inspect(source):
    candidates = [source/name for name in ('a650_zap.mbn', 'a650_zap.mdt') if (source/name).is_file()]
    if len(candidates) != 1:
        raise ValueError('provide exactly one a650_zap.mbn or a650_zap.mdt from this munch')
    header = candidates[0]
    data = header.read_bytes()
    if len(data) < 52 or data[:7] != b'\x7fELF\x01\x01\x01':
        raise ValueError('ZAP must be a little-endian ELF32 image')
    phoff = struct.unpack_from('<I', data, 28)[0]
    phsize, count = struct.unpack_from('<HH', data, 42)
    if phsize != 32 or count < 2 or phoff+count*32 > len(data):
        raise ValueError('invalid ELF program header bounds')
    files = {'a650_zap.mbn': data}
    for path in source.iterdir():
        if re.fullmatch(r'a650_zap\.b[0-9]{2}', path.name) and path.is_file():
            files[path.name] = path.read_bytes()
    low, high, loads, signed = 2**32, 0, 0, False
    for index in range(count):
        kind, offset, _, address, size, memory, flags, _ = struct.unpack_from('<8I', data, phoff+index*32)
        if flags & 0x07000000 == 0x02000000:
            signed = True
            continue
        if kind != 1 or not memory:
            continue
        if size > memory or address+memory > 2**32:
            raise ValueError('invalid load segment size/address')
        if size and offset+size > len(data):
            segment = files.get(f'a650_zap.b{index:02d}')
            if segment is None or len(segment) != size:
                raise ValueError(f'missing/truncated split segment a650_zap.b{index:02d}')
        low = min(low, address)
        high = max(high, (address+memory+4095) & ~4095)
        loads += 1
    if not signed or not loads:
        raise ValueError('missing Qualcomm hash segment or loadable program')
    if high-low > 8192:
        raise ValueError('ZAP exceeds the existing 8192-byte gpu_mem reservation')
    return files, high-low


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    try:
        files, memory = inspect(args.source)
        args.output.mkdir(parents=True, exist_ok=False)
        for name, data in files.items():
            (args.output/name).write_bytes(data)
        report = {'source': str(args.source.resolve()), 'reserved_bytes_required': memory,
                  'files': {name: hashlib.sha256(data).hexdigest() for name, data in files.items()},
                  'limitation': 'ELF/layout checks only; TrustZone authenticates signature on phone. Source must be this munch.'}
        (args.output/'manifest.json').write_text(json.dumps(report, indent=2)+'\n')
        print(json.dumps(report, indent=2))
    except (OSError, ValueError) as error:
        parser.exit(1, f'adreno-firmware: {error}\n')

if __name__ == '__main__':
    main()
