"""Check the install bundle and actual child-session environment/lifecycle."""
import importlib.util
import io
import os
from pathlib import Path
import subprocess
import tarfile
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('phosh_bundle', ROOT/'tools/build-phosh-tools.py')
bundle = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bundle)


class PhoshToolsTests(unittest.TestCase):
    def test_bundle_has_only_local_helpers_and_is_reproducible(self):
        data=bundle.build()
        self.assertEqual(data,bundle.build())
        with tarfile.open(fileobj=io.BytesIO(data),mode='r:gz') as tar:
            self.assertEqual(set(tar.getnames()),set(bundle.FILES))
            for item in tar:
                source,mode=bundle.FILES[item.name]
                self.assertTrue(item.isfile())
                self.assertEqual(item.mode,mode)
                self.assertEqual(tar.extractfile(item).read(),(ROOT/'phone'/source).read_bytes())

    def test_scripts_parse(self):
        for name in ('phosh-start','phosh-session'):
            subprocess.run(['sh','-n',str(ROOT/'phone'/name)],check=True)

    def test_keyboard_receives_same_bus_and_wayland_as_shell(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)
            commands={
                'gsettings':'if [ "$1" = get ]; then echo "@a(ss) []"; fi',
                'dbus-update-activation-environment':'exit 0',
                'squeekboard':'echo "$DBUS_SESSION_BUS_ADDRESS $WAYLAND_DISPLAY" > "$TEST_DIR/osk"; sleep 1',
                'phosh':'echo "$DBUS_SESSION_BUS_ADDRESS $WAYLAND_DISPLAY" > "$TEST_DIR/shell"; sleep 0.3',
            }
            for name,body in commands.items():
                f=p/name;f.write_text('#!/bin/sh\n'+body+'\n');f.chmod(0o755)
            code=(ROOT/'phone/phosh-session').read_text().replace('/usr/libexec/phosh',str(p/'phosh'))
            code=code.replace('/tmp/squeekboard.log',str(p/'osk.log'))
            env=dict(os.environ,PATH=str(p)+':'+os.environ['PATH'],TEST_DIR=str(p),
                     DBUS_SESSION_BUS_ADDRESS='unix:path=/test/bus',WAYLAND_DISPLAY='wayland-42',
                     XDG_RUNTIME_DIR=str(p))
            subprocess.run(['sh','-c',code],env=env,check=True,capture_output=True)
            self.assertEqual((p/'osk').read_text(),(p/'shell').read_text())
            self.assertIn('wayland-42',(p/'osk').read_text())

    def test_child_refuses_missing_session_bus(self):
        env=dict(os.environ);env.pop('DBUS_SESSION_BUS_ADDRESS',None)
        result=subprocess.run(['sh',str(ROOT/'phone/phosh-session')],env=env,text=True,capture_output=True)
        self.assertNotEqual(result.returncode,0)
        self.assertIn('Missing session D-Bus',result.stdout)
