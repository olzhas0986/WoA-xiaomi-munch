"""Check the refreshed archive rather than modifying a real chroot."""
import importlib.util
import io
import pathlib
import tarfile
import tempfile
import unittest
from unittest.mock import patch

ROOT = pathlib.Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('refresh_rootfs', ROOT/'tools/update-pmos-rootfs.py')
recipe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(recipe)


class RefreshTests(unittest.TestCase):
    def test_refresh_keys_repositories_helpers_and_firmware(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            keys = root/'out/pmbootstrap/pmb/data/keys'
            keys.mkdir(parents=True)
            (keys/'trusted.pub').write_bytes(b'public key fixture')
            (root/'tools').symlink_to(ROOT/'tools', target_is_directory=True)
            (root/'phone').symlink_to(ROOT/'phone', target_is_directory=True)
            firmware = root/'firmware'; firmware.mkdir()
            for name in ('a650_sqe.fw', 'a650_gmu.bin'):
                (firmware/name).write_bytes(b'firmware fixture')
            source = root/'original.tar.gz'
            with tarfile.open(source, 'w:gz') as archive:
                for name,data in {'etc/apk/repositories': b'/mnt/pmbootstrap/packages/edge\nhttps://example.org/main\n',
                                  '.pmos-munch-ready': b'ready', 'etc/os-release': b'ID=nura'}.items():
                    member=tarfile.TarInfo('./'+name);member.size=len(data)
                    archive.addfile(member,io.BytesIO(data))
            before = source.read_bytes()
            output = root/'updated.tar.gz'
            with patch.object(recipe, 'ROOT', root), patch.object(recipe.subprocess, 'check_output', return_value=recipe.PIN):
                recipe.refresh(source, output, firmware)
                with self.assertRaises(ValueError):
                    recipe.refresh(source, output, firmware)
            self.assertEqual(source.read_bytes(), before)
            with tarfile.open(output) as archive:
                names=archive.getnames()
                self.assertNotIn('./.pmos-munch-ready',names)
                self.assertEqual(archive.extractfile('./etc/apk/repositories').read(),b'https://example.org/main\n')
                self.assertEqual(archive.extractfile('./etc/apk/keys/trusted.pub').read(),b'public key fixture')
                self.assertEqual(archive.extractfile('./usr/lib/firmware/qcom/a650_sqe.fw').read(),b'firmware fixture')
                self.assertEqual(archive.getmember('./usr/local/bin/pmos-connect').mode,0o755)
                self.assertEqual(len(names),len(set(names)))
            self.assertTrue(output.with_name(output.name+'.sha256').exists())
