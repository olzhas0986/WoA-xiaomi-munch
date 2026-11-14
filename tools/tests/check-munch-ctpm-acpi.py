#!/usr/bin/env python3
"""Validate the contract required by the observed native CoreTopology assert."""
from pathlib import Path
import subprocess,runpy,contextlib,io
root=Path(__file__).resolve().parents[2]
with contextlib.redirect_stdout(io.StringIO()):d=runpy.run_path(str(root/'tools/audit-kona-peph.py'))
b=d['b'];offset=d['offset'];branch=d['branch_target']
assert b[offset(0x231cf0):offset(0x231cf0)+5]==b'CTPM\0'
assert b[offset(0x231cf8):offset(0x231cf8)+14]==b'CORE_TOPOLOGY\0'
assert branch(0x18e38)==0x1e3d48 and branch(0x18ea0)==0x101e80
result=subprocess.run(['acpiexec','-b','evaluate _SB.PEP0.CTPM',str(root/'firmware/munch/Acpi/DSDT.aml'),str(root/'firmware/munch/Acpi/SSDT-GPU-PEP.aml')],check=True,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT).stdout
assert 'ACPI Error' not in result and 'failed with status' not in result
assert '[Package] Contains 2 Elements' in result and 'CORE_TOPOLOGY' in result
assert '[Integer] = 0000000000000008' in result
(root/'out/kona-gpu/acpi-ctpm-evaluation.txt').write_text(result)
print('Native CTPM resource name, observed assertion path, evaluated package types and 8-core count: PASS')
