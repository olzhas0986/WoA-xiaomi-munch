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
