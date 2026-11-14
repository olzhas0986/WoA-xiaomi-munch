# F3-style modular Wi-Fi experiment

This isolated native image tests the driver lifecycle used by the inspected
postmarketOS SM8250 configuration: cfg80211, mac80211 and ath11k are modules,
loaded after a real rootfs containing firmware is available.
The user verified Wi-Fi connection through native Phosh and internet access
on two consecutive boots. Wider stability testing is still pending.

## What changes

- The kernel release gains `-pmos-munch-modular` to prevent reuse of incompatible
  modules from a saved rootfs.
- The image includes matching, stripped AArch64 modules and host-generated
  depmod metadata. They are stored as inactive bootstrap data under
  `/etc/pmos-munch/kernel-modules`, not `/lib/modules` in the bootstrap.
- Native handoff verifies the running release and installs those files under
  the RAM rootfs's `/lib/modules/<release>` before starting init or udev.
- Preflight checks module dependencies, modprobe and the three QCA6390 firmware
  files. The normal udev coldplug can then load the driver with firmware already
  present. The firmware service explicitly loads `pci-pwrctrl-pwrseq` and
  `ath11k_pci` if needed, and waits for a PHY without unbinding/rebinding PCI.
- The PCI power-sequencing helper is modular too, as selected by modular
  ath11k. Munch's actual regulator/GPIO/DT values remain unchanged.

The RX header counters remain available for comparison. No F3 calibration,
firmware or whole-board DT is substituted. The existing firmware comes from
the same saved RAM rootfs archive. No Android storage is mounted or changed.

## Build and test

Build `make pmos-touch` and `make pmos-wifi-rx` first on a clean checkout.
Then:

```sh
make pmos-native-modular
fastboot boot out/pmos-native-modular/munch-boot.img
```

Use the existing USB rootfs archive; no archive rebuild is required. After
native boot, confirm the variant and load state:

```sh
uname -r
lsmod
rc-service pmos-munch-firmware status
```

The release must end in `-pmos-munch-modular`, and ath11k_pci, ath11k,
mac80211 and cfg80211 should appear in lsmod. Keep the iPhone close as in the
successful chroot test and try the Phosh Wi-Fi interface. For directed scanning:

```sh
nmcli device wifi rescan ifname wlan0 ssid 'iPhone (Karakat)'
```

If connection fails, collect:

```sh
grep -H . /sys/module/ath11k/parameters/rx_probe_* \
  /sys/module/mac80211/parameters/rx_probe_*
dmesg | grep -iE 'ath11k|firmware|module|wlan0' | tail -n 60
```

The ordinary native, native-RX and touch images are not replaced by this target.
Their built-in-driver recovery remains available. A normal boot also removes
the RAM-root module-profile marker so saving this rootfs does not force modular
Wi-Fi loading under another kernel.

References: inspected local `out/pmaports` SM8250 config, pinned alioth DT at
`022f7f866a9377c34301e60ba131121c624d2e56`, and the F3 port's
[device package](https://github.com/nasaarmas/pmaports-alioth/blob/main/device-xiaomi-alioth/APKBUILD).
