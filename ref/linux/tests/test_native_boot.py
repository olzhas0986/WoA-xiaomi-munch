"""Native boot preparation in a fake RAM root; no mount or PID1 operations."""
import importlib.util
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('native_init',ROOT/'tools/build-native-init.py')
builder=importlib.util.module_from_spec(spec);spec.loader.exec_module(builder)


class NativeBootTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('node'), 'Node.js needed to evaluate PolicyKit rule')
    def test_network_policy_limits_user_and_actions(self):
        with tempfile.TemporaryDirectory() as tmp:
            root,result=self.prepare_fixture(Path(tmp))
            self.assertEqual(result.returncode,0,result.stderr)
            rule=root/'etc/polkit-1/rules.d/00-pmos-munch-network.rules'
            self.assertEqual(rule.stat().st_mode & 0o777,0o644)
            script='''
const assert = require('assert');
let authorize;
global.polkit = {addRule: f => authorize = f, Result: {YES: 'yes'}};
require(process.argv[1]);
const prefix = 'org.freedesktop.NetworkManager.';
for (const action of ['enable-disable-network', 'enable-disable-wifi',
 'network-control', 'wifi.scan', 'settings.modify.own', 'settings.modify.system']) {
 assert.strictEqual(authorize({id: prefix + action}, {user: 'pmos'}), 'yes');
 assert.strictEqual(authorize({id: prefix + action}, {user: 'other'}), undefined);
}
for (const id of [prefix + 'reload', prefix + 'enable-disable-wwan',
 prefix + 'settings.modify.hostname', 'org.freedesktop.policykit.exec'])
 assert.strictEqual(authorize({id}, {user: 'pmos'}), undefined);
'''
            # PolicyKit files have a .rules suffix; evaluate as JavaScript explicitly.
            script=script.replace('require(process.argv[1]);',
                "require('vm').runInThisContext(require('fs').readFileSync(process.argv[1], 'utf8'));")
            subprocess.run(['node','-e',script,str(rule)],check=True)

    def test_native_init_stops_before_bootstrap_daemons(self):
        source=(ROOT/'initramfs/init-pmos-display').read_text()
        native=builder.build(source)
        self.assertIn('. /etc/pmos-munch/native/stage',native)
        self.assertIn('setup_acm ||',native)
        self.assertNotIn('if setup_acm; then',native)
        self.assertNotIn('sleep "$delay"',native)
        self.assertNotIn('local_shell=$!',native)
        with tempfile.NamedTemporaryFile(mode='w') as f:
            f.write(native);f.flush()
            subprocess.run(['sh','-n',f.name],check=True)

    def test_changed_bootstrap_boundary_is_rejected(self):
        with self.assertRaises(ValueError):builder.build('#!/bin/sh\necho changed\n')

    def test_native_scripts_parse(self):
        for script in (ROOT/'native').iterdir():
            subprocess.run(['sh','-n',str(script)],check=True)

    def prepare_fixture(self,p,missing=False,missing_dev=False):
        root=p/'root'; root.mkdir()
        for path in ('etc/pmos-munch','etc/runlevels/default','etc/init.d','usr/libexec',
                     'usr/local/bin','usr/local/libexec','usr/lib/firmware/qcom/sm8250/xiaomi/munch',
                     'lib','sbin','home/pmos','dev'):
            (root/path).mkdir(parents=True,exist_ok=True)
        (root/'.pmos-munch-ready').touch()
        if not missing_dev:
            (root/'dev/null').symlink_to('/dev/null')
        (root/'usr/libexec/phosh').touch();(root/'usr/libexec/phosh').chmod(0o755)
        if not missing:
            (root/'lib/ld-musl-aarch64.so.1').touch();(root/'lib/ld-musl-aarch64.so.1').chmod(0o755)
        for path in ('a650_sqe.fw','a650_gmu.bin','sm8250/xiaomi/munch/a650_zap.mbn'):
            (root/'usr/lib/firmware/qcom'/path).write_bytes(b'fixture')
        (root/'etc/group').write_text('video:x:27:\ninput:x:23:\nrender:x:996:\n')
        (root/'etc/inittab').write_text('original login profile\n')
        (root/'etc/fstab').write_text('/dev/internal /data ext4 defaults 0 2\n')
        (root/'etc/rc.conf').write_text('# original\n')
        (root/'etc/runlevels/default/swapfile').symlink_to('/etc/init.d/swapfile')
        (root/'etc/udev/rules.d').mkdir(parents=True)
        (root/'etc/udev/rules.d/99-munch-touch-calibration.rules').touch()
        services=('devfs dmesg sysfs cgroups udev udev-trigger udev-settle hostname bootmisc sysctl tmpfs '
                  'pmos-munch-firmware dbus networkmanager pmos-munch-seatd pmos-munch-phosh killprocs mount-ro').split()
        for name in services:
            f=root/'etc/init.d'/name;f.touch();f.chmod(0o755)
        commands=p/'commands';commands.mkdir()
        required='openrc openrc-run rc-service udevd udevadm dbus-daemon NetworkManager nmcli nmtui seatd phoc squeekboard dbus-run-session setsid addgroup'
        for command in required.split():
            f=commands/command;f.write_text('#!/bin/sh\nexit 0\n');f.chmod(0o755)
        for name,body in {'id':'[ "$#" = 1 ] && echo 0 || echo 10000',
                          'chown':'exit 0', 'test-busybox':'echo init'}.items():
            f=commands/name;f.write_text('#!/bin/sh\n'+body+'\n');f.chmod(0o755)
        (root/'sbin/init').symlink_to(commands/'test-busybox')
        source=(ROOT/'native/prepare').read_text()
        # Rewrite known absolute paths once; do not rewrite generated temp paths.
        source=re.sub(r'(?<![A-Za-z0-9_/$])/(?:etc|usr|var|run|dev|home|lib|sbin|tmp|mnt|media|proc|sys)(?=/|[\s\"\'])|/\.pmos-munch-ready',
                      lambda m:str(root)+m.group(0),source)
        source=source.replace('/bin/busybox',str(commands/'test-busybox'))
        source=re.sub(r'^export PATH=.*$', 'export PATH='+shlex.quote(str(commands)+':'+os.environ['PATH']), source, flags=re.M)
        result=subprocess.run(['sh','-c',source],capture_output=True,text=True)
        return root,result

    def test_native_profile_replaces_only_ram_config_and_keeps_backup(self):
        with tempfile.TemporaryDirectory() as tmp:
            root,result=self.prepare_fixture(Path(tmp))
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertIn('::once:'+str(root)+'/sbin/openrc default',(root/'etc/inittab').read_text())
            self.assertNotIn('::wait:'+str(root)+'/sbin/openrc default',(root/'etc/inittab').read_text())
            self.assertEqual((root/'etc/pmos-munch/before-native/inittab').read_text(),'original login profile\n')
            self.assertNotIn('/dev/internal',(root/'etc/fstab').read_text())
            self.assertFalse((root/'etc/runlevels/default/swapfile').exists())
            self.assertTrue((root/'etc/runlevels/default/pmos-munch-phosh').is_symlink())
            self.assertFalse((root/'etc/udev/rules.d/99-munch-touch-calibration.rules').exists())
            self.assertIn('nmtui connect',(root/'usr/local/bin/pmos-connect').read_text())
            for directory in ('tmp','var/tmp','run','proc','sys','mnt','media'):
                self.assertTrue((root/directory).is_dir(),directory)
            for directory in ('tmp','var/tmp'):
                self.assertEqual((root/directory).stat().st_mode & 0o7777,0o1777)

    def test_bad_rootfs_fails_before_replacing_login_and_mount_profiles(self):
        with tempfile.TemporaryDirectory() as tmp:
            root,result=self.prepare_fixture(Path(tmp),missing=True)
            self.assertNotEqual(result.returncode,0)
            self.assertIn('musl loader',result.stderr)
            self.assertEqual((root/'etc/inittab').read_text(),'original login profile\n')
            self.assertIn('/dev/internal',(root/'etc/fstab').read_text())

    def test_missing_dev_is_reported_before_package_checks(self):
        with tempfile.TemporaryDirectory() as tmp:
            root,result=self.prepare_fixture(Path(tmp),missing_dev=True)
            self.assertNotEqual(result.returncode,0)
            self.assertIn('/dev/null is missing',result.stderr)
            self.assertNotIn('missing openrc',result.stderr)
            self.assertEqual((root/'etc/inittab').read_text(),'original login profile\n')

    def test_preflight_binds_dev_and_unbinds_on_both_outcomes(self):
        source=(ROOT/'native/stage').read_text()
        block=source.split('# Temporary device visibility',1)[1].split('# End temporary preflight mounts.',1)[0]
        block=block[block.index('mkdir -p /pmos/dev'):]
        for outcome in ('0','1'):
            with tempfile.TemporaryDirectory() as tmp:
                p=Path(tmp); commands=p/'commands';commands.mkdir()
                scripts={
                    'mount':'echo mount >> "$TRACE"; touch "$ACTIVE"',
                    'chroot':'[ -f "$ACTIVE" ] || exit 9; echo chroot >> "$TRACE"; exit "$OUTCOME"',
                    'umount':'[ -f "$ACTIVE" ] || exit 9; echo umount >> "$TRACE"; rm "$ACTIVE"',
                }
                for name,body in scripts.items():
                    f=commands/name;f.write_text('#!/bin/sh\n'+body+'\n');f.chmod(0o755)
                code='native_rescue() { echo "rescue: $*"; exit 1; }\n'+block
                code=code.replace('/pmos/dev',str(p/'dev')).replace('/run/pmos-munch-native-preflight.log',str(p/'preflight.log')).replace('/dev/kmsg',str(p/'kmsg'))
                env=dict(os.environ,PATH=str(commands)+':'+os.environ['PATH'],TRACE=str(p/'trace'),ACTIVE=str(p/'active'),OUTCOME=outcome)
                result=subprocess.run(['sh','-c',code],env=env,capture_output=True,text=True)
                self.assertEqual(result.returncode,int(outcome),result.stderr)
                self.assertEqual((p/'trace').read_text().splitlines(),['mount','chroot','umount'])
                self.assertFalse((p/'active').exists())

    def test_acm_recovery_uses_serial_tty_before_and_after_dev_move(self):
        source=(ROOT/'native/stage').read_text()
        function='native_acm_rescue() {'+source.split('native_acm_rescue() {',1)[1].split('\nnative_rescue()',1)[0]
        for moved in (False,True):
            with tempfile.TemporaryDirectory() as tmp:
                p=Path(tmp);commands=p/'commands';commands.mkdir()
                serial=p/('pmos/dev/ttyGS0' if moved else 'dev/ttyGS0')
                serial.parent.mkdir(parents=True);serial.touch()
                for name,body in {'setsid':'printf "%s\\n" "$@" > "$TRACE"',
                                  'sleep':'exit 7'}.items():
                    f=commands/name;f.write_text('#!/bin/sh\n'+body+'\n');f.chmod(0o755)
                # Plain files stand in for tty device nodes; no real tty is opened.
                code=function.replace('[ -c ', '[ -e ')
                code=re.sub(r'/pmos/dev/ttyGS0|/dev/ttyGS0',lambda m:str(p)+m.group(0),code)
                env=dict(os.environ,PATH=str(commands)+':'+os.environ['PATH'],TRACE=str(p/'trace'))
                result=subprocess.run(['sh','-c','set -e\n'+code+'\nnative_acm_rescue'],env=env,capture_output=True,text=True,timeout=5)
                self.assertEqual(result.returncode,7,result.stderr)
                trace=(p/'trace').read_text()
                self.assertEqual(trace.splitlines()[-1],str(serial))
                self.assertIn('exec 0<"$1" 1>"$1" 2>&1',trace)
                self.assertNotIn('cttyhack',trace)

    def test_diagnostics_include_session_errors_when_runtime_state_is_incomplete(self):
        with tempfile.TemporaryDirectory() as tmp:
            root,result=self.prepare_fixture(Path(tmp))
            self.assertEqual(result.returncode,0,result.stderr)
            (root/'var/log/pmos-munch-phosh.log').write_text('fixture EGL failure\n')
            report=subprocess.run(['sh',str(root/'usr/local/bin/pmos-diagnose')],text=True,capture_output=True)
            self.assertEqual(report.returncode,0,report.stderr)
            self.assertIn('fixture EGL failure',report.stdout)
            self.assertIn('OpenRC starting:',report.stdout)
            self.assertTrue((root/'run/pmos-munch-diagnostics.txt').exists())
