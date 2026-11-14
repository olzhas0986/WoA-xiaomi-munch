# USB preflight A — fix the observed RPMh OPP dependency first

This image does not enumerate a USB gadget. It isolates a prerequisite failure
visible in the confirmed baseline before adding DWC3, PHY, regulators or ACM.

Evidence in the pinned kernel:

- `drivers/pmdomain/core.c:of_genpd_add_provider_onecell()` invokes
  `dev_pm_opp_of_add_table_indexed()` for domains with performance states.
- With PM_OPP disabled, `include/linux/pm_opp.h` returns `-EOPNOTSUPP` (-95).
- The baseline builds QCOM_RPMHPD but not PM_OPP. Its photograph shows that exact
  error while registering index 0 of the RPMh genpd provider.
- PM_OPP is hidden. The one-line Kconfig patch makes QCOM_RPMHPD select the
  framework its DT-based registration requires. No CPU/apps_rsc DT links are
  deleted. This is a dependency correction, not an ignored error or idle quirk.

A separate unresolved issue is AOSS mailbox: sm8250.dtsi routes it to `ipcc`,
and baseline CONFIG_QCOM_IPCC is disabled. Do not fix it in test A.

## Build and boot

```sh
make usb-preflight
fastboot boot out/usb-preflight/munch-boot.img
```

The target exports a separate pinned kernel source tree and applies the tracked
patch there, with zero fuzz. It records patch SHA-256 in kernel.patches.json and
rejects reuse with another patch set. Default `make image` keeps the unpatched
minimal profile. Loader and DTS are unchanged. Baseline boot image is backed up
at `out/baseline/munch-boot.img` for this working checkout.

Only the OPP framework dependency is added to the kernel profile. Init prints a
short provider diagnostic before its usual local shell; it does not delay or
loop through pages. USB/PHY/clock-controller/regulator drivers remain unselected.
There is no new command line workaround.

The running RPMh provider can now participate in the existing power-domain
hierarchy. This can change boot/idle behaviour or cause a hang; test with
`fastboot boot` only. If the image hangs, use the handset's established forced
restart/recovery path and return to the baseline temporary image. No partition
writes are performed by the project.

Expected:

1. The same 8 CPUs, userspace and local shell.
2. `rpmhpd provider bound: yes` and the provider device name.
3. No OPP-table -95 failure. The AOSS mailbox error can remain in test A.

If the provider is absent, a new error appears, or boot hangs, transcribe the last readable
output and time to failure. A camera is no longer available. A different errno is useful evidence;
do not add GPIO reservation, domain deletions or ignore-unused parameters.

After A is confirmed, test B will add IPCC alone. Then introduce the USB2 device
controller/PHY with documented supplies, observe UDC state/speed and only then
bind an ACM gadget. Existing SM8250 DT already includes some Synopsys quirks;
we must distinguish inherited SoC properties from newly proposed changes.

## Local build validation

The preflight image was built successfully. Hardware test A is confirmed
by the user-supplied photographs; see the result below.
Seven archive/packer tests and shell syntax checks pass for both baseline and
preflight artifacts. Actual kernel configs differ only by `CONFIG_PM_OPP=y`.
Loader and board DTB are byte-identical to baseline. The packaged diagnostic
init was extracted and compared with its source. A mismatched patch-set request
was rejected without changing the exported source.

Preflight image SHA-256:

```text
647a1c1e019a96e23067270893c8ff7256379da759f09b09ceaed3dbecd6f952
```

Successful build/check logs are preserved under `out/usb-preflight/logs/`.
Existing BusyBox compiler and upstream DT QUP warnings remain visible.

## Hardware result A

The supplied photographs show:

- `online CPUs: 0-7`, `CPU count: 8`, userspace alive and BusyBox shell.
- `rpmhpd bound: 18200000.rsc:power-controller`.
- `rpmhpd provider bound: yes`.
- No OPP-table -95 failure in the photographed boot output.
- The expected AOSS `failed to acquire ipc mailbox` remains.
- RPMh `sync_state() pending` messages name DISPCC (`af00000`), CAMCC
  (`ad00000`) and VIDEOCC (`abf0000`). These drivers remain unselected;
  do not enable them merely to silence a message.

This confirms the OPP dependency correction allowed the RPMh provider to bind.
It does not establish complete RPMh sync_state or long-term idle/display stability.
Two photographs are evidence of this test, not evidence of two distinct boots.

The untracked photographs and their Windows sidecars were removed after recording
these observations, as authorized. SHA-256 for provenance:

- `5380107495512154968.jpg`: `89225906b443898e6cfb3fcc727e9e897f99588280869bff76b0cc9d93965720`.
- `5380107495512154969.jpg`: `2a384b99d4868f5f6f4ff349e0b03a626704841a3a7916c75b3b1d87fc236cb3`.
