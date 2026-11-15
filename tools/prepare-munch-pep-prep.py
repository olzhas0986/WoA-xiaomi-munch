#!/usr/bin/env python3
"""Package a read-only processor/foundation readiness check."""
import hashlib,json,subprocess,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'out/kona-gpu'
def sha(data):return hashlib.sha256(data).hexdigest()
def main():
    subprocess.run(['python3',str(ROOT/'tools/audit-kona-pep.py')],check=True)
    dsdt=(ROOT/'firmware/munch/Acpi/DSDT.aml').read_bytes()
    assert b'SYSM' in dsdt and b'CLUS' in dsdt and sum(dsdt)%256==0
    files={name:(ROOT/'firmware/munch/GpuPepPrep'/name).read_bytes() for name in ('setup.cmd','check.ps1','README.md')}
    files['contract.json']=(OUT/'pep-audit/contract.json').read_bytes()
    manifest={'stage':'PEP CPU namespace preparation; PEP not installed','dsdt_sha256':sha(dsdt),'files':[{'path':n,'sha256':sha(b)} for n,b in sorted(files.items())]}
    files['manifest.json']=(json.dumps(manifest,indent=2)+'\n').encode()
    sums=''.join(f'{sha(b)}  {n}\n' for n,b in sorted(files.items())).encode()
    script=(ROOT/'firmware/munch/Recovery/install-gpu-bootstrap').read_text().replace('@SUMS_SHA@',sha(sums)).replace('GPU23','GPU27').replace('gpu23','gpu27').replace('SCM package','PEP preparation files').replace('Boot Windows23 and run setup.cmd configure.','Boot the make stable image and run setup.cmd.')
    dest=OUT/'munch-gpu-pep-prep-twrp.zip'
    with zipfile.ZipFile(dest,'w',zipfile.ZIP_DEFLATED) as z:
        for n,b in files.items():z.writestr('payload/'+n,b)
        z.writestr('payload/SHA256SUMS',sums)
        info=zipfile.ZipInfo('META-INF/com/google/android/update-binary');info.external_attr=0o100755<<16
        z.writestr(info,script)
        z.writestr('META-INF/com/google/android/updater-script','# PEP readiness files only\n')
    with zipfile.ZipFile(dest) as z:
        assert z.testzip() is None
        for n,b in files.items():assert z.read('payload/'+n)==b
    print(dest);print('SHA256:',sha(dest.read_bytes()))
if __name__=='__main__':main()
