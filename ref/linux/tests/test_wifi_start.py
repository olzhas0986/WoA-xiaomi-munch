"""Exercise Wi-Fi startup refusal paths without touching the host's sysfs."""
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]

class WifiStartTests(unittest.TestCase):
    def run_helper(self, ready=False, firmware=False):
        source = (ROOT/'initramfs/init-pmos-wifi').read_text()
        script = source.split("<<'PMOS_MUNCH_WIFI'\n", 1)[1].split('\nPMOS_MUNCH_WIFI', 1)[0]
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            for name in ('pmos', 'sys/module/firmware_class/parameters', 'sys/bus/pci/devices'):
                (base/name).mkdir(parents=True, exist_ok=True)
            if ready:
                (base/'pmos/.pmos-munch-ready').touch()
            if firmware:
                (base/'pmos/usr/lib/firmware/ath11k/QCA6390/hw2.0').mkdir(parents=True)
            script = script.replace('/pmos', str(base/'pmos')).replace('/sys/', str(base/'sys')+'/')
            result = subprocess.run(['sh', '-c', script], text=True, capture_output=True)
            path = base/'sys/module/firmware_class/parameters/path'
            return result, path.read_text() if path.exists() else None

    def test_rootfs_must_be_loaded_first(self):
        result, path = self.run_helper()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Run pmos-load first', result.stdout)
        self.assertIsNone(path)

    def test_missing_firmware_does_not_rebind_device(self):
        result, path = self.run_helper(ready=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('firmware missing', result.stdout)
        self.assertIsNone(path)

    def test_missing_pci_device_is_not_reported_ready(self):
        result, path = self.run_helper(ready=True, firmware=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('not enumerated', result.stdout)
        self.assertIn('/pmos/usr/lib/firmware', path)
