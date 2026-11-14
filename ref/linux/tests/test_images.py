import gzip
import importlib.util
import os
from pathlib import Path
import struct
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(os.environ.get('PMOS_MUNCH_OUT', ROOT/'out'))

def module(name):
    spec = importlib.util.spec_from_file_location(name, ROOT/'tools'/f'{name}.py')
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value

pack = module('pack')
initramfs = module('mkinitramfs')

class PackerTests(unittest.TestCase):
    def setUp(self):
        self.stub = (OUT/'loader.bin').read_bytes()
        self.dt = (OUT/'sm8250-xiaomi-munch.dtb').read_bytes()
        image = bytearray(64)
        struct.pack_into('<QQQ', image, 8, 0, 4096, 0xa)
        image[56:60] = b'ARM\x64'
        self.image = bytes(image)

    def test_payload_layout_and_reproducibility(self):
        a, entries = pack.build(self.stub, self.image, self.dt, b'initrd')
        b, _ = pack.build(self.stub, self.image, self.dt, b'initrd')
        self.assertEqual(a, b)
        self.assertEqual(a[0x100000:0x100008], b'PMUNCH01')
        self.assertEqual(entries[0][2], 4096)  # memory footprint, not file size
        for entry, expected in zip(entries, [self.image, self.dt, b'initrd']):
            start = 0x100000+entry[3]
            self.assertEqual(a[start:start+entry[1]], expected)
            self.assertEqual(entry[3] % 4096, 0)

    def test_reject_kernel_footprint_overlapping_dtb(self):
        image = bytearray(self.image)
        struct.pack_into('<Q', image, 16, 0x8000000)
        with self.assertRaisesRegex(ValueError, 'window'):
            pack.build(self.stub, image, self.dt)

    def test_reject_incompatible_text_offset(self):
        image = bytearray(self.image)
        struct.pack_into('<Q', image, 8, 0x80000)
        with self.assertRaisesRegex(ValueError, 'text_offset'):
            pack.build(self.stub, image, self.dt)

    def test_reject_reserved_destination(self):
        with tempfile.TemporaryDirectory() as temporary:
            dt = Path(temporary)/'bad.dtb'
            dt.write_bytes(self.dt)
            subprocess.run(['fdtput', '-c', str(dt), '/reserved-memory/test@c0200000'], check=True)
            subprocess.run(['fdtput', '-t', 'x', str(dt), '/reserved-memory/test@c0200000',
                            'reg', '0', 'c0200000', '0', '1000'], check=True)
            with self.assertRaisesRegex(ValueError, 'reserved'):
                pack.build(self.stub, self.image, dt.read_bytes())

    def test_reject_bad_magic_and_truncated_fdt(self):
        with self.assertRaises(ValueError):
            pack.build(self.stub, bytes(64), self.dt)
        for dt in [self.dt[:39], self.dt[:-1], b'bad!'+self.dt[4:]]:
            with self.assertRaises(ValueError):
                pack.build(self.stub, self.image, dt)

    def test_reject_huge_kernel_footprint(self):
        # Check upper bound with a large effective footprint without allocating a huge file.
        image = bytearray(self.image)
        struct.pack_into('<Q', image, 16, (1 << 64)-1)
        with self.assertRaises(ValueError):
            pack.build(self.stub, image, self.dt)

class InitramfsTests(unittest.TestCase):
    def test_static_elf_and_deterministic_archive(self):
        elf = bytearray(120)
        elf[:6] = b'\x7fELF\x02\x01'
        struct.pack_into('<H', elf, 16, 2)
        struct.pack_into('<H', elf, 18, 183)
        struct.pack_into('<Q', elf, 32, 64)
        struct.pack_into('<HH', elf, 54, 56, 1)
        struct.pack_into('<I', elf, 64, 1)
        rootfs = gzip.compress(b'rootfs fixture', mtime=0)
        a = initramfs.archive(elf, b'#!/bin/busybox sh\n', rootfs)
        self.assertEqual(a, initramfs.archive(elf, b'#!/bin/busybox sh\n', rootfs))
        raw = gzip.decompress(a)
        p, records = 0, {}
        while p < len(raw):
            self.assertEqual(raw[p:p+6], b'070701')
            fields = [int(raw[p+6+i*8:p+14+i*8], 16) for i in range(13)]
            n, size = fields[11], fields[6]
            name = raw[p+110:p+110+n-1].decode()
            p = (p+110+n+3)&~3
            records[name] = (fields, raw[p:p+size])
            p = (p+size+3)&~3
            if name == 'TRAILER!!!':
                break
        self.assertEqual(records['dev/console'][0][9:11], [5, 1])
        self.assertEqual(records['init'][1], b'#!/bin/busybox sh\n')
        self.assertEqual(records['rootfs.tar.gz'][1], rootfs)
        self.assertEqual(records['rootfs.tar.gz'][0][1], 0o100400)
        self.assertTrue(initramfs.archive(elf, b'init'))
        with self.assertRaisesRegex(ValueError, 'gzip'):
            initramfs.archive(elf, b'init', b'not gzip')
        struct.pack_into('<I', elf, 64, 3)
        with self.assertRaisesRegex(ValueError, 'static'):
            initramfs.archive(elf, b'init')

if __name__ == '__main__':
    unittest.main()

class InitramfsGpuTests(unittest.TestCase):
    def elf(self):
        elf = bytearray(120)
        elf[:6] = b'\x7fELF\x02\x01'
        struct.pack_into('<H', elf, 16, 2)
        struct.pack_into('<H', elf, 18, 183)
        struct.pack_into('<Q', elf, 32, 64)
        struct.pack_into('<HH', elf, 54, 56, 1)
        struct.pack_into('<I', elf, 64, 1)
        return elf

    def test_zap_is_staged_at_kernel_default_firmware_path(self):
        files = {'a650_zap.mbn': b'header fixture', 'a650_zap.b02': b'segment fixture'}
        a = initramfs.archive(self.elf(), b'init', gpu_zap=files)
        self.assertEqual(a, initramfs.archive(self.elf(), b'init', gpu_zap=files))
        raw = gzip.decompress(a)
        self.assertIn(b'lib/firmware/qcom/sm8250/xiaomi/munch/a650_zap.mbn\0', raw)
        self.assertIn(b'segment fixture', raw)
        self.assertNotIn(b'rootfs.tar.gz\0', raw)

    def test_zap_mapping_rejects_other_names_and_traversal(self):
        for files in ({'../init': b'bad'}, {'a650_zap.mbn': b'header', 'a650_gmu.bin': b'other'}):
            with self.assertRaises(ValueError):
                initramfs.archive(self.elf(), b'init', gpu_zap=files)
