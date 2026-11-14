#!/usr/bin/env python3
"""Execute the supplied PMIC read wrappers; hardware operations are stubbed."""
from pathlib import Path
import hashlib,struct,zlib
from unicorn import Uc,UC_ARCH_ARM64,UC_MODE_ARM,UC_HOOK_CODE
from unicorn.arm64_const import UC_ARM64_REG_X0,UC_ARM64_REG_X1,UC_ARM64_REG_X30,UC_ARM64_REG_SP,UC_ARM64_REG_PC
ROOT=Path(__file__).resolve().parents[1]
p=(ROOT/'inputs/munch/extracted-xbl/QcomPkg/Drivers/PmicDxe/PmicDxeLa.efi').read_bytes()
assert hashlib.sha256(p).hexdigest()=='f3f69de82bd94c2f4b3443effc67b0ae1ba126b0e0731d11a8ddc885b337780f'
assert zlib.crc32(p[0x29b8:0x2ca4])==0x0b187554
pos=0x2e000
while pos+8<=len(p):
 page,size=struct.unpack_from('<II',p,pos)
 if not size:break
 for i in range(pos+8,pos+size,2):
  v=struct.unpack_from('<H',p,i)[0]
  if v>>12:assert not(page+(v&4095)<0x2ca4 and page+(v&4095)+8>0x29b8)
 pos+=size
for entry,width,initial,value,callback in [(0x2b88,4,5,0,0x101000),(0x2b88,4,5,1,0x101000),(0x2a34,1,0,1,0x101100),(0x2c4c,4,3,2,0xe3ac)]:
 for available in (True,False):
  u=Uc(UC_ARCH_ARM64,UC_MODE_ARM);u.mem_map(0,0x40000);u.mem_map(0x100000,0x10000);u.mem_write(0,p)
  u.mem_write(0x2c0a8,struct.pack('<Q',0x104000));u.mem_write(0x2b5b0,struct.pack('<I',1))
  u.mem_write(0x104078,struct.pack('<Q',0x101000));u.mem_write(0x104080,struct.pack('<Q',0x101100))
  u.mem_write(0x105000,b'\xff'*8);calls=[]
  def service(emulator,address,size,data):
   if address==0x29b8:result=0 if available else 0x8000000000000003
   else:
    assert address==callback and emulator.reg_read(UC_ARM64_REG_X0)==1
    output=emulator.reg_read(UC_ARM64_REG_X1);assert output==0x105000
    emulator.mem_write(output,value.to_bytes(width,'little'));calls.append(address);result=0
   emulator.reg_write(UC_ARM64_REG_X0,result)
   emulator.reg_write(UC_ARM64_REG_PC,emulator.reg_read(UC_ARM64_REG_X30))
  for addr in (0x29b8,callback):u.hook_add(UC_HOOK_CODE,service,begin=addr,end=addr)
  u.reg_write(UC_ARM64_REG_X0,0x105000);u.reg_write(UC_ARM64_REG_X30,0x102000);u.reg_write(UC_ARM64_REG_SP,0x10fff0)
  u.emu_start(entry,0x102000,count=10000)
  assert u.reg_read(UC_ARM64_REG_PC)==0x102000
  assert u.reg_read(UC_ARM64_REG_X0)==(0 if available else 0x8000000000000003)
  assert int.from_bytes(u.mem_read(0x105000,width),'little')==(value if available else initial)
  assert bool(calls)==available
 print('PASS PMIC read wrapper',hex(entry),'output size',width,'success and unavailable')
