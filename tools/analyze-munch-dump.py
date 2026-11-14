#!/usr/bin/env python3
"""Read-only ARM64 bitmap kernel dump inspection. No debugger inference."""
from pathlib import Path
import argparse,struct,json,uuid
p=argparse.ArgumentParser();p.add_argument('dump',type=Path);p.add_argument('--output',type=Path,default=Path('out/windows-full/dump-analysis'));a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True)
f=a.dump.open('rb');header=f.read(0x2000)
def u32(b,o=0):return struct.unpack_from('<I',b,o)[0]
def u64(b,o=0):return struct.unpack_from('<Q',b,o)[0]
assert header[:8]==b'PAGEDU64' and u32(header,0x30)==0xaa64
assert u32(header,0xf98) in (5,6),'Only bitmap dumps supported'
f.seek(0x2000);summary=f.read(0x38);assert summary[:8] in (b'SDMPDUMP',b'FDMPDUMP')
start,present,total=struct.unpack_from('<QQQ',summary,0x20)
bitmap=f.read((total+7)//8);mapping={};pos=start
for i,b in enumerate(bitmap):
 for bit in range(8):
  if b&(1<<bit):mapping[i*8+bit]=pos;pos+=4096
assert len(mapping)==present and pos<=a.dump.stat().st_size
root=u64(header,0x10)&0x0000fffffffff000
cache={}
def physical(addr,n):
 result=bytearray()
 while n:
  page=addr>>12;within=addr&4095;k=min(n,4096-within)
  if page not in mapping:raise ValueError(f'Physical page missing {addr:#x}')
  if page not in cache:
   f.seek(mapping[page]);cache[page]=f.read(4096)
   if len(cache)>8192:cache.pop(next(iter(cache)))
  result+=cache[page][within:within+k];addr+=k;n-=k
 return bytes(result)
def translate(va):
 table=root
 for shift in (39,30,21,12):
  desc=u64(physical(table+((va>>shift)&511)*8,8))
  if not desc&1:raise ValueError(f'Unmapped VA {va:#x} level {shift}')
  if shift==12:return (desc&0x0000fffffffff000)+(va&4095)
  if desc&3==1:return (desc&0x0000fffffffff000&~((1<<shift)-1))+(va&((1<<shift)-1))
  assert desc&3==3
  table=desc&0x0000fffffffff000
 raise AssertionError()
def read(va,n):
 result=bytearray()
 while n:
  k=min(n,4096-(va&4095));result+=physical(translate(va),k);va+=k;n-=k
 return bytes(result)
def q(va):return u64(read(va,8))
def string(addr):
 b=read(addr,16);length=struct.unpack_from('<H',b)[0];assert length<=4096
 return read(u64(b,8),length).decode('utf-16le',errors='replace')
modules=[];head=u64(header,0x20);entry=q(head)
while entry!=head:
 assert len(modules)<512
 b=read(entry,0x68);modules.append({'entry':entry,'base':u64(b,0x30),'size':u32(b,0x40),'name':string(entry+0x58),'path':string(entry+0x48)})
 entry=u64(b)
def symbolize(addr):
 for m in modules:
  if m['base']<=addr<m['base']+m['size']:return m['name']+f'+{addr-m["base"]:#x}'
 return None
report={'bugcheck':hex(u32(header,0x38)),'parameters':[hex(u64(header,0x40+i*8)) for i in range(4)],'dtb':hex(root),'pages':present,'modules':modules}
for m in modules:
 try:
  b=read(m['base'],4096);pe=u32(b,60);opt=pe+24;debug,size=struct.unpack_from('<II',b,opt+112+6*8)
  for offset in range(0,size,28):
   d=read(m['base']+debug+offset,28)
   if u32(d,12)!=2:continue
   cv=read(m['base']+u32(d,20),u32(d,16))
   if cv[:4]==b'RSDS':m['pdb']={'name':cv[24:].split(b'\0')[0].decode(errors='replace'),'guid':str(uuid.UUID(bytes_le=cv[4:20])),'age':u32(cv,20)}
 except (ValueError,AssertionError,struct.error):pass
(a.output/'modules.json').write_text(json.dumps(report,indent=2))
print('Bugcheck',report['bugcheck'],report['parameters'],'pages',present)
for m in modules:print(hex(m['base']),hex(m['size']),m['name'],m.get('pdb',''))
# Permit follow-up exploratory scripts to reuse only verified memory mappings.
if __name__=='__main__' and u32(header,0x38)==0x101:
 prcb=u64(header,0x50);print('Unresponsive PRCB',hex(prcb))
 (a.output/'hung-prcb.bin').write_bytes(read(prcb,0x4000))
