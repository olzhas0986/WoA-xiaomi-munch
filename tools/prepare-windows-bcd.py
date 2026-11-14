#!/usr/bin/env python3
"""Create an offline UEFI Windows BCD bound to the verified munch GPT GUIDs.
Requires hivex Python bindings (may be provided through PYTHONPATH).
Device serialization follows DiscUtils.BootConfig Device/PartitionRecord.
"""
from pathlib import Path
import hashlib,json,shutil,struct,uuid
import hivex
R=Path(__file__).resolve().parents[1];O=R/'out/windows-full'
template=O/'template/BCD-Template';target=O/'BCD'
# GUIDs read from the already-applied, CRC-checked GPT, not disk numbering.
gpt=(R/'out/munch-fresh/repartition32/primary-header.new.bin').read_bytes()
table=(R/'out/munch-fresh/repartition32/primary-table.new.bin').read_bytes()
disk=uuid.UUID(bytes_le=gpt[56:72]);esp=uuid.UUID(bytes_le=table[34*128+16:34*128+32]);win=uuid.UUID(bytes_le=table[36*128+16:36*128+32])
assert str(esp)=='3af48454-a46c-4350-9323-e7a9e4660636'
assert str(win)=='5e8ea554-d756-4ff0-9fd6-73448f9ef3aa'
shutil.copyfile(template,target);h=hivex.Hivex(str(target),write=True)
objects=h.node_get_child(h.root(),'Objects')
loader='{b012b84d-c47c-4ed5-b722-c0c42163e569}';manager='{9dea862c-5cdd-4e70-acc1-f32b344d4795}'
def elements(obj):return h.node_get_child(h.node_get_child(objects,obj),'Elements')
def remove(parent,name):
 n=h.node_get_child(parent,name)
 if n:h.node_delete_child(n)
def setval(parent,name,typ,data):
 n=h.node_get_child(parent,name) or h.node_add_child(parent,name)
 h.node_set_value(n,{'key':'Element','t':typ,'value':data})
def text(p,n,s):setval(p,n,1,(s+'\0').encode('utf-16le'))
def integer(p,n,v):setval(p,n,3,struct.pack('<Q',v))
def device(part):
 b=bytearray(0x58)
 struct.pack_into('<I',b,0x10,6);struct.pack_into('<I',b,0x18,0x48)
 b[0x20:0x30]=part.bytes_le;struct.pack_into('<I',b,0x34,0)
 b[0x38:0x48]=disk.bytes_le
 return bytes(b)
for obj in (loader,manager):
 e=elements(obj)
 for n in list(h.node_children(e)):
  if h.node_name(n).startswith('4'):h.node_delete_child(n) # BCD-Template-only instructions
l=elements(loader);m=elements(manager)
for n in ('23000003','26000022'):remove(l,n) # no resume object or WinPE flag
text(l,'12000002',r'\Windows\system32\winload.efi');text(l,'12000004','Windows 11 IoT Enterprise LTSC 2024')
text(l,'22000002',r'\Windows')
setval(l,'11000001',3,device(win));setval(l,'21000001',3,device(win))
setval(l,'26000024',3,b'\x01') # preserve a crash screen for the first boot
setval(m,'11000001',3,device(esp));text(m,'23000003',loader)
setval(m,'24000001',7,(loader+'\0\0').encode('utf-16le'));integer(m,'25000004',0)
description=h.node_get_child(h.root(),'Description')
h.node_set_value(description,{'key':'System','t':4,'value':struct.pack('<I',1)})
h.node_set_value(description,{'key':'KeyName','t':1,'value':('BCD00000000\0').encode('utf-16le')})
h.commit(None);del h
# Reopen through the native hive parser and verify every generated element.
h=hivex.Hivex(str(target));objects=h.node_get_child(h.root(),'Objects')
def value(obj,key):
 return h.value_value(h.node_get_value(h.node_get_child(elements(obj),key),'Element'))
for obj,key,part in ((loader,'11000001',win),(loader,'21000001',win),(manager,'11000001',esp)):
 typ,b=value(obj,key);assert typ==3 and len(b)==0x58
 assert struct.unpack_from('<III',b,0x10)==(6,0,0x48)
 assert uuid.UUID(bytes_le=b[0x20:0x30])==part and uuid.UUID(bytes_le=b[0x38:0x48])==disk
assert value(loader,'12000002')[1].decode('utf-16le').rstrip('\0')==r'\Windows\system32\winload.efi'
assert not h.node_get_child(elements(loader),'26000022')
report={'bcd':str(target),'sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'disk_guid':str(disk),'esp_guid':str(esp),'win_guid':str(win),'loader':loader,'winpe_mode':False,'native_boot_tested':False}
(O/'bcd.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
