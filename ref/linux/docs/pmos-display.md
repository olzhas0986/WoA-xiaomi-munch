# Native display experiment (U)

The user verified DPU/DSI takeover for POCO F4 (munch), Weston 16 with
freedreno FD650 on renderD128, a graphical terminal, USB keyboard and mouse.
Transient blue artifacts during boot remain unresolved. No compositor starts automatically at boot.
BusyBox stays PID1, and the existing RAM rootfs, Wi-Fi and GPU helpers remain.

## Panel evidence

The supplied Android `cmdline.txt` selects
`msm_drm.dsi_display0=qcom,mdss_dsi_l11r_38_08_0a_dsc_cmd:`.
This identifies the physical panel independently of the stock DT inventory.
Stock `vendor_boot.img` plus munch overlay 21 were extracted to
`out/stock-dt/munch-v21.dtb`. The audit is
`out/stock-display-evidence/munch-v21-audit.json`.
The DT contains 48 panel descriptions; its static default points at a simulator.
That default was not used to identify the phone's panel.

`tools/audit-display-dt.py` decodes the stock packet headers and supply references.
`tools/generate-display-patch.py` checks the Android selection and reviewed 60 Hz
timing, then generates patch 0004 from the driver template and exact stock bytes.
The generated header records the DT SHA256. Patch 0005 adapts the original
driver patch to this kernel's refcounted panel allocation API; the current
driver template already includes that adaptation. Packet types, payloads and delays
are preserved, including long packets with short payloads. No F3 initialization
sequence was substituted for the F4 sequence.

The first mode is 1080x2400 at 60 Hz, four DSI lanes, DSC 1.1, 8 bits per
component, 8 compressed bits per pixel, two 540x8 slices. Stock horizontal
porches/sync are 16/8/8 and vertical 600/32/560. Other refresh rates are omitted.
Physical reset GPIO12 goes low for 12 ms then high for 10 ms; TE is GPIO66.
Panel rails are L14A at 1.88 V and L11C at 3 V, as selected by the stock panel
supply entries. DSI controller L9A and PHY L5A reuse existing 1.2 V and 0.88 V
rails. Upstream regulator inputs remain firmware-managed, as in the working
minimal board; no unverified parent wiring is invented.

## Build and test

Run `make pmos-display`. The kernel source and output are isolated under
`out/pmos-display`, retaining the Wi-Fi and GPU outputs. The generated image
is `out/pmos-display/munch-boot.img`. The known working GPU fallback is
`out/baseline-pmos-gpu/munch-boot.img`.

Boot manually, without flashing:

```sh
fastboot boot out/pmos-display/munch-boot.img
```

First check the native console and collect through USB ACM:

```sh
ls /sys/class/drm
ls /sys/class/backlight
cat /sys/class/drm/card*-DSI-*/status
cat /sys/class/drm/card*-DSI-*/modes
cat /sys/kernel/debug/devices_deferred
dmesg | grep -iE 'l11r|dsi|dpu|mdss|dispcc|drm|failed|error'
echo 'NATIVE DISPLAY TEST' > /dev/tty0
```

GPU and scanout use separate DRM devices; enumeration order is not guaranteed.
Identify the display device through its DSI connector, rather than assuming
that card0 drives the screen. The inherited framebuffer may disappear during
DRM takeover. A blank screen needs the serial log, not a rootfs reinstall.

Stock 60 Hz timing is retained; flicker or transfer
errors must be investigated before enabling other modes. GPU thermal cooling
registration remains unresolved in the minimal kernel, so sustained GPU stress
is outside this test. Android storage and partition layout are unchanged.

## One-command desktop

The updated bootstrap installs `desktop-start` in BusyBox. After `pmos-load`,
run `desktop-start` at `munch#`. It prepares firmware, discovers the connected
DSI card, checks the required programs, waits 10 seconds for OTG, then starts
udev and Weston with GL rendering and a terminal. It runs in a detached session
so losing the USB ACM connection does not stop the desktop. Closing the launched
graphical terminal exits Weston. Repeated starts are refused while it is running.
Logs: `/run/desktop-start.log` in BusyBox and `/tmp/weston.log` inside pmOS.

Required rootfs packages:

```sh
apk add weston weston-backend-drm weston-shell-desktop weston-terminal \
    seatd seatd-launch eudev font-dejavu
```

## Save the RAM rootfs

With the updated bootstrap, finish package operations and close Weston, then
run `pmos-save` (or `pmos-save /dev/sda1`) from BusyBox. It waits 10 seconds,
checks USB storage ancestry, mounts NTFS read/write without `force`, writes
`postmarketos-desktop.tar.gz` plus SHA256 and unmounts the stick. It preserves existing desktop archives as numbered previous versions and
refuses to overwrite partial saves. The original console
archive is retained. `pmos-load` now prefers the desktop archive and verifies it.
Logs: `/tmp/pmos-save.log` inside pmOS; wait for `PMOS SAVED` before unplugging.
Virtual filesystems, runtime files, temporary files and mount directories are
excluded. This saves packages and rootfs files, not running processes or Wi-Fi
association. Stop package installation before saving; stop Weston as well.

### Preserve the current live session before booting the new image

New helpers only appear after booting the new image. First save the existing
RAM rootfs from the **current pmOS Bash**, otherwise its packages will be lost.
Close the graphical terminal to stop Weston, then use PuTTY to run the block
below. Use an NTFS USB stick at `/dev/sda1`, with no existing desktop archive.
It starts a detached job; connect OTG within 10 seconds. If `setsid` or `tar`
is absent, install `util-linux` or `tar` respectively before disconnecting.

```sh
setsid /bin/sh -c '
set -eu
sleep 10
mkdir -p /mnt/pmos-save
mount -t ntfs3 -o rw,nosuid,nodev,noexec /dev/sda1 /mnt/pmos-save
trap "sync; umount /mnt/pmos-save" EXIT
cd /mnt/pmos-save
for f in postmarketos-desktop.tar.gz postmarketos-desktop.tar.gz.sha256 postmarketos-desktop.tar.gz.partial; do
    [ ! -e "$f" ] || { echo "Refusing overwrite: $f"; exit 1; }
done
set -C
tar -czpf - -C / --exclude=./dev --exclude=./proc --exclude=./sys \
    --exclude=./run --exclude=./tmp --exclude=./mnt --exclude=./media \
    --exclude=./.pmos-munch-ready . > postmarketos-desktop.tar.gz.partial
mv postmarketos-desktop.tar.gz.partial postmarketos-desktop.tar.gz
sha256sum postmarketos-desktop.tar.gz > postmarketos-desktop.tar.gz.sha256
sync
umount /mnt/pmos-save
trap - EXIT
echo "PMOS SAVED; USB unmounted"
' </dev/null >/tmp/pmos-save.log 2>&1 &
```

Inspect `cat /tmp/pmos-save.log` from the phone terminal after reconnecting
the keyboard, or through PuTTY after reconnecting the PC. Reboot only after
`PMOS SAVED; USB unmounted`. A partial file after failure must be inspected
and explicitly renamed or removed before retrying.
