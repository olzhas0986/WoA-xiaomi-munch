# POCO F4 touch experiment

Build: `make pmos-touch`. Output: `out/pmos-touch/munch-boot.img`.
The display image and its source remain unchanged. Boot manually with
`fastboot boot out/pmos-touch/munch-boot.img`; no flashing is required.
User confirmed controller ID, touch-down, movement and release with evtest.
Weston input works after remounting the chroot sysfs read/write and triggering
udev input discovery. Final coordinate alignment and multi-touch are pending.

## Evidence and scope

Stock overlay 21 identifies FocalTech on GENI SPI4 at 0x990000, chip select 0,
6 MHz, reset TLMM33, IRQ TLMM39. The stock DT declares 10800x24000, but
`focaltech_spi/focaltech_core.c` defines `SUPER_RESOLUTION_FACOTR` as 8.
Our unscaled wire decoder therefore needs 8640x19200 (eight units per display
pixel). Initial tests with the DT's factor 10 compressed touch positions into
the upper-left 80% of the output. Stock pinmux uses GPIO8/9/10/11 as QUP4,
6 mA drive and no bias; GPIO33/39 are GPIO mode, pull-up, 8 mA drive.
The stock IRQ property encodes low-level plus one-shot, but the actual Xiaomi
driver overrides this to falling-edge plus one-shot; this experiment follows
the driver's runtime behavior.

The supplied official Xiaomi sources are pinned at
`9aba441cf6cd86f1e81ee6a2608e9102b05c52a7` on `munch-s-oss`.
Their hashes and URLs are recorded in `out/munch-touch-stock/manifest.json`.
`focaltech_spi/focaltech_config.h` selects FT3658U; the chip mapping in
`focaltech_common.h` expects app ID 56:52. `focaltech_core.c` decodes 15-bit
coordinates using additional bits in the pressure byte. `focaltech_spi.c`
provides the framing: command, read/CRC control, big-endian length, three
dummy bytes, data, little-endian CRC (polynomial 0x8408, seed 0xffff).

The small GPL driver implements this protocol and ten Type-B direct touch
slots. It rejects CRC failures, unexpected app IDs, duplicate/out-of-range IDs,
invalid coordinate/count frames, and does not publish partial touch frames.
Read buffers have the full transfer size and are reused without per-IRQ devm
allocation. Coordinates remain in raw units; libinput scales them to the output.

Stock supplies map VIO to PM8150L L1C at 1.8 V and VDD to L10C. Stock DT allows
3.0–3.312 V; Xiaomi's touch driver explicitly requests 3.2 V, which is used here.
Reset is low while VIO is enabled, then VDD; reset deasserts with a 200 ms wait.
No regulator input wiring is guessed. GPI DMA and QUP0 are enabled for SPI4.

There is no flash erase/update, ROM boot command, firmware upload, factory-test,
gesture-wakeup or suspend/resume implementation. The controller must boot its
existing application firmware and report 56:52. This is an initial bring-up,
not a full upstream-quality driver; power management and error recovery need
separate implementation after the first touch test.

## On-device test

First collect in BusyBox, without loading the rootfs:

```sh
dmesg | grep -iE 'ft3658|touch|geni|spi|gpi|failed|error'
cat /sys/kernel/debug/devices_deferred
cat /proc/bus/input/devices
```

Expected input name: `POCO F4 FT3658U Touchscreen`, with an event handler.
Then load the pmOS rootfs, prepare GPU and run Weston as before (or use
`desktop-start` if the saved rootfs contains Weston/eudev/seatd-launch).
Do not assume Weston packages survive reboot if the rootfs was not saved.

In pmOS, `apk add evtest`, run `evtest`, select the POCO F4 touchscreen and
test touch-down, motion, release and two fingers. Confirm no stuck contacts,
correct axes and alignment at all corners. Then check tapping and dragging
in Weston. Stop evtest with Ctrl+C. If probe fails, send the above kernel
logs; do not try firmware flashing or unrelated F3 binary firmware.
