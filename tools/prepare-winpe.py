#!/usr/bin/env python3
"""Build a FAT32 WinPE RAM image from the supplied ARM64 installation media."""
from pathlib import Path
import hashlib,json,struct,subprocess
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'out/winpe'; MEDIA=OUT/'media'
ISO=ROOT/'en-us_windows_11_iot_enterprise_ltsc_2024_arm64_dvd_ec517836.iso'
OUT.mkdir(parents=True,exist_ok=True)
subprocess.run(['7z','x','-y','-o'+str(MEDIA),str(ISO),'efi','boot/boot.sdi','sources/boot.wim'],check=True,stdout=subprocess.DEVNULL)
loader=(MEDIA/'efi/boot/bootaa64.efi').read_bytes()
pe=struct.unpack_from('<I',loader,60)[0]
assert loader[pe:pe+4]==b'PE\0\0' and struct.unpack_from('<H',loader,pe+4)[0]==0xaa64
assert (MEDIA/'sources/boot.wim').read_bytes()[:8]==b'MSWIM\0\0\0'
assert (MEDIA/'efi/microsoft/boot/bcd').read_bytes()[:4]==b'regf'
image=OUT/'winpe-arm64-fat.img'
with image.open('wb') as f:f.truncate(640*1024*1024)
subprocess.run(['mkfs.fat','-F','32','-n','WINPERAM',str(image)],check=True)
for source,target in [('efi','::/EFI'),('boot','::/BOOT'),('sources','::/SOURCES')]:
 subprocess.run(['mcopy','-i',str(image),'-s',str(MEDIA/source),target],check=True)
subprocess.run(['mdir','-i',str(image),'::/EFI/BOOT/BOOTAA64.EFI','::/SOURCES/BOOT.WIM','::/BOOT/BOOT.SDI'],check=True)
report={'image':str(image),'size':image.stat().st_size,'sha256':hashlib.file_digest(image.open('rb'),'sha256').hexdigest(),'loader_machine':'AARCH64','source_iso':ISO.name,'device_tested':False}
(image.with_suffix('.json')).write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
