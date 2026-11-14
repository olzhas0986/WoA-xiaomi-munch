# Windows28: first PEP core startup experiment

> Historical and crash-prone bring-up profile. Numbered image names below
> identify experiments, not published releases. Use `make pep` only with the
> recovery precautions in `docs/PEP.md`.

Windows27 passed the live DSDT/8-CPU/four-service check on the phone.
This stage attempts to start qcpep8250.sys itself. It is not proof of working
GPU power management, CPU frequency scaling, thermal control or low power.
A start failure or crash is possible with the still incomplete board port.

Firmware retains the tested SYSM/CLUS CPU paths and SCM/RPEN/SPMI/PMIC.
It adds PEP0 with the actual QCOM2519 ID, PNP0D80 CID, and the concrete
reference _CRS interrupt list, INTR package and GEPT method. PGDS/FPMD/PPRR
preserve native zero/empty defaults. Missing thermal/subsystem/firmware
contracts remain absent, so the driver may fail honestly rather than receiving
invented successful callbacks. No GPU/SMMU is exposed.

The first four TSENS interrupt numbers match SM8250's two thermal controllers.
The remaining IRQ order and INTR package are retained from the Qualcomm
alioth reference. INTR's 86000000/200000 range remains inside the firmware's
PIL Reserved range, not general-purpose RAM. This is not described as SMEM:
the captured munch SMEM is at 80900000. Not all vendor INTR fields have been
decoded. The old IPCC ID QCOM25C2 now binds a ThermalMDM device in the BSP;
no fake IPCC dependency or old IPCC node is introduced. IPC and optional
resources remain unresolved and may prevent startup.

Original BSP qcpep.wd8250.inf/.cat, qcpep8250.sys and the referenced
PPMSettings-8250Profiles.wd.ppkg are copied byte-identically from commit
22221a09e02cb7054792427af60299b1c34d3c3e. The existing WOA catalog signer is
reused. The native INF contains 13 analysed resource blobs and enables CPU
management/system low power by default. It also copies the provisioning
package, changes a global PoFx setting and configures a qcpep-rpmh autologger.
This is why the installer does not immediately start the device with defaults.

Installation sequence:

1. Require active test signing, existing publisher trust and four code-0 services.
2. Require a fresh PEP node (code 28). Save provisioning/PoFx/autologger state.
3. Disable PEP and require code 22 before package installation.
4. Install the original INF. Require code 22 and service State=Stopped afterward.
5. Save native parameters. Override only the explicit policy.json DWORD values,
   whose names are also checked against strings in the actual driver binary.
   Existing registry keys are retained. Verify every written value before enable.
6. Enable the device, save a report and print the actual device status.

The policy disables processor management, ACPI LPI, idle callbacks, system LPM,
CPU/L2 collapse/retention, bandwidth DCVS, directed P states, parking, BCL and
LTVR for the initial core test. WPP is enabled for diagnosis. These settings
reduce the initial scope; they do not guarantee that all PEP initialization
is inert. A crash may require offline recovery. No shutdown/reboot is automatic.

Build/package:

    MUNCH_GPU_FOUNDATION=6 MUNCH_USB_ACPI=1 MUNCH_UFS_ACPI=1 bash tools/build-munch.sh
    python3 tools/pack-munch.py --output out/munch-fresh/munch-uefi-windows28-pep.img
    .venv/bin/python tools/verify-munch.py --image out/munch-fresh/munch-uefi-windows28-pep.img --gpu-pep --pep-prep --winpe --usb-acpi --ufs-acpi --no-preboot-kbd
    python3 tools/prepare-kona-gpu-bootstrap.py --stage pep

Install out/kona-gpu/munch-gpu-pep-bootstrap-twrp.zip in TWRP with ESP unmounted,
then fastboot boot the image. Administrator PowerShell:

    mountvol S: /S
    S:\MUNCH\GPU28D\setup.cmd

Reports and install state: C:\munch-gpu-pep-core, also retrieved by the existing
read-only TWRP collector. A prior incomplete attempt requires inspecting report
or rollback rather than reapplying defaults. setup.cmd report is read-only
apart from writing its report. setup.cmd rollback disables/removes only an
owned, unshared PEP INF, restores the tracked global/provisioning state and
leaves the four tested drivers/signing settings. Then boot Windows27.
If Windows cannot boot, recovery/offline service removal is required instead;
normal in-Windows rollback cannot run in that situation.

