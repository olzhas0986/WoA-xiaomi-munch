#!/usr/bin/env python3
"""Pinned munch 4Kn GPT plan and guarded application through root recovery ADB."""
import argparse,hashlib,json,re,struct,subprocess,uuid,zlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
SRC=ROOT/'out/munch-fresh/recovery-storage'
OUT=ROOT/'out/munch-fresh/repartition32'
BS=4096
FMT='<8sIIIIQQQQ16sQIII'
def header(block,where,last):
 h=list(struct.unpack_from(FMT,block))
 assert h[0]==b'EFI PART' and h[1]==0x10000 and h[2]==92 and h[4]==0
 assert h[5]==where and h[6]==(last if where==1 else 1)
 b=bytearray(block[:h[2]]);struct.pack_into('<I',b,16,0)
 assert zlib.crc32(b)==h[3]
 assert h[7]>=2 and h[7]<=h[8]<last and h[11]==64 and h[12]==128
 return h
def patch(block,table):
 b=bytearray(block);struct.pack_into('<I',b,88,zlib.crc32(table));struct.pack_into('<I',b,16,0)
 struct.pack_into('<I',b,16,zlib.crc32(b[:92]));return bytes(b)
def sha(b):return hashlib.sha256(b).hexdigest()
def prepare():
 p=(SRC/'gpt-primary.bin').read_bytes();b=(SRC/'gpt-backup.bin').read_bytes()
 assert (SRC/'disk.txt').read_text().strip()=='/dev/block/sda'
 geometry=(SRC/'geometry.txt').read_text().split();assert geometry==['4096','245202944']
 last=30650367
 ph=p[BS:2*BS];bh=b[-BS:];hp=header(ph,1,last);hb=header(bh,last,last)
 assert hp[9]==hb[9] and hp[7:9]==hb[7:9]
 assert hp[10]==2 and hb[10]==last-4
 table=p[2*BS:4*BS];bt=b[(hb[10]-(last-31))*BS:(hb[10]-(last-31)+2)*BS]
 assert table==bt and zlib.crc32(table)==hp[13]==hb[13]
 old=table[33*128:34*128]
 assert old[56:128].decode('utf-16le').rstrip('\0')=='userdata'
 assert struct.unpack_from('<QQ',old,32)==(2949120,30650111)
 assert not any(table[34*128:])
 new=bytearray(table);split=22261504
 struct.pack_into('<Q',new,33*128+40,split-1)
 ranges=[('esp',split,split+131072-1,'c12a7328-f81f-11d2-ba4b-00a0c93ec93b'),('msr',split+131072,split+131072+4096-1,'e3c9e316-0b5c-4db8-817d-f92df00215ae'),('win',split+131072+4096,30650111,'ebd0a0a2-b9e5-4433-87c0-68b6b72699c7')]
 for i,(name,start,end,kind) in enumerate(ranges,34):
  e=bytearray(128);e[:16]=uuid.UUID(kind).bytes_le;e[16:32]=uuid.uuid4().bytes_le
  struct.pack_into('<QQQ',e,32,start,end,0);e[56:56+len(name)*2]=name.encode('utf-16le');new[i*128:(i+1)*128]=e
 assert new[:33*128]==table[:33*128]
 copy=bytearray(new[33*128:34*128]);struct.pack_into('<Q',copy,40,30650111);assert copy==old
 used=[]
 for i in range(64):
  e=new[i*128:(i+1)*128]
  if any(e[:16]):
   start,end=struct.unpack_from('<QQ',e,32);assert hp[7]<=start<=end<=hp[8];used.append((start,end))
 used.sort();assert all(a[1]<c[0] for a,c in zip(used,used[1:]))
 assert sum(end-start+1 for _,start,end,_ in ranges)*BS==32*1024**3
 files={'primary-header':(1,ph,patch(ph,new)),'primary-table':(hp[10],table,bytes(new)),'backup-header':(last,bh,patch(bh,new)),'backup-table':(hb[10],bt,bytes(new))}
 OUT.mkdir(parents=True,exist_ok=True)
 manifest={'disk':'/dev/block/sda','block_size':BS,'last_lba':last,'userdata_new_last':split-1,'windows_area_bytes':32*1024**3,'partitions':[{'name':n,'first':s,'last':e,'bytes':(e-s+1)*BS} for n,s,e,_ in ranges],'files':{}}
 for name,(lba,olddata,newdata) in files.items():
  (OUT/(name+'.old.bin')).write_bytes(olddata);(OUT/(name+'.new.bin')).write_bytes(newdata)
  manifest['files'][name]={'lba':lba,'bytes':len(newdata),'old_sha256':sha(olddata),'new_sha256':sha(newdata)}
 header(files['primary-header'][2],1,last);header(files['backup-header'][2],last,last)
 (OUT/'plan.json').write_text(json.dumps(manifest,indent=2)+'\n')
 return manifest
def adb(*args):return subprocess.check_output(['adb',*args])
def apply():
 m=json.loads((OUT/'plan.json').read_text());assert m['disk']=='/dev/block/sda' and m['block_size']==4096 and m['last_lba']==30650367
 assert b'uid=0(' in adb('shell','id')
 assert adb('shell','getprop','ro.twrp.version').strip(), 'Root TWRP recovery required'
 disk=m['disk']
 assert adb('shell','cat','/sys/class/block/sda/queue/logical_block_size').strip()==b'4096'
 assert adb('shell','cat','/sys/class/block/sda/size').strip()==b'245202944'
 def read(lba,size):return adb('exec-out',f'dd if={disk} bs=4096 skip={lba} count={size//BS} 2>/dev/null')
 for name,f in m['files'].items():
  assert sha(read(f['lba'],f['bytes']))==f['old_sha256'], 'Live GPT differs from backup: '+name
  assert sha((OUT/(name+'.new.bin')).read_bytes())==f['new_sha256']
 print('Live primary and backup GPT match saved originals.',flush=True)
 adb('shell','twrp unmount data')
 mounts=adb('shell','cat','/proc/mounts').decode()
 assert not re.search(r'\S+ /data(?:/\S*)? ',mounts) and '/dev/block/sda34 ' not in mounts,'userdata is still mounted; stopped'
 # Stage and verify each RAM file before the first disk write.
 for name,f in m['files'].items():
  dest='/tmp/munch32-'+name+'.bin'
  subprocess.run(['adb','push',str(OUT/(name+'.new.bin')),dest],check=True)
  assert sha(adb('exec-out','cat '+dest))==f['new_sha256']
 print('Writing backup GPT first, then primary GPT.',flush=True)
 for name in ('backup-table','backup-header','primary-table','primary-header'):
  f=m['files'][name];dest='/tmp/munch32-'+name+'.bin'
  result=adb('shell',f'dd if={dest} of={disk} bs=4096 seek={f["lba"]} count={f["bytes"]//BS} conv=notrunc && sync')
  print(result.decode(),end='',flush=True)
  assert sha(read(f['lba'],f['bytes']))==f['new_sha256'],'Readback failed: '+name
 (OUT/'applied.json').write_text(json.dumps({'status':'GPT written and read back','userdata_must_be_formatted_in_recovery':True},indent=2)+'\n')
 print('GPT VERIFIED. Rebooting recovery. Use Wipe > Format Data before booting Android.',flush=True)
 subprocess.run(['adb','reboot','recovery'],check=True)
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--apply',action='store_true');args=ap.parse_args()
 if args.apply:apply()
 else:
  m=prepare();print(json.dumps(m['partitions'],indent=2));print('Prepared and validated:',OUT/'plan.json')
