#!/usr/bin/env python3
"""Check compiled Kona CPU paths, stable UIDs and unchanged USB/UFS resources."""
from pathlib import Path
import re,struct,subprocess
root=Path(__file__).resolve().parents[2]
paths=['_SB.SYSM.CLUS.CPU'+str(i)+'._UID' for i in range(8)]
out=subprocess.run(['acpiexec','-b','; '.join('evaluate '+p for p in paths),str(root/'firmware/munch/Acpi/DSDT.aml'),str(root/'firmware/munch/Acpi/SSDT-GPU-PMIC.aml')],text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,check=True).stdout
assert 'failed with status' not in out and 'ACPI Error' not in out,out
assert [int(n,16) for n in re.findall(r'\[Integer\] = ([0-9A-F]{16})',out)]==list(range(8)),out
source=(root/'firmware/munch/Acpi/DSDT-pep-prep.asl').read_text()
old=(root/'firmware/munch/Acpi/DSDT-ufs-experimental.asl').read_text()
assert source.count('"ACPI0007"')==old.count('"ACPI0007"')==8
assert '_LPI' not in source and 'PEP0' not in source
# All existing peripheral device source, including resources and children,
# precedes the processor definitions and must remain byte-identical.
newperiph=source[source.index('    Scope'):source.index('        // Kona PEP')]
oldperiph=old[old.index('    Scope'):old.index('        Device (CPU0)')]
assert newperiph==oldperiph
madt=(root/'firmware/munch/Acpi/APIC.aml').read_bytes();pos=44;uids=[]
while pos<len(madt):
    kind,length=madt[pos:pos+2]
    if kind==11:uids.append(struct.unpack_from('<I',madt,pos+8)[0])
    assert length>=2
    pos+=length
assert uids==list(range(8)) and sum(madt)%256==0
report=root/'out/kona-gpu/acpi-pep-cpu-evaluation.txt'
report.parent.mkdir(parents=True,exist_ok=True)
report.write_text(out)
print('Eight Kona CPU paths, UIDs/MADT and unchanged peripheral definitions: PASS')
