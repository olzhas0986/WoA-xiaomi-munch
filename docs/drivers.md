# Windows drivers

This is the weakest part of the whole effort, and it does not depend on the
quality of the UEFI.

## What is known

- Mu-Silicium lists the hardware that works in Windows on alioth (UFS, touch,
  USB, battery, Bluetooth, speakers, accelerometer, compass, gyroscope), but
  unlike other devices it **does not link a driver pack** - the alioth entry
  in `Status.md` has no "Needs Windows Drivers" line.
- No public driver pack for Xiaomi SM8250 could be found.
  `Project-Silicium/Windows-Drivers` and `Project-Aloha/woa-drivers` do not
  exist; SM8150 and SM8350 have such packs, SM8250 does not.
- [zhishixuebao-0791/K40_Win11](https://github.com/zhishixuebao-0791/K40_Win11)
  has an `Alioth-Engineering` directory that calls itself a scaffold, "not a
  ready-to-flash driver pack".
- [alioth-woa-drivers](https://github.com/18934020489Xx/alioth-woa-drivers)
  provides an experimental stub PEP and a CPU frequency driver. According to
  its author, the stock `qcpep8250`/`qcpep8280` crash on SM8250 with
  BugCheck 0x101, and without a PEP the CPU stays around 1.5 GHz. Not tested.
- The edk2-msm-munch README claims working GPU, Wi-Fi and audio but names no
  driver pack.

## Findings on the installed system

Windows 11 IoT Enterprise LTSC 2024 boots to the desktop with no extra
drivers. Its SYSTEM hive (read with `tools/win_logs.sh`,
`tools/hive_recover.py`, `tools/hive_devices.py`) shows 47 ACPI devices
enumerated; only the CPUs (`FxPPM`), UFS (`storufs`) and the button device
(`hidinterrupt`) have drivers. 63 devices are not enumerated at all: almost
all of them depend through `_DEP` on `PEP0`, which itself waits for `IPCC`.
That includes every I2C/SPI bus (touch is on `SPI5`), USB (`URS0`), Type-C
(`UCP0`), audio, modem and subsystems. Registry tweaks such as
`OsDefaultRoleSwitchMode` cannot help while `URS0` does not exist.

The hardware IDs do not match the public SM8250 BSP. The alioth DSDT from
Silicium-ACPI (`QCOMM SDM8250` rev 3) and
[WOA-Project/windows_silicon_qcom_kona](https://github.com/WOA-Project/windows_silicon_qcom_kona)
use different `QCOM25xx` numbering:

| Device | alioth DSDT | Kona BSP INF |
|:--|:--|:--|
| GPIO | `QCOM250C` | `QCOM250D` |
| SPMI | `QCOM250B` | `QCOM250C` |
| I2C | `QCOM2510` | `QCOM2511` |
| SPI | `QCOM250E` | `QCOM250F` (`QCOM250E` is the IPC router) |
| PEP | `QCOM2517` | `QCOM2519` (`QCOM2517` is RemoteFS) |

Installing that BSP on these tables would bind drivers to the wrong devices.
The SM8150 BSP (Hana, `QCOM05xx`) follows the Kona numbering, so the alioth
DSDT comes from a third, older Qualcomm package. The DSDT shipped with
edk2-msm-munch only describes the CPUs and UFS.

## What to expect without a driver pack

Windows gets as far as the inbox drivers allow: kernel, ACPI, storage (if the
inbox `storufs` accepts the `UFS0` device from the alioth DSDT - storage is
reported working on alioth). There will be no touch and no USB, so there is
nothing to complete the out-of-box setup with. Installing only makes
practical sense together with drivers.

## What to do

1. First get UEFI and the Windows kernel to boot (steps 1-4 of
   [install.md](install.md)). This validates the port independently of
   drivers.
2. Ask the alioth maintainers in Mu-Silicium (N1kroks, SwedMlite,
   Robotix22) which driver set their status is based on. This is the shortest
   path: an alioth set fits munch almost entirely.
3. For touch, account for the different coordinate range (10800x24000 instead
   of 8640x19200); for speakers, the different amplifier; see
   [hardware.md](hardware.md).

Adding drivers to the applied image (Windows, as administrator):

```bat
dism /Image:W:\ /Add-Driver /Driver:<directory with .inf> /Recurse /ForceUnsigned
```

## What will definitely not work

Based on the alioth status and the platform: modem and calls, cameras, Wi-Fi,
GPU acceleration, fingerprint, NFC, fast charging. The display will work via
the UEFI framebuffer without acceleration.
