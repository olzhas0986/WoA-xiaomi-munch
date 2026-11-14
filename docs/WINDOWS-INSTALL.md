# Windows deployment notes

The successful test used Windows 11 ARM64 IoT Enterprise LTSC 24H2 on a
dedicated 32 GiB partition carved from userdata, plus a 512 MiB FAT32 ESP.
Changing a phone partition table can erase all data or make every boot mode
unavailable. Export the original GPT and back up userdata before proceeding.

This repository contains the tools used during bring-up:

- `tools/repartition32.py` prepares the tested layout;
- `tools/prepare-winpe.py` and `tools/prepare-winpe-disk.py` stage WinPE;
- `tools/prepare-windows-clean-install.py` prepares Windows deployment;
- `tools/package-winpe-recovery.py` and the scripts in
  `firmware/munch/Recovery/` build recovery-installable archives;
- `tools/collect-windows-setup-logs.py` collects Panther, PnP and event logs.

These are engineering tools, not a one-click installer. Inspect their device
and partition arguments before use. Never infer disk numbers from another
phone: Windows exposes several UFS logical units as separate disks. The
firmware boots an already prepared Windows installation automatically:

```sh
fastboot boot out/munch-fresh/munch-uefi.img
```

Immediately after the fastboot transfer finishes, physically disconnect the PC
cable so external USB power disappears. Wait for the Windows logo, then connect
the OTG mouse. `fastboot oem windows` is only a retry command if automatic boot
failed and the firmware entered its diagnostic fastboot endpoint; after its
`OKAY`, unplug the PC and attach OTG within ten seconds.

The repository does not distribute Windows or license keys. Obtain Windows
from Microsoft and follow its license terms.
