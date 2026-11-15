# PEP CPU namespace preparation

Базовые драйверы готовы. Следующий этап — ACPI-контракт и запуск Qualcomm PEP QCOM2519.

SCM, RPEN, SPMI and core PMIC have reached Running / Code 0. This read-only
check prepares research; it does not install PEP or establish GPU support.

The pinned qcpep.wd8250.inf contains a length-checked CCGP resource with
exact processor paths _SB.SYSM.CLUS.CPU0 through CPU7. The earlier foundation-only namespace has these
CPUs directly under _SB. The preparation profile moves the eight ACPI0007 devices into
SYSM/CLUS containers (ACPI0010), preserving processor UIDs 0 through 7,
MADT topology and USB/UFS resources. No deep idle _LPI state is added.
The existing SCM/RPEN/SPMI/PMIC SSDT is unchanged. See
[docs/PEP.md](../../../docs/PEP.md) for the current research scope.

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

    make stable
    make verify
    python3 tools/prepare-munch-pep-prep.py

Install out/kona-gpu/munch-gpu-pep-prep-twrp.zip in TWRP with ESP unmounted,
then follow the normal boot sequence in the root README.md. GPU27 is the
legacy package folder name, not a separate required firmware image. In administrator PowerShell:

    mountvol S: /S
    S:\MUNCH\GPU27\setup.cmd

The script reads the live DSDT through the documented Windows
GetSystemFirmwareTable API and checks its exact SHA256 against this build.
It checks eight logical processors and the four previously installed services.
The only Windows writes are C:\munch-gpu-pep/DSDT.aml and report.json.
No driver, BCD, certificate or policy is changed. Source:
https://learn.microsoft.com/en-us/windows/win32/api/sysinfoapi/nf-sysinfoapi-getsystemfirmwaretable

No driver rollback is needed because no driver is installed. The base profile
uses this preparation CPU layout without exposing a PEP device. The existing TWRP log collector also
retrieves the preparation report and live DSDT.
