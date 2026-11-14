#!/usr/bin/env python3
"""Build a v1 payload, then optionally wrap it in Android boot image v3."""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import tempfile

DEST = (0xc0200000, 0xc8000000, 0xc8400000)
LIMIT = (0xc8000000, 0xc8200000, 0xffc00000)
PAYLOAD_OFFSET = 0x100000

def require(ok, message):
    if not ok:
        raise ValueError(message)

def fdt_map(blob):
    require(len(blob) >= 40, 'FDT header truncated')
    magic, total, so, st, ro, ver, compat, cpu, ss, sz = struct.unpack_from('>10I', blob)
    require(magic == 0xd00dfeed and total == len(blob) and total <= 0x200000,
            'FDT magic/total size (maximum 2 MiB)')
    require(ver == 17 and compat <= 17, 'FDT version')
    require(so % 4 == 0 and ro % 8 == 0 and so >= 40 and st >= 40 and ro >= 40,
            'FDT block alignment/offset')
    require(so+sz <= total and st+ss <= total, 'FDT blocks outside file')
    strings = blob[st:st+ss]
    nodes, stack, p = {}, [], so
    end = so+sz
    while p < end:
        require(p+4 <= end, 'FDT token truncated')
        token, = struct.unpack_from('>I', blob, p)
        p += 4
        if token == 1:
            e = blob.find(b'\0', p, end)
            require(e >= p, 'FDT node name')
            stack.append(blob[p:e].decode('ascii'))
            nodes['/'.join(stack)] = {}
            p = (e+4) & ~3
        elif token == 2:
            require(bool(stack), 'FDT nesting')
            stack.pop()
        elif token == 3:
            require(stack and p+8 <= end, 'FDT property header')
            n, o = struct.unpack_from('>II', blob, p)
            p += 8
            require(p+n <= end and o < len(strings), 'FDT property bounds')
            e = strings.find(b'\0', o)
            require(e >= o, 'FDT string')
            key = strings[o:e].decode('ascii')
            require(key not in nodes['/'.join(stack)], 'duplicate FDT property')
            nodes['/'.join(stack)][key] = blob[p:p+n]
            p = (p+n+3) & ~3
        elif token == 4:
            pass
        elif token == 9:
            require(not stack, 'unclosed FDT nodes')
            break
        else:
            raise ValueError('unknown FDT token')
    else:
        raise ValueError('missing FDT_END')
    def cells(props, key):
        require(props.get(key) == struct.pack('>I', 2), key+' must be 2')
    cells(nodes[''], '#address-cells')
    cells(nodes[''], '#size-cells')
    cells(nodes['/reserved-memory'], '#address-cells')
    cells(nodes['/reserved-memory'], '#size-cells')
    require(nodes['/reserved-memory'].get('ranges') == b'', 'reserved-memory ranges')
    def regions(data):
        require(len(data) % 16 == 0, 'invalid 64-bit reg tuples')
        result = list(struct.iter_unpack('>QQ', data))
        for a, n in result:
            require(n > 0 and a+n <= 1 << 64, 'invalid physical range')
        return result
    ram, reserved = [], []
    for path, props in nodes.items():
        if path.count('/') == 1 and props.get('device_type') == b'memory\0':
            ram += regions(props['reg'])
        if path.startswith('/reserved-memory/'):
            if 'reg' in props:
                reserved += regions(props['reg'])
            elif 'size' in props:
                # Linux allocates this after reserving Image, DTB and initrd.
                # Validate constraints; it has no physical destination yet.
                require(len(props['size']) == 8, 'dynamic reservation size cells')
                size, = struct.unpack('>Q', props['size'])
                ranges = regions(props.get('alloc-ranges', b''))
                require(size > 0 and ranges and any(n >= size for _, n in ranges),
                        'invalid dynamic allocation constraints')
    reserve_start = ro
    while True:
        require(ro+16 <= total, 'FDT reserve map truncated')
        a, n = struct.unpack_from('>QQ', blob, ro)
        ro += 16
        if not (a or n):
            break
        require(n and a+n <= 1 << 64, 'invalid memreserve')
        reserved.append((a, n))
    require(not intersects(so, sz, st, ss) and
            not intersects(reserve_start, ro-reserve_start, so, sz) and
            not intersects(reserve_start, ro-reserve_start, st, ss), 'FDT blocks overlap')
    require(bool(ram), 'no RAM nodes')
    return ram, reserved

def intersects(a, n, b, m):
    return a < b+m and b < a+n

