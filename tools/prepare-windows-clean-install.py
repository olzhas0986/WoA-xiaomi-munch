#!/usr/bin/env python3
"""Build a fresh Windows recovery install with corrected system-store BCD."""
from pathlib import Path
import os,shutil,subprocess,sys
from ntfs_remote_reader import ReadOnlyNtfs
from windows_setup_state import hivex_module,mark_system_store,dword,get_node
R=Path(__file__).resolve().parents[1];O=R/'out/windows-full';work=O/'clean-install';work.mkdir(exist_ok=True)
image=O/'win-ntfs-4kn.img';fd=os.open(image,os.O_RDONLY);ntfs=None
try:
 ntfs=ReadOnlyNtfs(image.stat().st_size,lambda offset,count:os.pread(fd,count,offset))
 data,size=ntfs.read_file('/Windows/System32/config/SYSTEM');assert len(data)==size
 hive=work/'SYSTEM.source';hive.write_bytes(data);h=hivex_module().Hivex(str(hive))
 assert dword(h,'Setup','SetupPhase')==4
 assert dword(h,'Setup\\Status\\SysprepStatus','GeneralizationState')==4
 try:n=get_node(h,'Setup\\Status\\ChildCompletion')
 except ValueError:n=0
 assert not n,'Source has already started Setup; refuse to package'
 assert not any(name.lower()=='panther' for name,kind in ntfs.list('/Windows')),'Source has Setup progress files'
 print('PASS: untouched first-boot SYSTEM and no previous Panther progress',flush=True)
finally:
 if ntfs:ntfs.close()
 os.close(fd)
mark_system_store(O/'BCD',work/'BCD')
esp=work/'esp.img';shutil.copyfile(O/'esp-windows-4kn.img',esp)
subprocess.run(['mcopy','-o','-i',str(esp),str(work/'BCD'),'::/EFI/Microsoft/Boot/BCD'],check=True)
subprocess.run(['mcopy','-o','-i',str(esp),'::/EFI/Microsoft/Boot/BCD',str(work/'BCD.readback')],check=True)
assert (work/'BCD').read_bytes()==(work/'BCD.readback').read_bytes()
subprocess.run(['fsck.fat','-n',str(esp)],check=True)
subprocess.run([sys.executable,str(R/'tools/package-windows-recovery.py'),'--esp',str(esp),'--output',str(O/'munch-windows11-clean-v2-twrp.zip')],check=True)
