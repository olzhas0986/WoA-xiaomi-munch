#!/usr/bin/env python3
"""Install the reproducible diagnostic overlay; never consume old build outputs."""
import hashlib
import os
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MU = ROOT / 'Mu-Silicium'
SOURCE = ROOT / 'platform/munchPkg'
DEST = MU / 'Platforms/Xiaomi/munchFreshPkg'
EXPECTED_XBL = '696eaefeb4798b6c3427740232ae71006070b6bab079343cfe2a661363073c3b'

def main():
    xbl = ROOT / 'inputs/munch/xbl.img'
    if hashlib.sha256(xbl.read_bytes()).hexdigest() != EXPECTED_XBL:
        raise SystemExit('Input XBL changed: review the new version before building')
    extracted = ROOT / 'inputs/munch/extracted-xbl'
    manifest = json.loads((extracted / 'manifest.json').read_text())
    if manifest['xbl_sha256'] != EXPECTED_XBL:
        raise SystemExit('Extraction belongs to another XBL')
    for module in manifest['modules']:
        for section in module['sections']:
            if hashlib.sha256((extracted / section['file']).read_bytes()).hexdigest() != section['sha256']:
                raise SystemExit('Extracted module changed: ' + section['file'])
    shutil.copytree(extracted, MU / 'Binaries/munchFresh', dirs_exist_ok=True)
    for src in SOURCE.rglob('*'):
        if not src.is_file() or 'BootManagerLib' in src.parts or src.name == 'DeviceBuild.py':
            continue
        dest = DEST / src.relative_to(SOURCE)
        dest.parent.mkdir(parents=True, exist_ok=True)
        text = src.read_text().replace('munchPkg', 'munchFreshPkg').replace('Binaries/munch/', 'Binaries/munchFresh/')
        if src.suffix == '.dsc':
            text += '\n[LibraryClasses]\n  SerialPortLib|munchFreshPkg/Library/FrameBufferSerialPortLib/FrameBufferSerialPortLib.inf\n'
            text = text.replace('PLATFORM_NAME                  = munch', 'PLATFORM_NAME                  = munchFresh')
            text = text.replace('4243CCB9-8183-4C8B-A659-C2532F763586', 'FCB39AC3-1D77-4A52-BEF2-0FC825070001')
            text = text.replace("  # MUNCH-specific BDS hook starts the resident HackiOS loader.", '  # Diagnostic BDS, built from source, with no XNU payload hook.')
            text = text.replace('  # ACPI tables are not needed by the XNU loader\'s Apple device tree.',
                                '  munchFreshPkg/Acpi/AcpiTables.inf')
        if src.suffix == '.fdf':
            text = text.replace('  # RAM Manager',
                '  INF MdeModulePkg/Bus/Usb/UsbMassStorageDxe/UsbMassStorageDxe.inf\n'
                '  INF MdeModulePkg/Universal/Disk/DiskIoDxe/DiskIoDxe.inf\n'
                '  INF FatPkg/EnhancedFatDxe/Fat.inf\n'
                '\n  # RAM Manager')
            text = text.replace('  # ACPI\n', '  # ACPI\n  INF MdeModulePkg/Universal/Acpi/AcpiTableDxe/AcpiTableDxe.inf\n  INF MdeModulePkg/Universal/Acpi/AcpiPlatformDxe/AcpiPlatformDxe.inf\n  INF RuleOverride = ACPITABLE munchFreshPkg/Acpi/AcpiTables.inf\n')
        # Raw storage probe: avoid duplicate vendor disk drivers and automatic
        # GPT repair/filesystem writes from PartitionDxe/FAT during ConnectAll.
        if src.suffix == '.inc':
            text = '\n'.join(line for line in text.splitlines() if not any(
                name in line for name in ('/DiskIoDxe/', '/PartitionDxe/', '/UsbKbDxe/'))) + '\n'
        # No resident XNU payload exists in this image.
        if src.name == 'MemoryMapLib.c':
            text = text.replace('  // Name, Address, Length, HobOption, ResourceType, ResourceAttribute, MemoryType, ArmAttribute',
                '  // Name, Address, Length, HobOption, ResourceType, ResourceAttribute, MemoryType, ArmAttribute\n'
                '  {"UEFI RAM log", 0xF0000000, 0x00100000, AddMem, SYS_MEM, SYS_MEM_CAP, Reserv, WRITE_BACK_XN},')
            text = '\n'.join(line for line in text.splitlines() if '"XNU Payload"' not in line) + '\n'
            text = text.replace(
                '{"Kernel", 0xA0000000, 0x10000000, AddMem, SYS_MEM, SYS_MEM_CAP, Reserv, WRITE_BACK_XN}',
                '{"DXE additional RAM", 0xA0000000, 0x08000000, AddMem, SYS_MEM, SYS_MEM_CAP, Conv, WRITE_BACK_XN},\n'
                '  {"Boot handoff reserved", 0xA8000000, 0x08000000, AddMem, SYS_MEM, SYS_MEM_CAP, Reserv, WRITE_BACK_XN}')
        dest.write_text(text)
    shutil.copytree(ROOT / 'firmware/munch/BootManager', DEST / 'Library/BootManagerLib', dirs_exist_ok=True)
    shutil.copytree(ROOT / 'firmware/munch/Serial', DEST / 'Library/FrameBufferSerialPortLib', dirs_exist_ok=True)
    shutil.copy2(ROOT / 'firmware/munch/BootManager/RamLog.h', DEST / 'Library/FrameBufferSerialPortLib/RamLog.h')
    shutil.copytree(ROOT / 'firmware/munch/Acpi', DEST / 'Acpi', dirs_exist_ok=True)
    foundation = os.environ.get('MUNCH_GPU_FOUNDATION', '0')
    if foundation not in ('0', '1', '2', '3', '4', '5', '6'):
        raise SystemExit('Invalid GPU foundation profile')
    if foundation != '0':
        inf = DEST / 'Acpi/AcpiTables.inf'
        table = {'1': 'SSDT-GPU-FOUNDATION', '2': 'SSDT-GPU-RPEN', '3': 'SSDT-GPU-SPMI', '4': 'SSDT-GPU-PMIC', '5': 'SSDT-GPU-PMIC', '6': 'SSDT-GPU-PEP'}[foundation]
        inf.write_text(inf.read_text() + '  ASL|' + table + '.aml\n')
    print('Prepared munchFreshPkg from source with 91 verified local vendor modules')

if __name__ == '__main__':
    main()
