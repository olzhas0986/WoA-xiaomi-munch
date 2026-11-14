# Windows25: SPMI bus bring-up

Observed device results: SCM/qcscm and RPEN/QCRPEN both report Status OK,
ConfigManagerErrorCode 0 in Windows24. PnP startup does not verify every
operation offered by either driver.

Windows25 retains those nodes and adds only SPMI/QCOM250C, using the explicit
match from the pinned Kona BSP qcspmi8250.inf. No PMIC client, PEP, GPIO,
SMMU or GPU node is enumerated. This test measures bus-driver startup; it
is not a GPU acceleration or regulator-control test.

SPMI resource provenance:

* Captured inputs/munch/live.dtb, /soc/qcom,spmi@c440000, contains the
  register windows c440000/1100, c600000/2000000, e600000/100000,
  e700000/a0000 and c40a000/26000, execution environment 0, channel 0.
  The build refuses this profile if any of these properties changes.
* The Qualcomm reference ACPI SPMI window c400000/2800000 contains all
  those windows. It is the same in the alioth and nabu reference tables.
* The CONF method returns the exact 26-byte vendor configuration buffer
  found in both reference devices. Unknown fields are preserved rather
  than assigned guessed meanings. Compatibility with this particular
  Windows driver still requires a device test.
* The old alioth SPMI ID QCOM250B conflicts with our current SCM ID and
  must not be reused. qcspmi8250.inf explicitly matches QCOM250C.
* Native reference _CID PNP0CA2, _UID 1, and _CCA 0 are preserved.

Source BSP commit: 22221a09e02cb7054792427af60299b1c34d3c3e.
qcspmi8250.sys is ARM64, 1.0.2100.0000, boot-start service qcspmi, group
Filter. The original INF configures its WMI autologger. INF/CAT/SYS remain
byte-identical to the BSP. The WOA catalog certificate matches the already
installed SCM/RPEN signer. No new certificate or BCD change is required.

Build:

    MUNCH_GPU_FOUNDATION=3 MUNCH_USB_ACPI=1 MUNCH_UFS_ACPI=1 bash tools/build-munch.sh
    python3 tools/pack-munch.py --output out/munch-fresh/munch-uefi-windows25-spmi.img
    .venv/bin/python tools/verify-munch.py --image out/munch-fresh/munch-uefi-windows25-spmi.img --gpu-spmi --winpe --usb-acpi --ufs-acpi --no-preboot-kbd
    python3 tools/prepare-kona-gpu-bootstrap.py --stage spmi

Install out/kona-gpu/munch-gpu-spmi-bootstrap-twrp.zip in TWRP with ESP
unmounted, then boot the above image with fastboot boot. The ZIP only
copies its files to the separate ESP/MUNCH/GPU25 folder.

Administrator PowerShell, using an unused drive letter:

    mountvol S: /S
    S:\MUNCH\GPU25\setup.cmd

The script requires active test signing, the existing publisher certificate,
and both SCM and RPEN code 0 before installing only qcspmi8250.inf. It prints
a short status table and writes C:\munch-gpu-spmi/report.json. These files
are included in the existing read-only TWRP log collector.

Additional status: setup.cmd report. Normal removal: setup.cmd rollback,
then boot Windows24. SCM, RPEN and the existing signing settings remain.
Rollback removes the published INF only if this experiment added it and
it is not shared with another kind of device. A boot-time crash may require
recovery/offline service removal; that procedure is not automated.
