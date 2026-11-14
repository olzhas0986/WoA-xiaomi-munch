#!/usr/bin/env python3
"""Read ARM64 PAGEDU64 triage module records and saved frame chains.

Module layout follows Ghidra LoadedDriver (Apache 2.0); modern SizeOfImage
is a DWORD. NT labels use the local build-26100 symbol export.
"""
import struct,json,re,bisect,sys
from pathlib import Path
b=Path(sys.argv[1] if len(sys.argv)>1 else 'out/kona-gpu/040124-6093-01.dmp').read_bytes()
assert b[:8]==b'PAGEDU64' and struct.unpack_from('<I',b,0xf98)[0]==4
u=lambda o:struct.unpack_from('<I',b,o)[0]
q=lambda o:struct.unpack_from('<Q',b,o)[0]
mods=[]
for i in range(u(0x2034)):
 p=u(0x2030)+i*144;n=u(p);name=b[n+4:n+4+u(n)*2].decode('utf-16le',errors='replace');mods.append((q(p+56),u(p+72),name.split('\\')[-1]))
t=Path('out/windows-full/dump-analysis/nt-symbols.txt').read_text(errors='replace');sections={}
for block in re.split(r'SECTION HEADER #',t)[1:]:
 i=int(block.splitlines()[0]);m=re.search(r'([0-9A-F]+) virtual address',block)
 if m:sections[i]=int(m[1],16)
syms=sorted((sections[int(s)]+int(o),n) for n,s,o in re.findall(r'S_PUB32[^\n]*`([^`]+)`\n\s*flags = [^\n]*addr = (\d+):(\d+)',t) if int(s) in sections); addrs=[v[0] for v in syms]
def label(a):
 a=(a&0xffffffffffff)|0xffff000000000000
 for base,size,name in mods:
  if base<=a<base+size:
   r=a-base
   if name=='ntoskrnl.exe':
    i=bisect.bisect_right(addrs,r)-1
    return f'nt!{syms[i][1]}+{r-syms[i][0]:x} (RVA {r:x})'
   return f'{name}+{r:x}'
 return ''
ranges=[(q(0x2048),u(0x2028),u(0x202c))]
for i in range(u(0x207c)):
 p=u(0x2078)+16*i;ranges.append((q(p),u(p+8),u(p+12)))
def read(a,n):
 for va,o,size in ranges:
  if va<=a and a+n<=va+size:return b[o+a-va:o+a-va+n]
 return b''
print('fault',label(q(0x50)))
c=u(0x200c)
for n,o in [('fp',240),('lr',248),('sp',256),('pc',264)]:print(n,hex(q(c+o)),label(q(c+o)))
fp=q(c+240)
for i in range(40):
 d=read(fp,16)
 if len(d)!=16:break
 nxt,lr=struct.unpack('<QQ',d);print('FRAME',hex(fp),hex(lr),label(lr))
 if nxt<=fp:break
 fp=nxt
print('STACK CANDIDATES')
va,o,size=ranges[0]
for off in range(0,size-8,8):
 a=q(o+off);s=label(a)
 if s and ('qcpep' in s or 'Pep' in s or 'PoFx' in s):print(hex(va+off),hex(a),s)
