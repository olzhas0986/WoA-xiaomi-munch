#!/usr/bin/env python3
"""Package a staged, post-desktop PEP activation test and diagnostics."""
from pathlib import Path
import zipfile,hashlib,json
ROOT=Path(__file__).resolve().parents[1]
source=ROOT/'firmware/munch/GpuPepLate'
files={p.name:p.read_bytes() for p in source.iterdir() if p.is_file()}
for n in ('collect.cmd','collect.ps1'):files[n]=(ROOT/'firmware/munch/GpuPepDiagnostics'/n).read_bytes()
files['SHA256.json']=(json.dumps({n:hashlib.sha256(d).hexdigest() for n,d in files.items()},indent=2)+'\n').encode()
out=ROOT/'out/kona-gpu/munch-pep-late.zip'
with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as z:
 for name,data in files.items():z.writestr('MunchPepLate/'+name,data)
with zipfile.ZipFile(out) as z:
 assert z.testzip() is None
 for name,data in files.items():assert z.read('MunchPepLate/'+name)==data
print(out);print('SHA256:',hashlib.sha256(out.read_bytes()).hexdigest())
