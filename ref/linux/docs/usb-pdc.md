# USB preflight E: PDC wakeup interrupt provider

The user confirmed successful boot with clk_ignore_unused and chose to proceed
without an idle-duration test. Long-term stability remains unverified.

## Scope

Preserve the confirmed clock-cleanup image's kernel patches and command line.
Add CONFIG_QCOM_PDC=y only; require all GCC profile settings unchanged.
The initramfs adds one bound-driver check for qcom_pdc and an E summary.
No board DT changes, USB controller, PHY, gadget or regulator enablement.

Source references in the pinned kernel:

- arch/arm64/boot/dts/qcom/sm8250.dtsi: usb@a6f8800 uses PDC inputs
  14, 15 and 17 for wakeup IRQs; PDC is interrupt-controller@b220000.
- drivers/irqchip/qcom-pdc.c: qcom_pdc_probe registers the hierarchical
  IRQ domain. IRQCHIP_PLATFORM_DRIVER_END(qcom_pdc) names the sysfs driver.
- include/linux/irqchip.h: platform driver registration macro.

PDC is a wakeup interrupt controller, distinct from RPMh power domains.
A bound driver confirms probe/domain registration; it does not test USB wakeup
or traffic. Probe reads/configures interrupt-controller MMIO through the
unmodified mainline driver. No partition or persistent storage writes occur.

TEMPORARY WORKAROUND: clk_ignore_unused remains confined to this diagnostic
profile, preserving the working baseline. It is not a permanent display fix.
initcall_debug/loglevel=8 and cacheinfo trace instrumentation are retained to
avoid combining provider enablement with removal of earlier diagnostics.

## Build and hardware test

From pmos-munch:

```sh
make usb-pdc
fastboot boot out/usb-pdc/munch-boot.img
```

Expected summary followed by BusyBox shell:

```text
E CPU=8 RPMH=1 IPCC=1 AOSS=1 CLK=1 GCC=1 PDC=1
```

Report the E line. If PDC=0, copy the preceding PDC diagnostic messages.
If userspace does not appear, copy the last 2–4 visible lines. No camera needed.
No longevity wait is required for this provider test. USB enumeration is not
expected yet. The successful clock-cleanup image is preserved unchanged.

Full boot log stays in RAM at /run/dmesg.boot; without a working transport it
cannot yet be collected from the host.

## Local validation

Build succeeded. User confirmed PDC=1 and the shell screen remained visible
for about one minute. This does not test USB traffic or long-term stability. All eight existing tests passed.
Exact kernel config delta: QCOM_PDC changes from unset to y, no other symbol.
Loader bytes match the cacheinfo trace baseline. Sorted DTB decompilation
matches the confirmed clock-cleanup image, including bootargs and reservations.
DTB binary layout differs after fdtput; a byte comparison is not equivalent
here to a property comparison. Confirmed clock-cleanup image SHA is unchanged.
Shell syntax and git whitespace checks passed. Build log:
`out/usb-pdc/logs/build.log`.

Boot image SHA-256:

```text
a2547dd9c43073d5153d60eb2b2e72443e8815c29abe41ff755d1f8b87820f0d
```
