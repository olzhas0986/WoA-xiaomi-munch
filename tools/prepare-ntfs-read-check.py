#!/usr/bin/env python3
"""Pin small NTFS samples covering the directory path and loader data."""
from pathlib import Path
import hashlib,json,os,re,struct,subprocess
R=Path(__file__).resolve().parents[1];O=R/'out/windows-full';image=O/'win-ntfs-4kn.img'
bin=O/'host-tools/usr/bin';env=dict(os.environ,LD_LIBRARY_PATH=str(O/'host-tools/usr/lib'))
def tool(n,path):return subprocess.check_output([str(bin/n),'-F',path,str(image)],env=env,text=True)
def runs(path):
 text=tool('ntfscluster',path)
 return [tuple(map(int,row)) for row in re.findall(r'^\s+(\d+)\s+(\d+)\s+(\d+)\s*$',text,re.M)]
mft=runs('/$MFT')[:2] # MFT DATA runs, before its bitmap.
assert mft==[(0,4,65547),(65547,69648,17744)]
samples=[]
def add(name,sector,count):
 assert sector>=0 and count>0 and sector+count<=33806090240//4096
 with image.open('rb') as f:f.seek(sector*4096);data=f.read(count*4096)
 assert len(data)==count*4096
 samples.append({'name':name,'sector':sector,'count':count,'sha256':hashlib.sha256(data).hexdigest()})
def mft_sector(record):
 for vcn,lcn,n in mft:
  if vcn<=record<vcn+n:return lcn+record-vcn
 raise ValueError('MFT record outside DATA mapping')
add('ntfs-boot',0,1);add('ntfs-backup',33806090240//4096-1,1)
with image.open('rb') as f:b=f.read(4096)
mirror=struct.unpack_from('<Q',b,56)[0];add('mft-mirror',mirror,4)
paths=[('/', 'root'),('/Windows','windows'),('/Windows/System32','system32'),('/Windows/System32/winload.efi','winload'),('/$Volume','volume'),('/$UpCase','upcase'),('/$AttrDef','attrdef')]
for path,label in paths:
 info=tool('ntfsinfo',path);record=int(re.search(r'Dumping Inode (\d+)',info)[1])
 add('mft-'+label,mft_sector(record),1)
 for i,(vcn,lcn,n) in enumerate(runs(path)):
  assert lcn>=0 and n<=2048 # no multi-gigabyte reads; selected files only.
  add(label+'-data-'+str(i),lcn,n)
plan={'image_bytes':33806090240,'block_size':4096,'source_image':str(image),'samples':samples,'total_bytes':sum(s['count']*4096 for s in samples),'writes_phone':False}
(O/'ntfs-read-check.json').write_text(json.dumps(plan,indent=2)+'\n');print('Prepared',len(samples),'read-only ranges,',plan['total_bytes'],'bytes')
