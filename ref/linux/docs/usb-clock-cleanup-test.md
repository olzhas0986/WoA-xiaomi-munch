# Unused-clock cleanup A/B test

The latest photograph ends visibly at amba_stub_drv_init returned 0. The user
reports it stayed there. In this exact kernel's System.map, the next level-7s
initcall is clk_disable_unused, followed by genpd_power_off_unused. This makes
clock cleanup a testable suspect; it does not prove the CPU hung there or that
the timer/cacheinfo was broken. Earlier visible stop points differed.

## Single diagnostic change

TEMPORARY WORKAROUND: add only `clk_ignore_unused` to the cacheinfo trace image's
existing command line. The kernel, config, loader, initramfs and other DT
properties remain the same. No pd/regulator/cpuidle/SMMU flag is added.
The flag returns early from clk_disable_unused before its unused-clock scan.
It should print `clk: Not disabling unused clocks`.

Skipping cleanup keeps unclaimed clock resources enabled. It is a diagnostic
resource/power trade-off, not complete display ownership or a production fix.
A successful boot would implicate the cleanup path or its timing; it would not
alone distinguish framebuffer scanout loss from a CPU/MMIO/locking stall.

## Build and boot

```sh
make usb-clock-cleanup-test
fastboot boot out/usb-clock-cleanup-test/munch-boot.img
```

Report whether the D summary and BusyBox shell appear:

```text
D CPU=8 RPMH=1 IPCC=1 AOSS=1 CLK=1 GCC=1
```

Also report whether the screen stays on about one minute. If it stalls again,
transcribe the last 2–4 readable lines, especially calling/returned or the clock
cleanup message. No photo is required. Do not add another parameter yourself
in this test: a power-domain-only A/B test, if needed, must be separate.

This retains GCC's shared-clock behaviour and the existing diagnostic patches.
Use temporary fastboot boot only; no partition writes. C remains the confirmed
working fallback at `out/usb-clocks/munch-boot.img`. The original D and trace
images are preserved for comparison. USB gadget is still not enabled.

## Local validation

Image built successfully. Comparing the extracted
payloads confirms identical loader, kernel and initramfs. Every DTB property
and reservation-map entry matches the previous trace except chosen.bootargs,
which gains exactly `clk_ignore_unused`. Packer header/range validation passed.
The original cacheinfo trace and confirmed C retain their recorded hashes.
Build log: `out/usb-clock-cleanup-test/logs/build.log`.

Image SHA-256:

```text
ce14c5f82be6e9c53cf244fbf3c4894fddd0a68ba9a97ba865385825cfba4606
```

## Hardware result (2026-10-18)

The user reports that this image works as expected and boots successfully.
Long-duration stability has explicitly not been tested. This supports keeping
unused-clock cleanup as the current suspect, without proving which clock or
whether the earlier failure was a CPU stall or loss of framebuffer scanout.
No individual CI trace results or clock ownership have been established.

Keep this exact image as the temporary GCC-enabled baseline. The next hardware
check uses the same image and command line: leave it idle for 5 minutes, then
15 minutes if it remains visible. Record elapsed time and any last visible
message if it fails. A visible shell prompt alone does not establish ongoing
CPU progress or interactive shell access; no keyboard/USB transport is enabled.
Do not add consoleblank, power-domain or regulator flags during this check.
No rebuild is required. Even a passing idle check is limited evidence, not a
stress test or a permanent clock ownership fix.
