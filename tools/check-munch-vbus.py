#!/usr/bin/env python3
"""Execute the pinned VBUS query wrapper, stubbing connection/PMIC reads only."""
from pathlib import Path
import hashlib,struct,zlib
from unicorn import Uc,UC_ARCH_ARM64,UC_MODE_ARM,UC_HOOK_CODE
from unicorn.arm64_const import UC_ARM64_REG_X0,UC_ARM64_REG_X1,UC_ARM64_REG_X2,UC_ARM64_REG_X30,UC_ARM64_REG_SP,UC_ARM64_REG_PC
ROOT=Path(__file__).resolve().parents[1]
p=(ROOT/'inputs/munch/extracted-xbl/QcomPkg/Drivers/UsbConfigDxe/UsbConfigDxe.efi').read_bytes()
assert hashlib.sha256(p).hexdigest()=='09b54b03ab45797c7b8aabc15bcb5a5bc91796b290ae3e1e5e17748ba10aed87'
assert struct.unpack_from('<Q',p,0x15188+0x98)[0]==0x16c8
assert zlib.crc32(p[0x66e4:0x6a24])==0x2f2e9fe5
pos=0x16000
while pos+8<=len(p):
 page,size=struct.unpack_from('<II',p,pos)
 if not size:break
 for i in range(pos+8,pos+size,2):
  v=struct.unpack_from('<H',p,i)[0]
  if v>>12:assert not(page+(v&4095)<0x6a24 and page+(v&4095)+8>0x66e4)
 pos+=size
for mode,state in [(1,0),(2,0),(2,1)]:
 u=Uc(UC_ARCH_ARM64,UC_MODE_ARM);u.mem_map(0,0x20000);u.mem_map(0x100000,0x10000);u.mem_write(0,p)
 def q(addr,value):u.mem_write(addr,struct.pack('<Q',value))
 def w(addr,value):u.mem_write(addr,struct.pack('<I',value))
 w(0x15828,50);q(0x15378,0x104000);q(0x15380,0x106000);q(0x104020,0x101300);w(0x105000,0xffffffff)
 called=[]
 def read(emulator,address,size,data):
  output=emulator.reg_read(UC_ARM64_REG_X1)
  if address==0xcd20:w(output,mode)
  else:w(output,state);called.append(True)
  emulator.reg_write(UC_ARM64_REG_X0,0)
  emulator.reg_write(UC_ARM64_REG_PC,emulator.reg_read(UC_ARM64_REG_X30))
 for addr in (0xcd20,0x101300):u.hook_add(UC_HOOK_CODE,read,begin=addr,end=addr)
 u.reg_write(UC_ARM64_REG_X0,0x15558);u.reg_write(UC_ARM64_REG_X1,0);u.reg_write(UC_ARM64_REG_X2,0x105000)
 u.reg_write(UC_ARM64_REG_SP,0x10fff0);u.reg_write(UC_ARM64_REG_X30,0x102000)
 u.emu_start(0x16c8,0x102000,count=10000)
 assert u.reg_read(UC_ARM64_REG_PC)==0x102000 and u.reg_read(UC_ARM64_REG_X0)==(0x8000000000000003 if mode==1 else 0)
 result=struct.unpack('<I',u.mem_read(0x105000,4))[0]
 assert result==(0xffffffff if mode==1 else state)
 assert bool(called)==(mode==2)
 print('PASS query wrapper: port-mode',mode,'raw-state',result,'PMIC read',bool(called))
