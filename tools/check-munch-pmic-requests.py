#!/usr/bin/env python3
"""Execute pinned PMIC request wrappers; hardware writes are replaced by stubs."""
from pathlib import Path
import hashlib,struct,zlib
from unicorn import Uc,UC_ARCH_ARM64,UC_MODE_ARM,UC_HOOK_CODE
from unicorn.arm64_const import UC_ARM64_REG_X0,UC_ARM64_REG_X1,UC_ARM64_REG_X30,UC_ARM64_REG_SP,UC_ARM64_REG_PC
ROOT=Path(__file__).resolve().parents[1]
p=(ROOT/'inputs/munch/extracted-xbl/QcomPkg/Drivers/PmicDxe/PmicDxeLa.efi').read_bytes()
assert hashlib.sha256(p).hexdigest()=='f3f69de82bd94c2f4b3443effc67b0ae1ba126b0e0731d11a8ddc885b337780f'
assert zlib.crc32(p[0x29b8:0x2e0c])==0xb5cf6d7a
pos=0x2e000
while pos+8<=len(p):
 page,size=struct.unpack_from('<II',p,pos)
 if not size:break
 for i in range(pos+8,pos+size,2):
  v=struct.unpack_from('<H',p,i)[0]
  if v>>12:assert not(page+(v&4095)<0x2e0c and page+(v&4095)+8>0x29b8)
 pos+=size
for entry,arg,target in [(0x2b3c,1,0x101400),(0x2b3c,0,0x101400),(0x2cd0,0,0xe520)]:
 for available in (True,False):
  u=Uc(UC_ARCH_ARM64,UC_MODE_ARM);u.mem_map(0,0x40000);u.mem_map(0x100000,0x10000);u.mem_write(0,p)
  u.mem_write(0x2c0a8,struct.pack('<Q',0x104000));u.mem_write(0x2b5b0,struct.pack('<I',1));u.mem_write(0x104060,struct.pack('<Q',0x101400))
  calls=[]
  def service(emulator,address,size,data):
   if address==0x29b8:result=0 if available else 0x8000000000000003
   elif address==0x447c:result=42
   else:
    assert address==target and emulator.reg_read(UC_ARM64_REG_X0)==1
    assert emulator.reg_read(UC_ARM64_REG_X1)==arg
    calls.append(address);result=0
   emulator.reg_write(UC_ARM64_REG_X0,result);emulator.reg_write(UC_ARM64_REG_PC,emulator.reg_read(UC_ARM64_REG_X30))
  for addr in (0x29b8,0x447c,target):u.hook_add(UC_HOOK_CODE,service,begin=addr,end=addr)
  u.reg_write(UC_ARM64_REG_X0,arg);u.reg_write(UC_ARM64_REG_X30,0x102000);u.reg_write(UC_ARM64_REG_SP,0x10fff0)
  u.emu_start(entry,0x102000,count=10000)
  assert u.reg_read(UC_ARM64_REG_PC)==0x102000
  assert u.reg_read(UC_ARM64_REG_X0)==(0 if available else 0x8000000000000003)
  assert bool(calls)==available
 print('PASS PMIC request wrapper',hex(entry),'argument',arg,'success and unavailable')
