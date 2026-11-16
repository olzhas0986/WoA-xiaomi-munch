# munch hardware and differences from alioth

Source: `dts/munch.dts` (live DTB, E404 kernel on crDroid) and the alioth DTB
from Mu-Silicium.

## Summary

| Block | munch | Same as alioth |
|:--|:--|:--:|
| SoC | SM8250-AC (kona v2.1) | yes |
| RAM | 6 GB on this unit (8 and 12 GB variants exist) | - |
| Storage | UFS, `1d84000.ufshc` | yes |
| Panel | L11R 38 08 0a, AMOLED, DSC, command mode, 1080x2400 | no (K11A) |
| Touch | FocalTech FT3658U, SPI `990000` (se4), IRQ GPIO 39, RST GPIO 33 | yes |
| Touch coordinate range | 10800 x 24000 | no (8640 x 19200) |
| Wi-Fi / BT | QCA6390 | yes |
| Codec | WCD938x + WSA881x | yes |
| Speaker amplifier | NXP TFA98xx | no (Cirrus CS35L41) |
| Charging | SMB5 + two BQ2597x (master/slave), 67 W | no (single BQ2597x) |
| Fuel gauge | fg-gen4 + BQ27Z561 | partly (alioth has no BQ27Z561) |
| Haptics | AW8697 | yes |
| Fingerprint | Goodix / FPC1020 | yes |
| IR | `ir-spi-led` | yes |
| NFC | NQ-NCI | yes |
| USB | DWC3 `a600000`, QMP DP combo | yes |

## What this means for UEFI

Nothing beyond what is already done: UEFI uses the framebuffer left by the
XBL (`0x9C000000`), UFS, buttons and USB, all of which match. The panel is not
re-initialised in UEFI (`USE_CUSTOM_DISPLAY_DRIVER = 0`).

## What this means for ACPI and Windows

`munchPkg` pulls in the alioth tables
(`Silicium-ACPI/Platforms/Xiaomi/alioth`). Shared hardware is described
correctly. Differences:

- **Touch.** The `TSC1` device (`FTTS3658`) is described correctly, but a
  driver tuned for 8640x19200 will report touches about 25 % off on munch.
  This is fixed in the driver or its parameters, not in ACPI.
- **Speakers.** The alioth DSDT has two `CS35L41` devices; munch has a
  TFA98xx. Speaker audio will not work with the alioth tables; `SPK0/SPK1`
  should be disabled once there is a munch DSDT.
- **Charging.** Fast charging is controlled by two BQ2597x that the alioth
  ACPI does not describe. Basic SMB5 charging does not depend on them.
- **Panel.** The panel name in ACPI matters only to the GPU driver, which
  does not exist for Xiaomi SM8250 anyway.

A munch DSDT is the next step once the image boots: the decompiled alioth
`DSDT.dsl` is in Silicium-ACPI; the nodes to change are `SPK0`, `SPK1` and the
battery parameters.
