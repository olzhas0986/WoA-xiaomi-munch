"""libntfs-3g on a caller-provided read-only, bounded raw-byte source."""
from pathlib import Path
import ctypes as C,os,subprocess
ROOT=Path(__file__).resolve().parents[1]
FETCH=C.CFUNCTYPE(C.c_int64,C.c_int64,C.c_int64,C.c_void_p)
ENTRY=C.CFUNCTYPE(None,C.c_void_p,C.c_int,C.c_uint)
class ReadOnlyNtfs:
 def __init__(self,size,read):
  library=ROOT/'out/windows-full/ntfs-readonly-bridge.so'
  source=ROOT/'tools/ntfs_readonly_bridge.c';tools=ROOT/'out/windows-full/host-tools/usr'
  if not library.exists() or library.stat().st_mtime_ns<source.stat().st_mtime_ns:
   subprocess.run(['clang','-shared','-fPIC','-O2','-Wall','-Wextra','-I'+str(tools/'include'),str(source),'-L'+str(tools/'lib'),'-Wl,-rpath,'+str(tools/'lib'),'-lntfs-3g','-o',str(library)],check=True)
  self.lib=C.CDLL(str(library),use_errno=True);self.error=None
  lib=self.lib
  lib.bridge_open.argtypes=[C.c_int64,FETCH];lib.bridge_open.restype=C.c_void_p
  lib.bridge_close.argtypes=[C.c_void_p];lib.bridge_close.restype=None
  lib.bridge_file_open.argtypes=[C.c_void_p,C.c_char_p,C.POINTER(C.c_int64)];lib.bridge_file_open.restype=C.c_void_p
  lib.bridge_file_read.argtypes=[C.c_void_p,C.c_int64,C.c_int64,C.c_void_p];lib.bridge_file_read.restype=C.c_int64
  lib.bridge_file_map.argtypes=[C.c_void_p,C.c_int64];lib.bridge_file_map.restype=C.c_int64
  lib.bridge_file_close.argtypes=[C.c_void_p];lib.bridge_file_close.restype=None
  lib.bridge_list.argtypes=[C.c_void_p,C.c_char_p,ENTRY];lib.bridge_list.restype=C.c_int
  @FETCH
  def fetch(offset,count,buffer):
   try:
    if offset<0 or count<0 or offset+count>size:raise ValueError('Read outside partition')
    data=read(offset,count)
    if len(data)!=count:raise ValueError('Short raw read')
    C.memmove(buffer,data,count);return count
   except Exception as e:self.error=e;return -1
  self.fetch=fetch;self.handle=lib.bridge_open(size,fetch)
  if not self.handle:raise OSError(C.get_errno(),f'Cannot parse read-only NTFS: {self.error}')
 def close(self):
  if self.handle:self.lib.bridge_close(self.handle);self.handle=None
 def list(self,path):
  result=[]
  @ENTRY
  def emit(name,length,kind):result.append((C.string_at(name,length*2).decode('utf-16le'),kind))
  if self.lib.bridge_list(self.handle,path.encode(),emit)<0:raise OSError(C.get_errno(),path)
  return result
 def read_file(self,path,limit=32*1024*1024,tail=False):
  size=C.c_int64();f=self.lib.bridge_file_open(self.handle,path.encode(),C.byref(size))
  if not f:raise OSError(C.get_errno(),path)
  try:
   if size.value<0:raise ValueError('Negative file size')
   take=min(size.value,limit);start=size.value-take if tail else 0;result=bytearray()
   while len(result)<take:
    want=min(1024*1024,take-len(result));buffer=C.create_string_buffer(want)
    got=self.lib.bridge_file_read(f,start+len(result),want,buffer)
    if got<=0:raise OSError(C.get_errno(),f'Read failure {path}: {self.error}')
    result.extend(buffer.raw[:got])
   return bytes(result),size.value
  finally:self.lib.bridge_file_close(f)
 def map_file_offset(self,path,offset):
  size=C.c_int64();f=self.lib.bridge_file_open(self.handle,path.encode(),C.byref(size))
  if not f:raise OSError(C.get_errno(),path)
  try:
   pos=self.lib.bridge_file_map(f,offset)
   if pos<0:raise OSError(C.get_errno(),'Cannot safely map ordinary uncompressed file data')
   return pos
  finally:self.lib.bridge_file_close(f)
