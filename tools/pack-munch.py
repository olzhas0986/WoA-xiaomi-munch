#!/usr/bin/env python3
"""Build a temporary Android boot-v1 image containing the fresh diagnostic FD."""
import gzip
import argparse
import hashlib
import json
import struct
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'out/munch-fresh'
FD = ROOT / 'Mu-Silicium/Build/munchFreshPkg/DEBUG_CLANGPDB/FV/SILICIUM_UEFI.fd'
DTB = ROOT / 'inputs/munch/live.dtb'

def sha(data):
    return hashlib.sha256(data).hexdigest()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, default=OUT / 'munch-uefi.img')
    args = parser.parse_args()
    fd, dtb = FD.read_bytes(), DTB.read_bytes()
    if len(fd) != 0x300000:
        raise SystemExit('Unexpected FD size')
    OUT.mkdir(parents=True, exist_ok=True)
    subprocess.run(['clang', '--target=aarch64-linux-gnu', '-c',
                    str(ROOT / 'firmware/munch/bootshim.S'), '-DFD_BASE=0x9FC00000',
                    '-DFD_SIZE=0x300000', '-o', str(OUT / 'shim.o')], check=True)
    subprocess.run(['llvm-objcopy', '-O', 'binary', str(OUT / 'shim.o'),
                    str(OUT / 'shim.bin')], check=True)
    shim = (OUT / 'shim.bin').read_bytes()
    kernel = gzip.compress(shim + fd, mtime=0) + dtb
    (OUT / 'kernel.bin').write_bytes(kernel)
    name = b'TRAILER!!!\0'
    cpio = b'070701' + b''.join(f'{v:08x}'.encode() for v in
                              [0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, len(name), 0]) + name
    cpio += b'\0' * (-len(cpio) % 4)
    ramdisk = gzip.compress(cpio, mtime=0)
    (OUT / 'ramdisk.gz').write_bytes(ramdisk)
    image = args.output.resolve()
    image.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(['mkbootimg', '--kernel', str(OUT / 'kernel.bin'),
                    '--ramdisk', str(OUT / 'ramdisk.gz'), '--header_version', '1',
                    '--board', 'MUNCHFRESH1', '-o', str(image)], check=True)
    # Independently parse the packaged header and compare the exact payload bytes.
    packed = image.read_bytes()
    magic, kernel_size, _, ramdisk_size, _, _, _, _, page, version = struct.unpack_from('<8s9I', packed)
    assert magic == b'ANDROID!' and version == 1
    assert kernel_size == len(kernel) and ramdisk_size == len(ramdisk)
    assert packed[page:page + kernel_size] == kernel
    ramdisk_offset = page + (kernel_size + page - 1) // page * page
    assert packed[ramdisk_offset:ramdisk_offset + ramdisk_size] == ramdisk
    decoder = __import__('zlib').decompressobj(16 + __import__('zlib').MAX_WBITS)
    raw = decoder.decompress(kernel) + decoder.flush()
    assert raw == shim + fd and decoder.unused_data == dtb
    assert raw[56:60] == b'ARM\x64'
    report = {'image_sha256': sha(packed), 'image_size': len(packed),
              'fd_sha256': sha(fd), 'dtb_sha256': sha(dtb), 'shim_sha256': sha(shim),
              'shim_size': len(shim), 'boot_header_version': version,
              'profile': 'munchFreshPkg', 'device_tested': False,
              'purpose': 'UEFI diagnostic; no operating system or disk write commands',
              'acpi': 'Stable CPU namespace; Windows peripheral support remains incomplete'}
    image.with_suffix('.img.json').write_text(json.dumps(report, indent=2) + '\n')
    print(image)
    print('SHA256:', report['image_sha256'])

if __name__ == '__main__':
    main()
