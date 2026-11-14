#!/usr/bin/env python3
"""Verify the pinned PEP binary's identity-method gate without patching it."""
import hashlib,json,struct
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
source=ROOT/'reference/windows_silicon_qcom_kona/Drivers/SOC/PowerManagement/qcpep8250.sys'
b=source.read_bytes();pe=struct.unpack_from('<I',b,60)[0]
assert b[pe:pe+4]==b'PE\0\0' and struct.unpack_from('<H',b,pe+4)[0]==0xaa64
count=struct.unpack_from('<H',b,pe+6)[0];optional=pe+24
section=optional+struct.unpack_from('<H',b,pe+20)[0]
def offset(rva):
 for i in range(count):
  vs,va,rs,raw=struct.unpack_from('<IIII',b,section+i*40+8)
  if va<=rva<va+rs:return raw+rva-va
 raise ValueError(hex(rva))
def word(rva):return struct.unpack_from('<I',b,offset(rva))[0]
def branch_target(rva):
 instruction=word(rva);assert instruction>>26==0b100101
 imm=instruction&0x3ffffff
 if imm&(1<<25):imm-=1<<26
 return rva+imm*4
assert b[offset(0x3e684):offset(0x3e684)+4]==b'PEPH'
assert branch_target(0x20f314)==0x3e170
assert branch_target(0x20f340)==branch_target(0x20f360)==0x154568
# The compare thunk loads the import at RVA 16a458; resolve its actual name.
imp,_=struct.unpack_from('<II',b,optional+112+8);p=offset(imp);name=None
while b[p:p+20]!=b'\0'*20:
 orig,_,_,_,iat=struct.unpack_from('<IIIII',b,p);i=0
 while True:
  value=struct.unpack_from('<Q',b,offset(orig or iat)+i*8)[0]
  if not value:break
  if iat+i*8==0x16a458:
   start=offset(value)+2;name=b[start:b.index(0,start)].decode()
  i+=1
 p+=20
assert name=='wcscmp'
assert word(0x2121a8)==0xc000000e
instruction=word(0x20f488)
assert instruction&0xff00001f==0x18000000
imm=(instruction>>5)&0x7ffff
if imm&(1<<18):imm-=1<<19
assert 0x20f488+imm*4==0x2121a8
result={'binary_sha256':hashlib.sha256(b).hexdigest(),'method_name':'PEPH','method_name_rva':'0x3e684','eval_helper_rva':'0x3e170','eval_call_rva':'0x20f314','identity_comparisons':['0x20f340','0x20f360'],'compare_import':name,'rejection_instruction_rva':'0x20f488','rejection_status':'0xc000000e','device_reported_status':'0xc000000e','interpretation':'Missing PEPH can reach this early identity rejection; fixing it requires a new firmware/device test, not a binary patch.'}
out=ROOT/'out/kona-gpu/pep-audit/peph-gate.json';out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(result,indent=2)+'\n')
print('Native PEPH call, wcscmp identity gate and STATUS_NO_SUCH_DEVICE return: verified')
