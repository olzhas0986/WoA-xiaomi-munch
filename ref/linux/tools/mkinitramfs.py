#!/usr/bin/env python3
"""Deterministic newc + gzip, with explicit static ARM64 BusyBox input."""
import argparse
import gzip
from pathlib import Path, PurePosixPath
import struct
import re

def inspect_modules(directory):
    """Read a staged module release without following host build/source links."""
    if directory.is_symlink() or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.+-]*', directory.name):
        raise ValueError('invalid kernel module release')
    files = {}
    for path in sorted(directory.rglob('*')):
        relative = path.relative_to(directory).as_posix()
        if path.is_symlink():
            if relative in ('build', 'source'):
                continue
            raise ValueError('unexpected symlink in kernel modules: '+relative)
        if path.is_file():
            files[relative] = path.read_bytes()
    return directory.name, files

def archive(busybox, init, rootfs=None, gpu_zap=None, phone_tools=None, native_tools=None,
            kernel_modules=None):
    if len(busybox) < 64 or busybox[:6] != b'\x7fELF\x02\x01' or struct.unpack_from('<H', busybox, 18)[0] != 183:
        raise ValueError('BusyBox must be ELF64 little-endian AArch64')
    if struct.unpack_from('<H', busybox, 16)[0] != 2:
        raise ValueError('BusyBox must be an ET_EXEC static executable')
    phoff = struct.unpack_from('<Q', busybox, 32)[0]
    phsize, phnum = struct.unpack_from('<HH', busybox, 54)
    if phsize != 56 or not phnum or phoff < 64 or phoff+phsize*phnum > len(busybox):
        raise ValueError('invalid ELF program headers')
    load_segments = 0
    for i in range(phnum):
        kind = struct.unpack_from('<I', busybox, phoff+i*phsize)[0]
        load_segments += kind == 1
        if kind in (2, 3):
            raise ValueError('BusyBox must be static (no PT_DYNAMIC/PT_INTERP)')
    if not load_segments:
        raise ValueError('BusyBox has no PT_LOAD segment')
    output = bytearray()
    def entry(name, mode, data=b'', rmajor=0, rminor=0):
        name = name.encode()+b'\0'
        values = (entry.ino, mode, 0, 0, 1, 0, len(data), 0, 0, rmajor, rminor, len(name), 0)
        output.extend(b'070701'+b''.join(f'{v:08x}'.encode() for v in values)+name)
        output.extend(bytes(-len(output) % 4))
        output.extend(data)
        output.extend(bytes(-len(output) % 4))
        entry.ino += 1
    entry.ino = 1
    for name in ['dev', 'proc', 'sys', 'tmp', 'run', 'etc', 'bin', 'sbin']:
        entry(name, 0o40755)
    entry('dev/console', 0o20600, rmajor=5, rminor=1)
    entry('dev/null', 0o20666, rmajor=1, rminor=3)
    entry('bin/busybox', 0o100755, busybox)
    entry('init', 0o100755, init)
    if phone_tools is not None:
        allowed = {'phosh-start', 'phosh-session', 'xiaomi,munch.json', 'pmos-connect', 'pmos-save-current'}
        if set(phone_tools) != allowed:
            raise ValueError('phone tools must contain the reviewed phone helper files')
        entry('etc/pmos-munch', 0o40755)
        for name, data in sorted(phone_tools.items()):
            entry('etc/pmos-munch/'+name, 0o100644, data)
    if native_tools is not None:
        allowed = {'stage', 'prepare', 'firmware', 'phosh', 'console',
                   'service-firmware', 'service-seatd', 'service-phosh'}
        if set(native_tools) != allowed:
            raise ValueError('native tools must contain the reviewed native boot files')
        if phone_tools is None:
            raise ValueError('native boot requires the phone helpers')
        entry('etc/pmos-munch/native', 0o40755)
        for name, data in sorted(native_tools.items()):
            entry('etc/pmos-munch/native/'+name, 0o100644, data)
    if kernel_modules is not None:
        if native_tools is None:
            raise ValueError('kernel modules require native boot')
        release, files = kernel_modules
        if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.+-]*', release):
            raise ValueError('invalid kernel module release')
        if not files.get('modules.dep') or not files.get('modules.alias'):
            raise ValueError('depmod metadata missing')
        required = {'ath11k.ko', 'ath11k_pci.ko', 'cfg80211.ko', 'mac80211.ko',
                    'pci-pwrctrl-pwrseq.ko'}
        for name, data in files.items():
            path = PurePosixPath(name)
            if not path.parts or path.is_absolute() or '..' in path.parts or path.as_posix() != name:
                raise ValueError('unsafe module archive path')
            if name.endswith('.ko'):
                if (len(data) < 64 or data[:6] != b'\x7fELF\x02\x01' or
                        struct.unpack_from('<HH', data, 16) != (1, 183)):
                    raise ValueError('kernel module must be ELF64 AArch64 ET_REL')
                if b'vermagic='+release.encode()+b' ' not in data:
                    raise ValueError('kernel module release mismatch')
                required.discard(path.name)
        if required:
            raise ValueError('Wi-Fi modules missing: '+', '.join(sorted(required)))
        entry('etc/pmos-munch/modules.release', 0o100644, release.encode()+b'\n')
        base = 'etc/pmos-munch/kernel-modules'
        entry(base, 0o40755)
        directories = set()
        for name in files:
            for parent in PurePosixPath(name).parents:
                if str(parent) != '.':
                    directories.add(str(parent))
        for name in sorted(directories, key=lambda x: (x.count('/'), x)):
            entry(base+'/'+name, 0o40755)
        for name, data in sorted(files.items()):
            entry(base+'/'+name, 0o100644, data)
    if rootfs is not None:
        if not rootfs.startswith(b'\x1f\x8b'):
            raise ValueError('embedded rootfs must be gzip-compressed')
        entry('rootfs.tar.gz', 0o100400, rootfs)
    if gpu_zap is not None:
        if 'a650_zap.mbn' not in gpu_zap or any(not re.fullmatch(r'a650_zap\.(?:mbn|b[0-9]{2})', name) for name in gpu_zap):
            raise ValueError('GPU ZAP mapping must contain a650_zap.mbn and only its split files')
        directories = ['lib', 'lib/firmware', 'lib/firmware/qcom',
                       'lib/firmware/qcom/sm8250', 'lib/firmware/qcom/sm8250/xiaomi',
                       'lib/firmware/qcom/sm8250/xiaomi/munch']
        for directory in directories:
            entry(directory, 0o40755)
        for name, content in sorted(gpu_zap.items()):
            entry(directories[-1]+'/'+name, 0o100644, content)
    entry('TRAILER!!!', 0)
    return gzip.compress(bytes(output), compresslevel=9, mtime=0)

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--busybox', type=Path, required=True)
    p.add_argument('--init', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--rootfs', type=Path, help='embed an inspected gzip tar as /rootfs.tar.gz')
    p.add_argument('--gpu-zap', type=Path, help='validated A650 ZAP staging directory (small GPU bootstrap only)')
    p.add_argument('--phone-tools', type=Path, help='reviewed phone helper directory')
    p.add_argument('--native-tools', type=Path, help='reviewed native OpenRC boot helpers')
    p.add_argument('--kernel-modules', type=Path, help='depmod-ready staged module release directory')
    a = p.parse_args()
    try:
        zap = None
        if a.gpu_zap:
            import importlib.util
            spec = importlib.util.spec_from_file_location('adreno_firmware', Path(__file__).with_name('stage-adreno-firmware.py'))
            validator = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(validator)
            zap, _ = validator.inspect(a.gpu_zap)
        phone = {name: (a.phone_tools/name).read_bytes() for name in
                 ('phosh-start', 'phosh-session', 'xiaomi,munch.json', 'pmos-connect', 'pmos-save-current')} if a.phone_tools else None
        native = {name: (a.native_tools/name).read_bytes() for name in
                  ('stage', 'prepare', 'firmware', 'phosh', 'console',
                   'service-firmware', 'service-seatd', 'service-phosh')} if a.native_tools else None
        data = archive(a.busybox.read_bytes(), a.init.read_bytes(),
                       a.rootfs.read_bytes() if a.rootfs else None, zap, phone, native,
                       inspect_modules(a.kernel_modules) if a.kernel_modules else None)
        a.output.parent.mkdir(parents=True, exist_ok=True)
        a.output.write_bytes(data)
    except (ValueError, OSError, struct.error) as error:
        p.exit(1, f'initramfs: {error}\n')
if __name__ == '__main__':
    main()
