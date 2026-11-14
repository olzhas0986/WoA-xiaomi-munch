"""Exercise USB wait/read-only/cleanup behavior without real mounts or sleeps."""
from pathlib import Path
import os
import subprocess
import signal
import shlex
import time
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]

class PmosUsbTests(unittest.TestCase):
    init_name = "init-pmos-usb"
    def exercise(self, hash_exit=0, tar_exit=0, archive=True, detached=False, checksum="a"*64):
        body = (ROOT/'initramfs'/self.init_name).read_text().split("<<'PMOS_MUNCH_HELPER'\n", 1)[1].split('\nPMOS_MUNCH_HELPER', 1)[0]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name in ['bin', 'dev', 'proc', 'mnt/usb', 'run/load.lock']:
                (root/name).mkdir(parents=True)
            (root/'dev/sda1').touch()
            (root/'proc/mounts').touch()
            (root/'proc/meminfo').write_text('MemAvailable: 5000000 kB\n')
            (root/'sys/bus/usb/devices/1-1:1.0/host0/target0/0:0/block/sda').mkdir(parents=True)
            if archive:
                (root/'mnt/usb/postmarketos-aarch64-console.tar.gz').touch()
                if checksum is not None:
                    (root/'mnt/usb/postmarketos-aarch64-console.tar.gz.sha256').write_text(checksum+'  postmarketos-aarch64-console.tar.gz\n')
            # Only the filesystem paths and block-file predicate are substituted.
            body = body.replace('/mnt/pmos-usb', str(root/'mnt/usb'))
            body = body.replace('/run/pmos-load', str(root/'run/load'))
            for path in ['/sys/bus/usb/devices', '/proc/mounts', '/proc/meminfo', '/dev/sd', '/pmos']:
                body = body.replace(path, str(root)+path)
            body = body.replace('[ -b "$device" ]', '[ -e "$device" ]')
            body = body.replace('export PATH=/bin:/sbin', 'export PATH='+shlex.quote(str(root/'bin')+':'+os.defpath+':/usr/sbin:/sbin'))
            (root/'load').write_text(body)
            (root/'load').chmod(0o755)
            stubs = {
                'sleep': 'echo "sleep $*" >> "$LOG"\n',
                'mount': 'echo "mount $*" >> "$LOG"\n',
                'umount': 'echo "umount $*" >> "$LOG"\n',
                'sha256sum': 'cat >/dev/null\necho hash >> "$LOG"\nexit "$HASH_EXIT"\n',
                'tar': '''echo extract >> "$LOG"
[ "$TAR_EXIT" = 0 ] || exit "$TAR_EXIT"
mkdir -p "$RAMROOT/bin" "$RAMROOT/etc"
printf '#!/bin/sh\\n' > "$RAMROOT/bin/bash"
chmod +x "$RAMROOT/bin/bash"
touch "$RAMROOT/etc/os-release"
''',
            }
            for name, code in stubs.items():
                path = root/'bin'/name
                path.write_text('#!/bin/sh\n'+code)
                path.chmod(0o755)
            if detached:
                sleep_stub = root/'bin/sleep'
                sleep_stub.write_text(sleep_stub.read_text()+'/bin/sleep 0.3\n')
            log = root/'log'
            env = dict(os.environ, LOG=str(log), RAMROOT=str(root/'pmos'), HASH_EXIT=str(hash_exit), TAR_EXIT=str(tar_exit))
            if detached:
                launcher = (ROOT/'initramfs'/self.init_name).read_text().split("<<'PMOS_MUNCH_HELPER'\n")[2].split('\nPMOS_MUNCH_HELPER', 1)[0]
                launcher = launcher.replace('/bin/pmos-usb-worker', str(root/'load'))
                launcher = launcher.replace('/dev/console', str(root/'console'))
                launcher = launcher.replace('/run/pmos-load', str(root/'run/load'))
                launcher = launcher.replace('/pmos', str(root/'pmos'))
                launcher = launcher.replace('/dev/sd', str(root/'dev/sd'))
                launcher = launcher.replace('export PATH=/bin:/sbin', 'export PATH='+shlex.quote(str(root/'bin')+':'+os.defpath+':/usr/sbin:/sbin'))
                (root/'launcher').write_text(launcher)
                # The real launcher takes the lock; the direct-worker fixture
                # created it above for other tests.
                (root/'run/load.lock').rmdir()
                parent = subprocess.Popen(['sh', '-c', 'sh "$1"; /bin/sleep 30', 'sh', str(root/'launcher')], env=env, start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                try:
                    deadline = time.monotonic()+5
                    while not log.exists() and time.monotonic()<deadline:
                        time.sleep(0.01)
                    self.assertTrue(log.exists(), 'detached worker did not start')
                    os.killpg(parent.pid, signal.SIGHUP)
                    parent.wait(timeout=5)
                    self.assertNotEqual(parent.returncode, 0)
                    while (not (root/'run/load.status').exists() or (root/'run/load.lock').exists()) and time.monotonic()<deadline:
                        time.sleep(0.01)
                    status = int((root/'run/load.status').read_text())
                    result = subprocess.CompletedProcess([], status, '', '')
                finally:
                    if parent.poll() is None:
                        os.killpg(parent.pid, signal.SIGKILL)
                        parent.wait()
            else:
                result = subprocess.run(['sh', str(root/'load')], env=env, capture_output=True, text=True)
            self.assertFalse((root/'run/load.lock').exists(), 'worker must release its lock: '+result.stderr)
            self.assertEqual((root/'run/load.status').read_text().strip(), str(result.returncode))
            return result, log.read_text().splitlines(), (root/'pmos/.pmos-munch-ready').exists()

    def test_default_sda1_waits_ten_seconds_then_loads_read_only(self):
        result, log, ready = self.exercise()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(log[0], 'sleep 10')
        self.assertIn('-t ntfs3 -o ro,nosuid,nodev,noexec ', log[1])
        self.assertIn('/dev/sda1 ', log[1])
        self.assertEqual(log[2], 'hash')
        self.assertTrue(log[3].startswith('mount -t tmpfs '))
        self.assertEqual(log[4], 'extract')
        self.assertTrue(log[5].startswith('umount '))
        self.assertTrue(ready)

    def test_bad_hash_unmounts_usb_without_extraction(self):
        result, log, ready = self.exercise(hash_exit=1)
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn('extract', log)
        self.assertFalse(any('-t tmpfs ' in line for line in log))
        self.assertTrue(log[-1].startswith('umount '))
        self.assertFalse(ready)

    def test_missing_archive_unmounts_usb(self):
        result, log, ready = self.exercise(archive=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn('hash', log)
        self.assertTrue(log[-1].startswith('umount '))
        self.assertFalse(ready)

    def test_extraction_failure_does_not_publish_ready(self):
        result, log, ready = self.exercise(tar_exit=1)
        self.assertNotEqual(result.returncode, 0)
        self.assertTrue(log[-1].startswith('umount '))
        self.assertFalse(ready)

    def test_worker_survives_parent_terminal_session_hangup(self):
        result, log, ready = self.exercise(detached=True)
        self.assertEqual(result.returncode, 0)
        self.assertTrue(ready)
        self.assertIn('extract', log)


class PmosWifiUsbTests(PmosUsbTests):
    init_name = "init-pmos-wifi"

    def test_missing_checksum_prevents_extraction(self):
        result, log, ready = self.exercise(checksum=None)
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn('extract', log)
        self.assertFalse(ready)

    def test_invalid_checksum_prevents_hash_command(self):
        result, log, ready = self.exercise(checksum='z'*64)
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn('hash', log)
        self.assertNotIn('extract', log)
        self.assertFalse(ready)
