"""Bundle and delayed-load checks for the isolated modular Wi-Fi image."""
import gzip
import importlib.util
import os
from pathlib import Path
import struct
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('module_initramfs', ROOT/'tools/mkinitramfs.py')
initramfs = importlib.util.module_from_spec(spec); spec.loader.exec_module(initramfs)


class WifiModuleTests(unittest.TestCase):
    release = '7.3.0-rc7-pmos-munch-modular'

    def fixtures(self):
        elf = bytearray(120); elf[:6] = b'\x7fELF\x02\x01'
        struct.pack_into('<HH', elf, 16, 2, 183)
        struct.pack_into('<Q', elf, 32, 64)
        struct.pack_into('<HH', elf, 54, 56, 1)
        struct.pack_into('<I', elf, 64, 1)
        ko = bytearray(64); ko[:6] = elf[:6]
        struct.pack_into('<HH', ko, 16, 1, 183)
        ko += b'vermagic='+self.release.encode()+b' SMP\0'
        files = {'modules.dep': b'kernel/ath11k_pci.ko: kernel/ath11k.ko\n',
                 'modules.alias': b'alias pci:fixture ath11k_pci\n'}
        for name in ('ath11k', 'ath11k_pci', 'cfg80211', 'mac80211', 'pci-pwrctrl-pwrseq'):
            files['kernel/'+name+'.ko'] = bytes(ko)
        native = {p.name: p.read_bytes() for p in (ROOT/'native').iterdir()}
        phone = {p.name: p.read_bytes() for p in (ROOT/'phone').iterdir()}
        return elf, files, native, phone

    def bundle(self, files=None, release=None):
        elf, defaults, native, phone = self.fixtures()
        return initramfs.archive(elf, b'init', phone_tools=phone, native_tools=native,
            kernel_modules=(release or self.release, defaults if files is None else files))

    def test_modules_are_data_until_native_rootfs_install(self):
        packed = self.bundle()
        self.assertEqual(packed, self.bundle())
        raw = gzip.decompress(packed)
        self.assertIn(b'etc/pmos-munch/kernel-modules/kernel/ath11k_pci.ko\0', raw)
        self.assertIn(b'etc/pmos-munch/modules.release\0', raw)
        names = []; offset = 0
        while True:
            fields = [int(raw[offset+6+i*8:offset+14+i*8], 16) for i in range(13)]
            size, name_size = fields[6], fields[11]
            name = raw[offset+110:offset+110+name_size-1].decode()
            if name == 'TRAILER!!!':
                break
            names.append(name)
            offset = (offset+110+name_size+3) & ~3
            offset = (offset+size+3) & ~3
        self.assertFalse(any(name.startswith('lib/modules/') for name in names))

    def test_rejects_wrong_release_wrong_arch_and_incomplete_bundle(self):
        _, files, _, _ = self.fixtures()
        with self.assertRaisesRegex(ValueError, 'release mismatch'):
            self.bundle(release='different-kernel')
        bad = dict(files); ko = bytearray(bad['kernel/ath11k.ko'])
        struct.pack_into('<H', ko, 18, 62); bad['kernel/ath11k.ko'] = bytes(ko)
        with self.assertRaisesRegex(ValueError, 'AArch64'):
            self.bundle(bad)
        bad = dict(files); del bad['kernel/mac80211.ko']
        with self.assertRaisesRegex(ValueError, 'Wi-Fi modules missing'):
            self.bundle(bad)
        bad = dict(files); del bad['modules.dep']
        with self.assertRaisesRegex(ValueError, 'depmod'):
            self.bundle(bad)

    def test_rejects_escaping_paths_and_symlinks(self):
        _, files, _, _ = self.fixtures()
        for name in ('../escape', '/absolute', '.', 'kernel/../escape'):
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, 'unsafe'):
                self.bundle(dict(files, **{name: b'x'}))
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/self.release; path.mkdir()
            (path/'build').symlink_to('/host/build')
            (path/'modules.dep').write_text('fixture')
            self.assertEqual(initramfs.inspect_modules(path)[1], {'modules.dep': b'fixture'})
            (path/'unexpected').symlink_to('/etc/passwd')
            with self.assertRaisesRegex(ValueError, 'symlink'):
                initramfs.inspect_modules(path)

    def test_module_load_waits_for_firmware_and_does_not_rebind_pci(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp); commands = p/'commands'; commands.mkdir()
            marker = p/'release'; marker.write_text(self.release+'\n')
            phy = p/'phys'; phy.mkdir()
            for name, body in {
                'uname': 'echo "$RELEASE"',
                'modprobe': '''[ "$(cat "$FWPATH")" = /usr/lib/firmware ] || exit 9
echo "$1" >> "$TRACE"
[ "$1" != ath11k_pci ] || mkdir "$PHY/phy0"
exit 0''',
            }.items():
                cmd = commands/name; cmd.write_text('#!/bin/sh\n'+body+'\n'); cmd.chmod(0o755)
            source = (ROOT/'native/firmware').read_text()
            source = source.replace('[ -d "$fw/qcom" ] || fw=/lib/firmware', ':')
            source = source.replace('/etc/pmos-munch/wifi-module-release', str(marker))
            source = source.replace('/sys/module/firmware_class/parameters/path', str(p/'fwpath'))
            source = source.replace('/sys/class/ieee80211', str(phy))
            env = dict(os.environ, PATH=str(commands)+':'+os.environ['PATH'],
                       FWPATH=str(p/'fwpath'), RELEASE=self.release,
                       TRACE=str(p/'trace'), PHY=str(phy))
            result = subprocess.run(['sh', '-c', source], env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual((p/'trace').read_text().splitlines(),
                             ['pci-pwrctrl-pwrseq', 'ath11k_pci'])
            (p/'trace').unlink(); marker.write_text('wrong-release\n')
            result = subprocess.run(['sh', '-c', source], env=env, capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('release mismatch', result.stdout)
            self.assertFalse((p/'trace').exists())

    def test_stage_installs_matching_modules_and_rejects_wrong_release(self):
        source = (ROOT/'native/stage').read_text()
        block = source[source.index('rm -f /pmos/etc/pmos-munch/wifi-module-release'):
                       source.index('# Unbind it on both outcomes')]
        for correct in (True, False):
            with self.subTest(correct=correct), tempfile.TemporaryDirectory() as tmp:
                p = Path(tmp); root = p/'root'; stage = p/'stage'; commands = p/'commands'
                (root/'etc/pmos-munch').mkdir(parents=True)
                (stage/'kernel-modules/kernel').mkdir(parents=True)
                commands.mkdir()
                (stage/'modules.release').write_text(self.release if correct else 'wrong')
                (stage/'kernel-modules/modules.dep').write_text('fixture deps')
                (stage/'kernel-modules/kernel/ath11k_pci.ko').write_bytes(b'fixture module')
                uname = commands/'uname'; uname.write_text('#!/bin/sh\necho "$RELEASE"\n'); uname.chmod(0o755)
                code = 'native_rescue() { echo "$*"; exit 1; }\n'+block
                code = code.replace('/pmos/', str(root)+'/')
                code = code.replace('/etc/pmos-munch/modules.release', str(stage/'modules.release'))
                code = code.replace('/etc/pmos-munch/kernel-modules', str(stage/'kernel-modules'))
                result = subprocess.run(['sh', '-c', code], capture_output=True, text=True,
                    env=dict(os.environ, PATH=str(commands)+':'+os.environ['PATH'], RELEASE=self.release))
                self.assertEqual(result.returncode, 0 if correct else 1, result.stderr)
                destination = root/'lib/modules'/self.release
                if correct:
                    self.assertEqual((destination/'modules.dep').read_text(), 'fixture deps')
                    self.assertEqual((root/'etc/pmos-munch/wifi-module-release').read_text(), self.release+'\n')
                else:
                    self.assertIn('release mismatch', result.stdout)
                    self.assertFalse(destination.exists())
