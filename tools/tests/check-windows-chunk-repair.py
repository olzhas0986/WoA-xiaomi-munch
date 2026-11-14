#!/usr/bin/env python3
"""Execute production recovery shell against tiny file-backed fake partitions."""
from pathlib import Path
import hashlib,os,subprocess,tempfile,zipfile
R=Path(__file__).resolve().parents[2]
def sha(b):return hashlib.sha256(b).hexdigest()
with tempfile.TemporaryDirectory(prefix='munch-full-test-') as t:
 p=Path(t);mock=p/'bin';mock.mkdir()
 def command(name,body):
  f=mock/name;f.write_text('#!/bin/sh\n'+body+'\n');f.chmod(0o755)
 command('id','echo 0')
 command('getprop','case "$1" in ro.twrp.version) echo 3.7.1;; *) if [ "$CASE" = bad-device ]; then echo other; else echo munch; fi;; esac')
 command('readlink','case "$*" in *by-name/esp) echo /dev/block/sda35;; *by-name/win) echo /dev/block/sda37;; *) /usr/bin/readlink "$@";; esac')
 command('blockdev','if [ "$1" = --getss ]; then echo 4096; elif [ "$CASE" = bad-size ]; then echo 42; elif [ "$2" = /dev/block/sda35 ]; then echo 536870912; else echo 33806090240; fi')
 command('sync',':')
 dd=mock/'dd';dd.write_text('''#!/usr/bin/python3
import os,subprocess,sys
from pathlib import Path
args=[];target=None
for arg in sys.argv[1:]:
 for prefix in ('if=','of='):
  if arg.startswith(prefix+'/dev/block/'):
   name=arg.split('/')[-1];assert name in ('sda','sda35','sda37')
   if prefix=='of=':
    assert name!='sda';target=Path(os.environ['FAKE_DISKS'])/name
    with open(os.environ['MARKER'],'a') as f:f.write(name+'\\n')
   arg=prefix+os.environ['FAKE_DISKS']+'/'+name
 args.append(arg)
r=subprocess.run(['/usr/bin/dd',*args])
if target and os.environ['CASE']=='bad-readback':
 with target.open('r+b') as f:f.write(b'!')
sys.exit(r.returncode)
''');dd.chmod(0o755)
 source=(R/'firmware/munch/Recovery/repair-windows-chunks').read_text().replace('PATH=/system/bin:/system/xbin:/sbin:/vendor/bin:/tmp:$PATH','PATH='+str(mock)+':/usr/bin:/bin')
 gpt=b'G'*8192;data={'win':b'W'*4096,'esp':b'E'*4096}
 for case in ('bad-device','bad-size','bad-gpt','bad-manifest','bad-payload','bad-range','bad-readback','unexpected-current','already-esp','all-correct','success'):
  disks=p/case;disks.mkdir();marker=disks/'writes'
  (disks/'sda').write_bytes(b'\0'*8192+(gpt if case!='bad-gpt' else b'?'*8192))
  rows=[]
  for part in ('win','esp'):
   offset=8253440 if part=='win' and case=='bad-range' else 0
   rows.append(f'{part} payload/{part}-0000.bin {offset} 1 {sha(data[part])} {sha(data[part].lower())}\n')
  for part,node in (('win','sda37'),('esp','sda35')):
   current=data[part] if case=='all-correct' or (case=='already-esp' and part=='esp') else data[part].lower()
   if case=='unexpected-current' and part=='win':current=b'?'*4096
   (disks/node).write_bytes(current)
  manifest=''.join(rows).encode();archive=disks/'test.zip'
  with zipfile.ZipFile(archive,'w') as z:
   z.writestr('payload/PARTS',manifest)
   for part in data:z.writestr(f'payload/{part}-0000.bin',b'?'*4096 if part=='esp' and case=='bad-payload' else data[part])
  script=source.replace('@GPT_SHA@',sha(gpt)).replace('@MANIFEST_SHA@','0'*64 if case=='bad-manifest' else sha(manifest)).replace('@CHUNKS@','2')
  installer=disks/'installer.sh';installer.write_text(script)
  env=dict(os.environ,CASE=case,FAKE_DISKS=str(disks),MARKER=str(marker))
  r=subprocess.run(['/bin/sh',str(installer),'3','1',str(archive)],env=env,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
  if case in ('success','already-esp','all-correct'):
   assert r.returncode==0,(case,r.stdout)
   assert (marker.read_text().splitlines() if marker.exists() else [])==({'success':['sda37','sda35'],'already-esp':['sda37'],'all-correct':[]}[case])
   assert (disks/'sda37').read_bytes()==data['win'] and (disks/'sda35').read_bytes()==data['esp']
  elif case=='bad-readback':assert r.returncode!=0 and 'Readback mismatch' in r.stdout
  else:assert r.returncode!=0 and not marker.exists(),(case,r.stdout)
  print('PASS guarded repair:',case,flush=True)