def build(stub, image, dtb, initrd=None):
    require(64 <= len(stub) <= PAYLOAD_OFFSET, 'loader size')
    require(stub[56:60] == b'ARM\x64', 'loader Image magic')
    stub_offset, stub_mem = struct.unpack_from('<QQ', stub, 8)
    require(stub_offset == 0 and len(stub) <= stub_mem <= PAYLOAD_OFFSET,
            'loader runtime footprint exceeds payload offset')
    require(len(image) >= 64 and image[56:60] == b'ARM\x64', 'Linux Image magic')
    text_offset, image_size, flags = struct.unpack_from('<QQQ', image, 8)
    require(image_size >= len(image) and image_size > 0, 'Image image_size')
    require(not flags & 1 and flags & 8, 'require LE Image with placement flag bit 3')
    require(text_offset <= DEST[0] and (DEST[0]-text_offset) % 0x200000 == 0,
            'Image text_offset is incompatible with fixed kernel address')
    ram, reserved = fdt_map(dtb)
    blobs = [image, dtb] + ([initrd] if initrd is not None else [])
    sizes = [image_size, len(dtb)] + ([len(initrd)] if initrd is not None else [])
    entries, data, offset = [], bytearray(), 4096
    for i, (blob, memory_size) in enumerate(zip(blobs, sizes)):
        addr = DEST[i]
        require(len(blob) > 0 and memory_size <= LIMIT[i]-addr, 'payload exceeds destination window')
        require(any(a <= addr and addr+memory_size <= a+n for a, n in ram), 'payload outside RAM')
        require(not any(intersects(addr, memory_size, a, n) for a, n in reserved),
                'payload overlaps reserved RAM')
        entries.append((addr, len(blob), memory_size, offset))
        data += blob
        data += bytes(-len(data) % 4096)
        offset = 4096+len(data)
    require(offset <= 0x10000000, 'payload exceeds loader v1 limit')
    if initrd is not None:
        # Stronger than the protocol: kernel and initrd fit in the same 1 GiB window.
        require((DEST[0] >> 30) == ((DEST[2]+len(initrd)-1) >> 30), 'initrd placement window')
    header = b'PMUNCH01'+struct.pack('<5Q', 1, len(entries), offset, DEST[0], DEST[1])
    header += b''.join(struct.pack('<4Q', *e) for e in entries)
    payload = header+bytes(4096-len(header))+data
    return stub+bytes(PAYLOAD_OFFSET-len(stub))+payload, entries

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--loader', required=True, type=Path)
    p.add_argument('--image', required=True, type=Path)
    p.add_argument('--dtb', required=True, type=Path)
    p.add_argument('--initramfs', type=Path)
    p.add_argument('--output', required=True, type=Path)
    p.add_argument('--boot-image', type=Path)
    a = p.parse_args()
    try:
        with tempfile.TemporaryDirectory() as temporary:
            dt = Path(temporary)/'board.dtb'
            dt.write_bytes(a.dtb.read_bytes())
            if a.initramfs:
                n = a.initramfs.stat().st_size
                for prop, value in [('linux,initrd-start', DEST[2]), ('linux,initrd-end', DEST[2]+n)]:
                    subprocess.run(['fdtput', '-t', 'x', str(dt), '/chosen', prop,
                                    f'{value >> 32:x}', f'{value & 0xffffffff:x}'], check=True)
            else:
                # Reject stale initrd references rather than booting unrelated RAM.
                for prop in ['linux,initrd-start', 'linux,initrd-end']:
                    result = subprocess.run(['fdtget', str(dt), '/chosen', prop], capture_output=True)
                    require(result.returncode != 0, 'DT contains initrd references without initramfs')
            blob, entries = build(a.loader.read_bytes(), a.image.read_bytes(), dt.read_bytes(),
                                  a.initramfs.read_bytes() if a.initramfs else None)
        a.output.parent.mkdir(parents=True, exist_ok=True)
        a.output.write_bytes(blob)
        if a.boot_image:
            subprocess.run(['mkbootimg', '--header_version', '3', '--kernel', str(a.output),
                            '--os_version', '14.0.0', '--os_patch_level', '2024-01',
                            '-o', str(a.boot_image)], check=True)
        dtb_entry = entries[1]
        start = PAYLOAD_OFFSET+dtb_entry[3]
        manifest = {'format': 'PMUNCH01', 'entries': entries,
                    'packed_dtb_sha256': hashlib.sha256(blob[start:start+dtb_entry[1]]).hexdigest(),
                    'inputs': {str(path): hashlib.sha256(path.read_bytes()).hexdigest()
                               for path in [a.loader, a.image, a.dtb, a.initramfs] if path},
                    'outputs': {str(path): hashlib.sha256(path.read_bytes()).hexdigest()
                                for path in [a.output, a.boot_image] if path}}
        a.output.with_suffix('.json').write_text(json.dumps(manifest, indent=2)+'\n')
        print(json.dumps(manifest, indent=2))
    except (ValueError, KeyError, UnicodeError, struct.error, OSError, subprocess.CalledProcessError) as error:
        p.exit(1, f'pack: {error}\n')
if __name__ == '__main__':
    main()
