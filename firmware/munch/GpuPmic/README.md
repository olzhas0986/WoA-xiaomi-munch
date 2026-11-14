# Windows26: core PMIC interface

The user has confirmed SCM, RPEN and SPMI all show Status OK, code 0 in
Windows25. Windows26 preserves those nodes and adds PMIC/QCOM252E, the exact
ID in the pinned qcpmic8250.inf. _CID PNP0CA3 and _DEP on SPMI follow the
reference Qualcomm namespace. No PMIC GPIO, battery, charger, regulator,
PEP, SMMU or GPU clients are added by this stage.

The alioth PMCF template contains four pairs (0/1, 2/3, 4/5, 6/7), but 6/7
are absent from the captured munch DT. Do not copy that board layout.
This core-interface test uses the native three-pair PMCF layout found in the
nabu Kona reference: count 3, pairs (0/1, 2/3, 4/5). Those correspond to the
captured PM8150, PM8150B and PM8150L nodes. The build explicitly checks each
of the six captured slave addresses before enabling this profile.

The captured DT additionally contains modem PMXprairie at 8/9 and camera
PM8009 at a/b. Those are outside this initial core-interface test; this is
not a complete description of all physical PMICs. No guessed device at
6/7 is exposed. The PMIC driver's runtime interpretation still requires
hardware validation, even though the package ABI matches a reference.

Driver: qcpmic8250.sys, ARM64, version 1.0.2100.0000, KMDF 1.25,
boot-start service qcpmic, group Filter. The original INF contains no
board-specific regulator settings. INF/CAT/SYS are copied unchanged from
WOA-Project/windows_silicon_qcom_kona commit
22221a09e02cb7054792427af60299b1c34d3c3e. The catalog certificate is the same
WOA signer already accepted for SCM/RPEN/SPMI. The original license is included.

Build:

    MUNCH_GPU_FOUNDATION=4 MUNCH_USB_ACPI=1 MUNCH_UFS_ACPI=1 bash tools/build-munch.sh
    python3 tools/pack-munch.py --output out/munch-fresh/munch-uefi-windows26-pmic.img
    .venv/bin/python tools/verify-munch.py --image out/munch-fresh/munch-uefi-windows26-pmic.img --gpu-pmic --winpe --usb-acpi --ufs-acpi --no-preboot-kbd
    python3 tools/prepare-kona-gpu-bootstrap.py --stage pmic

Install out/kona-gpu/munch-gpu-pmic-bootstrap-twrp.zip in TWRP with ESP
unmounted. It only copies its files to ESP/MUNCH/GPU26. Then boot the
Windows26 image with fastboot boot. In administrator PowerShell:

    mountvol S: /S
    S:\MUNCH\GPU26\setup.cmd

Choose another unused letter if S: is occupied. Installation requires active
test signing, the existing publisher certificate and SCM/RPEN/SPMI code 0.
Only qcpmic8250.inf is installed. The script prints four services and saves
C:\munch-gpu-pmic/report.json for the existing TWRP log collector.

Additional status: setup.cmd report. Normal removal: setup.cmd rollback,
then boot Windows25. Existing SCM/RPEN/SPMI and signing settings are retained.
Removal requires that this experiment owns the recorded published INF and
that it is not bound to another kind of device. A startup crash can require
offline service removal in recovery; that procedure is not automated.

Code 0 would confirm only core PMIC PnP startup. GPU acceleration and working
power transitions are not established by this test. PEP and the remaining
GPU dependencies still require adaptation.
