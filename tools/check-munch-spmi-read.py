#!/usr/bin/env python3
"""Run actual SPMI ReadLong wrapper against fake TPL and read-only bus operations."""
from pathlib import Path
import hashlib,struct,zlib
from unicorn import Uc,UC_ARCH_ARM64,UC_MODE_ARM,UC_HOOK_CODE
from unicorn.arm64_const import *
ROOT=Path(__file__).resolve().parents[1]
p=(ROOT/'inputs/munch/extracted-xbl/QcomPkg/Drivers/SPMIDxe/SPMIDxe.efi').read_bytes()
assert hashlib.sha256(p).hexdigest()=='19f0598523dcc9f4854659f7531a8e7621b308db6d599a0819a00f7ed7091cf1'
assert struct.unpack_from('<QQ',p,0x8088)==(0x10001,0x13dc)
assert zlib.crc32(p[0x13dc:0x1494])==0xe72b1d9a
pos=0xa000
while pos+8<=len(p):
 page,size=struct.unpack_from('<II',p,pos)
 if not size:break
 for i in range(pos+8,pos+size,2):
  v=struct.unpack_from('<H',p,i)[0]
  if v>>12:assert not(page+(v&4095)<0x1494 and page+(v&4095)+8>0x13dc)
 pos+=size
for error in (0,9):
 u=Uc(UC_ARCH_ARM64,UC_MODE_ARM);u.mem_map(0,0x20000);u.mem_map(0x100000,0x10000);u.mem_write(0,p)
 u.mem_write(0x81b8,struct.pack('<Q',0x104000));u.mem_write(0x104018,struct.pack('<Q',0x101100));u.mem_write(0x104020,struct.pack('<Q',0x101200))
 calls=[]
 def service(emulator,address,size,data):
  if address==0x101100:assert emulator.reg_read(UC_ARM64_REG_X0)==8;result=4;calls.append('raise')
  elif address==0x101200:assert emulator.reg_read(UC_ARM64_REG_X0)==4;result=0;calls.append('restore')
  else:
   assert [emulator.reg_read(r) for r in (UC_ARM64_REG_X0,UC_ARM64_REG_X1,UC_ARM64_REG_X2,UC_ARM64_REG_X3,UC_ARM64_REG_X4)]==[2,0,0x1544,0x105000,1]
   if not error:
    emulator.mem_write(0x105000,b'\x12');emulator.mem_write(emulator.reg_read(UC_ARM64_REG_X5),struct.pack('<I',1))
   result=error;calls.append('read')
  emulator.reg_write(UC_ARM64_REG_X0,result);emulator.reg_write(UC_ARM64_REG_PC,emulator.reg_read(UC_ARM64_REG_X30))
 for addr in (0x101100,0x101200,0x26f8):u.hook_add(UC_HOOK_CODE,service,begin=addr,end=addr)
 regs=(UC_ARM64_REG_X0,UC_ARM64_REG_X1,UC_ARM64_REG_X2,UC_ARM64_REG_X3,UC_ARM64_REG_X4,UC_ARM64_REG_X5,UC_ARM64_REG_X6)
 for r,v in zip(regs,(0x8088,2,0,0x1544,0x105000,1,0x105010)):u.reg_write(r,v)
 u.reg_write(UC_ARM64_REG_SP,0x10fff0);u.reg_write(UC_ARM64_REG_X30,0x102000)
 u.emu_start(0x13dc,0x102000,count=2000)
 assert u.reg_read(UC_ARM64_REG_PC)==0x102000 and u.reg_read(UC_ARM64_REG_X0)==error
 assert calls==['raise','read','restore']
 assert struct.unpack('<I',u.mem_read(0x105010,4))[0]==(0 if error else 1)
 print('PASS SPMI ReadLong: SID/address/buffer/count/TPL and return status',error)
