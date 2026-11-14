"""Exercise the delayed launcher without accessing host DRM or mounts."""
from pathlib import Path
import os
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT/'initramfs/init-pmos-display').read_text()


def helper(marker):
    return SOURCE.split("<<'"+marker+"'\n", 1)[1].split('\n'+marker, 1)[0]


class DesktopTests(unittest.TestCase):
    def test_all_new_helpers_parse(self):
        for marker in ('PMOS_MUNCH_DESKTOP', 'PMOS_MUNCH_DESKTOP_START', 'PMOS_MUNCH_SAVE_START'):
            subprocess.run(['sh', '-n'], input=helper(marker), text=True, check=True)

    def test_save_refuses_internal_storage(self):
        result = subprocess.run(['sh', '-c', (ROOT/'phone/pmos-save-current').read_text(), 'sh', '/dev/sda/../../sdc'], text=True, capture_output=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('expected USB', result.stdout+result.stderr)

    def test_worker_waits_then_uses_connected_card(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            (p/'pmos').mkdir(); (p/'pmos/.pmos-munch-ready').touch()
            (p/'drm/card7-DSI-1').mkdir(parents=True)
            (p/'drm/card7-DSI-1/status').write_text('connected\n')
            (p/'bin').mkdir()
            for name, body in {
                'pidof':'exit 1',
                'gpu-prepare':'echo gpu >> "$CALL_LOG"',
                'sleep':'echo "sleep $*" >> "$CALL_LOG"',
                'pmos-enter':'echo "enter $*" >> "$CALL_LOG"',
            }.items():
                f=p/'bin'/name; f.write_text('#!/bin/sh\n'+body+'\n'); f.chmod(0o755)
            script=helper('PMOS_MUNCH_DESKTOP').replace('/pmos/', str(p/'pmos')+'/')
            script=script.replace('/sys/class/drm/', str(p/'drm')+'/')
            for name in ('pmos-enter','gpu-prepare'):
                script=script.replace('/bin/'+name,str(p/'bin'/name))
            script=script.replace('/run/desktop-start.lock',str(p/'lock'))
            env=dict(os.environ,PATH=str(p/'bin')+':'+os.environ['PATH'],CALL_LOG=str(p/'calls'))
            subprocess.run(['sh','-c',script],env=env,check=True,capture_output=True)
            calls=(p/'calls').read_text()
            self.assertLess(calls.index('sleep 10'),calls.index('Starting Weston'))
            self.assertIn('sh card7',calls)

    def test_launcher_refuses_arguments(self):
        result=subprocess.run(['sh','-c',helper('PMOS_MUNCH_DESKTOP_START'),'sh','extra'],text=True,capture_output=True)
        self.assertNotEqual(result.returncode,0)
        self.assertIn('Usage: desktop-start',result.stdout)
