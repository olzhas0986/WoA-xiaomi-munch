# Windows24 SCM + RPEN bring-up

Windows23 device result: Qualcomm SCM bound to qcscm, Status OK,
ConfigManagerErrorCode 0, as shown in the user's report. This establishes
successful PnP startup; individual SCM operations are not fully validated.

Windows24 preserves the same SCM0 namespace and adds only RPEN/QCOM2533.
The reference alioth RPEN device has no MMIO, interrupts, or ACPI methods
other than identification and status. Its older QCOM25E1 ID is replaced by
the explicit QCOM2533 match from the pinned Kona BSP qcrpen8250.inf.
No reference panel configuration or firmware-placeholder addresses are copied.

qcrpen8250.sys is ARM64, version 1.0.2100.0000. Its imports are Windows
kernel/WDF/WPP interfaces. The service is demand-start (StartType 3).
The INF has no explicit service dependency or board-specific AddReg settings
other than its administrator/system device ACL. The combined Kona reference
GPU node lists RPEN as a dependency. These facts justify testing this node
separately; they do not establish full runtime compatibility in advance.

Package inputs come unchanged from BSP commit
22221a09e02cb7054792427af60299b1c34d3c3e. Its catalog certificate thumbprint
946CF507369A80E65F2B58BEBF5D02CC159A484D matches the Windows23 SCM catalog.
The Windows24 installer requires active test signing, the existing publisher
certificate, and SCM code 0. It does not change BCD or certificate stores.

Build:

    MUNCH_GPU_FOUNDATION=2 MUNCH_USB_ACPI=1 MUNCH_UFS_ACPI=1 bash tools/build-munch.sh
    python3 tools/pack-munch.py --output out/munch-fresh/munch-uefi-windows24-rpen.img
    .venv/bin/python tools/verify-munch.py --image out/munch-fresh/munch-uefi-windows24-rpen.img --gpu-rpen --winpe --usb-acpi --ufs-acpi --no-preboot-kbd
    python3 tools/prepare-kona-gpu-bootstrap.py --stage rpen

Device steps:

1. Install out/kona-gpu/munch-gpu-rpen-bootstrap-twrp.zip in TWRP with ESP
   unmounted. Only the separate ESP/MUNCH/GPU24 folder is populated.
2. fastboot boot out/munch-fresh/munch-uefi-windows24-rpen.img
3. In administrator PowerShell:

       mountvol S: /S
       S:\MUNCH\GPU24\setup.cmd

   Use another unused letter if S: is occupied. The default phase installs
   only RPEN and prints the SCM/RPEN status table. Reports are stored in
   C:\munch-gpu-rpen and can be collected with the existing TWRP log collector.
4. Additional status: setup.cmd report. Normal removal: setup.cmd rollback,
   then boot Windows23. SCM and signing settings remain intact. The script
   records the published INF and removes it only if this experiment added it
   and it is not bound to another kind of device.

GPU acceleration is still disabled. PEP, PMIC/SPMI, SMMU/IOMMU and the secure
firmware/display contracts remain to be adapted before exposing GPU0.
In particular, the reference MMU1 node is disabled, while GPU0 names both
MMU0/MMU1 as dependencies: simply copying those devices is not sufficient.
Do not install the entire BSP or load the display miniport at this stage.
