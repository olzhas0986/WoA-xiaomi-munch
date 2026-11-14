#!/usr/bin/env python3
"""Read PEP ETL buffers; retain raw data when no matching manifest is available."""
import collections,json,re,sys,uuid
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
for name in ('dissect.etl-3.14','dissect.cstruct-4.6','dissect.util-main'):sys.path.insert(0,str(ROOT/'out/kona-gpu/host-tools'/name))
from dissect.etl import ETL,Buffer
from collections.abc import Mapping
from dissect.etl.headers.event import EventHeader,EventHeaderExtendedDataItem
folder=Path(sys.argv[2]) if len(sys.argv)>2 else ROOT/'out/kona-gpu/device-pep-fault/traces'
def normalize(v):
 if isinstance(v,(str,int,float,bool)) or v is None:return v
 if isinstance(v,(bytes,bytearray,memoryview)):return bytes(v).hex()
 if isinstance(v,Mapping):return {str(k):normalize(x) for k,x in v.items()}
 if isinstance(v,(list,tuple)):return [normalize(x) for x in v]
 if hasattr(v,'__values__'):return normalize(v.__values__)
 return str(v)
for path in sorted(folder.glob(sys.argv[1] if len(sys.argv)>1 else 'MunchPepBoot.etl.*')):
 rows=[];counts=collections.Counter();errors=[];last=collections.deque(maxlen=30);total=0
 with path.open('rb') as f:
  etl=ETL(f)
  declared_buffers=etl.logfile_header.buffers_written
  recover_live=(declared_buffers==0)
  offsets=(range(0,path.stat().st_size,etl.buffer_size) if recover_live else None)
  buffers=(Buffer(etl,offset) for offset in offsets) if recover_live else etl.buffers()
  for buf in buffers:
   try:
    if buf.size!=etl.buffer_size or not 72<=buf.filled_bytes<=buf.size or buf.offset+buf.size>path.stat().st_size:
     raise ValueError('Invalid/incomplete ETL buffer while recovering live trace')
    for record in buf:
     h=record.header;total+=1
     guid=uuid.UUID(bytes_le=h.header.ProviderId) if isinstance(h,EventHeader) else h.provider_id
     counts[str(guid)]+=1
     if not isinstance(h,EventHeader):continue
     payload=bytes(h.payload);extensions=[]
     if h.header.Flags&1:
      while len(payload)>=8:
       try:ext=EventHeaderExtendedDataItem(payload)
       except Exception:break
       if ext.size>len(payload) or ext.ext_type==0:break
       extensions.append(normalize(ext.data));payload=payload[ext.size:]
     event_id=h.header.Id;version=h.header.Version;symbol=None;values=None;decode_error=None
     # The bundled manifests predate this Windows build. Keep payload bytes
     # rather than assigning names/types from a mismatched event schema.
     row={'time':str(h.timestamp),'qpc':h.time_delta,'provider':str(guid),'id':event_id,'version':version,'thread':h.thread_id,'symbol':symbol,'values':values,'payload_hex':payload.hex(),'stacks':extensions}
     if decode_error:row['decode_error']=decode_error
     last.append(row)
     raw=payload.lower();decoded=json.dumps(values).lower() if values else ''
     if b'qcpep' in raw or 'qcpep'.encode('utf-16le') in raw or 'qcom2519'.encode('utf-16le') in raw or 'qcpep' in decoded or str(guid) in ('5412704e-b2e1-4624-8ffd-55777b8f7373','2c89c855-6301-41f9-bf56-63416dfe9ca9'):
      rows.append(row)
   except Exception as exc:errors.append({'buffer':buf.offset,'error':str(exc)})
  report={'file':path.name,'start':str(etl.start),'end':str(etl.end),'buffers_written':etl.logfile_header.buffers_written,'recovered_unfinalized_buffers':recover_live,'records':total,'providers':dict(counts),'errors':errors,'selected':rows,'last_records':list(last)}
 out=path.with_suffix(path.suffix+'.json');out.write_text(json.dumps(report,indent=2))
 print(path.name,'records',total,'selected',len(rows),'errors',len(errors),'providers',dict(counts),flush=True)
 for row in rows[-8:]:print(row['time'],row['id'],row['symbol'],str(row['values'])[:500],flush=True)
