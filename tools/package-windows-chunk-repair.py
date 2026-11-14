#!/usr/bin/env python3
"""Package only source/ZIP mismatches, guarded by known old/on-disk hashes."""
from pathlib import Path
from windows_image_io import read_image_range
import hashlib,json,os,zipfile
R=Path(__file__).resolve().parents[1];O=R/'out/windows-full';audit=json.loads((O/'package-source-audit.json').read_text())
output=O/'munch-windows-chunks-fix-twrp.zip';rows=[s for s in audit['bad_chunks'] if s['part']=='win'];assert len(rows)==197
images={'win':O/'win-ntfs-4kn.img','esp':O/'esp-windows-4kn.img'}
manifest=''.join(f"{s['part']} {s['name']} {s['sector']} {s['count']} {s['correct_sha256']} {s['old_sha256']}\n" for s in rows).encode()
gpt=json.loads((R/'out/munch-fresh/repartition32/plan.json').read_text())['files']['primary-table']['new_sha256']
source=(R/'firmware/munch/Recovery/repair-windows-chunks').read_text().replace('@GPT_SHA@',gpt).replace('@MANIFEST_SHA@',hashlib.sha256(manifest).hexdigest()).replace('@CHUNKS@',str(len(rows)))
with zipfile.ZipFile(output,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=1,allowZip64=False) as z:
 info=zipfile.ZipInfo('META-INF/com/google/android/update-binary');info.create_system=3;info.external_attr=0o100755<<16
 z.writestr(info,source);z.writestr('META-INF/com/google/android/updater-script','# Handled by update-binary.\n');z.writestr('payload/PARTS',manifest)
 for s in rows:
  with images[s['part']].open('rb',buffering=0) as f:data=read_image_range(f.fileno(),s['sector']*4096,s['count']*4096)
  assert len(data)==s['count']*4096 and hashlib.sha256(data).hexdigest()==s['correct_sha256']
  z.writestr(s['name'],data)
 z.writestr('README.txt','POCO F4 munch: repair197 known bad Windows chunks of the original ZIP.\nFixes a host packaging bug mixing buffered reads and SEEK_DATA/SEEK_HOLE.\nOnly win is repaired; the already-fixed ESP is left alone. No formatting\nor repartitioning. Requires unmounted esp/win in root TWRP.\nBefore writes validates model/nodes/sizes/GPT, every payload and every current\nrange. Only known old bytes or already-correct bytes are accepted. Unexpected\nbytes abort before writes. Already-correct chunks are skipped; each\nreplacement is read back and verified.\nThen fastboot boot the current stable UEFI and unplug the PC cable immediately after transfer.\n')
# Independently reread both ZIP and original sectors after archive creation.
with zipfile.ZipFile(output) as z:
 for s in rows:
  with images[s['part']].open('rb',buffering=0) as f:expected=read_image_range(f.fileno(),s['sector']*4096,s['count']*4096)
  assert z.read(s['name'])==expected
r={'zip':str(output),'bytes':output.stat().st_size,'sha256':hashlib.file_digest(output.open('rb'),'sha256').hexdigest(),'chunks':len(rows),'replacement_bytes':sum(s['count']*4096 for s in rows),'writes':['win'],'all_payloads_match_source_ranges':True,'guards_current_data':True,'device_tested':False}
(O/'chunk-repair.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2))
