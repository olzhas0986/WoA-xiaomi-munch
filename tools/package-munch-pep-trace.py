#!/usr/bin/env python3
"""Bundle the PEP trace preparation and updated read-only collector."""
import hashlib,json,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
files={n:(ROOT/'firmware/munch/GpuPepTrace'/n).read_bytes() for n in ('prepare.cmd','trace.ps1','README.md')}
for n in ('collect.cmd','collect.ps1'):files[n]=(ROOT/'firmware/munch/GpuPepDiagnostics'/n).read_bytes()
manifest={n:hashlib.sha256(data).hexdigest() for n,data in files.items()}
files['SHA256.json']=(json.dumps(manifest,indent=2)+'\n').encode()
p=ROOT/'out/kona-gpu/munch-pep-trace.zip'
with zipfile.ZipFile(p,'w',zipfile.ZIP_DEFLATED) as z:
 for n,data in files.items():z.writestr('MunchPepTrace/'+n,data)
with zipfile.ZipFile(p) as z:
 assert z.testzip() is None
 for n,data in files.items():assert z.read('MunchPepTrace/'+n)==data
print(p);print('SHA256:',hashlib.sha256(p.read_bytes()).hexdigest())
