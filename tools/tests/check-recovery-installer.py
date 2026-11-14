#!/usr/bin/env python3
"""Run the actual shell installer with fake device commands and file-backed disks."""
from pathlib import Path
import os,subprocess,tempfile
ROOT=Path(__file__).resolve().parents[2]
ZIP=ROOT/'out/winpe/munch-winpe-files-twrp.zip'
with tempfile.TemporaryDirectory(prefix='munch-recovery-test-') as temp:
 p=Path(temp);mock=p/'bin';mock.mkdir()
 def command(name,body):
  f=mock/name;f.write_text('#!/bin/sh\n'+body+'\n');f.chmod(0o755)
 command('id','echo 0')
 command('getprop','case "$1" in ro.twrp.version) echo 3.7.1;; *) if [ "$CASE" = bad-device ]; then echo other; else echo munch; fi;; esac')
 command('readlink','case "$*" in *by-name/esp) echo /dev/block/sda35;; *by-name/win) echo /dev/block/sda37;; *) /usr/bin/readlink "$@";; esac')
 command('blockdev','if [ "$1" = --getss ]; then echo 4096; elif [ "$CASE" = bad-size ]; then echo 42; elif [ "$2" = /dev/block/sda35 ]; then echo 536870912; else echo 33806090240; fi')
 command('sync',':')
 command('sha256sum','if [ "$CASE" = bad-hash ] && [ "${1:-}" = -c ]; then exit 1; fi\nexec /usr/bin/sha256sum "$@"')
 dd=mock/'dd';dd.write_text('''#!/usr/bin/python3
import os,subprocess,sys
from pathlib import Path
args=[]
for arg in sys.argv[1:]:
 for prefix in ('if=','of='):
  if arg.startswith(prefix+'/dev/block/'):
   name=arg.split('/')[-1]
   assert name in ('sda35','sda37')
   if prefix=='of=':
    with open(os.environ['MARKER'],'a') as f:f.write(name+'\\n')
   arg=prefix+os.environ['FAKE_DISKS']+'/'+name
 args.append(arg)
sys.exit(subprocess.run(['/usr/bin/dd',*args]).returncode)
''');dd.chmod(0o755)
 source=(ROOT/'firmware/munch/Recovery/update-binary').read_text()
 source=source.replace('PATH=/system/bin:/system/xbin:/sbin:/vendor/bin:/tmp:$PATH','PATH='+str(mock)+':/usr/bin:/bin')
 installer=p/'installer.sh';installer.write_text(source)
 for case in ('bad-device','bad-size','bad-hash','success'):
  disks=p/case;disks.mkdir();marker=disks/'writes'
  env=dict(os.environ,CASE=case,FAKE_DISKS=str(disks),MARKER=str(marker))
  r=subprocess.run(['/bin/sh',str(installer),'3','1',str(ZIP)],env=env,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
  if case!='success':
   assert r.returncode!=0 and not marker.exists(),(case,r.stdout)
  else:
   assert r.returncode==0,(case,r.stdout)
   assert marker.read_text().splitlines()==['sda37','sda35']
   assert 'both test volumes written and verified' in r.stdout
  print('PASS',case,flush=True)
