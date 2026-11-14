# OTG preflight L: host/HID software, unchanged peripheral hardware mode

The user authorized proceeding toward an OTG keyboard with a phone-powered hub.
Keep the postmarketOS-in-RAM objective and the confirmed ACM fallback. This is the first
isolated kernel configuration step, not a working OTG/VBUS image.

## Change

Preserve K's configfs ACM and corrected init. Enable USB host core, xHCI platform,
HID/USB_HID/HID_GENERIC and INPUT_EVDEV. Replace gadget-only DWC3 build mode with
USB_DWC3_DUAL_ROLE (which selects USB_ROLE_SWITCH). The very same DT still sets
dr_mode=peripheral, USB2-only PHY and maximum-speed=high-speed. No Type-C role
switch, PMIC, SPMI, GPIO, VBUS or current/charging settings change.

Keyboard VT input needs the HID path; INPUT_KEYBOARD is not needed for USB HID
and would expose unrelated keyboard controller choices. No USB storage, filesystem,
UFS or block-device mount is enabled. USB3/QMP PHY remains disabled. The xHCI
platform driver is compiled/registered, but DWC3 must not create a host instance
while its selected role remains peripheral.

Sources: drivers/usb/dwc3/{Kconfig,core.c,host.c,drd.c}, drivers/usb/host/Kconfig,
drivers/hid/{Kconfig,usbhid/Kconfig}. Dual role does not mean simultaneous host
and gadget operation on the single port.

## Build and check

```sh
make usb-host-ready
fastboot boot out/usb-host-ready/munch-boot.img
```

Use the PC cable as before; do not connect OTG/hub for this preflight.
The reused init still labels its summary K to keep its bytes unchanged.
Expected: same COM shell, CPU online 0-7, UDC configured after enumeration.
On the phone's shell run:

```sh
cat /sys/devices/system/cpu/online
cat /sys/class/udc/*/state
cat /sys/class/udc/*/current_speed
ls /sys/bus/platform/drivers/xhci-hcd
ls /sys/bus/hid/drivers/hid-generic
```

Driver directories should exist, but no host controller/keyboard device is
expected yet. Empty driver directories may still show bind/unbind/uevent entries.
Report shell access and these short outputs. If boot stalls, report last visible
lines. No prolonged wait or photo is needed. Current Full Speed operation is
accepted for this regression test; no speed/PHY quirk is added.

Next stages audit/enable SPMI/PM8150B Type-C/VBUS support and only then switch
roles. Stock munch default/suspend GPIO46 pinctrl sets LOW; the disable-active
state sets HIGH. This identifies stock pin states, not complete electrical
semantics or authorization for blind GPIO writes. Use real connector/role and
VBUS control, not always-on VBUS with a PC still attached (backfeed risk).

Prior clk_ignore_unused, three always-on output LDOs and UPSTREAM=UNMODELED are
retained. No flash or storage write. Confirmed K/termios images stay unchanged.

## Local validation

Build and all ten existing tests passed. Loader, DTB and corrected initramfs
are byte-identical to the respective confirmed K artifacts. The DT still says
peripheral. K and termios-only boot-image hashes remain unchanged. Previous
enabled config values are preserved except replacing DWC3_GADGET with
DWC3_DUAL_ROLE. Additions are USB, XHCI_HCD/PLATFORM, HID_SUPPORT/HID/GENERIC,
USB_HID, INPUT_EVDEV and selected USB_ROLE_SWITCH; newly visible USB core
numeric defaults are also recorded in .config. No storage or PMIC driver added.
Kernel config and build log are in out/usb-host-ready/. Hardware test pending.

Image SHA-256:
`200f7852461567144a5633446ccec4dc5fe35a384900ec22e9c1ec245b712eb4`.

Hardware confirmed by user: CPUs 0-7 online, UDC configured, xhci-hcd and hid-generic registered.
