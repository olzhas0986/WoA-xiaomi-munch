"""Offline Qualcomm ZAP container checks; no claim of signature authentication."""
import importlib.util
from pathlib import Path
import struct
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('adreno_fw', Path(__file__).resolve().parents[1]/'tools/stage-adreno-firmware.py')
fw = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fw)


def image(memory=4096):
    b = bytearray(52+3*32)
    b[:7] = b'\x7fELF\x01\x01\x01'
    struct.pack_into('<I', b, 28, 52)
    struct.pack_into('<HH', b, 42, 32, 3)
    struct.pack_into('<8I', b, 52, 0, 0, 0, 0, 52, 0, 0, 0)
    struct.pack_into('<8I', b, 84, 0, 0, 0, 0, 1, 0, 0x02000000, 0)
    struct.pack_into('<8I', b, 116, 1, 4096, 0, 0x8681a000, 4, memory, 0, 4096)
    return bytes(b)


class AdrenoFirmwareTests(unittest.TestCase):
    def test_split_dump_keeps_binary_and_segment_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            (p/'a650_zap.mdt').write_bytes(image())
            (p/'a650_zap.b02').write_bytes(b'zap!')
            files, size = fw.inspect(p)
            self.assertEqual(files['a650_zap.mbn'], image())
            self.assertEqual(files['a650_zap.b02'], b'zap!')
            self.assertEqual(size, 4096)

    def test_missing_split_segment_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            (p/'a650_zap.mdt').write_bytes(image())
            with self.assertRaisesRegex(ValueError, 'split segment'):
                fw.inspect(p)

    def test_oversized_image_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            (p/'a650_zap.mdt').write_bytes(image(12288))
            (p/'a650_zap.b02').write_bytes(b'zap!')
            with self.assertRaisesRegex(ValueError, '8192'):
                fw.inspect(p)

    def test_not_an_elf_image_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            (p/'a650_zap.mbn').write_bytes(b'not firmware')
            with self.assertRaisesRegex(ValueError, 'ELF32'):
                fw.inspect(p)
