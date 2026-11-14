# Native Wi-Fi experiment S (munch)

Status: image built (14872576 bytes), 34 host tests passed; QCA6390/PCIe/TLMM are not yet
confirmed on the phone. The working R image remains `out/pmos-usb/munch-boot.img`.
Native display work is separate; this image retains simplefb.

## Evidence and scope

Supplied stock `out/stock-dt/munch-v21.dtb`, overlay 21:
`/soc/qcom,cnss-qca6390@b0000000` selects PCIe RC 0, WLAN GPIO20,
BT GPIO21. Its supplies resolve to PM8150 S6A (950000 uV), S4A
(1800000), S5A (1900000), PM8150L S8C (1350000). PCIe0 uses L5A
(880000) and L9A (1200000), PERST GPIO79 and WAKE GPIO81.
Nominal requests are bounded to the next supported RPMh voltage selector:
S6A 950–952 mV, S5A 1900–1904 mV, S8C 1350–1352 mV, all inside
the stock regulator limits. Exact nominal values are not representable.
The inherited SM8250 PCIe0 pinctrl also configures CLKREQ GPIO80.

The PMU output topology comes from the same QCA6390 in alioth source
022f7f866a9377c34301e60ba131121c624d2e56; inputs above were checked
against munch, not merely copied. Current kernel's qca6390-pmu binding and
PCI_PWRCTRL_PWRSEQ implementation are used. No downstream CNSS driver.
The alioth exclusion of TLMM GPIO28–31/40–43 is retained as a precaution;
stock munch does not establish these secure reservations. This is an
explicit hardware-test uncertainty. Only WLAN/BT enable and PCIe0 pins
are configured. Bluetooth transport is not enabled.

S4A/S5A/S6A/S8C are real RPMh resources. Their external input supplies,
and L9A's parent, remain unmodeled as in the USB baseline; firmware must
retain those inputs. No dummy output regulators, DMA bypass, internal
storage driver or Android partition writes are introduced.

## Prepare Wi-Fi userspace on the PC

The old rootfs lacks ath11k firmware. In the project directory:

```sh
python3 tools/pmos-rootfs.py wifi-build
python3 tools/pmos-rootfs.py wifi-export
make pmos-wifi
```

The first command requires host network/sudo through pmbootstrap. It adds
linux-firmware-ath11k, wireless-regdb, iw, wpa_supplicant, iproute2,
pciutils to the existing build chroot. The old exported archive is preserved.
The new archive and checksum are in `out/pmos-rootfs/wifi/`; copy both
`postmarketos-aarch64-console.tar.gz` and its `.sha256` to the NTFS stick,
replacing the copies there. Do not mix the old archive with the new checksum.
The boot image still contains no rootfs or Wi-Fi firmware.

## Manual phone test

```sh
fastboot boot out/pmos-wifi/munch-boot.img
```

On the phone:

```sh
pmos-load
# Wait for PMOS READY, then:
wifi-start
pmos-enter
iw dev
ip link
```

Built-in ath11k may initially fail firmware lookup, because the rootfs
is not loaded at boot. `wifi-start` sets firmware_class.path to the RAM
rootfs and rebinds only PCI device 17cb:1101 to ath11k_pci. It waits for
a PHY, never claims association or Internet connectivity. Firmware stays
in RAM. Retry is skipped if a PHY already exists. Board calibration may
still be absent from generic board-2.bin; collect the exact driver error
rather than renaming board files or substituting random calibration.

If there is no PHY, collect outside the chroot:

```sh
ls /sys/bus/pci/devices
cat /sys/kernel/debug/devices_deferred
dmesg | tail -n 100
```

If boot itself stalls after enabling TLMM/PCIe, return to the R image and
provide the last display messages. Do not flash S.

Association/DHCP will be tested after a PHY appears. Use the interface
name reported by `iw dev`; passwords should be entered locally, not sent
in logs. This chroot still has BusyBox PID1 and does not start services.

## S follow-up: syscon

First hardware test reached BusyBox over ACM but reported QMP PCIe PHY
`failed to lookup syscon: -524`. The profile omitted MFD_SYSCON, so the
syscon helper returned its -ENOTSUPP stub even without the optional
qcom,4ln-config-sel property. CONFIG_MFD_SYSCON=y fixes that dependency.
This does not establish the cause of the frozen inherited framebuffer.
The previous S image is saved as `munch-boot-before-syscon.img`.

The Wi-Fi loader now reads a mandatory adjacent `.sha256` instead of the
R image's embedded base-rootfs digest, so the Wi-Fi export can load.
This checks integrity relative to the user-supplied checksum, not authenticity.

## S follow-up: PCIe confirmed, framebuffer clock workaround restored

Hardware reports PCIe Gen.2 x1, endpoint 17cb:1101, 32 MSI vectors,
qca6390 hw2.0. Early MHI firmware lookup fails for amss.bin (-2), before
the USB rootfs is loaded. Association has not been tested.

The first S recipe accidentally inherited the base DT command line without
clk_ignore_unused. Restore the P/R bootargs in the Wi-Fi DTS itself, so
repeated builds retain them. This is a likely cause of the frozen inherited
framebuffer, still requiring a hardware test. Enable FB_DEVICE to expose
/dev/fb0 and /sys/class/graphics/fb0; absence of that sysfs node previously
was not proof that simplefb failed to register.
