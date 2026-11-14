import subprocess
import sys
import tempfile
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]

class CacheIsolationTests(unittest.TestCase):
    def test_seed_is_independent_and_requires_new_config(self):
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary)
            source = parent/'source cache'
            output = parent/'new cache'
            source.mkdir()
            (source/'.config').write_text('old config')
            (source/'Makefile').write_text('old output wrapper')
            (source/'object.o').write_bytes(b'original cache')
            command = [sys.executable, str(ROOT/'tools/seed-kernel-build.py'),
                       '--source', str(source), '--output', str(output)]
            subprocess.run(command, check=True, capture_output=True)
            self.assertFalse((output/'.config').exists())
            self.assertFalse((output/'Makefile').exists())
            self.assertEqual((source/'.config').read_text(), 'old config')
            self.assertNotEqual((source/'object.o').stat().st_ino,
                                (output/'object.o').stat().st_ino)
            (output/'object.o').write_bytes(b'new build')
            self.assertEqual((source/'object.o').read_bytes(), b'original cache')
            subprocess.run(command, check=True, capture_output=True)
            self.assertEqual((output/'object.o').read_bytes(), b'new build')
