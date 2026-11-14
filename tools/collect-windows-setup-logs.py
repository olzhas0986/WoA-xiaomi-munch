#!/usr/bin/env python3
"""Read Setup logs via libntfs-3g + raw ADB reads. No device mounts or writes."""
from pathlib import Path
import argparse,collections,hashlib,json,os,subprocess,time
from ntfs_remote_reader import ReadOnlyNtfs
R=Path(__file__).resolve().parents[1];SIZE=33806090240;BLOCK=65536
p=argparse.ArgumentParser();p.add_argument('--full-dump',action='store_true',help='Collect complete MEMORY.DMP up to 1GiB (read-only, more data/time)');p.add_argument('--serial');p.add_argument('--image',type=Path,help='Host-only test with a raw image');p.add_argument('--output',type=Path,default=R/'out/windows-full/device-setup-logs');a=p.parse_args()
BLOCK=1048576 if a.full_dump else BLOCK
READ_BUDGET=(2*1024*1024*1024 if a.full_dump else 256*1024*1024)
CACHE_BLOCKS=(64 if a.full_dump else 512)
adb=['adb']+(['-s',a.serial] if a.serial else [])
def remote(command,binary=False):
 r=subprocess.run(adb+['exec-out' if binary else 'shell',command],check=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
 return r.stdout if binary else r.stdout.decode(errors='replace').strip()
fd=None
if a.image:
 assert a.image.is_file() and a.image.stat().st_size==SIZE;fd=os.open(a.image,os.O_RDONLY)
else:
 subprocess.run(adb+['get-state'],check=True,stdout=subprocess.DEVNULL)
 assert remote('id -u')=='0' and remote('getprop ro.twrp.version'),'Boot root TWRP first'
 assert 'munch' in [remote('getprop '+p) for p in ('ro.product.device','ro.product.vendor.device','ro.product.system.device','ro.build.product')],'Unexpected device'
 assert remote('readlink -f /dev/block/bootdevice/by-name/win')=='/dev/block/sda37'
 assert remote('blockdev --getss /dev/block/sda37')=='4096' and int(remote('blockdev --getsize64 /dev/block/sda37'))==SIZE
 mounted=remote('while read s m opts rest; do if [ "$(readlink -f "$s" 2>/dev/null)" = /dev/block/sda37 ]; then echo "$m $opts"; fi; done </proc/mounts')
 assert not mounted,'Unmount win in TWRP first (do not format): '+mounted
cache=collections.OrderedDict();fetched=0;last_progress=0;rows=[];a.output.mkdir(parents=True,exist_ok=True)
def read(offset,count):
 global fetched,last_progress
 result=bytearray()
 while count:
  start=offset//BLOCK*BLOCK
  if start not in cache:
   n=min(BLOCK,SIZE-start)
   if fetched+n>READ_BUDGET:raise RuntimeError('Read budget exceeded; stopping without writes')
   data=os.pread(fd,n,start) if fd is not None else remote(f'dd if=/dev/block/sda37 bs=4096 skip={start//4096} count={n//4096} 2>/dev/null',True)
   if len(data)!=n:raise RuntimeError('Short ADB raw read')
   cache[start]=data;fetched+=n
   if fetched-last_progress>=16*1024*1024:print('Read',fetched//(1024*1024),'MiB from NTFS',flush=True);last_progress=fetched
   if len(cache)>CACHE_BLOCKS:cache.popitem(last=False)
  else:cache.move_to_end(start)
  n=min(count,len(cache[start])-(offset-start));result.extend(cache[start][offset-start:offset-start+n]);offset+=n;count-=n
 return bytes(result)
r=None
try:
 r=ReadOnlyNtfs(SIZE,read)
 targets=[
 '/Windows/Panther/setuperr.log','/Windows/Panther/setupact.log',
 '/Windows/Panther/UnattendGC/setuperr.log','/Windows/Panther/UnattendGC/setupact.log',
 '/Windows/System32/Sysprep/Panther/setuperr.log','/Windows/System32/Sysprep/Panther/setupact.log',
 '/Windows/setupact.log','/Windows/setuperr.log',
 '/Windows/INF/setupapi.dev.log','/Windows/INF/setupapi.app.log',
 '/Windows/System32/config/SYSTEM','/Windows/System32/winevt/Logs/System.evtx','/Windows/bootstat.dat',
 '/munch-gpu/report.json','/munch-gpu/pnp.txt','/munch-gpu/install.log',
 '/munch-gpu/signing-configure.log','/munch-gpu/state.json',
 '/munch-gpu-rpen/report.json','/munch-gpu-rpen/install.log','/munch-gpu-rpen/state.json',
 '/munch-gpu-spmi/report.json','/munch-gpu-spmi/install.log','/munch-gpu-spmi/state.json',
 '/munch-gpu-pmic/report.json','/munch-gpu-pmic/install.log','/munch-gpu-pmic/state.json',
 '/munch-gpu-pep/report.json','/munch-gpu-pep/DSDT.aml',
 '/munch-gpu-pep-core/report.json','/munch-gpu-pep-core/state.json',
 '/munch-gpu-pep-core/install.log','/munch-gpu-pep-core/disable-before-install.log',
 '/munch-gpu-pep-core/enable.log','/munch-gpu-pep-core/native-policy-before.json']
 try:
  dumps=[n for n,k in r.list('/Windows/Minidump') if n.lower().endswith('.dmp') and all(c not in n for c in ('/','\\','\0'))]
  targets.extend('/Windows/Minidump/'+n for n in sorted(dumps)[-3:])
 except OSError:pass
 targets.append('/Windows/MEMORY.DMP')
 for path in targets:
  limit=(1024*1024*1024 if a.full_dump else 65536) if path.endswith('/MEMORY.DMP') else 32*1024*1024
  tail=path.lower().endswith('.log')
  try:
   data,size=r.read_file(path,limit,tail)
   if a.full_dump and path.endswith('/MEMORY.DMP') and len(data)!=size:raise ValueError('MEMORY.DMP exceeds 1GiB safety limit; refusing a partial full dump')
   output=a.output/path.lstrip('/');output.parent.mkdir(parents=True,exist_ok=True);output.write_bytes(data)
   rows.append({'path':path,'bytes':len(data),'original_size':size,'truncated':len(data)!=size,'tail':tail,'sha256':hashlib.sha256(data).hexdigest()})
   print('SAVED',path,len(data),'bytes',flush=True)
  except OSError as e:
   rows.append({'path':path,'error':str(e)});print('MISSING/UNREADABLE',path,flush=True)
finally:
 if r:r.close()
 if fd is not None:os.close(fd)
 report={'source':'host image' if a.image else 'root TWRP raw ADB','mode':'read-only NTFS, forensic/no journal recovery','writes_phone':False,'raw_bytes_read':fetched,'files':rows}
 (a.output/'report.json').write_text(json.dumps(report,indent=2)+'\n')
print('Saved report:',a.output/'report.json')
