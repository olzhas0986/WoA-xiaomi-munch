#!/usr/bin/env python3
"""Execute original vendor exit cleanup: host policy alone does not save PHY."""
from pathlib import Path
import struct,zlib
from unicorn import Uc,UC_ARCH_ARM64,UC_MODE_ARM,UC_HOOK_CODE
from unicorn.arm64_const import *
p=(Path(__file__).resolve().parents[1]/'inputs/munch/extracted-xbl/QcomPkg/Drivers/UsbConfigDxe/UsbConfigDxe.efi').read_bytes()
ranges=((0x16ec,0x60,0xff5914dd),(0x5400,0x388,0x39872245),(0x1798,0x150,0xbf9cfae7))
for start,size,crc in ranges:assert zlib.crc32(p[start:start+size])==crc
pos=0x16000
while pos+8<=len(p):
 page,size=struct.unpack_from('<II',p,pos)
 if not size:break
 for i in range(pos+8,pos+size,2):
  v=struct.unpack_from('<H',p,i)[0]
  if v>>12:
   for a,n,c in ranges:assert not(page+(v&4095)<a+n and page+(v&4095)+8>a)
 pos+=size
assert p[0x10098]==0
for feature in (0,1):
 u=Uc(UC_ARCH_ARM64,UC_MODE_ARM);u.mem_map(0,0x20000);u.mem_map(0x100000,0x10000);u.mem_write(0,p)
 def word(a,v):u.mem_write(a,struct.pack('<Q',v))
 u.mem_write(0x10098,bytes([feature]));u.mem_write(0x15bd8,b'\x00')
 for a in (0x15c08,0x15be0):word(a,0)
 for i in range(2):
  core=0x104000+i*0x100
  word(0x15378+i*0xe8,core);word(core+0x60,0x101000)
  u.mem_write(0x15440+i*0xe8,b'\x01');u.mem_write(0x15444+i*0xe8,struct.pack('<I',1))
 calls=[]
 def stub(cpu,address,size,data):
  if address==0x101000:
   assert cpu.reg_read(UC_ARM64_REG_X1)==1
   calls.append(cpu.reg_read(UC_ARM64_REG_X0))
  cpu.reg_write(UC_ARM64_REG_X0,0);cpu.reg_write(UC_ARM64_REG_PC,cpu.reg_read(UC_ARM64_REG_X30))
 for a in (0x101000,0xb2e0,0xc348):u.hook_add(UC_HOOK_CODE,stub,begin=a,end=a)
 u.reg_write(UC_ARM64_REG_SP,0x10fff0);u.reg_write(UC_ARM64_REG_X30,0x102000)
 u.emu_start(0x5400,0x102000,count=2000)
 assert u.reg_read(UC_ARM64_REG_PC)==0x102000
 assert len(calls)==(2 if feature==0 else 0)
 print('PASS actual vendor exit: HostModeSupported=%d, non-driving calls=%d despite host policy'%(feature,len(calls)))
