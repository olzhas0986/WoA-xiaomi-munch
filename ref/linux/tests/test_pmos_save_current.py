"""Exercise archive exclusions and backup publication on temporary directories."""
from pathlib import Path
import hashlib
import subprocess
import tarfile
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
SOURCE=(ROOT/'phone/pmos-save-current').read_text()


class SaveCurrentTests(unittest.TestCase):
    def test_archive_excludes_live_mounts_and_its_own_destination(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);root=p/'root';root.mkdir()
            for directory in ('dev','proc','sys','run','tmp','mnt','media','etc'):
                (root/directory).mkdir();(root/directory/'fixture').write_text(directory)
            (root/'.pmos-munch-ready').touch()
            (root/'etc/keep').write_text('installed packages')
            script=SOURCE.split('(set -C; tar',1)[1].split(' || fail',1)[0]
            script='(set -C; tar'+script
            script=script.replace('-C / ', '-C "$ROOTFS" ')
            subprocess.run(['sh','-c','base="$DEST"; '+script],check=True,
                           env={'PATH':'/usr/bin:/bin','ROOTFS':str(root),'DEST':str(root/'mnt/archive')})
            with tarfile.open(root/'mnt/archive.partial','r:gz') as tar:
                names=tar.getnames()
                self.assertIn('./etc/keep',names)
                for directory in ('dev','proc','sys','run','tmp','mnt','media'):
                    self.assertFalse(any(n=='./'+directory or n.startswith('./'+directory+'/') for n in names))
                self.assertNotIn('./.pmos-munch-ready',names)

    def test_repeated_save_preserves_previous_archive_and_matching_checksum(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);base='postmarketos-desktop.tar.gz'
            (p/base).write_bytes(b'old')
            digest=hashlib.sha256(b'old').hexdigest()
            (p/(base+'.sha256')).write_text(digest+'  '+base+'\n')
            (p/(base+'.partial')).write_bytes(b'new')
            (p/(base+'.sha256.partial')).write_text('new checksum')
            body='if [ -e "$base" ]'+SOURCE.split('if [ -e "$base" ]',1)[1].split('\nsync\ncd /',1)[0]
            subprocess.run(['sh','-c','base='+base+'\n'+body],cwd=p,check=True)
            previous='postmarketos-desktop.previous-1.tar.gz'
            self.assertEqual((p/previous).read_bytes(),b'old')
            self.assertEqual((p/(previous+'.sha256')).read_text(),digest+'  '+previous+'\n')
            self.assertEqual((p/base).read_bytes(),b'new')

    def test_ram_guard_uses_chroot_root_mount(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp); (p/'ready').touch()
            prefix=SOURCE.split('if [ "$worker" = 0 ]; then',1)[0]
            prefix=prefix.replace('/.pmos-munch-ready',str(p/'ready')).replace('/proc/mounts',str(p/'mounts'))
            for mounts,expected in [('tmpfs / tmpfs rw 0 0\n',0),
                                    ('rootfs / rootfs rw 0 0\ntmpfs /pmos tmpfs rw 0 0\n',1),
                                    ('/dev/sda1 / ext4 rw 0 0\n',1)]:
                (p/'mounts').write_text(mounts)
                result=subprocess.run(['sh','-c',prefix],capture_output=True,text=True)
                self.assertEqual(result.returncode,expected,result.stderr)

    def test_usb_ancestry_handles_hubs_and_rejects_internal_storage(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp); sys=p/'sys'; (sys/'bus/usb').mkdir(parents=True)
            (sys/'bus/scsi').mkdir(); (sys/'class/block').mkdir(parents=True)
            usb=sys/'devices/platform/controller/usb1/1-1/1-1.2/1-1.2:1.0'
            usb.mkdir(parents=True)
            (usb/'subsystem').symlink_to(sys/'bus/usb')
            partition=usb/'host0/target0/0:0:0:0/block/sda/sda1'
            partition.mkdir(parents=True)
            (sys/'class/block/sda1').symlink_to(partition)
            internal=sys/'devices/platform/ufs/host1/target1/block/sdb/sdb1'
            internal.mkdir(parents=True)
            (sys/'class/block/sdb1').symlink_to(internal)
            function='is_usb_block() {'+SOURCE.split('is_usb_block() {',1)[1].split('\n# OTG role',1)[0]
            function=function.replace('/sys/',str(sys)+'/')
            for name,expected in [('sda1',0),('sdb1',1),('sdc1',1)]:
                result=subprocess.run(['sh','-c',function+'\nname='+name+'; is_usb_block'])
                self.assertEqual(result.returncode,expected)
