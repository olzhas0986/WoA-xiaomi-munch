#!/usr/bin/env python3
"""Check the actual PEP identity method result and the native binary gate."""
from pathlib import Path
import subprocess
root=Path(__file__).resolve().parents[2]
subprocess.run(['python3',str(root/'tools/audit-kona-peph.py')],check=True)
b=(root/'firmware/munch/Acpi/SSDT-GPU-PEP.aml').read_bytes()
# The AML payload must contain one actual slash, not two literal slashes.
expected=b'ACPI\\VEN_QCOM&DEV_2519\0'
assert expected in b and b'ACPI\\\\VEN_QCOM&DEV_2519\0' not in b
s=subprocess.run(['acpiexec','-b','evaluate _SB.PEP0.PEPH',str(root/'firmware/munch/Acpi/DSDT.aml'),str(root/'firmware/munch/Acpi/SSDT-GPU-PEP.aml')],text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,check=True).stdout
assert 'failed with status' not in s and 'ACPI Error' not in s
assert '[Package] Contains 1 Elements' in s and '[String] Length 16' in s
assert 'VEN_QCOM&DEV_2519' in s
(root/'out/kona-gpu/acpi-peph-evaluation.txt').write_text(s)
print('PEPH package type, single full PnP ID, string length and native identity gate: PASS')
