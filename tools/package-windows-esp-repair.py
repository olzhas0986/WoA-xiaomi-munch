#!/usr/bin/env python3
"""Package the full, locally verified FAT ESP rather than its sparse extents."""
from pathlib import Path
import hashlib,json,subprocess,zipfile
R=Path(__file__).resolve().parents[1];O=R/'out/windows-full'
image=O/'esp-windows-4kn.img';assert image.stat().st_size==536870912
subprocess.run(['fsck.fat','-n',str(image)],check=True)
sha=hashlib.file_digest(image.open('rb'),'sha256').hexdigest()
gpt=json.loads((R/'out/munch-fresh/repartition32/plan.json').read_text())['files']['primary-table']['new_sha256']
source=(R/'firmware/munch/Recovery/repair-windows-esp').read_text().replace('@GPT_SHA@',gpt).replace('@ESP_SHA@',sha)
output=O/'munch-windows-esp-repair-twrp.zip'
with zipfile.ZipFile(output,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=1,allowZip64=False) as z:
 info=zipfile.ZipInfo('META-INF/com/google/android/update-binary');info.create_system=3;info.external_attr=0o100755<<16
 z.writestr(info,source);z.writestr('META-INF/com/google/android/updater-script','# Handled by update-binary.\n')
 z.write(image,'payload/esp.img')
 z.writestr('README.txt','POCO F4 munch: rewrite only the full512MiB ESP, including zero sectors.\nRequires the verified32GiB layout and an unmounted ESP in TWRP.\n512MiB recovery RAM workspace. Checks model/node/size/GPT/payload hash\nbefore writing; reads the entire written ESP back and checks its hash.\nWindows NTFS, GPT, userdata and Android boot partitions are not written.\nThen fastboot boot the current stable UEFI and unplug the PC cable immediately after transfer.\nDevice result remains unverified.\n')
with zipfile.ZipFile(output) as z:
 with z.open('payload/esp.img') as f:assert hashlib.file_digest(f,'sha256').hexdigest()==sha
r={'zip':str(output),'bytes':output.stat().st_size,'sha256':hashlib.file_digest(output.open('rb'),'sha256').hexdigest(),'esp_payload_sha256':sha,'payload_size':536870912,'writes':['esp'],'device_tested':False}
(O/'esp-repair.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2))
