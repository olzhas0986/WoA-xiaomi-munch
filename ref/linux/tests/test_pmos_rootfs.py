"""Regression checks for first-run pmbootstrap workdir setup."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('pmos_rootfs', Path(__file__).resolve().parents[1]/'tools/pmos-rootfs.py')
recipe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(recipe)

class WorkdirTests(unittest.TestCase):
    def test_first_run_creates_version_and_user_owned_cache(self):
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)/'work'
            with patch.object(recipe, 'WORK', work):
                recipe.initialize_work()
            self.assertEqual((work/'version').read_text(), '8\n')
            self.assertTrue((work/'cache_git').is_dir())
            self.assertEqual(work.stat().st_mode & 0o777, 0o700)

    def test_repeat_preserves_existing_work(self):
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)/'work'
            with patch.object(recipe, 'WORK', work):
                recipe.initialize_work()
                sentinel = work/'chroot-native-state'
                sentinel.write_text('keep')
                recipe.initialize_work()
            self.assertEqual(sentinel.read_text(), 'keep')

    def test_incompatible_or_unversioned_data_is_not_adopted(self):
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)/'work'
            work.mkdir()
            sentinel = work/'data'
            sentinel.write_text('keep')
            with patch.object(recipe, 'WORK', work):
                with self.assertRaises(RuntimeError):
                    recipe.initialize_work()
                (work/'version').write_text('7\n')
                with self.assertRaises(RuntimeError):
                    recipe.initialize_work()
            self.assertEqual((work/'version').read_text(), '7\n')
            self.assertEqual(sentinel.read_text(), 'keep')


class WifiRecipeTests(unittest.TestCase):
    def test_wifi_packages_are_installed_in_existing_host_rootfs(self):
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            release = work/('chroot_rootfs_'+recipe.DEVICE)/'etc/os-release'
            release.parent.mkdir(parents=True)
            release.write_text('ID=nura')
            with patch.object(recipe, 'WORK', work), patch.object(recipe, 'prepare'), patch.object(recipe, 'pmb') as pmb:
                recipe.wifi_build()
            command = pmb.call_args.args
            self.assertEqual(command[:5], ('chroot', '-r', '--', 'apk', 'add'))
            self.assertIn('linux-firmware-ath11k', command)
            self.assertIn('wpa_supplicant', command)

    def test_wifi_build_requires_existing_rootfs(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(recipe, 'WORK', Path(tmp)), patch.object(recipe, 'prepare'), patch.object(recipe, 'pmb') as pmb:
                with self.assertRaises(RuntimeError):
                    recipe.wifi_build()
                pmb.assert_not_called()

    def test_wifi_export_preserves_base_archive(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)/'out'
            work = out/'work'
            source = work/('chroot_rootfs_'+recipe.DEVICE)
            (source/'etc').mkdir(parents=True)
            (source/'etc/os-release').write_text('ID=nura')
            firmware = source/'usr/lib/firmware/ath11k/QCA6390/hw2.0'
            firmware.mkdir(parents=True)
            (firmware/'amss.bin.zst').write_bytes(b'fixture')
            original = out/'postmarketos-aarch64-console.tar.gz'
            original.write_bytes(b'confirmed base')
            def archive(command, **kwargs):
                self.assertIn('--one-file-system', command)
                Path(command[command.index('-czf')+1]).write_bytes(b'wifi archive fixture')
            with patch.object(recipe, 'OUT', out), patch.object(recipe, 'WORK', work), patch.object(recipe, 'prepare'), patch.object(recipe, 'pmb'), patch.object(recipe.subprocess, 'run', side_effect=archive):
                recipe.export(wifi=True)
            self.assertEqual(original.read_bytes(), b'confirmed base')
            target = out/'wifi'/original.name
            self.assertEqual(target.read_bytes(), b'wifi archive fixture')
            self.assertTrue(target.with_suffix('.gz.sha256').exists())
