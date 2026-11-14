#!/usr/bin/env python3
"""Create 4Kn FAT images for the newly allocated munch ESP and WinPE partition."""
from pathlib import Path
import hashlib,json,struct,subprocess,uuid
ROOT=Path(__file__).resolve().parents[1]; OUT=ROOT/'out/winpe'; MEDIA=OUT/'media'
OUT.mkdir(parents=True,exist_ok=True)
iso=ROOT/'en-us_windows_11_iot_enterprise_ltsc_2024_arm64_dvd_ec517836.iso'
subprocess.run(['7z','x','-y','-o'+str(MEDIA),str(iso),'efi','boot/boot.sdi','sources/boot.wim'],check=True,stdout=subprocess.DEVNULL)
loader=(MEDIA/'efi/boot/bootaa64.efi').read_bytes();pe=struct.unpack_from('<I',loader,60)[0]
assert loader[pe:pe+4]==b'PE\0\0' and struct.unpack_from('<H',loader,pe+4)[0]==0xaa64
assert (MEDIA/'sources/boot.wim').read_bytes()[:8]==b'MSWIM\0\0\0'
manifest={'source_iso':iso.name,'device_tested':False,'images':{}}
for kind,mib,folders in [('esp',512,['efi']),('win',640,['efi','boot','sources'])]:
 image=OUT/(kind+'-winpe-4kn.img')
 with image.open('wb') as f:f.truncate(mib*1024*1024)
 subprocess.run(['mkfs.fat','-F','32','-S','4096','-s','1','-n','WINPE'+kind.upper(),str(image)],check=True)
 for folder in folders:subprocess.run(['mcopy','-i',str(image),'-s',str(MEDIA/folder),'::/'+folder.upper()],check=True)
 subprocess.run(['fsck.fat','-n',str(image)],check=True)
 subprocess.run(['mdir','-i',str(image),'::/EFI/BOOT/BOOTAA64.EFI'],check=True)
 if kind=='win':subprocess.run(['mdir','-i',str(image),'::/SOURCES/BOOT.WIM','::/BOOT/BOOT.SDI'],check=True)
 sparse=OUT/(kind+'-winpe-4kn.sparse.img')
 subprocess.run(['img2simg',str(image),str(sparse),'4096'],check=True)
 manifest['images'][kind]={'raw_size':image.stat().st_size,'sparse_file':str(sparse.relative_to(ROOT)),'sha256':hashlib.file_digest(sparse.open('rb'),'sha256').hexdigest()}
# Bind UEFI's read-only views to the exact partition identities created earlier.
entries=(ROOT/'out/munch-fresh/repartition32/primary-table.new.bin').read_bytes()
def cguid(b):
 g=uuid.UUID(bytes_le=b);v=g.fields
 return '{0x%08x,0x%04x,0x%04x,{%s}}'%(v[0],v[1],v[2],','.join('0x%02x'%x for x in g.bytes[8:]))
header='// Generated from the verified local repartition plan.\n'
for name,index in [('Esp',34),('Win',36)]:
 e=entries[index*128:(index+1)*128]
 assert e[56:128].decode('utf-16le').rstrip('\0')==name.lower()
 header+='STATIC EFI_GUID Expected%sGuid = %s;\n'%(name,cguid(e[16:32]))
(ROOT/'firmware/munch/BootManager/WinpeLayout.h').write_text(header)
(OUT/'disk-images.json').write_text(json.dumps(manifest,indent=2)+'\n')
print(json.dumps(manifest,indent=2))
