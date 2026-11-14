#!/usr/bin/env python3
"""Package verified raw 4Kn images for the user's root TWRP recovery."""
from pathlib import Path
import hashlib,json,zipfile,struct
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'out/winpe'
output=OUT/'munch-winpe-files-twrp.zip'
files={name:OUT/(name+'-winpe-4kn.img') for name in ('esp','win')}
hashes={}
for name,path in files.items():
 with path.open('rb') as f:
  boot=f.read(4096)
  assert struct.unpack_from('<H',boot,11)[0]==4096 and boot[82:90]==b'FAT32   '
  f.seek(0);hashes[name]=hashlib.file_digest(f,'sha256').hexdigest()
 assert path.stat().st_size==({'esp':512,'win':640}[name])*1024*1024
manifest=''.join(hashes[n]+'  '+n+'.img\n' for n in files)
readme='''POCO F4 munch WinPE files test 1, for the already-created 32GiB layout.
Install using root TWRP > Install > this ZIP. It requires /dev/block/sda35
esp=512MiB and /dev/block/sda37 win=33806090240 bytes, both 4Kn, unmounted.
The archive needs about 1.2GiB free recovery RAM for extraction before writing.
Checks all image hashes before writing; reads each written image back afterward.
Only esp and the first 640MiB of win are written. No GPT or boot partitions
are changed. win holds a temporary WinPE FAT32 test filesystem; the final NTFS
Windows deployment is not yet done. UEFI launch is a separate step.
After installing, boot the prepared munch-uefi-winpe-ufs1.img by the separately
chosen method and invoke its diagnostic fastboot command: oem winpe-disk.
Host filesystem/build tests passed. Actual Windows/WinPE boot is unverified;
CPU-only ACPI and Windows hardware drivers are still incomplete.
'''
with zipfile.ZipFile(output,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=1,allowZip64=False) as z:
 info=zipfile.ZipInfo('META-INF/com/google/android/update-binary')
 info.create_system=3;info.external_attr=0o100755<<16
 z.writestr(info,(ROOT/'firmware/munch/Recovery/update-binary').read_bytes())
 z.writestr('META-INF/com/google/android/updater-script','# Installation is handled by update-binary.\n')
 z.writestr('payload/SHA256SUMS',manifest)
 z.writestr('README.txt',readme)
 for name,path in files.items():z.write(path,'payload/'+name+'.img')
with zipfile.ZipFile(output) as z:
 assert z.testzip() is None
 for name in files:
  with z.open('payload/'+name+'.img') as f:assert hashlib.file_digest(f,'sha256').hexdigest()==hashes[name]
report={'zip':str(output),'size':output.stat().st_size,'sha256':hashlib.file_digest(output.open('rb'),'sha256').hexdigest(),'payload_sha256':hashes,'device_tested':False,'writes':['esp','first 640MiB of win'],'changes_boot_partition':False}
output.with_suffix('.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
