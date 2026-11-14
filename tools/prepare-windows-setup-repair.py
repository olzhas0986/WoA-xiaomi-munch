#!/usr/bin/env python3
"""Prepare a device-specific recovery ZIP using read-only ADB access."""
from pathlib import Path
import argparse, collections, hashlib, json, os, shutil, subprocess, zipfile
from ntfs_remote_reader import ReadOnlyNtfs
from windows_setup_state import mark_system_store, prepare_specialize_retry, prepare_setup_child_retry
R=Path(__file__).resolve().parents[1]; O=R/'out/windows-full'; SIZE=33806090240
p=argparse.ArgumentParser();p.add_argument('--serial');p.add_argument('--image',type=Path);p.add_argument('--retry-child',action='store_true',help='Retry interrupted setup.exe after the BCD/Specialize repair');a=p.parse_args()
adb=['adb']+(['-s',a.serial] if a.serial else [])
def remote(cmd,binary=False):
 b=subprocess.check_output(adb+['exec-out' if binary else 'shell',cmd]);return b if binary else b.decode().strip()
gpt='fcd05950e644d334b97e2c0b8be9ed52fc55bcf79d8c251d62c227b47bd75bb6'
fd=None
if a.image:
 assert a.image.stat().st_size==SIZE;fd=os.open(a.image,os.O_RDONLY)
else:
 assert remote('id -u')=='0' and remote('getprop ro.twrp.version'),'Root TWRP required'
 assert 'munch' in [remote('getprop '+n) for n in ('ro.product.device','ro.product.vendor.device','ro.product.system.device','ro.build.product')]
 assert remote('readlink -f /dev/block/bootdevice/by-name/win')=='/dev/block/sda37'
 assert remote('blockdev --getss /dev/block/sda37')=='4096' and int(remote('blockdev --getsize64 /dev/block/sda37'))==SIZE
 assert not remote('while read s rest; do [ "$(readlink -f "$s" 2>/dev/null)" != /dev/block/sda37 ] || echo mounted; done </proc/mounts'),'Unmount win first'
 assert hashlib.sha256(remote('dd if=/dev/block/sda bs=4096 skip=2 count=2 2>/dev/null',True)).hexdigest()==gpt
cache=collections.OrderedDict(); fetched=0
def read(off,n):
 global fetched
 result=bytearray()
 while n:
  start=off//65536*65536
  if start not in cache:
   count=min(65536,SIZE-start);fetched+=count
   assert fetched<=256*1024*1024,'Raw read budget exceeded'
   b=os.pread(fd,count,start) if fd is not None else remote(f'dd if=/dev/block/sda37 bs=4096 skip={start//4096} count={count//4096} 2>/dev/null',True)
   assert len(b)==count,'Short raw read';cache[start]=b
   if len(cache)>512:cache.popitem(last=False)
  chunk=cache[start]; k=min(n,len(chunk)-(off-start));result.extend(chunk[off-start:off-start+k]);off+=k;n-=k
 return bytes(result)
work=O/('setup-child-fix' if a.retry_child else 'setup-state-fix');work.mkdir(exist_ok=True)
reader=None
try:
 reader=ReadOnlyNtfs(SIZE,read);path='/Windows/System32/config/SYSTEM'
 data,size=reader.read_file(path);assert len(data)==size
 source=work/'SYSTEM.before';source.write_bytes(data)
 offset=(prepare_setup_child_retry if a.retry_child else prepare_specialize_retry)(source,work/'SYSTEM.retry')
 physical=reader.map_file_offset(path,offset);assert physical%4096<=4092
 assert reader.map_file_offset(path,offset+3)==physical+3
 sector=physical//4096;before=read(sector*4096,4096);within=physical%4096
 assert before[within:within+4]==data[offset:offset+4]
 after=bytearray(before);after[within:within+4]=(work/'SYSTEM.retry').read_bytes()[offset:offset+4]
 assert sum(x!=y for x,y in zip(before,after))==1
 (work/'sector.before').write_bytes(before);(work/'sector.after').write_bytes(after)
finally:
 if reader:reader.close()
 if fd is not None:os.close(fd)
print('SYSTEM backup saved; phone has not been modified.',flush=True)
mark_system_store(O/'BCD',work/'BCD')
esp=work/'esp.img';shutil.copyfile(O/'esp-windows-4kn.img',esp)
subprocess.run(['mcopy','-o','-i',str(esp),str(work/'BCD'),'::/EFI/Microsoft/Boot/BCD'],check=True)
subprocess.run(['fsck.fat','-n',str(esp)],check=True)
def sha(path):
 with Path(path).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
script=(R/'firmware/munch/Recovery/repair-windows-setup').read_text()
values={'GPT_SHA':gpt,'ESP_SHA':sha(esp),'BEFORE_SHA':sha(work/'sector.before'),'AFTER_SHA':sha(work/'sector.after'),'SECTOR':str(sector)}
for k,v in values.items():script=script.replace('@'+k+'@',v)
if a.retry_child:
 script=script.replace('Retrying failed Specialize state...', 'Retrying interrupted Setup child...').replace('Specialize retry prepared.', 'Setup child retry prepared.')
assert '@' not in script
output=O/(('HOST-TEST-ONLY-' if a.image else 'munch-windows-')+('setup-child-fix' if a.retry_child else 'setup-fix')+('' if a.image else '-twrp')+'.zip')
with zipfile.ZipFile(output,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=1) as z:
 info=zipfile.ZipInfo('META-INF/com/google/android/update-binary');info.create_system=3;info.external_attr=0o100755<<16;z.writestr(info,script)
 z.writestr('META-INF/com/google/android/updater-script','# Handled by update-binary\n')
 z.write(esp,'payload/esp.img');z.write(work/'sector.after','payload/sector.after')
with zipfile.ZipFile(output) as z:
 assert z.testzip() is None
 for name,expected in [('payload/esp.img',values['ESP_SHA']),('payload/sector.after',values['AFTER_SHA'])]:
  with z.open(name) as f:assert hashlib.file_digest(f,'sha256').hexdigest()==expected
report=dict(values,zip=str(output),zip_sha256=sha(output),system_file_offset=offset,system_physical_offset=physical,host_fixture=bool(a.image),device_tested=False,retry_child=a.retry_child)
(work/'report.json').write_text(json.dumps(report,indent=2)+'\n');print('READY',output)
