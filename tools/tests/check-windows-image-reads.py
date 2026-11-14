#!/usr/bin/env python3
"""Reproduce bad archived metadata and verify the real position-independent reader."""
from pathlib import Path
import hashlib,json,os,sys,zipfile
R=Path(__file__).resolve().parents[2];sys.path.insert(0,str(R/'tools'))
from windows_image_io import read_image_range
image=R/'out/windows-full/win-ntfs-4kn.img'
plan=json.loads((R/'out/windows-full/ntfs-read-check.json').read_text())
with image.open('rb') as f:
 f.read(4096)
 first=os.lseek(f.fileno(),0,os.SEEK_DATA);end=os.lseek(f.fileno(),first,os.SEEK_HOLE)
 f.seek(first);bad=f.read(min(64*1024*1024,end-first))
 with zipfile.ZipFile(R/'out/windows-full/BROKEN-original-windows-package-DO-NOT-INSTALL.zip') as z:assert bad==z.read('payload/win-0000.bin')
 for name in ('mft-windows','mft-system32'):
  s=next(x for x in plan['samples'] if x['name']==name)
  data=read_image_range(f.fileno(),s['sector']*4096,s['count']*4096)
  assert data[:4]==b'FILE' and hashlib.sha256(data).hexdigest()==s['sha256']
  assert not any(bad[s['sector']*4096:(s['sector']+1)*4096])
 try:read_image_range(f.fileno(),image.stat().st_size,4096)
 except ValueError:pass
 else:raise AssertionError('Short read accepted')
print('PASS reproduced original wrong ZIP bytes; corrected reader preserves both directory MFT records and rejects short reads')
