#!/usr/bin/env python3
"""Inspect the final compressed FV, not only the source-side extraction."""
import hashlib
import argparse
import json
import struct
import uuid
from pathlib import Path
from uefi_firmware.uefi import FirmwareVolume, FirmwareFile, FirmwareFileSystemSection

ROOT = Path(__file__).resolve().parents[1]

def main():
    parser = argparse.ArgumentParser()
    gpu = parser.add_mutually_exclusive_group()
    gpu.add_argument('--gpu-foundation', action='store_true')
    gpu.add_argument('--gpu-rpen', action='store_true')
    gpu.add_argument('--gpu-spmi', action='store_true')
    gpu.add_argument('--gpu-pmic', action='store_true')
    gpu.add_argument('--gpu-pep', action='store_true')
    parser.add_argument('--pep-prep', action='store_true', help='Require Kona CPU container paths; combine with --gpu-pmic')
    parser.add_argument('--image', type=Path, default=ROOT / 'out/munch-fresh/munch-uefi-diag1.img')
    parser.add_argument('--raw-storage', action='store_true', help='Require UFS and exclude partition/FAT drivers')
    parser.add_argument('--winpe', action='store_true', help='Require UFS/FAT with custom read-only partition views')
    parser.add_argument('--usb-acpi', action='store_true', help='Require the experimental xHCI DSDT in the final FV')
    parser.add_argument('--ufs-acpi', action='store_true', help='Require primary UFS resources and Qualcomm driver ID')
    parser.add_argument('--no-preboot-kbd', action='store_true', help='Exclude firmware USB keyboard binding; Windows retains its own driver')
    args = parser.parse_args()
    if args.pep_prep and not (args.gpu_pmic or args.gpu_pep):
        parser.error('--pep-prep requires --gpu-pmic or --gpu-pep')
    platform = ROOT / 'Mu-Silicium/Platforms/Xiaomi/munchFreshPkg'
    fdf = '\n'.join(p.read_text() for p in (platform / 'Include').glob('*.inc'))
    source_fdf = '\n'.join(p.read_text() for p in platform.glob('*.fdf'))
    manifest = json.loads((ROOT / 'inputs/munch/extracted-xbl/manifest.json').read_text())
    expected = {m['guid']:m for m in manifest['modules']
                if 'Binaries/munchFresh/' + m['template'] in fdf
                and 'INF ' + m['template'] not in source_fdf}
    fd = (ROOT / 'Mu-Silicium/Build/munchFreshPkg/DEBUG_CLANGPDB/FV/SILICIUM_UEFI.fd').read_bytes()
    volume = FirmwareVolume(fd)
    assert volume.process()
    checked, acpi, present = set(), set(), set()
    def walk(obj):
        if isinstance(obj, FirmwareFile):
            guid = str(uuid.UUID(bytes_le=obj.guid))
            present.add(guid)
            if guid in expected:
                hashes = {s['sha256'] for s in expected[guid]['sections']}
                def verify(section):
                    if isinstance(section, FirmwareFileSystemSection) and section.type in (0x10, 0x13, 0x19):
                        assert hashlib.sha256(section.data).hexdigest() in hashes, guid
                    else:
                        for child in getattr(section, 'objects', []):
                            verify(child)
                verify(obj)
                checked.add(guid)
        if isinstance(obj, FirmwareFileSystemSection) and obj.type == 0x19:
            data = obj.data
            if data[:4] in (b'DSDT', b'APIC', b'FACP', b'GTDT', b'SSDT'):
                assert len(data) == struct.unpack_from('<I', data, 4)[0] and sum(data) % 256 == 0
                acpi.add(data[:4].decode())
                if data[:4] == b'SSDT':
                    assert args.gpu_foundation or args.gpu_rpen or args.gpu_spmi or args.gpu_pmic or args.gpu_pep
                    name = ('SSDT-GPU-PEP.aml' if args.gpu_pep else
                            'SSDT-GPU-PMIC.aml' if args.gpu_pmic else
                            'SSDT-GPU-SPMI.aml' if args.gpu_spmi else
                            'SSDT-GPU-RPEN.aml' if args.gpu_rpen else 'SSDT-GPU-FOUNDATION.aml')
                    assert data == (ROOT / 'firmware/munch/Acpi' / name).read_bytes()
                    assert (b'QCOM2533' in data) == (args.gpu_rpen or args.gpu_spmi or args.gpu_pmic or args.gpu_pep)
                    assert b'QCOM250B' in data and b'QCOM253A' not in data
                    assert (b'QCOM250C' in data) == (args.gpu_spmi or args.gpu_pmic or args.gpu_pep)
                    if args.gpu_spmi or args.gpu_pmic or args.gpu_pep:
                        assert struct.pack('<II', 0x0c400000, 0x02800000) in data
                        assert bytes.fromhex('00010101ff0002000a07040701ff100100010c40000002800000') in data
                        assert (b'QCOM252E' in data) == (args.gpu_pmic or args.gpu_pep)
                        assert (b'QCOM2519' in data) == args.gpu_pep
                        if args.gpu_pep:
                            assert b'PEPH' in data and b'ACPI\\VEN_QCOM&DEV_2519' in data
                        if args.gpu_pmic or args.gpu_pep:
                            assert b'PMCF' in data and b'PNP0CA3' in data
                if data[:4] == b'DSDT' and args.usb_acpi:
                    assert data == (ROOT / 'firmware/munch/Acpi/DSDT.aml').read_bytes()
                    assert (b'SYSM' in data and b'CLUS' in data) == args.pep_prep
                    assert b'PNP0D10' in data and b'XHC0' in data and b'RHUB' in data
                    # Fixed memory resource and GSI, from the independently checked live DT.
                    assert struct.pack('<II', 0x0a600000, 0xd93c) in data
                    assert struct.pack('<I', 165) in data
                if data[:4] == b'DSDT' and args.ufs_acpi:
                    assert data == (ROOT / 'firmware/munch/Acpi/DSDT.aml').read_bytes()
                    assert b'QCOM24A5' in data and b'UFS0' in data
                    assert struct.pack('<II', 0x1d84000, 0x3000) in data
                    assert struct.pack('<I', 297) in data
        for child in getattr(obj, 'objects', []):
            if hasattr(child, '__dict__'):
                walk(child)
    walk(volume)
    if args.no_preboot_kbd:
        assert '2d2e62cf-9ecf-43b7-8219-94e7fc713dfe' not in present, 'UEFI USB keyboard driver still present'
    if args.raw_storage:
        assert '0d35cd8e-97ea-4f9a-96af-0f0d89f76567' in checked, 'UFS missing or not verified'
        assert '1fa1f39e-feff-4aae-bd7b-38a070a3b609' not in present, 'PartitionDxe can repair GPT'
        assert '961578fe-b6b7-44c3-af35-6bc705cd2b1f' not in present, 'FAT must not mount in raw probe'
    if args.winpe:
        assert '0d35cd8e-97ea-4f9a-96af-0f0d89f76567' in checked
        assert '961578fe-b6b7-44c3-af35-6bc705cd2b1f' in present
        assert '1fa1f39e-feff-4aae-bd7b-38a070a3b609' not in present
    assert len(checked) > 40 and acpi == ({'DSDT', 'APIC', 'FACP', 'GTDT', 'SSDT'} if (args.gpu_foundation or args.gpu_rpen or args.gpu_spmi or args.gpu_pmic or args.gpu_pep) else {'DSDT', 'APIC', 'FACP', 'GTDT'}), (checked, acpi)
    pe_count = 0
    for path in (ROOT / 'Mu-Silicium/Build/munchFreshPkg/DEBUG_CLANGPDB/AARCH64').glob('*.efi'):
        data = path.read_bytes()
        offset = struct.unpack_from('<I', data, 60)[0]
        assert data[offset:offset+4] == b'PE\0\0' and struct.unpack_from('<H', data, offset+4)[0] == 0xAA64, path
        pe_count += 1
    result = {'unchanged_vendor_modules_in_final_fd': len(checked),
              'valid_acpi_tables_in_final_fd': sorted(acpi),
              'arm64_compiled_efi_images': pe_count,
              'packaged_image_sha256': hashlib.sha256(args.image.read_bytes()).hexdigest(),
              'device_tested': False}
    if args.raw_storage:
        result['raw_storage_profile'] = 'UFS verified; PartitionDxe and FAT absent'
    (ROOT / 'out/munch-fresh/verification.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))

if __name__ == '__main__':
    main()
