#!/usr/bin/env python3
"""Read-only verification of the Windows30 PEP watchdog dump evidence."""
import contextlib,io,json,runpy,struct,sys
from pathlib import Path
root=Path(__file__).resolve().parents[1]
dump=Path(sys.argv[1]) if len(sys.argv)>1 else root/'out/kona-gpu/watchdog-full/Windows/MEMORY.DMP'
out=root/'out/kona-gpu/watchdog-full/analysis'
sys.argv=['analyze-munch-dump.py',str(dump),'--output',str(out)]
with contextlib.redirect_stdout(io.StringIO()):d=runpy.run_path(str(root/'tools/analyze-munch-dump.py'))
q=d['q'];read=d['read'];h=d['header'];u32=d['u32'];u64=d['u64']
assert u32(h,0x38)==0x101 and u64(h,0x58)==6
pep=next(m for m in d['modules'] if m['name']=='qcpep8250.sys');base=pep['base']
# This audit's saved stack offsets belong only to this particular crash.
assert u64(h,0x50)==0xffffe680754a2980
mappings=[]
for off,expected in [(0x1c7100,0x18358800),(0x1c7108,0x18350800)]:
 va=q(base+off);pa=d['translate'](va);assert pa==expected
 mappings.append({'global_rva':hex(off),'virtual':hex(va),'physical':hex(pa)})
frames=[]
fp=0xffff8a0727bb7b50
for expected in [0x3360,0x33b8,0x5c48,0x5fa8,0x1df35c,0x1dc30c,0x2116c4]:
 nextfp,lr=struct.unpack('<QQ',read(fp,16));assert lr-base==expected and nextfp>fp
 frames.append({'frame':hex(fp),'return_rva':hex(expected)});fp=nextfp
saved_target=q(0xffff8a0727bb7b68)
assert saved_target==int(mappings[1]['virtual'],16)
cache=read(base+0x1cd1e0,0x60)
assert cache[0x30:0x36]==b'SM8250' and u32(cache,8)==356
result={'bugcheck':'0x101','hung_cpu':6,'pep':pep,'mapped_registers':mappings,'saved_write_target':hex(saved_target),'saved_write_value':hex(u32(read(0xffff8a0727bb7b60,4))),'saved_frame_chain':frames,'native_cached_soc_id':u32(cache,8),'native_cached_chip_string':'SM8250','limitations':['CPU6 did not freeze; saved processor context is zero. Frame chain and locals do not prove current PC.','Register mapping does not by itself prove access permissions or the causal instruction.','No driver or firmware patch is applied by this audit.']}
(out/'pep-watchdog-evidence.json').write_text(json.dumps(result,indent=2)+'\n')
print('Verified fresh watchdog, CPU6 PEP frame chain, MMIO translations and native SM8250 identification.')
