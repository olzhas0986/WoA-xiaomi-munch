#!/usr/bin/env python3
"""Exercise actual ESP repair shell with production payload and fake block nodes."""
from pathlib import Path
import os,subprocess,tempfile,zipfile,sys
R=Path(__file__).resolve().parents[2];child='--retry-child' in sys.argv
archive=R/'out/windows-full'/('HOST-TEST-ONLY-setup-child-fix.zip' if child else 'HOST-TEST-ONLY-setup-fix.zip')
work=R/'out/windows-full'/('setup-child-fix' if child else 'setup-state-fix')
with tempfile.TemporaryDirectory(prefix='munch-esp-test-') as t:
 p=Path(t);mock=p/'bin';mock.mkdir()
 def cmd(name,body):
  f=mock/name;f.write_text('#!/bin/sh\n'+body+'\n');f.chmod(0o755)
 cmd('id','echo 0')
 cmd('getprop','case "$1" in ro.twrp.version) echo 3.7.1;; *) [ "$CASE" = bad-device ] && echo other || echo munch;; esac')
 cmd('readlink','case "$*" in *by-name/esp) echo /dev/block/sda35;; *by-name/win) echo /dev/block/sda37;; *) /usr/bin/readlink "$@";; esac')
 cmd('blockdev','if [ "$1" = --getss ]; then echo 4096; elif [ "$2" = /dev/block/sda37 ]; then echo 33806090240; else echo 536870912; fi')
 cmd('sync',':')
 cmd('sha256sum','if [ "$CASE" = bad-hash ] && [ -n "${1:-}" ]; then echo "bad  $1";else exec /usr/bin/sha256sum "$@";fi')
 dd=mock/'dd';dd.write_text('''#!/usr/bin/python3
import os,subprocess,sys
args=[]
for a in sys.argv[1:]:
 for prefix in ('if=','of='):
  if a.startswith(prefix+'/dev/block/'):
   n=a.split('/')[-1];assert n in ('sda','sda35','sda37')
   if prefix=='of=':
    assert n in ('sda35','sda37');open(os.environ['MARKER'],'a').write(n+'\\n')
   a=prefix+os.environ['DISKS']+'/'+n
 args.append(a)
sys.exit(subprocess.run(['/usr/bin/dd',*args]).returncode)
''');dd.chmod(0o755)
 with zipfile.ZipFile(archive) as z:source=z.read('META-INF/com/google/android/update-binary').decode()
 source=source.replace('PATH=/system/bin:/system/xbin:/sbin:/vendor/bin:/tmp:$PATH','PATH='+str(mock)+':/usr/bin:/bin')
 for case in ('bad-device','bad-gpt','bad-hash','bad-preimage','success','idempotent'):
  d=p/case;d.mkdir();marker=d/'writes';(d/'sda').write_bytes(b'\0'*8192+(R/'out/munch-fresh/repartition32/primary-table.new.bin').read_bytes())
  if case=='bad-gpt':(d/'sda').write_bytes(b'?'*16384)
  report=__import__('json').loads((work/'report.json').read_text())
  sector=int(report['SECTOR']);sectorfile=d/'sda37'
  with sectorfile.open('wb') as sf:
   sf.truncate(33806090240);sf.seek(sector*4096)
   sf.write(b'?'*4096 if case=='bad-preimage' else (work/('sector.after' if case=='idempotent' else 'sector.before')).read_bytes())
  f=d/'installer.sh';f.write_text(source)
  r=subprocess.run(['/bin/sh',str(f),'3','1',str(archive)],env=dict(os.environ,CASE=case,DISKS=str(d),MARKER=str(marker)),stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
  if case in ('success','idempotent'):
   assert r.returncode==0 and marker.read_text()==('sda35\nsda37\n' if case=='success' else 'sda35\n'),r.stdout
   with sectorfile.open('rb') as sf:
    sf.seek(sector*4096);assert sf.read(4096)==(work/'sector.after').read_bytes()
   assert (d/'sda35').stat().st_size==536870912
  else:assert r.returncode!=0 and not marker.exists(),(case,r.stdout)
  print('PASS Setup repair:',case,flush=True)
