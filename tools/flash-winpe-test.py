#!/usr/bin/env python3
"""Flash only the two newly created munch partitions after size/hash checks."""
from pathlib import Path
import argparse,hashlib,json,re,subprocess
ROOT=Path(__file__).resolve().parents[1]
def run(*args):
 r=subprocess.run(['fastboot',*args],text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
 print(r.stdout,end='',flush=True)
 if r.returncode:raise RuntimeError('fastboot command failed')
 return r.stdout
def value(name):
 s=run('getvar',name)
 m=re.search(r'(?:^|\n)(?:\(bootloader\)\s*)?'+re.escape(name)+r':\s*(\S+)',s)
 if not m:raise RuntimeError('Missing fastboot variable: '+name)
 return m[1]
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--flash',action='store_true');args=ap.parse_args()
 manifest=json.loads((ROOT/'out/winpe/disk-images.json').read_text())
 plan=json.loads((ROOT/'out/munch-fresh/repartition32/plan.json').read_text())
 targets={x['name']:x['bytes'] for x in plan['partitions']}
 for name in ('esp','win'):
  item=manifest['images'][name];p=ROOT/item['sparse_file']
  assert item['raw_size']<=targets[name]
  assert hashlib.file_digest(p.open('rb'),'sha256').hexdigest()==item['sha256']
  print(f'{name}: {item["raw_size"]} bytes of FAT32 test image, target {targets[name]} bytes')
 if not args.flash:
  print('Images verified. --flash applies them to esp and win on the connected phone.');return
 devices=run('devices').strip().splitlines();assert len(devices)==1,'Connect exactly one fastboot phone'
 assert value('product')=='munch','Expected ordinary munch bootloader fastboot'
 for name in ('esp','win'):
  assert int(value('partition-size:'+name),16)==targets[name], 'Unexpected '+name+' partition size'
 # WinPE first: if transfer fails, the firmware and Android partitions are untouched.
 for name in ('win','esp'):
  run('flash',name,str(ROOT/manifest['images'][name]['sparse_file']))
 (ROOT/'out/winpe/flashed.json').write_text(json.dumps({'fastboot_flash_succeeded':['win','esp'],'source':manifest,'device_readback_verified':False},indent=2)+'\n')
 print('WinPE test files flashed. Next: fastboot boot out/munch-fresh/munch-uefi-winpe-ufs1.img')
if __name__=='__main__':main()
