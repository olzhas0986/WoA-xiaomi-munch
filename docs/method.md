# Choice of method

Windows on ARM needs UEFI with ACPI. On Snapdragon phones the stock boot
chain (XBL -> ABL) can only boot an Android image, so the general approach is
always the same: UEFI is packed as the "kernel" of a `boot.img`, ABL starts
it, and UEFI then loads `bootmgfw.efi`. The options differ in which UEFI is
used.

## Options

### 1. Mu-Silicium + own `munchPkg` - chosen

[Mu-Silicium](https://github.com/Project-Silicium/Mu-Silicium) (Project Mu)
is a maintained project with a shared code base for dozens of Snapdragon
devices. munch is not in it, but **alioth** (POCO F3 / Redmi K40) is, with
status Active.

How close alioth is to munch, checked against the files in this repository:

| What | alioth | munch | Source |
|:--|:--|:--|:--|
| SoC | SM8250-AC | SM8250-AC | `qcom,msm-id = <0x164 0x20001>` |
| XBL branch | BOOT.XF.3.2-00304 | BOOT.XF.3.2-00354 | strings in `xbl.img` |
| XBL modules the port needs | 91 | the same 91 GUIDs | `tools/make_binaries.py` |
| Register map | 22 regions | the same + `MCCC_MCCC_MSTR` | `uefiplat.cfg` |
| Linux reserved-memory | - | matches the alioth map in Mu-Silicium | DTB |
| Touch | FT3658U, SPI se4, IRQ GPIO 39, RST GPIO 33 | same | DTB |
| Framebuffer | 0x9C000000, 1080x2400 | same | DTB, `uefiplat.cfg` |
| UEFI FD | 0x9FC00000 / 0x300000 | same | `uefiplat.cfg` |

What Mu-Silicium's `Status.md` reports for alioth: in UEFI - display, UFS,
buttons, USB device, Mass Storage, Windows and Linux boot; in Windows - UFS,
touch, USB, battery, Bluetooth, speakers, some sensors; not working - Wi-Fi,
GPU, camera, modem, microphone. That is the status of another device, not a
measurement on munch.

Pros: maintained code base, the munch XBL's own drivers, memory map and
patches derived from the firmware rather than guessed.
Cons: has to be built locally; ACPI comes from alioth for now.

### 2. Prebuilt edk2-msm-munch image - fallback

[0xSelenicDove/edk2-msm-munch](https://github.com/0xSelenicDove/edk2-msm-munch)
is a fork of edk2-msm (Renegade Project) with munch support and prebuilt
releases.

Why it is not the base:

- 4 stars, a single author, releases built by CI in August 2026;
- the history has a run of commits like "safe universal RAM Partition size
  0x130000000 to eliminate MEMORY_MANAGEMENT BSOD", "restore 12GB memory map",
  "match UEFI memory descriptors to device tree" - the memory map was tuned
  by trial;
- the FD is moved to `0xCE000000` with 7 MB instead of the stock XBL region;
- `PmicDxe` is commented out, the watchdog is disabled;
- the README's "everything works, including GPU and Wi-Fi" table is not
  backed by anything, contradicts the alioth status in Mu-Silicium, and links
  no driver pack;
- installation is a zip run from Magisk/recovery that writes partitions itself.

Useful for comparison: if `Mu-munch` does not start but this image does, the
difference between the memory maps points to the cause.

### 3. Mu-Silicium alioth image as is - does not work

The alioth image cannot simply be booted on munch: ABL picks the DTB by
`board-id` (0x2c on alioth, 0x32 on munch), and the alioth XBL drivers are a
different build with their own tables (L11R panel, charging, PMIC settings).

### 4. Virtualisation (KVM/QEMU from Android) - does not work

The Qualcomm hypervisor on SM8250 does not hand EL2 to the Android kernel,
so KVM is unavailable; emulation without KVM is unusable for Windows.

## What was done for munch

1. DXE drivers and `uefiplat.cfg` were extracted from `xbl.img`
   (`tools/xbl_fv_extract.py`).
2. The drivers were laid out in Mu-Silicium format and patched
   (`tools/make_binaries.py`, `port/patches.toml`).
3. `munchPkg` was derived from `aliothPkg` with munch-specific changes
   (see the commit history and [analysis.md](analysis.md)).
4. The boot image DTB is made from a `/sys/firmware/fdt` snapshot, as is
   customary in Mu-Silicium (`tools/prepare_dtb.py`).

## Unknown until the first boot

- Whether the munch ABL accepts a v1 image with an appended DTB (alioth's
  does; the ABL is of the same family but newer).
- Whether the patches behave as on alioth: bytes and offsets match, but the
  behaviour has not been tested on hardware.
- How well the alioth ACPI fits munch beyond touch and UFS (the speaker
  amplifier and charging are definitely different, see
  [hardware.md](hardware.md)).
