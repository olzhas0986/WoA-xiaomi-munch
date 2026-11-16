# Firmware analysis

Everything below can be reproduced with the commands in this repository.

## payload.bin (crDroid)

```sh
tools/payload_extract.py payload.bin --list
tools/payload_extract.py payload.bin -o out/crdroid -p abl,xbl,xbl_config,boot,vendor_boot,dtbo
```

27 partitions, a full (non-delta) OTA. Relevant for the port:

| Partition | What it provides |
|:--|:--|
| `xbl` | UEFI volume with DXE drivers and `uefiplat.cfg` |
| `boot` | header v3, 47 MB kernel |
| `vendor_boot` | header v3, three base DTBs (kona v1 / v2 / v2.1) |
| `dtbo` | 12 overlays for the Xiaomi SM8250 family; munch is `board-id 0x32` |

The `xbl.img` dumped from the device is byte-identical to `xbl` from crDroid
over the whole length of the OTA image (3,563,520 bytes); the rest of the dump
is the partition tail.

## XBL

```sh
tools/xbl_fv_extract.py xbl.img -o out/xbl-fv
```

- Version: `BOOT.XF.3.2-00354-SM8250-1`, variant `Soc8250LAE`.
- The UEFI volume lives in an ELF segment at `0x9FC00000` (size `0x270000`).
- The main DXE volume is gzip-compressed under GUID
  `1D301FE9-BE79-4353-91C2-D23BC959AE0C` (not the standard LZMA); the
  extractor handles this.
- 151 files: SEC, DXE core, 88 drivers, `QcomChargerApp`, 40 panel
  descriptions, charger configs and battery profiles.

The XBL is shared across the Xiaomi SM8250 family: it carries panel
descriptions for both K11A (alioth) and L11R (munch). The panel is selected
from data passed by the bootloader.

### uefiplat.cfg vs alioth

| Parameter | alioth | munch |
|:--|:--|:--|
| TZApps Reserved | 0x82400000 + 0x09600000 | 0x82400000 + 0x03A00000 |
| PIL Reserved | 0x8BC00000 + 0x12E00000 | 0x86000000 + 0x0D200000 |
| MCCC_MCCC_MSTR | absent | 0x090BA000 + 0x6000 |
| SecPagePoolCount | 0x800 | 0x980 |

Everything else is identical. The alioth map in Mu-Silicium follows the Linux
layout rather than the alioth `uefiplat.cfg`, and that layout is exactly what
reserved-memory in the munch DTB describes (PIL 0x86200000...0x92700000, TZ up
to 0x85E00000). In `munchPkg` the PIL region follows the munch `uefiplat.cfg`:
it is wider and covers both variants.

Check:

```sh
tools/check_memmap.py --cfg out/xbl-fv/uefiplat.cfg/uefiplat.cfg.raw --dtb munch-live.dtb
```

## Driver patches

Mu-Silicium keeps both stock and patched drivers for alioth, so every patch
shows up as a diff of two files. For each patch it was verified that the
munch driver has the same original bytes in that place.

| Driver | Offset | Before -> after | Purpose |
|:--|:--|:--|:--|
| ButtonsDxe | 0x36DC | `mov w17,#0x102; strh [sp,#0x18]` -> `mov w17,#0xd; strh [sp,#0x1a]` | power = ENTER in menus |
| UsbConfigDxe | 0x5684, 0x56E0 | `cbz w10` -> `b` | keep USB alive on ExitBootServices |
| TzDxe | 0xD469 | `00` -> `01` | do not load TZ apps twice |
| FeatureEnablerDxe | 0x1790 | prologue -> `mov x0,#0; ret` | leave display clocks alone |
| UsbMsdDxe | 0x3A98 | `orr w12,wzr,#0x80` -> `mov w12,#0` | non-removable disk in Mass Storage |
| DALSys | `$\_SB_.UFS0` - 8 | `00` -> `01` | CacheCoherency for UFS |

Five offsets match alioth. The table in DALSys is shifted by 0xA0 (0x2C6F4 on
alioth, 0x2C654 on munch), so that patch is located by signature.

The code of `ButtonsDxe` and `UsbConfigDxe` changed between builds 00304 and
00354, but the patched spots did not; `TzDxe` code is identical up to data
addresses.

## DTB

`munch-live.dtb` is a `/sys/firmware/fdt` snapshot: the kona v2.1 base DTB
with the munch overlay already applied and `/memory` and `/chosen` filled in
by ABL.

- `model = "Qualcomm Technologies, Inc. xiaomi munch"`, `board-id = <0x32 0>`.
- Memory: `0x80000000 + 0x3CC00000` and `0xC0000000 + 0x140000000` - 6 GB.
- `bootargs` contained the serial number and cpuid; `tools/prepare_dtb.py`
  strips them.
- Panel: `mdss_dsi_l11r_38_08_0a_dsc_cmd`, 1080x2400.

Mu-Silicium does not use the DTB inside UEFI (memory size comes from the XBL
RAM partition table); it is only needed so that ABL agrees to start the image.
