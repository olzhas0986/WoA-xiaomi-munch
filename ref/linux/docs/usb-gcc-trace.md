# GCC D trace — diagnostic logging only

D did not reach the userspace summary. The last visible timer message is a
position marker, not sufficient evidence that the timer caused the stall.
The exact unreturned initcall must be identified before instrumenting GCC.

```sh
make usb-gcc-trace
fastboot boot out/usb-gcc-trace/munch-boot.img
```

The target reuses D's exact kernel, loader and initramfs. It modifies only
/chosen/bootargs in a copied DTB, adding `initcall_debug loglevel=8`.
initcall_debug emits DEBUG-level `calling`/`returned` pairs; loglevel=8 makes
them visible on tty0. KALLSYMS is already enabled. This kernel has a direct
initcall-debug fallback even without FTRACE; no tracing config is needed.
No hardware workaround, new driver or register write is added by this profile.
The original D image and confirmed C remain unchanged.

On another stall, transcribe the last few lines and especially:

```text
calling <function_name>+... @ ...
```

Find the last such call without a matching `initcall <function_name> returned`.
The function name is sufficient initially; full offsets and a camera are not
required. If the output still stops at the same timer message without any
calling lines, report that explicitly. If there is a returned line, include it
and any line after it rather than treating that call as blocked.

If the D summary and shell now appear, report that instead. Extra printk can
change timing; successful traced boot alone is not a fix. Do not add other
parameters in the same test. If display output freezes while CPUs continue,
this logging path may still be insufficient; no CPU-hang claim is made yet.

GCC has the same shared-clock/scanout risk as D. This is temporary fastboot boot
only; use the handset's established restart path if needed. C is still available
at `out/usb-clocks/munch-boot.img`.

## Local validation

Trace image built successfully; hardware result pending. Extracted payloads have
identical loader, kernel and initramfs content compared to D. Comparing every DTB
property and the FDT reservation map shows exactly one property change:
/chosen/bootargs gains the two diagnostic tokens. C and D boot image hashes
remain unchanged. Packer header/range validation passed during packaging.
Build log is saved in `out/usb-gcc-trace/logs/build.log`.

Trace image SHA-256:

```text
be8431412f8647f1b84cf0309a5fa359be0de1d9e11e522608efdb49fb02a0a2
```

## Hardware result

User reports the last visible line:

```text
calling cacheinfo_sysfs_init+0x0/0x30 @ 1
```

No returned line was supplied. This narrows the visible stop to cacheinfo
registration; it does not yet prove a cache-register fault or a specific CPU.
System.map places gcc_sm8250_init at subsys level 4, cacheinfo at device level 6,
psci_idle_init immediately after cacheinfo, and clk_disable_unused at level 7s.
Thus skipping unused-clock cleanup or changing PSCI idle is not the first
well-supported diagnostic. Instrument the cacheinfo CPU hotplug dispatch path.
