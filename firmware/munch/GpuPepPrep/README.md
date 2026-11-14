# Windows27: prepare processor paths for the Kona PEP contract

> Historical bring-up profile. Numbered image names below identify experiments,
> not published releases. Normal users should follow the root `BUILDING.md`.

Windows26 device result: SCM, RPEN, SPMI and core PMIC all report code 0.
The PEP is not installed in this stage. This is a processor namespace test,
not a fifth working driver or working GPU power management.

The pinned qcpep.wd8250.inf contains a length-checked CCGP resource with
exact processor paths _SB.SYSM.CLUS.CPU0 through CPU7. Windows26 has these
CPUs directly under _SB. Windows27 moves the eight ACPI0007 devices into
SYSM/CLUS containers (ACPI0010), preserving processor UIDs 0 through 7,
MADT topology and USB/UFS resources. No deep idle _LPI state is added.
The existing SCM/RPEN/SPMI/PMIC SSDT is unchanged.

The PEP INF is more than a binding ID: its service defaults enable processor
management, ACPI LPI and system low power. Installing it with incomplete
resources would not be an adequate bring-up test. Outstanding contracts:

* Correct IPCC/IPC binding. The old alioth IPCC ID QCOM25C2 now matches the
  BSP's ThermalMDM sensor INF, so it must not be copied blindly.
* PEP interrupt ordering and trigger types (11 reference interrupts).
* Thermal callbacks, firmware libraries, board clocks/rails and shared memory.
* Controlled processor and system idle/performance policies.

Run python3 tools/audit-kona-pep.py to extract the native registry resource
blobs and a machine-readable audit under out/kona-gpu/pep-audit. These blobs
are analysed only and are not installed into Windows.

Build:

    MUNCH_GPU_FOUNDATION=5 MUNCH_USB_ACPI=1 MUNCH_UFS_ACPI=1 bash tools/build-munch.sh
    python3 tools/pack-munch.py --output out/munch-fresh/munch-uefi-windows27-pep-prep.img
    .venv/bin/python tools/verify-munch.py --image out/munch-fresh/munch-uefi-windows27-pep-prep.img --gpu-pmic --pep-prep --winpe --usb-acpi --ufs-acpi --no-preboot-kbd
    python3 tools/prepare-munch-pep-prep.py

Install out/kona-gpu/munch-gpu-pep-prep-twrp.zip in TWRP with ESP unmounted,
then boot the Windows27 image with fastboot boot. In administrator PowerShell:

    mountvol S: /S
    S:\MUNCH\GPU27\setup.cmd

The script reads the live DSDT through the documented Windows
GetSystemFirmwareTable API and checks its exact SHA256 against this build.
It checks eight logical processors and the four previously installed services.
The only Windows writes are C:\munch-gpu-pep/DSDT.aml and report.json.
No driver, BCD, certificate or policy is changed. Source:
https://learn.microsoft.com/en-us/windows/win32/api/sysinfoapi/nf-sysinfoapi-getsystemfirmwaretable

Normal return to the old CPU layout: boot Windows26. No driver rollback is
needed because no driver is installed. The existing TWRP log collector also
retrieves the Windows27 report and live DSDT.
