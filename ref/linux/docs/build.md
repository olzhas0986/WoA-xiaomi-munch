# Building pmos-munch

## Host prerequisites

Use GNU make, Python 3.12 or newer, Git, an AArch64 GCC/binutils cross toolchain,
a host C compiler, flex, bison, bc, OpenSSL development headers, dtc (including
`fdtget` and `fdtput`), and Android `mkbootimg` with header v3 support.

Defaults:

```text
KERNEL_REPO=$HOME/linux
BUSYBOX_TAR=../busybox-1.37.0.tar.bz2
OUT=./out
JOBS=8
```

The kernel checkout must contain commit
`58161ead29e50d70a317ea26b472e0c7508e69da`. `tools/sources.py` exports tracked
sources and verifies the BusyBox 1.37.0 tarball. It rejects a source directory
with a different revision or patch set. Do not edit generated source trees.

The kernel and BusyBox use explicit Kconfig fragments. Configuration fails when
Kconfig silently drops a requested option. All outputs live under `out/`.
The packer records hashes and validates destination bounds and reserved memory.

## First build

The historical bring-up targets seed isolated build caches from preceding
stages. From a clean `out/`, build them in order:

```sh
make usb-preflight
make usb-ipcc
make usb-clocks
make usb-gcc
make usb-cacheinfo-trace
make usb-pdc
make usb-icc
make usb-smmu
make usb-rails
make usb-phy
make usb-udc
make usb-acm
make usb-host-ready
make usb-otg-keyboard
make pmos-preflight
make pmos-usb
make pmos-wifi
```

Before building graphics targets, stage the user-supplied, device-specific GPU
ZAP firmware as documented in [pmos-gpu.md](pmos-gpu.md). Then:

```sh
make pmos-gpu
make pmos-display
make pmos-touch
PMOS_MUNCH_OUT=out/pmos-touch python3 -m unittest discover -s tests -v
```

Existing build caches can be reused only with matching source/patch markers.
Metadata changes to a patch still change its hash; use a fresh output tree or a
reviewed cache migration rather than bypassing the source check.

## Userspace and tools

See [pmos-ram.md](pmos-ram.md) and [pmos-phosh.md](pmos-phosh.md) for rootfs
preparation and desktop packages. To package the current small phone helpers:

```sh
python3 tools/build-phosh-tools.py
```

This produces `out/phosh-tools.tar.gz` and its SHA256 file. The generic host
rootfs does not automatically contain packages installed only on the phone.

## Device testing

```sh
fastboot boot out/pmos-touch/munch-boot.img
```

The target is an unlocked Xiaomi POCO F4 (munch). Build targets do not execute
phone commands or write Android partitions. Preserve a working image when
trying a new profile. The [native init image](pmos-native.md) is experimental
and requires an existing touch build and a suitably prepared saved rootfs.
