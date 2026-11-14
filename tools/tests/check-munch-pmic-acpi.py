#!/usr/bin/env python3
"""Check the core PMIC package and dependency using the compiled ACPI tables."""
from pathlib import Path
import re
import subprocess
root=Path(__file__).resolve().parents[2]
for model,first in (('pm8150',0),('pm8150b',2),('pm8150l',4)):
    for sid in (first,first+1):
        node=f'/soc/qcom,spmi@c440000/qcom,{model}@{sid:x}'
        data=subprocess.check_output(['fdtget','-tx',str(root/'inputs/munch/live.dtb'),node,'reg'],text=True)
        assert [int(n,16) for n in data.split()]==[sid,0]
reference=(root/'Mu-Silicium/Silicium-ACPI/Platforms/Xiaomi/nabu/Decompiled/DSDT.dsl').read_text()
ref=reference.split('Method (PMCF',1)[1].split('Device (PM01)',1)[0]
assert 'Package (0x04)' in ref and '0x03' in ref
assert 'Zero' in ref and 'One' in ref and all(f'0x0{i}' in ref for i in (2,4,5))
args=['acpiexec','-b','evaluate _SB.PMIC.PMCF; evaluate _SB.PMIC._DEP; evaluate _SB.PMIC._HID; evaluate _SB.PMIC._STA',str(root/'firmware/munch/Acpi/DSDT.aml'),str(root/'firmware/munch/Acpi/SSDT-GPU-PMIC.aml')]
out=subprocess.run(args,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,check=True).stdout
assert 'failed with status' not in out and 'ACPI Error' not in out,out
pmcf=out.split('Evaluating \\_SB.PMIC.PMCF',1)[1].split('Evaluating \\_SB.PMIC._DEP',1)[0]
assert [int(n,16) for n in re.findall(r'\[Integer\] = ([0-9A-F]{16})',pmcf)]==[3,0,1,2,3,4,5],out
assert 'SPMI' in out and 'QCOM252E' in out and '[Integer] = 000000000000000F' in out
aml=(root/'firmware/munch/Acpi/SSDT-GPU-PMIC.aml').read_bytes()
assert sum(aml)%256==0
assert all(h in aml for h in (b'QCOM250B',b'QCOM2533',b'QCOM250C',b'QCOM252E'))
assert all(h not in aml for h in (b'QCOM253A',b'QCOM2519',b'QCOM2509'))
(root/'out/kona-gpu/acpi-pmic-evaluation.txt').write_text(out)
print('Core PMIC slave pairs, compiled PMCF, SPMI dependency and namespace: PASS')
