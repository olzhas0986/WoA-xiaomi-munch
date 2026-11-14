# USB preflight C — RPMh clock provider, camera-free reporting

B confirmed RPMh, IPCC and AOSS bind. C adds COMMON_CLK_QCOM and QCOM_CLK_RPMH.
COMMON_CLK_QCOM also selects the regmap/reset/interconnect framework helpers;
these are required Kconfig dependencies, not separate SoC provider drivers.
No GCC, DISPCC, VIDEOCC, CAMCC, regulator, PHY or DWC3 driver is enabled.

The HS USB PHY references rpmhcc/RPMH_CXO_CLK in sm8250.dtsi. Establish that
provider before trying the PHY. GCC is another required USB dependency, but its
SM8250 driver also controls gcc_disp_* parent clocks and writes shared clock
registers at probe. It will be a separate test to isolate framebuffer regressions.

## Build and boot

```sh
make usb-clocks
fastboot boot out/usb-clocks/munch-boot.img
```

Expected summary (copy this line as text; no photograph needed):

```text
C CPU=8 RPMH=1 IPCC=1 AOSS=1 CLK=1 GCC=0
```

CLK means at least one device is bound to clk-rpmh, not that every clock has
been exercised. GCC=0 is deliberate. A local shell follows. Full dmesg snapshot
is saved in `/run/dmesg.boot`, in RAM only. If CLK=0, the last five matching clock
messages are printed before the summary; transcribe the relevant error if possible.

Also report whether the screen remains visible after about one minute. If it
turns black before the summary, report that and the approximate delay instead.
Do not add ignore-unused flags automatically. Enabling the RPMh clock driver can
change clock votes/cleanup even without a display driver, so this test can reveal
a framebuffer regression. All images are temporary fastboot boots; keep B at
`out/usb-ipcc/munch-boot.img` as the previous confirmed fallback.

This still does not expose USB ACM. The next tests will cover GCC, remaining
DWC3/PHY dependencies and UDC before gadget enumeration. USB host-side logs can
replace camera reporting once the controller is active; device logs become
retrievable only after a working transport exists. Until then, a black screen
may require a separate validated RAM/pstore diagnostic path rather than guessing.

## Local validation

Image built successfully; hardware result is confirmed below. Seven image/archive tests
and all init shell syntax checks pass. Loader and board DTB match the baseline
byte-for-byte. Minimal/A/B boot images retain their recorded SHA-256. The packed
init matches the short diagnostic script. The actual config delta from B is
COMMON_CLK_QCOM, QCOM_CLK_RPMH and the five expected helpers INTERCONNECT,
INTERCONNECT_CLK, REGMAP, REGMAP_MMIO, RESET_CONTROLLER. No SoC GCC/display or
USB controller driver was pulled in. Logs: `out/usb-clocks/logs/`.

C boot image SHA-256:

```text
22a54aaf0cac52f5bfbfd1f08682a8f552c3ee97340cf58dc365262ac7cd6460
```

## Hardware result C

User transcribed `C CPU=8 RPMH=1 IPCC=1 AOSS=1 CLX=1 GCC=0`.
The image prints CLK, so CLX is interpreted as a transcription typo for CLK.
This confirms eight CPUs, the existing providers and RPMh clock provider bound.
GCC remained deliberately disabled. The user also confirmed the screen stayed
on in response to the one-minute observation question. This is a short screen
preservation check, not proof of indefinite stability or all clock functions.
