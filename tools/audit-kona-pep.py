#!/usr/bin/env python3
"""Extract PEP resource contracts from the pinned, local primary sources."""
import hashlib,json,re,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
REPO=ROOT/'reference/windows_silicon_qcom_kona'
OUT=ROOT/'out/kona-gpu/pep-audit'
COMMIT='22221a09e02cb7054792427af60299b1c34d3c3e'
def main():
    assert subprocess.check_output(['git','-C',str(REPO),'rev-parse','HEAD'],text=True).strip()==COMMIT
    OUT.mkdir(parents=True,exist_ok=True)
    source=REPO/'Drivers/SOC/PowerManagement/qcpep.wd8250.inf'
    text=source.read_text(encoding='utf-16')
    section='';resources=[]
    for line in text.splitlines():
        if line.startswith('['):section=line.strip('[]')
        if not line.startswith('HKR,') or '%REG_BINARY%' not in line:continue
        fields=line.split(',')
        data=bytes(int(n,16) for n in re.findall(r'0x([0-9A-Fa-f]{2})\b',','.join(fields[4:]).split(';',1)[0]))
        name=fields[2].strip()
        if data[:4]!=b'AeoB':continue
        declared=int.from_bytes(data[4:8],'little')
        assert declared==len(data),(name,declared,len(data))
        filename=section+'-'+name+'.bin';(OUT/filename).write_bytes(data)
        resources.append(dict(section=section,name=name,length=len(data),sha256=hashlib.sha256(data).hexdigest(),strings=[s.decode() for s in re.findall(rb'[A-Za-z_/][A-Za-z0-9_/ .-]{5,}',data)]))
    cpu=next(r for r in resources if r['name']=='CCGP')
    assert cpu['strings']==['_SB.SYSM.CLUS.CPU'+str(i) for i in range(8)]
    reference=(ROOT/'Mu-Silicium/Silicium-ACPI/Platforms/Xiaomi/alioth/Decompiled/DSDT.dsl').read_text()
    start=reference.index('        Device (PEP0)');brace=reference.index('{',start);depth=1;end=brace+1
    while depth:
        depth+=(reference[end]=='{')-(reference[end]=='}');end+=1
    node=reference[start:end]
    scope_methods=[]
    for match in re.finditer(r'Scope \(\\_SB\.PEP0\)', reference):
        brace=reference.index('{',match.end());end=brace+1;depth=1
        while depth:
            depth+=(reference[end]=='{')-(reference[end]=='}');end+=1
        scope_methods.extend(re.findall(r'Method \((\w+)',reference[brace:end]))
    external=sorted(set(re.findall(r'\\_SB\.[A-Za-z0-9_.]+',node)))
    allinf=[]
    for path in (REPO/'Drivers').rglob('*.inf'):
        raw=path.read_bytes();s=raw.decode('utf-16' if raw[:2] in (b'\xff\xfe',b'\xfe\xff') else 'utf-8',errors='replace')
        if re.search(r'ACPI\\(?:VEN_QCOM&DEV_|QCOM)25C2',s,re.I):allinf.append(str(path.relative_to(REPO)))
    result=dict(bsp_commit=COMMIT,inf_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),driver_version='1.0.2140.0000',hid='QCOM2519',resources=resources,reference_pep_external_references=external,reference_pep_separate_scope_methods=scope_methods,ipcc_reference_hid='QCOM25C2',matching_ipcc_infs_in_bsp=allinf,unresolved=['IPCC binding/IPC interface contract','PEP interrupt ordering and trigger modes','thermal callbacks and firmware/library resources','processor/system low-power policy','munch board-specific clock and rail configuration'])
    (OUT/'contract.json').write_text(json.dumps(result,indent=2)+'\n')
    print('Extracted',len(resources),'length-checked PEP resource blobs')
    print('PEP CPU paths:',', '.join(cpu['strings']))
    print('Reference IPCC ID matches in BSP:',allinf)
if __name__=='__main__':main()
