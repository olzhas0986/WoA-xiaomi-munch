# Preflight J: primary USB2 peripheral UDC

User confirmed expected I fields and userspace boot. The PHY provider binds;
its initialization and USB communication were not established by I alone.

## Change

Add USB_SUPPORT, USB_GADGET, USB_DWC3, USB_DWC3_GADGET and USB_DWC3_QCOM.
Host USB, configfs and composite functions remain disabled. The separate board
DTS includes I, enables usb_1 with qcom,select-utmi-as-pipe-clk and configures
usb_1_dwc3 for peripheral, maximum-speed=high-speed and only usb_1_hsphy.
No USB3/QMP, role-switch, Type-C/PD controller, VBUS sourcing or gadget function.

The inherited nested SM8250 binding matches qcom,dwc3 in dwc3-qcom-legacy.c,
compiled by USB_DWC3_QCOM. The newer dwc3-qcom.c serves qcom,snps-dwc3 and is
not substituted for this binding. The child binds to dwc3. Expected parent
name is dwc3-qcom-legacy; the init script checks both drivers and the UDC class.

The USB2-only UTMI selection follows the mainline SM8250/elish configuration;
stock munch disables its USB3 PHY. Inherited sm8250.dtsi USB quirks are unchanged.
Do not count inherited dis_u2_susphy/dis_enblslpm properties as new fixes.

This test performs hardware initialization: GCC clocks/resets/GDSC, PDC IRQs,
interconnect votes, SMMU and the PHY consumer path may now run. It may expose
errors or change shared resources/display behaviour. UDC registration indicates
progress through gadget initialization, not working transfers or descriptors.
Runtime PM may later suspend an unbound UDC; no power/control writes are added.

TEMPORARY WORKAROUND: clk_ignore_unused, the three always-on LDOs and explicit
UPSTREAM=UNMODELED are retained from I. Physical input supply wiring and PHY
analog tuning are not proven by provider binding. Earlier trace patches remain.

Sources in pinned kernel: drivers/usb/dwc3/{Kconfig,Makefile,dwc3-qcom-legacy.c,
core.c,gadget.c}, drivers/usb/gadget/udc/core.c, and sm8250.dtsi plus
sm8250-xiaomi-elish-common.dtsi. No kernel source patch is added by J.

## Build and temporary boot

```sh
make usb-udc
fastboot boot out/usb-udc/munch-boot.img
```

Expected previous CPU/provider/LDO fields, PHY=1, and:

```text
J WRAP=1 CORE=1 UDC=1
J state=not attached speed=UNKNOWN max=high-speed
```

Without a gadget, not attached/UNKNOWN is normal. No Windows enumeration or ACM
shell is expected. UDC maximum_speed is read explicitly; link_state is not a
generic UDC sysfs attribute and is recorded only if exposed. Current state and
speed are diagnostic values, not required to match across runtime PM timings.

Report WRAP/CORE/UDC and state/speed/max lines. For a zero, report preceding
DWC3/PHY/defer errors. If userspace stalls, report last visible messages. Do not
add USB quirks or command-line workarounds. A photo is not needed. I is preserved
as the fallback; no flash or partition writes. Full logs remain in /run/dmesg.boot.

## Local validation

Build succeeded. User confirmed expected J fields and successful boot,
including the expected no-gadget/not-attached message. USB enumeration is untested. Ten existing tests plus shell syntax
and whitespace checks passed. Prior enabled config settings are unchanged.
New enabled booleans are USB_SUPPORT/COMMON/ARCH_HAS_HCD, USB_GADGET,
USB_DWC3/GADGET/QCOM and selected NLS, plus their default string/numeric settings.
ARCH_HAS_HCD is a platform capability; CONFIG_USB and host controllers stay off.
Configfs/libcomposite are not enabled. The hidden libcomposite symbol is omitted
by Kconfig when unavailable, so it is checked by absence of an enabled setting.

Preprocessed DT source extends I only by the two USB wrapper/core overrides.
Compiled DT confirms peripheral/high-speed and one primary USB2 PHY reference.
Loader bytes and confirmed I boot-image hash remain unchanged. Packer checks
passed. Build log: out/usb-udc/logs/build.log.

Image SHA-256:

```text
de617474c8b1d2f02eaa1a9ef5caada4eba27e51c8407b5e2bb53bc783aefa46
```
