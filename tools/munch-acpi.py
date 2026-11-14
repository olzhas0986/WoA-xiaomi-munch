#!/usr/bin/env python3
"""Generate minimal ACPI tables using EDK II ACPI layouts and captured DT data."""
import struct
import subprocess
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'firmware/munch/Acpi'
DTB = ROOT / 'inputs/munch/live.dtb'

def prop(node, name):
    return [int(x, 16) for x in subprocess.check_output(
        ['fdtget', '-t', 'x', str(DTB), node, name], text=True).split()]

def write(signature, revision, body):
    data = bytearray(struct.pack('<4sIBB6s8sI4sI', signature.encode(), 36 + len(body),
                                revision, 0, b'MUNCH ', b'MUNCHCPU', 1, b'PYTH', 1) + body)
    data[9] = (-sum(data)) & 255
    (OUT / (signature + '.aml')).write_bytes(data)

def main():
    cpus = subprocess.check_output(['fdtget', '-l', str(DTB), '/cpus'], text=True).split()
    mpidrs = []
    for cpu in cpus:
        if cpu.startswith('cpu@'):
            cells = prop('/cpus/' + cpu, 'reg')
            mpidrs.append((cells[0] << 32) | cells[1])
    if mpidrs != [i << 8 for i in range(8)]:
        raise SystemExit('Unexpected CPU topology: ' + repr(mpidrs))
    if prop('/soc/ssusb@a600000/dwc3@a600000', 'reg') != [0x0A600000, 0xD93C] or prop('/soc/ssusb@a600000/dwc3@a600000', 'interrupts') != [0, 133, 4]:
        raise SystemExit('Unexpected primary USB resources; review ACPI')
    # MADT 5, ACPI 6.0 GICC length 80, GICv3, PSCI (no parking protocol).
    madt = bytearray(8)
    for uid, mpidr in enumerate(mpidrs):
        gicc = bytearray(80)
        struct.pack_into('<BBHIIIII', gicc, 0, 11, 80, 0, uid, uid, 1, 0, 23)
        struct.pack_into('<I', gicc, 56, 25)
        struct.pack_into('<Q', gicc, 68, mpidr)
        gicc[76] = 0 if uid < 4 else (1 if uid < 7 else 2)
        madt += gicc
    madt += struct.pack('<BBHIQIB3s', 12, 24, 0, 0, 0x17A00000, 0, 3, b'\0' * 3)
    madt += struct.pack('<BBHQI', 14, 16, 0, 0x17A60000, 0x100000)
    write('APIC', 5, madt)
    # FADT 6.5: HW_REDUCED_ACPI; PSCI via SMC. Firmware installs DSDT pointers.
    fadt = bytearray(276 - 36)
    struct.pack_into('<I', fadt, 112 - 36, 1 << 20)
    struct.pack_into('<H', fadt, 129 - 36, 1)
    fadt[131 - 36] = 5
    write('FACP', 6, fadt)
    # GTDT 2: architected timer PPIs from the live DT, no platform timer blocks.
    if prop('/soc/interrupt-controller@17a00000', 'reg') != [0x17A00000, 0x10000, 0x17A60000, 0x100000]:
        raise SystemExit('Unexpected GIC layout')
    method = subprocess.check_output(['fdtget', str(DTB), '/psci', 'method'], text=True).strip()
    if method != 'smc':
        raise SystemExit('Unexpected PSCI conduit')
    timer = prop('/soc/timer', 'interrupts')
    if len(timer) < 12:
        raise SystemExit('Missing architected timer interrupts')
    gtdt = bytearray(96 - 36)
    struct.pack_into('<Q', gtdt, 0, 0xFFFFFFFFFFFFFFFF)
    for index, pos in enumerate((48, 56, 64, 72)):
        kind, irq, flags = timer[index * 3:index * 3 + 3]
        if kind != 1 or flags & 15 not in (4, 8):
            raise SystemExit('Unexpected timer IRQ encoding')
        struct.pack_into('<II', gtdt, pos - 36, irq + 16, 2 if flags & 15 == 8 else 0)
    struct.pack_into('<Q', gtdt, 80 - 36, 0xFFFFFFFFFFFFFFFF)
    write('GTDT', 2, gtdt)
    usb_acpi = os.environ.get('MUNCH_USB_ACPI', '0')
    ufs_acpi = os.environ.get('MUNCH_UFS_ACPI', '0')
    if usb_acpi not in ('0', '1') or ufs_acpi not in ('0', '1'):
        raise SystemExit('MUNCH_USB_ACPI and MUNCH_UFS_ACPI must be 0 or 1')
    if ufs_acpi == '1':
        if usb_acpi != '1':
            raise SystemExit('UFS test requires the working USB ACPI profile')
        if prop('/soc/ufshc@1d84000', 'reg') != [0x1d84000, 0x3000, 0x1d90000, 0x8000] or prop('/soc/ufshc@1d84000', 'interrupts') != [0, 265, 4]:
            raise SystemExit('Unexpected primary UFS resources; review ACPI')
    foundation = os.environ.get('MUNCH_GPU_FOUNDATION', '0')
    if foundation not in ('0', '1', '2', '3', '4', '5', '6'):
        raise SystemExit('MUNCH_GPU_FOUNDATION must be 0, 1 (SCM), 2 (SCM/RPEN), 3 (SCM/RPEN/SPMI), 4 (core PMIC), 5 (PEP CPU preparation), or 6 (PEP core)')
    if foundation != '0' and ufs_acpi != '1':
        raise SystemExit('GPU foundation requires the working USB/UFS profile')
    if foundation in ('3', '4', '5', '6'):
        node = '/soc/qcom,spmi@c440000'
        expected = [0xc440000, 0x1100, 0xc600000, 0x2000000,
                    0xe600000, 0x100000, 0xe700000, 0xa0000, 0xc40a000, 0x26000]
        if prop(node, 'reg') != expected or prop(node, 'qcom,ee') != [0] or prop(node, 'qcom,channel') != [0]:
            raise SystemExit('Unexpected live SPMI resources/ownership; review the bus configuration')
    if foundation in ('4', '5', '6'):
        for model, sid in (('pm8150', 0), ('pm8150b', 2), ('pm8150l', 4)):
            for addr in (sid, sid + 1):
                if prop('/soc/qcom,spmi@c440000/qcom,%s@%x' % (model, addr), 'reg') != [addr, 0]:
                    raise SystemExit('Core PMIC slave address differs from the captured configuration')
    source = OUT / ('DSDT-pep-prep.asl' if foundation in ('5', '6') else
                    'DSDT-ufs-experimental.asl' if ufs_acpi == '1' else
                    'DSDT-usb-experimental.asl' if usb_acpi == '1' else 'DSDT.asl')
    subprocess.run(['iasl', '-p', str(OUT / 'DSDT'), str(source)], check=True)
    if foundation != '0':
        table = {'1': 'SSDT-GPU-FOUNDATION', '2': 'SSDT-GPU-RPEN', '3': 'SSDT-GPU-SPMI', '4': 'SSDT-GPU-PMIC', '5': 'SSDT-GPU-PMIC', '6': 'SSDT-GPU-PEP'}[foundation]
        subprocess.run(['iasl', '-p', str(OUT / table), str(OUT / (table + '.asl'))], check=True)
        ssdt = (OUT / (table + '.aml')).read_bytes()
        assert ssdt[:4] == b'SSDT' and sum(ssdt) % 256 == 0
        assert b'QCOM250B' in ssdt and b'QCOM253A' not in ssdt
        assert (b'QCOM2519' in ssdt) == (foundation == '6')
        assert (b'QCOM2533' in ssdt) == (foundation in ('2', '3', '4', '5', '6'))
        assert (b'QCOM250C' in ssdt) == (foundation in ('3', '4', '5', '6'))
        assert (b'QCOM252E' in ssdt) == (foundation in ('4', '5', '6'))
    for sig in ('DSDT', 'APIC', 'FACP', 'GTDT'):
        data = (OUT / (sig + '.aml')).read_bytes()
        assert len(data) == struct.unpack_from('<I', data, 4)[0] and sum(data) % 256 == 0
    print('Generated CPU ACPI; xHCI namespace ' + ('enabled (experimental)' if usb_acpi == '1' else 'disabled'))
    print('UFS namespace ' + ('enabled (experimental)' if ufs_acpi == '1' else 'disabled'))

if __name__ == '__main__':
    main()
