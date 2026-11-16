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

## 3. Partitioning

Before partitioning, back up the partitions that cannot be restored from
firmware: `persist`, `modemst1`, `modemst2`, `fsg`, `fsc`.

Windows needs two partitions at the end of `sda`: ESP (FAT32, 512 MB) and the
main one (NTFS, 64 GB or more). The space is taken from `userdata`, which is
the last partition on the disk.

From recovery with `parted` (take numbers and boundaries from `print`, they
depend on the storage size):

```
parted /dev/block/sda
(parted) print
(parted) rm <userdata number>
(parted) mkpart userdata ext4 <userdata start> <new end>
(parted) mkpart esp fat32 <new end> <new end + 512MB>
(parted) mkpart win ntfs <new end + 512MB> 100%
(parted) set <esp number> esp on
(parted) quit
```

After rebooting into recovery, format `userdata` with recovery (Format Data)
and `esp` as FAT32. NTFS is created by the Windows tooling in the next step.

Do not touch anything except `userdata` and the two new partitions: the other
`sda` partitions and all other LUNs (`sdb`...`sdf`) hold the bootloader and
calibration data.

## 4. Deploying Windows

Boot UEFI (`fastboot boot`), choose Mass Storage in the menu and connect the
phone to a PC: UFS shows up as a regular disk (thanks to the `UsbMsdDxe`
patch).

On a Windows PC (or a VM with USB passthrough), as administrator. Assign
letters in `diskpart` (`select volume` / `assign`; for the NTFS partition run
`format quick fs=ntfs` first):

```bat
dism /Get-ImageInfo /ImageFile:D:\sources\install.wim
dism /Apply-Image /ImageFile:D:\sources\install.wim /Index:<N> /ApplyDir:W:\
bcdboot W:\Windows /s S: /f UEFI
bcdedit /store S:\EFI\Microsoft\Boot\BCD /set {default} testsigning on
bcdedit /store S:\EFI\Microsoft\Boot\BCD /set {default} nointegritychecks on
bcdedit /store S:\EFI\Microsoft\Boot\BCD /set {default} recoveryenabled no
```

`D:` is the mounted ISO, `W:` the `win` partition, `S:` the `esp`.
`testsigning` is needed for device drivers not signed by Microsoft.

The image can be applied from Linux alone (`wimlib-imagex apply`), but the BCD
store is properly created only by `bcdboot`, so this step is easier on
Windows.

Drivers are added to the applied image before the first boot - see
[drivers.md](drivers.md).

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

- After steps 1-2 there is nothing to roll back.
- After partitioning: delete `esp` and `win`, restore `userdata` to its
  original size, format it.
- After flashing `boot`: flash the saved image back via fastboot.
