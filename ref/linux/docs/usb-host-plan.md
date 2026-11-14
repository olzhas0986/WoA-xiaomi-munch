# OTG input for the RAM userspace

User has an OTG adapter, a hub powered only by the phone, and a 16 GB USB flash
drive. The userspace target is postmarketOS in RAM. A keyboard
would provide local framebuffer-console input without requiring touchscreen.

The current image is DWC3 peripheral-only with configfs ACM. A USB hub does not
let this single port simultaneously provide a PC gadget connection and act as
host for a keyboard. Preserve the ACM image as a fallback. Host tests must use
the framebuffer and local keyboard, with the PC disconnected from that port.

Needed stages:

1. Host software: USB host/xHCI, DWC3 host or dual-role, HID/generic USB keyboard
   and VT input. First leave existing peripheral DT mode to test ACM regression.
2. Board power/role path: audit SPMI/PM8150B Type-C/VBUS support and munch-specific
   switching before enabling VBUS. A bus-powered hub needs phone-sourced 5 V.
3. Dedicated host image: OTG + hub + keyboard only. Confirm hub/keyboard binding
   and typed input on the existing console, before introducing USB storage.
4. Flash drive discovery/read support later; no format, partition writes or
   automount. A postmarketOS rootfs can be read from the flash drive into
   RAM, subject to memory/transport/driver validation. It need not be installed
   to internal UFS or overwrite the flash drive to try Arch in RAM.

Stock evidence (out/stock-dt/munch-v21.dts, supply/image hashes in the stock report):
- PM8150B PD PHY vbus-supply references smb5_vbus.
- Charger has vbus-disable-gpio = <&tlmm 46 0>, with default/active/suspend
  pinctrl references. Do not infer electrical semantics solely from this name.
- PM8150B gpio12 has an otg_vbus_boost_default pinctrl state, output-low.
  Its mere presence is not proof the active charger consumer uses that pin.

Mainline pm8150b.dtsi contains a disabled USB VBUS regulator at 0x1100 and a
disabled Type-C controller. qcom_usb_vbus-regulator.c implements OTG enable and
current limits and changes the hardware/software VBUS enable source in probe.
Elish demonstrates Type-C connector/role-switch integration, but its complete
power configuration must not be transplanted blindly to munch.

Do not force dr_mode=host and assume power appears. Do not connect PC/charger as
a second power source to an unverified powered-OTG wiring setup: VBUS backfeed
is a concrete electrical risk. Use the normal OTG adapter/hub topology for the
first host test, initially with keyboard only. No VBUS/charging/Type-C hardware
change or new host boot image has been made in this analysis step.
