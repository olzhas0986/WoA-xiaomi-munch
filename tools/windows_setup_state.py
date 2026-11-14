"""Small, validated fixes for the observed BCD-specialize failure."""
from pathlib import Path
import ctypes,importlib,struct,sys
ROOT=Path(__file__).resolve().parents[1]
def hivex_module():
 try:return importlib.import_module('hivex')
 except ModuleNotFoundError:
  root=ROOT/'out/windows-full/host-tools/usr/lib'
  ctypes.CDLL(str(root/'libhivex.so.0'),mode=ctypes.RTLD_GLOBAL)
  sys.path.insert(0,str(root/f'python{sys.version_info.major}.{sys.version_info.minor}/site-packages'))
  return importlib.import_module('hivex')
def get_node(h,path):
 n=h.root()
 for name in path.split('\\'):
  n=h.node_get_child(n,name)
  if not n:raise ValueError('Missing registry path '+path)
 return n
def dword(h,path,key):
 v=h.node_get_value(get_node(h,path),key)
 if not v:raise ValueError('Missing registry value '+key)
 t,b=h.value_value(v)
 if t!=4 or len(b)!=4:raise ValueError('Wrong DWORD type '+key)
 return struct.unpack('<I',b)[0]
def mark_system_store(source,target):
 target=Path(target);target.write_bytes(Path(source).read_bytes())
 hv=hivex_module();h=hv.Hivex(str(target),write=True);n=get_node(h,'Description')
 h.node_set_value(n,{'key':'System','t':4,'value':struct.pack('<I',1)})
 h.node_set_value(n,{'key':'KeyName','t':1,'value':('BCD00000000\0').encode('utf-16le')})
 h.commit(None);del h
 h=hv.Hivex(str(target));assert dword(h,'Description','System')==1
 # Verify OS objects were not altered while marking the store.
 def tree(h,n):
  values={h.value_key(v):h.value_value(v) for v in h.node_values(n)}
  return values,{h.node_name(c):tree(h,c) for c in h.node_children(n)}
 before=hv.Hivex(str(source))
 assert tree(before,get_node(before,'Objects'))==tree(h,get_node(h,'Objects'))
 return target
def prepare_specialize_retry(source,target):
 source=Path(source);data=bytearray(source.read_bytes())
 if data[:4]!=b'regf' or struct.unpack_from('<I',data,4)[0]!=struct.unpack_from('<I',data,8)[0]:
  raise ValueError('SYSTEM hive is dirty/incomplete; do not patch without log recovery')
 hv=hivex_module();h=hv.Hivex(str(source))
 assert dword(h,'Setup','SystemSetupInProgress')==1 and dword(h,'Setup','SetupPhase')==4,'Not the observed first-boot specialize stage'
 path='Setup\\Status\\SysprepStatus'
 assert dword(h,path,'GeneralizationState')==6,'Not the observed failed specialize state'
 v=h.node_get_value(get_node(h,path),'GeneralizationState')
 assert data[v+4:v+6]==b'vk' and struct.unpack_from('<I',data,v+8)[0]==0x80000004
 assert struct.unpack_from('<I',data,v+16)[0]==4
 offset=v+12;assert struct.unpack_from('<I',data,offset)[0]==6
 struct.pack_into('<I',data,offset,4)
 target=Path(target);target.write_bytes(data)
 check=hv.Hivex(str(target));assert dword(check,path,'GeneralizationState')==4
 assert [i for i,(a,b) in enumerate(zip(source.read_bytes(),data)) if a!=b]==[offset]
 return offset

def prepare_setup_child_retry(source,target):
 """Retry a blocked Setup child without marking it completed (value 3)."""
 source=Path(source);data=bytearray(source.read_bytes())
 if data[:4]!=b'regf' or struct.unpack_from('<I',data,4)[0]!=struct.unpack_from('<I',data,8)[0]:
  raise ValueError('SYSTEM hive is dirty/incomplete')
 hv=hivex_module();h=hv.Hivex(str(source))
 assert dword(h,'Setup','SystemSetupInProgress')==1 and dword(h,'Setup','SetupPhase')==4,'Unexpected Setup stage'
 assert dword(h,'Setup\\Status\\SysprepStatus','GeneralizationState')==4,'Apply only after the Specialize retry repair'
 path='Setup\\Status\\ChildCompletion';key='setup.exe'
 assert dword(h,path,key)==1,'Not the observed interrupted Setup child'
 v=h.node_get_value(get_node(h,path),key)
 assert data[v+4:v+6]==b'vk' and struct.unpack_from('<I',data,v+8)[0]==0x80000004
 assert struct.unpack_from('<I',data,v+16)[0]==4
 offset=v+12;assert struct.unpack_from('<I',data,offset)[0]==1
 struct.pack_into('<I',data,offset,0);target=Path(target);target.write_bytes(data)
 check=hv.Hivex(str(target));assert dword(check,path,key)==0
 assert dword(check,'Setup\\Status\\SysprepStatus','GeneralizationState')==4
 assert [i for i,(a,b) in enumerate(zip(source.read_bytes(),data)) if a!=b]==[offset]
 return offset
