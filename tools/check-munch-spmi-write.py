#!/usr/bin/env python3
"""Check actual pinned SPMI WriteLong ABI with a fake bus; no hardware writes."""
from pathlib import Path
import struct,zlib
from unicorn import Uc,UC_ARCH_ARM64,UC_MODE_ARM,UC_HOOK_CODE
from unicorn.arm64_const import *
p=(Path(__file__).resolve().parents[1]/'inputs/munch/extracted-xbl/QcomPkg/Drivers/SPMIDxe/SPMIDxe.efi').read_bytes()
assert struct.unpack_from('<Q',p,0x8098)[0]==0x1494
assert zlib.crc32(p[0x1494:0x152c])==0x7034a44d
pos=0xa000
while pos+8<=len(p):
 page,size=struct.unpack_from('<II',p,pos)
 if not size:break
 for i in range(pos+8,pos+size,2):
  v=struct.unpack_from('<H',p,i)[0]
  if v>>12:assert not(page+(v&4095)<0x152c and page+(v&4095)+8>0x1494)
 pos+=size
for error in (0,9):
 u=Uc(UC_ARCH_ARM64,UC_MODE_ARM);u.mem_map(0,0x20000);u.mem_map(0x100000,0x10000);u.mem_write(0,p)
 u.mem_write(0x81b8,struct.pack('<Q',0x104000));u.mem_write(0x104018,struct.pack('<Q',0x101100));u.mem_write(0x104020,struct.pack('<Q',0x101200));u.mem_write(0x105000,b'\x04')
 calls=[]
 def service(cpu,address,size,data):
  if address==0x101100:assert cpu.reg_read(UC_ARM64_REG_X0)==8;result=4;calls.append('raise')
  elif address==0x101200:assert cpu.reg_read(UC_ARM64_REG_X0)==4;result=0;calls.append('restore')
  else:
   assert [cpu.reg_read(r) for r in (UC_ARM64_REG_X0,UC_ARM64_REG_X1,UC_ARM64_REG_X2,UC_ARM64_REG_X3,UC_ARM64_REG_X4)]==[2,0,0x1544,0x105000,1]
   assert bytes(cpu.mem_read(0x105000,1))==b'\x04'
   result=error;calls.append('write')
  cpu.reg_write(UC_ARM64_REG_X0,result);cpu.reg_write(UC_ARM64_REG_PC,cpu.reg_read(UC_ARM64_REG_X30))
 for addr in (0x101100,0x101200,0x2ab4):u.hook_add(UC_HOOK_CODE,service,begin=addr,end=addr)
 for r,v in zip((UC_ARM64_REG_X0,UC_ARM64_REG_X1,UC_ARM64_REG_X2,UC_ARM64_REG_X3,UC_ARM64_REG_X4,UC_ARM64_REG_X5),(0x8088,2,0,0x1544,0x105000,1)):u.reg_write(r,v)
 u.reg_write(UC_ARM64_REG_SP,0x10fff0);u.reg_write(UC_ARM64_REG_X30,0x102000)
 u.emu_start(0x1494,0x102000,count=2000)
 assert u.reg_read(UC_ARM64_REG_PC)==0x102000 and u.reg_read(UC_ARM64_REG_X0)==error
 assert calls==['raise','write','restore']
 print('PASS actual SPMI WriteLong arguments/TPL/status',error)
