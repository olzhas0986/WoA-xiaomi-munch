# Windows 11 ARM64 on POCO F4 (`munch`)

An experimental Mu-Silicium UEFI port that boots Windows 11 ARM64 on the
Xiaomi POCO F4 (Snapdragon 870, tested on the 6 GB model). It provides the
firmware hand-off, ACPI tables, UFS access, USB host mode, fastboot diagnostics,
recovery tools, and the Linux bring-up sources used to determine the hardware
configuration.

This is a source-and-build-tools repository, not a ROM distribution. It contains
no prebuilt UEFI or Windows image, Qualcomm firmware executable, device backup,
crash dump, or private key. Each user must lawfully obtain the supported XBL and
live DTB and build the image locally. Generated images can contain proprietary
modules extracted from that user-supplied XBL and must not be published as this
project's releases. It is not based on Renegade Project; the UEFI base is
Project Silicium / Microsoft Project Mu.

## Current state

Базовые драйверы готовы. Следующий этап — ACPI-контракт и запуск Qualcomm PEP QCOM2519.

SCM (`qcscm`), RPEN (`QCRPEN`), SPMI (`qcspmi`) and core PMIC (`qcpmic`)
have reached Running / Code 0. PEP implementation and validation begin here.

| Area | State | Notes |
|---|---|---|
| UEFI display / GOP | Working | 1080×2400 framebuffer |
| CPU and RAM | Working | 8 CPUs; about 5.34 GiB usable on the tested 6 GB phone |
| Windows 11 ARM64 desktop | Working | Tested with IoT Enterprise LTSC 24H2, build 26100.1742 |
| UFS / Windows partition | Working | Windows installs and boots from internal storage |
| USB host | Partial | Mouse and USB storage tested; keyboard was not revalidated on the final profile |
| Fastboot log/control endpoint | Working fallback | Appears only if automatic Windows boot returns/fails |
| Touch | Not working | Linux driver work is included as reference; no Windows driver |
| GPU acceleration | Not working | Windows uses Microsoft Basic Display Adapter |
| PEP (`QCOM2519`) | Not validated | Next: ACPI contract and initial driver startup |
| Power management | Unstable | Shutdown and power transitions remain unreliable |
| Audio, cameras, modem, Wi-Fi, Bluetooth | Not implemented/tested | Do not assume support |

See [STATUS.md](STATUS.md) for confirmed results and limitations.

## Build in four commands

On a supported Linux host:

```sh
make deps
make inputs XBL=/path/to/xbl.img DTB=/path/to/munch-live.dtb
make stable
make verify
```

The result is `out/munch-fresh/munch-uefi.img`. Dependencies are checked out at
fixed commits and device inputs are accepted only when their SHA-256 hashes
match the tested files. Full host setup and input acquisition are documented in
[BUILDING.md](BUILDING.md).

## Temporary boot: cable timing matters

Use an unlocked bootloader and test without flashing:

```sh
fastboot boot out/munch-fresh/munch-uefi.img
```

As soon as the host-side `fastboot boot` transfer finishes (`OKAY`/`Finished`),
physically disconnect the PC USB cable so the phone has no external USB power.
The firmware automatically boots the installed Windows system and waits up to
about ten seconds for PC power to disappear when it prepares USB host mode.
Do **not** wait for or issue `fastboot oem windows` in the normal path.

After the Windows logo appears, connect the OTG adapter and mouse. Disconnecting
the PC cable is a required device-to-host role transition, not an optional
hot-unplug. Hot-unplugging an OTG device later, after the Windows hand-off, is
still unstable.

If automatic boot fails and the firmware instead exposes its diagnostic
fastboot endpoint, this is the fallback retry command:

```sh
fastboot oem windows
```

After that command returns `OKAY`, unplug the PC immediately and attach OTG
within the displayed ten-second window. Keep Android/recovery bootable and back
up all partitions before changing the partition table. The repository
deliberately does not automate flashing a boot partition.

## Repository map

| Path | Purpose |
|---|---|
| `firmware/munch/` | UEFI BDS, ACPI, USB/UFS, fastboot and framebuffer console sources |
| `platform/munchPkg/` | Small platform overlay used to create `munchFreshPkg` |
| `tools/` | Build, verification, Windows/recovery and hardware-analysis utilities |
| `vendor-templates/` | Metadata-only INF templates used to extract the user's own XBL |
| `ref/linux/` | Reference device trees, kernel patches, drivers and initramfs used during hardware bring-up |
| `docs/` | Architecture, installation, PEP research and provenance |

The normal path is `make stable`; here “stable” means the tested UEFI profile,
not that Windows power management is stable. `make pep` exposes the unfinished
Windows PEP device for driver research and is not a more complete or safer
build.

## Contributing

Keep hardware claims tied to a log, screenshot, dump, or repeatable command.
Never commit or publish generated images, Windows files, extracted XBL modules,
firmware blobs without clear redistribution permission, user partitions, or
crash dumps containing private data. New device firmware revisions must be
audited rather than added by hash alone.

## License and credits

Source files retain their original notices. New UEFI and tooling code is
distributed under the BSD 2-Clause license in [LICENSE](LICENSE). Files carrying
another SPDX identifier remain under that license; see [THIRD_PARTY.md](THIRD_PARTY.md)
and [LICENSES/README.md](LICENSES/README.md). See [CREDITS.md](CREDITS.md) for
upstream projects and device bring-up attribution.
Windows, POCO, Xiaomi, Snapdragon and Qualcomm are trademarks of their
respective owners; this project is unaffiliated with them.
