#!/usr/bin/env python3
"""Create an isolated PEP fixed-register-call experiment, never edit BSP input."""
from pathlib import Path
import hashlib,json,struct,zipfile
ROOT=Path(__file__).resolve().parents[1]
source=ROOT/'reference/windows_silicon_qcom_kona/Drivers/SOC/PowerManagement/qcpep8250.sys'
b=source.read_bytes();expected='39fafcd60536c7d36dd95187dc9f51bfc4af661b614bce4a5e9ec0729fe24e01'
assert hashlib.sha256(b).hexdigest()==expected
pe=struct.unpack_from('<I',b,60)[0];opt=pe+24;section=opt+struct.unpack_from('<H',b,pe+20)[0]
assert struct.unpack_from('<H',b,pe+4)[0]==0xaa64
count=struct.unpack_from('<H',b,pe+6)[0]
def offset(rva):
 for i in range(count):
  vs,va,rs,raw=struct.unpack_from('<IIII',b,section+i*40+8)
  if va<=rva<va+rs:return raw+rva-va
 raise ValueError(hex(rva))
patched=bytearray(b);changes=[]
for rva in (0x1df358,0x21555c):
 off=offset(rva);instruction=struct.unpack_from('<I',b,off)[0]
 assert instruction>>26==0b100101
 imm=instruction&0x3ffffff
 if imm&(1<<25):imm-=1<<26
 assert rva+imm*4==0x5c50
 old=b[off:off+4];new=bytes.fromhex('1f2003d5');patched[off:off+4]=new
 changes.append({'rva':rva,'offset':off,'before':old.hex(),'after':new.hex(),'target_rva':0x5c50})
# No original embedded signature may survive a code modification.
security,size=struct.unpack_from('<II',b,opt+112+4*8)
assert security and size and security+size==len(b), 'Expected trailing WIN_CERTIFICATE'
assert security%8==0 and struct.unpack_from('<HH',b,security+4)==(0x200,2)
patched=patched[:security]
struct.pack_into('<II',patched,opt+112+4*8,0,0)
# PE checksum is regenerated for the unsigned diagnostic copy.
checksum_offset=opt+64;struct.pack_into('<I',patched,checksum_offset,0)
total=0
for i in range(0,len(patched),2):
 total+=int.from_bytes(patched[i:i+2],'little');total=(total&0xffff)+(total>>16)
total=(total&0xffff)+(total>>16);checksum=(total+len(patched))&0xffffffff
struct.pack_into('<I',patched,checksum_offset,checksum)
allowed=set(range(checksum_offset,checksum_offset+4))
allowed.update(range(opt+112+4*8,opt+112+5*8))
for c in changes:allowed.update(range(c['offset'],c['offset']+4))
assert all(i in allowed for i,(a,z) in enumerate(zip(b,patched)) if a!=z)
manifest={'original_sha256':expected,'unsigned_sha256':hashlib.sha256(patched).hexdigest(),'changes':changes,'checksum_offset':checksum_offset,'removed_embedded_certificate':{'offset':security,'size':size},'purpose':'Diagnostic skip of both calls to fixed 18358800/18350800 register helper. Does not establish the helper caused watchdog. Thermal/power behavior is not validated; do not deploy as a normal driver.'}
files={p.name:p.read_bytes() for p in (ROOT/'firmware/munch/GpuPepLmh').iterdir() if p.is_file()}
files['qcpep-lmh-unsigned.sys']=bytes(patched);files['patch.json']=(json.dumps(manifest,indent=2)+'\n').encode()
for n in ('late.ps1','policy.json','providers.txt'):files[n]=(ROOT/'firmware/munch/GpuPepLate'/n).read_bytes()
for n in ('collect.cmd','collect.ps1'):files[n]=(ROOT/'firmware/munch/GpuPepDiagnostics'/n).read_bytes()
files['SHA256.json']=(json.dumps({n:hashlib.sha256(v).hexdigest() for n,v in files.items()},indent=2)+'\n').encode()
out=ROOT/'out/kona-gpu/munch-pep-lmh-test.zip'
with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as z:
 for n,v in files.items():z.writestr('MunchPepLmh/'+n,v)
with zipfile.ZipFile(out) as z:
 assert z.testzip() is None
 for n,v in files.items():assert z.read('MunchPepLmh/'+n)==v
assert source.read_bytes()==b
print(out);print(json.dumps(manifest,indent=2))
