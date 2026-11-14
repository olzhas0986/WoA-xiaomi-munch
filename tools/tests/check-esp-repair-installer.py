#!/usr/bin/env python3
"""Exercise actual ESP repair shell with production payload and fake block nodes."""
from pathlib import Path
import os,subprocess,tempfile,zipfile
R=Path(__file__).resolve().parents[2];archive=R/'out/windows-full/munch-windows-esp-repair-twrp.zip'
with tempfile.TemporaryDirectory(prefix='munch-esp-test-') as t:
 p=Path(t);mock=p/'bin';mock.mkdir()
 def cmd(name,body):
  f=mock/name;f.write_text('#!/bin/sh\n'+body+'\n');f.chmod(0o755)
 cmd('id','echo 0')
 cmd('getprop','case "$1" in ro.twrp.version) echo 3.7.1;; *) [ "$CASE" = bad-device ] && echo other || echo munch;; esac')
 cmd('readlink','case "$*" in *by-name/esp) echo /dev/block/sda35;; *) /usr/bin/readlink "$@";; esac')
 cmd('blockdev','[ "$1" = --getss ] && echo 4096 || echo 536870912')
 cmd('sync',':')
 cmd('sha256sum','if [ "$CASE" = bad-hash ] && [ -n "${1:-}" ]; then echo "bad  $1";else exec /usr/bin/sha256sum "$@";fi')
 dd=mock/'dd';dd.write_text('''#!/usr/bin/python3
import os,subprocess,sys
args=[]
for a in sys.argv[1:]:
 for prefix in ('if=','of='):
  if a.startswith(prefix+'/dev/block/'):
   n=a.split('/')[-1];assert n in ('sda','sda35')
   if prefix=='of=':
    assert n=='sda35';open(os.environ['MARKER'],'w').write(n)
   a=prefix+os.environ['DISKS']+'/'+n
 args.append(a)
sys.exit(subprocess.run(['/usr/bin/dd',*args]).returncode)
''');dd.chmod(0o755)
 with zipfile.ZipFile(archive) as z:source=z.read('META-INF/com/google/android/update-binary').decode()
 source=source.replace('PATH=/system/bin:/system/xbin:/sbin:/vendor/bin:/tmp:$PATH','PATH='+str(mock)+':/usr/bin:/bin')
 for case in ('bad-device','bad-gpt','bad-hash','success'):
  d=p/case;d.mkdir();marker=d/'writes';(d/'sda').write_bytes(b'\0'*8192+(R/'out/munch-fresh/repartition32/primary-table.new.bin').read_bytes())
  if case=='bad-gpt':(d/'sda').write_bytes(b'?'*16384)
  f=d/'installer.sh';f.write_text(source)
  r=subprocess.run(['/bin/sh',str(f),'3','1',str(archive)],env=dict(os.environ,CASE=case,DISKS=str(d),MARKER=str(marker)),stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
  if case=='success':assert r.returncode==0 and marker.read_text()=='sda35' and (d/'sda35').stat().st_size==536870912,r.stdout
  else:assert r.returncode!=0 and not marker.exists(),(case,r.stdout)
  print('PASS ESP-only recovery:',case,flush=True)
