# USB preflight B — IPCC mailbox for AOSS

Test A confirmed the RPMh provider now binds after fixing its OPP dependency.
This test adds only `CONFIG_QCOM_IPCC=y` to the kernel config from A.
There is no new kernel patch, DT change, boot argument or USB gadget.

Evidence from the pinned source:

- `sm8250.dtsi:aoss_qmp` references `ipcc` both as mailbox and interrupt provider.
- `qcom_aoss.c:qmp_probe()` fails at mbox_request_channel() when the provider is
  unavailable, with the message visible in both previous tests.
- Baseline and A have QCOM_IPCC disabled. QCOM_IPCC is the driver that matches
  the inherited SM8250 IPCC node; it registers at arch_initcall.

## Build and test

```sh
make usb-ipcc
fastboot boot out/usb-ipcc/munch-boot.img
```

B keeps a separate kernel build directory and image. It reuses A's pinned,
patched source export and unchanged BusyBox build via SOURCE_OUT/BOUT; it does
not overwrite the A boot image or minimal baseline. On a fresh checkout the
shared source export and BusyBox build are prepared automatically.

Expected diagnostic before the shell:

```text
rpmhpd provider bound: yes
ipcc provider bound: yes
aoss provider bound: yes
```

The OPP -95 failure should stay absent; the AOSS mailbox-acquisition error should
also disappear. If AOSS still does not bind, the next failure may be a QMP magic,
version, channel handshake, interrupt or timeout error. Preserve that exact
message. The existing init prints the last 12 matching kernel messages and
saves the full boot snapshot to `/run/dmesg.boot` in RAM.

IPCC now touches its mailbox/interrupt hardware and permits the already-enabled
AOSS driver to attempt a QMP handshake. This can expose firmware-access issues
or a boot hang; test only through temporary `fastboot boot`. No partition write
or display workaround is introduced. Retain test A as the fallback:
`out/usb-preflight/munch-boot.img`.

Report the three provider status values and whether shell starts. If boot
stops, transcribe the last readable error and elapsed time; no camera is required. RPMh sync_state messages naming DISPCC/CAMCC/VIDEOCC
are a separate issue: those clock drivers are still deliberately unselected.
Windows is not expected to enumerate an ACM device in this test; DWC3/PHY and
configfs ACM come after these provider checks.

## Local validation

B built successfully. Hardware result is confirmed below.
Seven packer/archive tests and shell syntax checks pass. The actual kernel config
diff from A contains only QCOM_IPCC=y. Loader and board DTB are byte-identical
across minimal, A and B. The archived init matches init-usb-ipcc exactly; baseline
and A boot image SHA-256 remain unchanged. Build/check logs are saved in
`out/usb-ipcc/logs/`.

B boot image SHA-256:

```text
b5abb796e5036adcef5dee415480c027253997330a3072d053f2ae03c7cd6360
```

## Hardware result B

The last supplied photograph shows all three providers bound (`rpmhpd`, `ipcc`,
`aoss`) and a BusyBox shell. The photographed diagnostic block has no AOSS
mailbox-acquisition error. RPMh sync_state remains pending on the unselected
DISPCC/CAMCC/VIDEOCC clock providers. This confirms the IPCC dependency test;
it does not prove complete sync_state or long-term stability.

The user no longer has a second camera. Subsequent test output must be short
and transcribable; do not require photographs for progress. Full logs remain
in RAM until a USB transport or independently validated persistent dump exists.

The untracked photograph and Windows sidecar were removed after recording this
result, under the user's existing authorization. Photo SHA-256:
`c49b3072865ef5c56ca4847f26e3aa04cc976298d356ab66102d12351676c4cd`.
