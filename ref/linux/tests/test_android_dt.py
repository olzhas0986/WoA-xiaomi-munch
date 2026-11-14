"""Regression tests for live-tree directory pulls without an Android device."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(shutil.which('dtc') and shutil.which('fdtget'), 'needs host DT tools')
class AndroidDTTests(unittest.TestCase):
    def collect(self, layout, work):
        adb = work/'fake-adb'
        adb.write_text('''#!/usr/bin/env python3
import os
from pathlib import Path
import sys
a = sys.argv[1:]
if a == ['get-state']: print('device')
elif a == ['shell', 'getprop', 'ro.product.device']: print('munch')
elif a == ['shell', 'getprop', 'ro.build.fingerprint']: print('test/fixture')
elif a[:1] == ['exec-out'] and len(a) == 2 and os.environ['DT_LAYOUT'] == 'archive':
 import io,tarfile
 stream=io.BytesIO()
 with tarfile.open(fileobj=stream,mode='w') as tar:
  data=b'xiaomi,munch\\0'
  info=tarfile.TarInfo('./compatible');info.size=len(data)
  tar.addfile(info,io.BytesIO(data))
 sys.stdout.buffer.write(stream.getvalue())
elif a[:1] == ['exec-out']:
 print('Permission denied', file=sys.stderr); sys.exit(1)
elif a[:1] == ['pull']:
 p = Path(a[-1])
 if os.environ['DT_LAYOUT'] == 'nested': p /= 'base'
 p.mkdir(parents=True)
 if os.environ['DT_LAYOUT'] not in ('empty', 'archive'):
  (p/'compatible').write_bytes(b'xiaomi,munch\\0')
  (p/'model').write_bytes(b'test fixture\\0')
 else:
  (p/'soc').mkdir()
  (p/'soc'/'compatible').write_bytes(b'simple-bus\\0')
 print('fixture pull completed')
else: sys.exit(3)
''')
        adb.chmod(0o755)
        output = work/'published'
        result = subprocess.run(
            ['python3', str(ROOT/'tools/collect-android-dt.py'), '--adb', str(adb),
             '--output', str(output)], capture_output=True, text=True,
            env=dict(os.environ, DT_LAYOUT=layout))
        return result, output

    def test_direct_and_nested_pull_produce_real_root(self):
        for layout in ('direct', 'nested', 'archive'):
            with self.subTest(layout=layout), tempfile.TemporaryDirectory() as t:
                result, output = self.collect(layout, Path(t))
                self.assertEqual(result.returncode, 0, result.stderr)
                compatible = subprocess.check_output(
                    ['fdtget', str(output/'active.dtb'), '/', 'compatible'], text=True)
                self.assertEqual(compatible.strip(), 'xiaomi,munch')

    def test_missing_root_retains_evidence_without_publishing(self):
        with tempfile.TemporaryDirectory() as t:
            work = Path(t)
            result, output = self.collect('empty', work)
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(output.exists())
            self.assertIn('diagnostics retained', result.stderr)
            retained = list(work.glob('android-dt-*'))
            self.assertEqual(len(retained), 1)
            self.assertIn('fixture pull completed', (retained[0]/'adb-pull.log').read_text())
            self.assertTrue((retained[0]/'base/soc/compatible').exists())
