# OTG keyboard experiment M

L hardware passed: CPU 0-7 online, ACM configured, xhci-hcd and hid-generic
registered. M adds one functional keyboard experiment on top of L.

Build: `make usb-otg-keyboard`. Boot only:

```
fastboot boot out/usb-otg-keyboard/munch-boot.img
```

After the local shell appears, disconnect the PC and attach the normal OTG
adapter, phone-powered hub and keyboard only. Type `uname -a` on the keyboard.
Do not add the flash drive yet. No flashing, UFS support, storage mounting or
partition writes are introduced. The single port cannot provide PC ACM and
host keyboard simultaneously. ACM setup is optional when the controller is
already in host role; the local framebuffer shell always remains available.

The board includes upstream pm8150b.dtsi, SPMI arbiter/MFD, PM8150B TCPM and
VBUS regulator drivers. Stock munch evidence establishes PM8150B USID 2 and
PD PHY L2A supply. The connector graph connects TCPM to DWC3 usb-role-switch.
Only fixed 5 V / 500 mA PDOs are advertised; the VBUS regulator current limit
is 500 mA. No always-on VBUS, forced host role, fast charging or USB3.
The VBUS driver selects software OTG enable; TCPM owns attachment and power.

Unverified board detail: stock charger uses TLMM GPIO46 as vbus-disable with
stock default output-low. M retains firmware's gate state without requesting
or toggling the GPIO. This can prevent VBUS from reaching the hub; driver
presence alone does not establish a functioning electrical path. PM8150B GPIO12
is not manipulated: a pinctrl state alone did not prove an active consumer.
Use only the normal OTG connection, without a charger or external hub supply.

Existing temporary baseline workarounds remain: clk_ignore_unused, always-on
USB PHY rails with unmodeled upstream inputs, cacheinfo trace patch. No new
SMMU bypass or EL2 access. Upstream unrelated PM8150B ADC/GPIO/thermal drivers
are not enabled by this profile.

On-screen M snapshots show role and the last relevant kernel messages at
5, 15, 30 and 60 seconds. Full logs remain in /run/dmesg.otg. Success requires
actual keyboard typing; PMIC probing and a lit keyboard alone are insufficient.
Hardware result: user confirmed working keyboard and local input.

Build validated: 10 tests passed, shell syntax checked, required Kconfig symbols enabled and DT dr_mode=otg. Image SHA256: `18f1aff8dee44276c7e01a24c05e7b0e4953c7cb3f7d77fde758a0f76283cb3c`. Working termios ACM image hash unchanged.

## Loader display follow-up

`make usb-otg-keyboard-ui` reuses the confirmed M kernel, DTB and initramfs and
changes only the loader display. Boot `out/usb-otg-keyboard-ui/munch-boot.img`
with fastboot boot. No artificial delay is added. The original M image remains
untouched. The loader uses a complete uppercase 5x7 font, a plain black background, no banner, white text and
white brackets with green OK markers and red descriptive errors with exact codes.
Messages describe checks actually performed, not hardware health or a checksum
that was never calculated. Pre-C entry rejection in start.S still halts silently.

UI image SHA256: `2a31619f0c31641e815f02273adbcee3875fc6552889f23e33c1d69e8988fd54`. Container after loader offset is byte-identical to confirmed M. Render preview: `out/usb-otg-keyboard-ui/loader-preview.png`.
