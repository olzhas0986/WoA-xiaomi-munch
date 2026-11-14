# USB preflight D — SM8250 GCC and GDSC helper

C is hardware-confirmed: 8 CPUs, RPMh/IPCC/AOSS and RPMh clock provider bound,
with the screen staying on during the requested short observation.
D adds only SM_GCC_8250 plus its selected QCOM_GDSC helper. No new kernel patch,
DT property, command-line flag, PHY, regulator or DWC3 driver is introduced.

GCC supplies the USB core/interface/sleep/UTMI clocks, PHY resets and USB GDSC.
Test it before enabling USB consumers. GCC is shared hardware: the unmodified
mainline probe forces some AHB clocks on (including GCC_DISP_AHB_CLK) and changes
GPLL0 routing for NPU/GPU. It also registers gcc_disp_* parent clocks. This test
therefore can affect scanout despite keeping MDSS/DSI/PHY/display drivers off.
No claim that display hardware is completely untouched is made for this stage.

## Build and boot

```sh
make usb-gcc
fastboot boot out/usb-gcc/munch-boot.img
```

Expected transcribable summary:

```text
D CPU=8 RPMH=1 IPCC=1 AOSS=1 CLK=1 GCC=1
```

Report this line and whether the screen stays on for about one minute. If it
turns black before the summary, report that and the approximate delay. If GCC=0,
the init prints the last five matching clock/defer messages before the summary.
Transcribe the relevant error if possible; no camera is required.

A bound GCC driver confirms provider registration, not PHY/UDC operation or all
GDSC transitions. USB does not enumerate yet. Full boot dmesg stays in RAM at
`/run/dmesg.boot`; retrieval still requires a transport or a validated dump path.

GCC probe/clock cleanup can blank the screen or expose a boot hang. Use temporary
`fastboot boot` only and retain the established forced restart path. C remains
at `out/usb-clocks/munch-boot.img`. Do not add clk_ignore_unused, pd_ignore_unused
or change display nodes simultaneously with this test.

## Build isolation

D has its own kernel output and image, reusing the pinned source export from A.
If C's build cache exists, the helper copies/reflinks it atomically into D,
without hard links to C. Copied .config and output Makefile are removed so D's
config is regenerated and checked. Kbuild updates changed dependencies.
If no C cache exists, D builds normally from scratch. The baseline and previous
images/build directories are preserved. The helper's independence is tested.

## Local validation

D built successfully; hardware test failed to reach userspace, as recorded below. Eight tests pass, including
cache-copy isolation, plus all init shell syntax checks. The actual config delta
from C is exactly SM_GCC_8250 and QCOM_GDSC. GCC code is present in System.map.
Loader/DTB remain byte-identical to baseline, and the archived init matches D's
script. Baseline/A/B/C images and C's kernel Image retain their SHA-256.
Repeated incremental build/packing produced the same D image. Build/check logs
are saved in `out/usb-gcc/logs/`.

D boot image SHA-256:

```text
cccbc3eedf2d4345ba35f49eda5fbf62822e8be56fab6f4ab24079449c35c092
```

## Hardware result D

User reports no D summary or shell. The last visible output is:

```text
clocksource: arch_mmio_counter: mask: 0x... max_cycles: 0x46d987e47, max_idle_ms: 440795202767 ms
arch-timer-mmio 17c2000.timer: mmio timer running at 19.20MHz (virt)
```

The screen stayed at that output for more than a minute. Treat this as failure
to reach observable userspace, not proof the timer is broken or that the CPU
stopped there. C was the previous successful image. Adding GCC/GDSC is the
controlled difference; the exact blocking function is not yet known.

Next test adds only diagnostic logging (`initcall_debug loglevel=8`) to D's
chosen.bootargs. Do not mix this with clk_ignore_unused, pd_ignore_unused,
cpuidle changes or register access workarounds. Keep D for comparison and C as
the confirmed temporary-boot fallback.
