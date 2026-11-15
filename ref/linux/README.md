# pmos-munch

Bringing postmarketOS to the **Xiaomi POCO F4 (munch)**, one working driver at a time.

A custom EL1 loader, mainline-derived Linux, a RAM rootfs and a touch-driven
Phosh desktop. Development boots use `fastboot boot`; Android partitions stay
untouched.

## What works

| Component | Device results |
| --- | --- |
| CPU and RAM | All eight CPUs online, about 5.4 GiB usable RAM |
| USB | ACM console, OTG input, USB storage and NTFS rootfs loading |
| Wi-Fi | QCA6390, association, DHCP and internet access |
| GPU | Adreno 650 / Freedreno hardware rendering |
| Display | Native 1080×2400 DSI panel at 60 Hz |
| Touch | FT3658U, calibrated input and two-finger tracking |
| Desktop | Native Phosh and Squeekboard with OpenRC |
| Native Wi-Fi | Modular ath11k; Phosh connection and internet verified on two boots |

Battery reporting, charging policy, audio, cameras, suspend and GPU thermal
management still need work. This is a development port, not a daily-driver image.

## Try the working desktop

With the existing build environment and saved rootfs:

```sh
make pmos-native-modular
fastboot boot out/pmos-native-modular/munch-boot.img
```

Connect the OTG stick when prompted. The loader verifies the saved archive,
extracts it into RAM and starts native Phosh. Connect Wi-Fi through the shade.
See [modular Wi-Fi](docs/wifi-modular.md) for build prerequisites.

The separate [120 Hz and battery test](docs/120hz-battery.md) adds stock panel
timings and BQ27Z561 telemetry; hardware verification is pending.

Installed packages live in RAM. Save them with `pmos-save-current`, passing the
current USB partition if needed, and wait for **PMOS SAVED** before unplugging.

## Build and explore

- Arch Linux ARM in RAM — separate console boot experiment; its notes are not
  included in this source snapshot.
- [Build setup](docs/build.md) — dependencies, pinned sources and build stages.
- [Project history](docs/history.md) — milestones and the current direction.
- [Phosh](docs/pmos-phosh.md) — desktop, keyboard, networking and persistence.
- [Native init experiment](docs/pmos-native.md) — separate OpenRC test image.
- [Display](docs/pmos-display.md), [GPU](docs/pmos-gpu.md),
  [touch](docs/pmos-touch.md), [Wi-Fi](docs/pmos-wifi.md) — hardware details.
- [Boot contract](docs/boot-contract.md) — loader ABI, memory layout and checks.

Builds, firmware inputs and rootfs archives are kept outside version control.
Keep a known-working boot image and rootfs backup when testing a new stage.
