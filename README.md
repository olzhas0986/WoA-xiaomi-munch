# Windows 11 ARM on POCO F4 (munch)

A UEFI port for the Xiaomi POCO F4 / Redmi K40S (`munch`, Snapdragon 870,
SM8250-AC) on top of [Mu-Silicium](https://github.com/Project-Silicium/Mu-Silicium),
together with the tools used to derive it from the device's own firmware.

## Status

| Stage | Status |
|:--|:--|
| Analysis of `payload.bin`, XBL, DTB | done, reproducible with the tools in `tools/` |
| `Binaries/munch` tree (91 XBL modules, 6 patches) | generated, patches verified byte-for-byte against alioth |
| `munchPkg` package for Mu-Silicium | written, static checks pass |
| `Mu-munch-0.img` build | **not built yet** - run `scripts/build.sh` |
| Boot on the device | **not tested** |
| Windows drivers | no ready-made pack for Xiaomi SM8250, see [docs/drivers.md](docs/drivers.md) |

Nothing from this repository has been flashed to a phone yet. The first run
uses `fastboot boot` and writes nothing to storage.

## Why Mu-Silicium and not a prebuilt image

In short (details in [docs/method.md](docs/method.md)):

- Mu-Silicium actively supports **alioth** (POCO F3), which is effectively the
  same board: same SoC, same memory layout, same FT3658U touch on the same
  lines, same XBL family (`BOOT.XF.3.2`). For alioth it reports Windows boot,
  UFS, touch, USB, battery and Bluetooth.
- All 91 modules Mu-Silicium takes from the alioth XBL are present in the
  munch XBL under the same GUIDs; five of the six binary patches apply at the
  same offsets.
- The only prebuilt image for munch
  ([edk2-msm-munch](https://github.com/0xSelenicDove/edk2-msm-munch)) is a
  recent single-author fork whose memory map was changed several times to
  work around BSODs, with the FD moved to a non-standard address. It is a
  useful fallback for comparison, not a base.

## Quick start

Requirements: `git`, `python3`, `mono`, `dtc`, `clang`, `lld`, `llvm`,
`iasl`, `nasm`, `make`, about 6 GB of disk space. `xbl.img` (or
`payload.bin`) and `munch-live.dtb` must be in the repository root.

```sh
scripts/build.sh                 # result: out/Mu-munch-0.img
fastboot boot out/Mu-munch-0.img # trial run, storage is untouched
```

Next: [docs/install.md](docs/install.md).

## Layout

```
tools/payload_extract.py   extract partitions from an OTA payload.bin
tools/xbl_fv_extract.py    extract UEFI firmware volumes from xbl.img
tools/make_binaries.py     XBL -> Binaries/munch + patches + RAW.inc
tools/prepare_dtb.py       live DTB -> DTB for the boot image
tools/check_memmap.py      check the memory map against the XBL and DTB
tools/check_port.py        static consistency check of the port
port/munchPkg/             platform package for Mu-Silicium
port/patches.toml          binary patches for XBL drivers
port/binaries-map.tsv      GUID -> Binaries layout mapping
port/Resources/            boot image configuration
scripts/build.sh           end-to-end build
dts/munch.dts              device tree (reference)
docs/                      method, hardware, install, drivers, firmware analysis
firmware/SHA256SUMS        checksums of the input files
```

The input binaries (`*.iso`, `payload.bin`, `xbl.img`, `*.dtb`) are not kept
in git: they are proprietary and large. Their checksums are in
`firmware/SHA256SUMS`.

## Licenses

`port/munchPkg` is derived from `aliothPkg` in Mu-Silicium
(BSD-2-Clause-Patent). `dts/munch.dts` is a decompiled Linux device tree
(GPL-2.0). The tools in `tools/` and `scripts/` were written for this
repository.