Host checks validate the image/ACPI, package integrity and policy-name presence.
The Windows installer and PEP startup still require testing on the phone.

Installer revision 28A (firmware remains Windows28):

The device was observed as present ACPI\QCOM2519\0, no service, problem 0.
The original script failed its device-count check even though Get-PnpDevice
showed this node. The revision uses Get-PnpDevice -PresentOnly with explicit
numeric DEVPKEY_Device_ProblemCode and DEVPKEY_Device_Service properties,
and materializes every Pep result with @(...) to avoid scalar Count behavior.
A fresh unbound node is accepted with problem 0 or 28, never merely because
it reports OK. The disable/code-22/stopped-driver/policy-readback guards remain.
No particular one of the WMI visibility/scalar-count issues is claimed as
proven independently by the original report.

Recovery destination is a new MUNCH/GPU28D folder so the previous package is
not overwritten. A portable out/kona-gpu/munch-pep-fix-windows.zip also contains
exactly the same checked files in GPU28D/. Copy it via a USB drive, extract
inside Windows, and run GPU28D/setup.cmd as administrator. This avoids a
firmware/recovery round trip. Existing Windows28 firmware is sufficient.

Installer revision 28B: a missing PoFxSystemIrpWaitForReportDevicePowered
value produced PSArgumentException from Get-ItemPropertyValue despite the
SilentlyContinue option. All optional named registry-value reads now query
an existing key and inspect PSObject.Properties, preserving missing versus
numeric zero. Access failures still stop installation. A read-only missing-value
self-check runs before device/policy changes. The CMD wrapper pauses on errors
so an Explorer launch does not silently lose the error window. The image is
unchanged; the portable package now extracts into GPU28D.

Installer revision 28C: Windows refused to disable the fresh, unbound PEP node
as a critical device. The initial disable now uses the documented pnputil
/disable-device <exact-instance-id> /force form (Windows 11 23H2+). It is reached
only after checking the expected node has no service and problem 0/28. Code 22
is still mandatory before adding the package; there is no fallback to installing
with the device enabled. Normal rollback retains its original disable behavior.
Source: https://learn.microsoft.com/en-us/windows-hardware/drivers/devtest/pnputil-command-syntax

A saved before-disable attempt can resume only if the matching BSP state has
no published INF or ownership, the device remains fresh/unbound, and no qcpep
system driver exists. Original provisioning/global-setting/autologger snapshots
are retained rather than overwritten. All later/inconsistent phases still stop.

Installer revision 28D: device code 22 is now an explicit resumable pre-install
state after a saved before-disable/waiting-disable-reboot phase. The node must
still have no service, no qcpep system driver, no recorded package, and matching
BSP state. The original backups remain intact. An already disabled device is
not disabled again. If disabling is deferred until reboot, the script records
waiting-disable-reboot and stops normally before package installation.

Windows29 identity-method correction:

The device returned problem status 3221225486 (C000000E) with code 31.
The pinned binary explicitly evaluates PEPH at RVA 03e170, called from
20f314, compares its returned full hardware ID via wcscmp calls 20f340 and
20f360, and has an early C000000E identity-rejection return at 20f488.
The reference adds PEPH in a separate Scope(\_SB.PEP0), outside the main
PEP Device block. The initial port missed that separate scope. Windows29
adds PEPH returning Package(){"ACPI\\VEN_QCOM&DEV_2519"}, adapted to the
actual installed driver's ID. The signed driver and test policy are unchanged.

Run tools/audit-kona-peph.py and tools/tests/check-munch-peph-acpi.py for the
binary/AML evidence. tools/audit-kona-pep.py now inventories the methods in
all separate PEP0 scopes, not just the main Device block. Additional contracts
remain incomplete, so a later error is possible after this identity check.

For the already-installed device, boot
out/munch-fresh/munch-uefi-windows29-peph.img and run the existing GPU28D
setup.cmd report. No driver reinstallation or portable ZIP update is needed.
