#!/usr/bin/env python3
"""Inspect saved ARM64 contexts and stack candidates using matching NT symbols."""
import runpy,contextlib,io,re,bisect,json,struct
from pathlib import Path
with contextlib.redirect_stdout(io.StringIO()):d=runpy.run_path(str(Path(__file__).with_name('analyze-munch-dump.py')))
read,q,header,out=d['read'],d['q'],d['header'],d['a'].output
text=(out/'nt-symbols.txt').read_text(errors='replace');sections={}
for block in re.split(r'SECTION HEADER #',text)[1:]:
 i=int(block.splitlines()[0]);m=re.search(r'([0-9A-F]+) virtual address',block)
 if m:sections[i]=int(m[1],16)
nt=next(m['base'] for m in d['modules'] if m['name']=='ntoskrnl.exe')
symbols=[]
for name,sec,off in re.findall(r'S_PUB32[^\n]*`([^`]+)`\n\s*flags = [^\n]*addr = (\d+):(\d+)',text):
 sec=int(sec)
 if sec in sections:symbols.append((nt+sections[sec]+int(off),name))
symbols.sort();addresses=[x[0] for x in symbols];byname={name:addr for addr,name in symbols}
def name(va):
 raw=va;va=(va&0x0000ffffffffffff)|0xffff000000000000
 if nt<=va<nt+0x1249000:
  i=bisect.bisect_right(addresses,va)-1
  if i>=0:return 'nt!'+symbols[i][1]+f'+{va-symbols[i][0]:#x}'
 return d['symbolize'](va)
print('Symbols:',len(symbols),'KiProcessorBlock',hex(byname['KiProcessorBlock']))
results=[]
for cpu in range(8):
 prcb=q(byname['KiProcessorBlock']+cpu*8);thread=q(prcb+8);context=read(prcb+64+832,912)
 regs={key:struct.unpack_from('<Q',context,off)[0] for key,off in [('fp',240),('lr',248),('sp',256),('pc',264)]}
 limit,base,ksp=q(thread+48),q(thread+56),q(thread+88)
 print('\nCPU',cpu,'PRCB',hex(prcb),'thread',hex(thread),'stack',hex(limit),hex(base),'ksp',hex(ksp))
 print('Saved context flags',hex(struct.unpack_from('<I',context)[0]),[(k,hex(v),name(v)) for k,v in regs.items()])
 row={'cpu':cpu,'prcb':hex(prcb),'thread':hex(thread),'registers':{k:hex(v) for k,v in regs.items()},'stack_limit':hex(limit),'stack_base':hex(base),'candidates':[]}
 if 0<base-limit<=0x20000:
  stack=read(limit,base-limit);(out/f'cpu{cpu}-stack.bin').write_bytes(stack)
  for off in range(0,len(stack)-8,8):
   value=struct.unpack_from('<Q',stack,off)[0];label=name(value)
   if label:
    row['candidates'].append({'slot':hex(limit+off),'value':hex(value),'symbol':label})
  if cpu==6:
   for item in row['candidates']:print(item)
 results.append(row)
(out/'cpu-stack-candidates.json').write_text(json.dumps(results,indent=2))
(out/'nt-public-symbols.json').write_text(json.dumps(symbols))
