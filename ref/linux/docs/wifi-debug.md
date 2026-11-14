# Wi-Fi association timeout investigation

## Confirmed on the phone

The iPhone hotspot provides internet to a PC. Both the native OpenRC image and
the touch/chroot image associate with its BSSID, then time out before the
supplicant reaches COMPLETED. Native testing reproduces this with WPA2-PSK,
with NetworkManager stopped, and with `control_port=0`. The passphrase has not
been proven incorrect. Missing names in ordinary scans are a separate issue:
directed SSID probing finds the hotspot. Console onboarding now enables that
probing for the selected network.

Early firmware lookup fails before the RAM rootfs exists; the later successful
ath11k reprobe must be considered separately. The reported firmware identifies
as QCA6390 hw2.0, version 0x10121492, build timestamp 2021-11-04 11:23.

## Source audit

The retained Wi-Fi, GPU and touch build configurations have the same inspected
PACKET, cfg80211, mac80211, ath11k and CCM settings. The retained GPU, display
and touch copies of ath11k `dp_rx.c` have identical SHA256 digests. No project
patch changes ath11k. Native boot reuses the touch kernel and DT. These checks
do not establish equivalence with every previously booted image or rootfs.
No driver regression or root cause has been established.

The ordinary kernel disables ATH11K_DEBUG and ATH11K_DEBUGFS. The separate
diagnostic target enables those plus cfg80211/mac80211 debugfs, while keeping
the touch DT, firmware loading path, chroot init and driver source unchanged.

## Isolated image

Build `make pmos-touch` first on a clean checkout, then:

```sh
make pmos-wifi-debug
fastboot boot out/pmos-wifi-debug/munch-boot.img
```

Load the existing rootfs archive with `pmos-load`, use `wifi-start` if needed,
and enter the chroot with `pmos-enter`. Existing archives are not overwritten.
Before a single connection attempt:

```sh
mountpoint -q /sys/kernel/debug || mount -t debugfs none /sys/kernel/debug
cat /sys/module/ath11k/parameters/frame_mode
cat /sys/module/ath11k/parameters/crypto_mode
find /sys/kernel/debug/ath11k -name soc_dp_stats -exec cat {} \; > /tmp/wifi-dp-before.txt
```

Run `pmos-connect`, select the real SSID, and exit its menu with `0` after a
failed attempt. Then collect:

```sh
find /sys/kernel/debug/ath11k -name soc_dp_stats -exec cat {} \; > /tmp/wifi-dp-after.txt
diff -u /tmp/wifi-dp-before.txt /tmp/wifi-dp-after.txt
dmesg | tail -n 100
```

Do not enable every debug-mask bit or publish packet/SRAM dumps: some ath11k
debug paths dump key material. Leave the mask at zero for this counter test.
This image is diagnostic; it does not claim to fix Wi-Fi or change calibration.

## RX/EAPOL probe image

Phone testing found unchanged RXDMA/REO error counters, including after a
temporary switch to frame mode 2. Group 0 DP interrupts increased while ordinary
RX groups stayed at zero in the captured interval. Station RX and beacon counts
also increased. These observations do not prove complete absence of reception
or isolate a faulty MSI controller. WPA2 association still timed out.

`make pmos-wifi-rx` builds an additional image from an independent pinned source
export. Only this target applies patch 0007 and stages the headers from
`diagnostics/wifi-rx/`. Normal touch/native/debug builds do not include the probe.
Firmware, DT and default frame mode remain unchanged.

```sh
make pmos-wifi-rx
fastboot boot out/pmos-wifi-rx/munch-boot.img
```

After loading the existing RAM rootfs and entering pmOS, save a baseline:

```sh
grep -H . /sys/module/ath11k/parameters/rx_probe_* \
  /sys/module/mac80211/parameters/rx_probe_* > /tmp/rx-before.txt
```

Try one connection, leave the helper menu with `0`, then:

```sh
grep -H . /sys/module/ath11k/parameters/rx_probe_* \
  /sys/module/mac80211/parameters/rx_probe_* > /tmp/rx-after.txt
cat /tmp/rx-after.txt
diff -u /tmp/rx-before.txt /tmp/rx-after.txt
```

These read-only atomic counters are cumulative across all radios for the boot;
take differences rather than assuming they reset on PCI reprobe. Reads of the
different counters are not an atomic snapshot.

| Counter | Meaning |
| --- | --- |
| ath11k `rx_probe_reo_buffers` | Buffers recovered from normal REO destination rings, before processing/drop checks |
| ath11k `rx_probe_total` | MSDUs at the datapath handoff immediately before `ieee80211_rx_napi()` |
| mac80211 `rx_probe_total` | Frames entering `ieee80211_rx_napi()`, including other paths such as WMI management RX |
| `rx_probe_data` | Data frames recognized from the bounded Ethernet/802.11 header inspection |
| `rx_probe_eapol` | Frames recognized as EAPOL from EtherType or cleartext LLC/SNAP |
| `rx_probe_unknown` | Header unavailable, too short or prefixed with unsupported radiotap metadata |

The classifier checks at most 64 bytes through `skb_header_pointer()`, without
changing the skb. It recognizes regular/QoS/four-address/HT-control MAC headers.
Encrypted bodies with an unstripped IV and A-MSDU payloads are counted as data
without guessing the inner protocol. Thus zero EAPOL is not conclusive if data
or unknown counters grow. The probe records neither contents, addresses, SSIDs,
passwords nor keys, and adds no packet hexdumps or per-frame log output.

Matching ath11k/mac80211 EAPOL increments prove arrival at the mac80211 entry,
not successful delivery to a userspace socket or completed WPA authentication.

## Confirmed connection and native comparison

With the iPhone moved closer (reported signal -43 dBm), the RX probe chroot image
completed WPA2 association and DHCP. IPv4 and IPv6 pings and DNS resolution
worked. Both layers counted 24 data frames and two EAPOL frames, with zero
unknown classifications. This disproves a permanently broken RX path, but does
not establish why earlier attempts timed out. Ordinary native boot still timed
out after association at a strong signal, both with NetworkManager and a single
standalone supplicant. Permanent MAC and WPA2-only profile tests did not fix it.

Use the exact successful RX kernel in native boot without rebuilding it:

```sh
make pmos-native-rx
fastboot boot out/pmos-native-rx/munch-boot.img
```

This target writes a separate boot image with the normal native init/services,
the unchanged touch DT and `out/pmos-wifi-rx/kernel/arch/arm64/boot/Image` as its
kernel input. It does not replace `out/pmos-native/munch-boot.img` or rebuild the
RX kernel. Keep the iPhone in the same close position. Capture the same sysfs
counters before and after one native connection attempt; debugfs is unnecessary.

A later attempt to test with graphics stopped was inconclusive: OpenRC reported
the Phosh service stopped, but Phoc, Phosh and an application remained alive.
The native launcher now cleans up the entire session group on termination.
Do not interpret a successful OpenRC stop message alone as proof that graphics
was absent during a Wi-Fi experiment; verify the running processes as well.
