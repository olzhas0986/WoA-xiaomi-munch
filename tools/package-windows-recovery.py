#!/usr/bin/env python3
"""Package allocated extents of the full NTFS image for bounded-RAM TWRP writes."""
from pathlib import Path
from windows_image_io import read_image_range
import argparse,os,errno,hashlib,json,struct,zipfile
R=Path(__file__).resolve().parents[1];O=R/'out/windows-full'
parser=argparse.ArgumentParser()
parser.add_argument('--esp',type=Path,default=O/'esp-windows-4kn.img')
parser.add_argument('--output',type=Path,default=O/'munch-windows11-iot-ltsc-twrp.zip')
a=parser.parse_args()
images={'win':(O/'win-ntfs-4kn.img',33806090240),'esp':(a.esp,536870912)}
output=a.output;parts=[];total=0
stamps={k:(p.stat().st_size,p.stat().st_mtime_ns,p.stat().st_ctime_ns) for k,(p,n) in images.items()}
with zipfile.ZipFile(output,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=1,allowZip64=True) as z:
 for part,(path,length) in images.items():
  assert path.is_file() and not path.is_symlink() and path.stat().st_size==length
  with path.open('rb') as f:
   boot=f.read(4096);assert struct.unpack_from('<H',boot,11)[0]==4096
   assert boot[3:11]==b'NTFS    ' if part=='win' else boot[82:90]==b'FAT32   '
   pos=0;index=0;end_previous=0
   while pos<length:
    if part=='esp':
     # Replace the complete FAT volume, including zero regions. This also
     # makes full-image readback meaningful when diagnosing directory errors.
     start,end=pos,length
    else:
     try:start=os.lseek(f.fileno(),pos,os.SEEK_DATA)
     except OSError as e:
      if e.errno==errno.ENXIO:break
      raise
     end=min(os.lseek(f.fileno(),start,os.SEEK_HOLE),length)
    assert start%4096==0 and end%4096==0 and start>=end_previous
    while start<end:
     # SEEK_DATA/SEEK_HOLE move the descriptor behind BufferedReader's back.
     # An absolute pread must be used; f.seek can otherwise reuse stale data.
     n=min(64*1024*1024,end-start);data=read_image_range(f.fileno(),start,n);assert len(data)==n
     name=f'payload/{part}-{index:04d}.bin';digest=hashlib.sha256(data).hexdigest()
     z.writestr(name,data)
     parts.append((part,name,start//4096,n//4096,digest));total+=n
     start+=n;index+=1
    pos=end;end_previous=end
   assert any(p[0]==part and p[2]==0 for p in parts)
   if part=='win':
    assert any(p[0]==part and p[2]+p[3]==length//4096 for p in parts), 'NTFS backup boot sector missing'
 manifest=''.join(' '.join(map(str,p))+'\n' for p in parts).encode()
 z.writestr('payload/PARTS',manifest)
 gpt=json.loads((R/'out/munch-fresh/repartition32/plan.json').read_text())['files']['primary-table']['new_sha256']
 installer=(R/'firmware/munch/Recovery/install-windows-chunks').read_text().replace('@GPT_SHA@',gpt).replace('@MANIFEST_SHA@',hashlib.sha256(manifest).hexdigest()).replace('@CHUNKS@',str(len(parts)))
 assert '@GPT_SHA@' not in installer
 info=zipfile.ZipInfo('META-INF/com/google/android/update-binary');info.create_system=3;info.external_attr=0o100755<<16
 z.writestr(info,installer)
 z.writestr('META-INF/com/google/android/updater-script','# Installation is handled by update-binary.\n')
 z.writestr('README.txt','POCO F4 munch: full Windows 11 IoT Enterprise LTSC 2024 ARM64.\nReinstalls NTFS Windows in win; replaces esp boot files and BCD.\nRequires original verified 32GiB repartition and unmounted esp/win in TWRP.\nChecks all payload hashes and GPT before writes; verifies every written range.\nOnly esp/win are written. GPT, userdata and Android boot are not modified.\nRAM workspace <=64MiB per chunk. ZIP64-capable recovery unzip is required.\nBoot the current stable UEFI with fastboot boot; unplug the PC cable immediately after transfer so Windows can auto-boot with USB host mode.\n')
assert stamps=={k:(p.stat().st_size,p.stat().st_mtime_ns,p.stat().st_ctime_ns) for k,(p,n) in images.items()}, 'Source changed during packaging'
# Validate against the actual source ranges, not just our own ZIP manifest.
with zipfile.ZipFile(output) as z:
 for part,name,offset,count,digest in parts:
  with images[part][0].open('rb',buffering=0) as f:expected=read_image_range(f.fileno(),offset*4096,count*4096)
  actual=z.read(name)
  assert actual==expected and hashlib.sha256(actual).hexdigest()==digest,name
report={'source_images':{k:str(v[0]) for k,v in images.items()},'zip':str(output),'bytes':output.stat().st_size,'allocated_payload_bytes':total,'chunks':len(parts),'image_bytes':{k:v[1] for k,v in images.items()},'writes':['win','esp'],'changes_gpt':False,'changes_android':False,'all_payloads_match_source_ranges':True,'device_tested':False}
output.with_suffix('.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2),flush=True)
