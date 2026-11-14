# Preflight I: bind primary USB2 FEMTO PHY

H passed: the user confirmed expected provider/LDO fields and userspace boot.
Reported LDO voltage/enable votes do not measure physical power or input wiring.

## Change and limits

Enable PHY_QCOM_USB_SNPS_FEMTO_V2 and selected GENERIC_PHY. Separate board DTS
includes H and enables only usb_1_hsphy at 88e3000 with three explicit supplies:
vdda-pll -> L5A, vdda18 -> L12A, vdda33 -> L2A. Stock phandle evidence and the
mainline binding establish this mapping. Clock/reset/compatible/reg are inherited
from sm8250.dtsi. No PHY tuning overrides or USB quirks are added.

The upstream PHY probe obtains the RPMh reference clock, GCC reset and all three
real output regulators, creates the generic PHY and registers the provider.
The init script checks qcom-snps-hs-femto-v2-phy binding. DWC3 remains disabled,
so no consumer calls phy_init/set_mode and no USB link or descriptor is expected.
A bound provider is not proof of successful PHY initialization or link training.
The mainline driver leaves runtime PM forbidden by default; do not write its
power/control in this test. No PHY driver modifications are introduced.

TEMPORARY WORKAROUND: H's three always-on LDOs and unmodeled input supplies
remain explicit, as does clk_ignore_unused. UPSTREAM=UNMODELED stays on screen.
Do not reinterpret this as a complete mainline regulator graph.

Sources in the pinned kernel: drivers/phy/qualcomm/phy-qcom-snps-femto-v2.c
(probe vs init ops), drivers/phy/qualcomm/Kconfig and
Documentation/devicetree/bindings/phy/qcom,usb-snps-femto-v2.yaml.

## Build and boot

```sh
make usb-phy
fastboot boot out/usb-phy/munch-boot.img
```

Expected CPU=8, previous provider fields=1, and:

```text
I L5=1 L12=1 L2=1 PHY=1 UPSTREAM=UNMODELED
```

Report the I lines. If PHY=0, report the preceding PHY/supply diagnostic messages.
If userspace does not appear, report the last visible lines. No camera, host
USB enumeration or prolonged idle check is needed. Full dmesg stays in RAM at
/run/dmesg.boot. H remains unchanged as the fallback. Temporary fastboot boot
only; no partition writes.

## Local validation

Build succeeded. User confirmed expected I fields and successful userspace boot.
This establishes provider binding, not PHY init or USB traffic. All ten existing tests passed. Shell
syntax/whitespace checks passed. Kernel config adds exactly GENERIC_PHY and
PHY_QCOM_USB_SNPS_FEMTO_V2; all previous enabled settings are unchanged.
Preprocessed I source is exactly H followed by the one usb_1_hsphy override.
Compiled supply phandles resolve to the three intended LDO nodes. Adding these
references renumbers dtc-generated phandles; raw sorted DT diffs include that
renumbering and are not a direct list of hardware changes. Loader bytes and the
confirmed H image hash remain unchanged. Packer range/header checks passed.
Logs: out/usb-phy/logs/.

Image SHA-256:

```text
b09d1a43df219188d3462dc000bd28064f2e5da24d68739c48a21fcaff87b25a
```
