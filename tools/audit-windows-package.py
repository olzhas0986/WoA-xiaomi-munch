#!/usr/bin/env python3
"""Compare every original ZIP payload against source image using independent pread."""
from pathlib import Path
import hashlib,json,os,zipfile
R=Path(__file__).resolve().parents[1];O=R/'out/windows-full';bad=[];total=0
fds={p:os.open(O/(p+'-ntfs-4kn.img' if p=='win' else 'esp-windows-4kn.img'),os.O_RDONLY) for p in ('win','esp')}
with zipfile.ZipFile(O/'BROKEN-original-windows-package-DO-NOT-INSTALL.zip') as z:
 rows=[x.split() for x in z.read('payload/PARTS').decode().splitlines()]
 for part,name,offset,count,digest in rows:
  offset,count=int(offset),int(count);data=z.read(name)
  assert len(data)==count*4096 and hashlib.sha256(data).hexdigest()==digest
  expected=os.pread(fds[part],len(data),offset*4096);assert len(expected)==len(data)
  total+=len(data)
  if expected!=data:
   row={'part':part,'name':name,'sector':offset,'count':count,'old_sha256':digest,'correct_sha256':hashlib.sha256(expected).hexdigest()}
   bad.append(row);print('MISMATCH',part,name,'bytes',len(data),flush=True)
for f in fds.values():os.close(f)
r={'checked':len(rows),'checked_bytes':total,'bad_chunks':bad,'bad_bytes':sum(x['count']*4096 for x in bad),'source_read_method':'os.pread (no shared file-position/buffering)'}
(O/'package-source-audit.json').write_text(json.dumps(r,indent=2)+'\n');print('Bad chunks:',len(bad),'bytes:',r['bad_bytes'],flush=True)
