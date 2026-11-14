# Windows23: SCM foundation for the Kona GPU port

This is a device test, not a working GPU port. The firmware adds only SCM0
(ACPI QCOM250B) to the Windows22 CPU/USB/UFS namespace. No GPU, PEP or SMMU
nodes are exposed. Existing Windows USB handoff remains in place.

Source BSP: WOA-Project/windows_silicon_qcom_kona,
commit 22221a09e02cb7054792427af60299b1c34d3c3e.
The package includes only unchanged qcscm8250 INF/CAT/SYS, the original
license and the public catalog certificate. No private signing key is used.
SCM version: 1.0.2100.0000, ARM64. The catalog uses the WOA KMCI certificate.

The eventual graphics driver is qcdxkm8250.sys (27.20.2140.0000), matching
QCOM253A. The available alioth DSDT uses an older QCOM2536 GPU node, older
IDs for several dependencies, panel-specific methods, and firmware placeholders.
Its GPU dependencies include MMU0/MMU1, IMM0/IMM1, PEP0, PMIC, PILC, RPEN,
TREE and SCM0. Copying this DSDT or installing the entire BSP is not a tested
munch port. Further ACPI, firmware and power work is required after SCM testing.

## Device procedure

1. Build with MUNCH_GPU_FOUNDATION=1 MUNCH_USB_ACPI=1 MUNCH_UFS_ACPI=1
   using tools/build-munch.sh; pack with tools/pack-munch.py. The final image
   was verified with tools/verify-munch.py --gpu-foundation --winpe
   --usb-acpi --ufs-acpi --no-preboot-kbd.
2. Generate the ZIP using python3 tools/prepare-kona-gpu-bootstrap.py.
3. Install out/kona-gpu/munch-gpu-scm-bootstrap-twrp.zip in TWRP with ESP
   unmounted. It verifies the device, geometry, GPT and package hashes, then
   copies only its files into ESP/MUNCH/GPU23. It does not install a driver
   or replace EFI/BCD files. A differing existing GPU23 folder stops installation.
4. Boot out/munch-fresh/munch-uefi-windows23-scm.img with fastboot boot.
5. In administrator CMD, run:

       mountvol S: /S
       S:\MUNCH\GPU23\setup.cmd configure

   Choose another unused drive letter if S: is already occupied. Configure
   saves a BCD backup and previous certificate/testsigning state under
   C:\munch-gpu, imports the included public certificate into machine Root
   and TrustedPublisher, and enables test signing. This changes Windows
   signing policy and takes effect at the next boot. It does not install SCM.
6. Boot the same Windows23 image again. Run the following in administrator CMD:

       mountvol S: /S
       S:\MUNCH\GPU23\setup.cmd install

   This requires active test signing and exactly one SCM ACPI device. It
   installs only qcscm8250.inf. Hardware status is recorded in
   C:\munch-gpu\report.json. Code 0 would establish only SCM readiness,
   not GPU readiness. No automatic reboot or shutdown is requested.
7. Additional status: setup.cmd report. Normal rollback: setup.cmd rollback,
   followed by booting the previous Windows22 image. Rollback removes only
   the recorded SCM OEM INF and certificates added by configure, and restores
   the previous effective test signing setting. A driver that crashes during
   startup may require recovery/offline service removal; that is not automated.
8. The existing read-only tools/collect-windows-setup-logs.py also retrieves
   C:\munch-gpu reports while in TWRP.

Host validation covers compilation, packaged ACPI checksums/namespace, unchanged
vendor firmware modules, driver architecture, unchanged BSP files and ZIP
integrity. Windows scripts and SCM behavior still require testing on the phone.
