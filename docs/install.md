# Installation

Steps are ordered so that irreversible actions come as late as possible.
Steps 1-2 write nothing to the phone.

> The bootloader must be unlocked. Partitioning (step 3) destroys Android
> data. None of this has been tested on a real munch yet - see "Status" in the
> [README](../README.md).

## 1. Build

```sh
scripts/build.sh
```

The script checks the memory map and that the patches apply to your
`xbl.img`. With a different XBL build it stops at the first byte mismatch -
that is intended behaviour, not a failure.

### Build dependencies

Besides the compilers, edk2 needs **mono**: stuart runs NuGet through it to
fetch `mu_nasm` and the BaseTools binaries. Without it the environment step
fails with "Mono is required to run NuGet on non-Windows platforms".

```sh
# Arch / CachyOS
sudo pacman -S --needed mono clang lld llvm dtc acpica nasm
# Debian / Ubuntu
sudo apt install mono-devel ca-certificates-mono clang lld llvm device-tree-compiler acpica-tools nasm
```

`scripts/build.sh` checks for these tools up front and runs stuart
setup/update on every invocation, so a run that failed half-way recovers
after the missing package is installed.

Individual checks:

```sh
tools/xbl_fv_extract.py xbl.img -o out/xbl-fv
tools/make_binaries.py out/xbl-fv -o out/Binaries/munch
tools/check_memmap.py --cfg out/xbl-fv/uefiplat.cfg/uefiplat.cfg.raw --dtb munch-live.dtb
tools/check_port.py --binaries out/Binaries/munch
```

## 2. Trial boot without flashing

```sh
adb reboot bootloader
fastboot boot out/Mu-munch-0.img
```

The image is loaded into RAM, partitions are untouched; a reboot returns to
Android.

Success means: the Mu-Silicium logo and menu, volume keys move the selection,
power selects (that is the `ButtonsDxe` patch), UFS is listed in the menu.

If it fails:

| Symptom | Likely cause | What to try |
|:--|:--|:--|
| `fastboot boot` rejects the image | ABL does not accept v1 with an appended DTB | build with the base DTBs from `vendor_boot`: `scripts/build.sh --raw-dtb out/vboot/dtb` |
| Black screen, phone alive | UEFI started, framebuffer lost | check the `FeatureEnablerDxe` patch; build with `--debug` |
| Instant reboot | crash in SEC/early DXE | compare with the edk2-msm-munch image, build with `--debug` |
| Reboot after a few seconds | watchdog or driver crash | `--debug`, read the last line on screen |

Base DTBs for the fallback:

```sh
tools/payload_extract.py payload.bin -o out/crdroid -p vendor_boot
unpack_bootimg --boot_img out/crdroid/vendor_boot.img --out out/vboot
```

Only continue after a successful trial boot.

## 3. Windows payload on the PC

Needs `wimlib`, `hivex` and `7z` (Arch: `sudo pacman -S --needed wimlib hivex 7zip`).

```sh
tools/prepare_image.sh en-us_windows_11_iot_enterprise_ltsc_2024_arm64_dvd_ec517836.iso
scripts/build_recovery_tools.sh
```

`prepare_image.sh` keeps only the IoT Enterprise LTSC edition, adds
`port/windows/unattend.xml` (local administrator `user` without a password,
automatic logon - there is no touch or USB to get through OOBE otherwise) and
writes a solid `out/win/install.esd` of about 3 GB, plus the boot manager files
and `BCD-Template` taken from the same image.

Device drivers cannot be injected offline from Linux (that needs `dism`); see
[drivers.md](drivers.md) for what exists and how to add it.

## 4. Installer zip

The installer replaces one spare partition on `sda` - for example the one
previously used for Arch - with three: ESP (FAT32, 512 MiB), MSR (16 MiB) and
Windows (NTFS, the rest). Nothing else on the disk is touched.

1. Boot the phone into recovery and dump the start of the disk (read-only):

   ```sh
   adb exec-out "dd if=/dev/block/sda bs=4096 count=6 2>/dev/null" > out/sda-gpt.bin
   tools/gpt_read.py out/sda-gpt.bin
   ```

2. Build the zip for the spare partition (by name or number):

   ```sh
   tools/make_installer.py --gpt out/sda-gpt.bin --target <name>
   cat out/installer/layout.txt
   ```

   It refuses partitions with stock Android names or vendor type GUIDs and
   anything outside 20-128 GiB. Partition GUIDs are generated here and written
   into both the BCD and the zip, which is why the BCD can be made on Linux.

3. Copy the image and run the dry run first:

   ```sh
   adb push out/win/install.esd /sdcard/
   adb push out/installer/win-install-munch-dryrun.zip /sdcard/
   ```

   Flash `win-install-munch-dryrun.zip` from recovery. It checks the tools,
   the disk GUID, the target partition (number, name, GUID, start, size), that
   nothing is mounted on it and that `install.esd` is complete - and writes
   nothing.

4. Flash `win-install-munch.zip`. It backs up the partition table to
   `/sdcard/win-install/`, repartitions, formats, applies the image (20-40
   minutes) and copies the boot manager and BCD to the ESP. If it stops after
   repartitioning, reboot recovery and flash it again: it detects the new
   layout and continues.

`/sdcard` must be readable in recovery, i.e. `/data` must be decrypted.

Then boot UEFI again:

```sh
fastboot boot out/Mu-munch-0.img
```

Mu-Silicium finds `\EFI\Boot\bootaa64.efi` on the ESP and starts the Windows
boot manager. The first boot runs the specialize pass and reboots once.

### Alternative: from a Windows PC

With UEFI booted, choose Mass Storage in its menu; the whole UFS shows up on
the PC (the `UsbMsdDxe` patch makes it a fixed disk). Create the partitions in
`diskpart`, then:

```bat
dism /Apply-Image /ImageFile:D:\sources\install.wim /Index:<N> /ApplyDir:W:\
bcdboot W:\Windows /s S: /f UEFI
bcdedit /store S:\EFI\Microsoft\Boot\BCD /set {default} testsigning on
bcdedit /store S:\EFI\Microsoft\Boot\BCD /set {default} nointegritychecks on
```

## 5. Persistent boot

The device is A/B and has no `recovery` partition. Options:

- **Tethered boot** - `fastboot boot out/Mu-munch-0.img` every time. Android
  is not affected at all. Recommended while the port is unproven.
- **Flash `boot` of the inactive slot** and switch with `fastboot set_active`.
  Works only if the inactive slot holds a complete firmware (true after an
  OTA). An Android update will overwrite that slot.

Before flashing, save the current `boot` of both slots:

```sh
adb shell su -c 'dd if=/dev/block/by-name/boot_a of=/sdcard/boot_a.img'
adb shell su -c 'dd if=/dev/block/by-name/boot_b of=/sdcard/boot_b.img'
adb pull /sdcard/boot_a.img && adb pull /sdcard/boot_b.img
```

## Rollback

- After steps 1-3 there is nothing to roll back.
- After the installer zip: the original table is in
  `/sdcard/win-install/sda-before.sfdisk`; restore it from recovery with
  `sfdisk /dev/block/sda < sda-before.sfdisk` (the static `sfdisk` is inside
  the zip under `bin/`).
- After flashing `boot`: flash the saved image back via fastboot.
