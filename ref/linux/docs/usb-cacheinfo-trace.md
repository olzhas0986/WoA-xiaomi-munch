# Cacheinfo / CPU hotplug trace

The user reports the final GCC trace line as:
`calling cacheinfo_sysfs_init+0x0/0x30 @ 1`.
No matching returned line was supplied. This is a narrowed observation, not
proof of defective cache geometry or a cacheinfo bug.

## Why these markers

cacheinfo_sysfs_init registers a CPU hotplug state and synchronously calls its
startup callback for already-online CPUs. It can wait on registration locks,
a per-CPU hotplug thread, cache detection/sysfs work or cache-sharing updates.

The diagnostic patch adds only pr_info markers around these existing steps:

- `CI init`: entered cacheinfo_sysfs_init.
- `CI read-lock` / `read-locked`: acquiring the CPU read lock.
- `CI state-lock` / `state-locked`: acquiring the hotplug state mutex.
- `CI cpu=N call`: dispatching this CPU's callback.
- `CI cpu=N enter`: the callback actually began.
- `CI cpu=N attr ret=R`: cache attribute detection returned R.
- `CI cpu=N sysfs ret=R`: cache device/sysfs creation returned R.
- `CI cpu=N shared` / `pcp`: before/after per-CPU cache-sharing updates.
- `CI cpu=N exit` / `done ret=R`: callback body and dispatch returned.

The core CPU hotplug markers are conditional on the cacheinfo state; unrelated
states do not print. Existing locks, callbacks, errors and CPU power-domain
properties are preserved. No cacheinfo blacklist, CPU limit, idle switch,
ignore-unused flag or register access workaround is introduced. ARM64 cache
register code and EL2 state are unchanged.

System.map from D places GCC registration at level 4, cacheinfo at level 6,
PSCI idle driver registration immediately after cacheinfo, and unused-clock
cleanup at level 7s. Therefore a blanket unused-clock or cpuidle workaround
would be premature. GCC registration having run does not by itself prove its
provider bound successfully.

## Build and test

```sh
make usb-cacheinfo-trace
fastboot boot out/usb-cacheinfo-trace/munch-boot.img
```

The profile exports a separate pinned source tree and applies the original OPP
dependency patch plus the diagnostic patch. Kernel config matches D. It reuses
the same BusyBox build/init script and keeps the same `initcall_debug loglevel=8`
command line as the previous trace. The loader and hardware DTS are unchanged.
Baseline/A/B/C/D and the earlier trace are retained.

Transcribe the last 2–4 `CI` lines and any subsequent error. The CPU number and
last stage are enough; no camera or full offsets are needed. Examples:
`CI cpu=1 call` without enter suggests callback dispatch/progress needs tracing;
`CI cpu=1 enter` without attr narrows the stop to attribute detection. Neither
alone proves the CPU is physically off or that printk itself cannot stall.
If no CI line appears after calling cacheinfo, report that explicitly.
If the shell starts, report that too: extra printk can change timing and is
not itself a fix.

This keeps D's GCC hardware behaviour and its boot/display risks. Temporary
fastboot boot only; use the established restart path if it stalls. C remains
the last confirmed working fallback at `out/usb-clocks/munch-boot.img`.

## Local validation

Image built successfully; subsequent visible hardware progress is recorded below. Kernel config matches D
exactly. The expected CI strings are present in the compiled Image. Loader,
initramfs and DTB match the earlier GCC trace byte-for-byte, including its
command line. Extracted non-kernel payload items were compared as well as the
input files. C, D and the previous trace retain their recorded hashes.
Eight image/cache tests and init shell syntax checks pass. The two modified
kernel sources pass whitespace checks. Repeated incremental build/pack produces
the same image. Logs: `out/usb-cacheinfo-trace/logs/`.

Image SHA-256:

```text
8ea31f0658fc420f35340945e15f1db144d8afb41219f868fc515a568bcfeb6e
```

## Subsequent hardware observation

The supplied photograph shows progress through late initcalls, ending visibly at
`amba_stub_drv_init ... returned 0`. CI markers are not visible in this cropped
portion, so no per-CPU stage result is recorded. The user confirmed the screen
remained at this last output. No userspace summary or shell is visible.

This boot advanced beyond the previously reported cacheinfo call; it does not
establish a cacheinfo root cause or a fix from printk instrumentation.
System.map places clk_disable_unused immediately after amba_stub_drv_init at
level 7s, followed by genpd_power_off_unused. Those calls are not visible in
the photo. Clock cleanup is therefore a targeted next A/B test, not a proven
culprit. A frozen visible framebuffer is not proof the CPU stopped there.

Photo/Windows sidecar were untracked and removed after recording these results,
under the user's existing authorization. Photo SHA-256:
`f23732cdb55dc15fde7e026ac9748c37756a0c3335108318516466bbf9728d62`.
