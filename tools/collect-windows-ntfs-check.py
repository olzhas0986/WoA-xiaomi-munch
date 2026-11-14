#!/usr/bin/env python3
"""Read selected Windows NTFS sectors via root TWRP ADB and compare locally.
Never mounts, formats, repairs, writes, reboots or changes the phone.
"""
from pathlib import Path
import argparse,hashlib,json,subprocess
R=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--serial');p.add_argument('--image',type=Path,help='Host-only replay instead of ADB');p.add_argument('--output',type=Path,default=R/'out/windows-full/device-ntfs-check')
a=p.parse_args();plan=json.loads((R/'out/windows-full/ntfs-read-check.json').read_text());bs=plan['block_size']
assert bs==4096 and plan['image_bytes']==33806090240
adb=['adb']+(['-s',a.serial] if a.serial else [])
def run(command,binary=False):
 r=subprocess.run(adb+['exec-out' if binary else 'shell',command],check=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
 return r.stdout if binary else r.stdout.decode(errors='replace').strip()
if a.image:
 assert a.image.is_file() and a.image.stat().st_size==plan['image_bytes']
else:
 subprocess.run(adb+['get-state'],check=True,stdout=subprocess.DEVNULL)
 assert run('id -u')=='0','Root TWRP required'
 assert run('getprop ro.twrp.version'),'Boot TWRP first; this script will not reboot the phone'
 devices=[run('getprop '+x) for x in ('ro.product.device','ro.product.vendor.device','ro.product.system.device','ro.build.product')]
 assert 'munch' in devices,'Unexpected device'
 assert run('readlink -f /dev/block/bootdevice/by-name/win')=='/dev/block/sda37','Unexpected win node'
 assert run('blockdev --getss /dev/block/sda37')=='4096','Expected 4Kn'
 assert int(run('blockdev --getsize64 /dev/block/sda37'))==plan['image_bytes'],'Unexpected win size'
a.output.mkdir(parents=True,exist_ok=True);results=[]
for s in plan['samples']:
 name=s['name'];sector=s['sector'];count=s['count']
 assert all(x.isalnum() or x=='-' for x in name) and 0<count<=2048
 assert 0<=sector and sector+count<=plan['image_bytes']//bs
 if a.image:
  with a.image.open('rb') as f:f.seek(sector*bs);data=f.read(count*bs)
 else:
  data=run(f'dd if=/dev/block/sda37 bs=4096 skip={sector} count={count} 2>/dev/null',binary=True)
 assert len(data)==count*bs,f'Short/bad read of {name}: {len(data)} bytes'
 actual=hashlib.sha256(data).hexdigest();match=actual==s['sha256']
 (a.output/(name+'.bin')).write_bytes(data)
 results.append(dict(s,actual_sha256=actual,match=match))
 print(('MATCH' if match else 'DIFF '),name,flush=True)
report={'source':'host replay' if a.image else 'root TWRP ADB raw reads','all_match':all(s['match'] for s in results),'bytes_read':sum(s['count']*bs for s in results),'writes_phone':False,'samples':results}
(a.output/'report.json').write_text(json.dumps(report,indent=2)+'\n')
print('Saved:',a.output/'report.json')
print('ALL SELECTED RANGES MATCH' if report['all_match'] else 'DIFFERENCES FOUND; do not rewrite or repair until the report is inspected')
