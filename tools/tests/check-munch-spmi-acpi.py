#!/usr/bin/env python3
"""Validate the SPMI vendor ABI, live resource provenance and compiled namespace."""
from pathlib import Path
import re
import subprocess
root=Path(__file__).resolve().parents[2]
expected=bytes.fromhex('00010101ff0002000a07040701ff100100010c40000002800000')
for platform in ('alioth','nabu'):
    text=(root/f'Mu-Silicium/Silicium-ACPI/Platforms/Xiaomi/{platform}/Decompiled/DSDT.dsl').read_text()
    node=text.split('Device (SPMI)',1)[1].split('Device (GIO0)',1)[0]
    body=re.search(r'Buffer \(0x1A\)\s*\{(.*?)\}',node,re.S).group(1)
    body=re.sub(r'/\*.*?\*/','',body,flags=re.S)
    assert bytes(int(n,16) for n in re.findall(r'0x([0-9A-Fa-f]{2})\b',body))==expected
    assert '0x0C400000' in node and '0x02800000' in node
props=lambda name:[int(n,16) for n in subprocess.check_output(['fdtget','-tx',str(root/'inputs/munch/live.dtb'),'/soc/qcom,spmi@c440000',name],text=True).split()]
regs=props('reg')
assert len(regs)==10 and props('qcom,ee')==[0] and props('qcom,channel')==[0]
for base,length in zip(regs[::2],regs[1::2]):
    assert 0xc400000<=base<base+length<=0xc400000+0x2800000
commands='; '.join('evaluate _SB.'+name for name in ('SCM0._HID','SCM0._STA','RPEN._HID','RPEN._STA','SPMI._HID','SPMI._STA','SPMI._CRS','SPMI.CONF'))
result=subprocess.run(['acpiexec','-b',commands,str(root/'firmware/munch/Acpi/DSDT.aml'),str(root/'firmware/munch/Acpi/SSDT-GPU-SPMI.aml')],text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,check=True)
out=result.stdout
assert 'failed with status' not in out and 'ACPI Error' not in out,out
assert all(s in out for s in ('QCOM250B','QCOM2533','QCOM250C'))
assert out.count('[Integer] = 000000000000000F')==3
assert '[Buffer] Length 1A' in out
aml=(root/'firmware/munch/Acpi/SSDT-GPU-SPMI.aml').read_bytes()
assert expected in aml and sum(aml)%256==0
assert all(h not in aml for h in (b'QCOM253A',b'QCOM2519',b'QCOM252E'))
(root/'out/kona-gpu/acpi-spmi-evaluation.txt').write_text(out)
print('Reference CONF ABI, live resource coverage, SCM/RPEN/SPMI IDs and _STA: PASS')
