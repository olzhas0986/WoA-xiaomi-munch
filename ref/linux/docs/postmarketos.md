# postmarketOS on POCO F4

The confirmed path is a postmarketOS AArch64 rootfs in RAM, entered through
chroot under the munch kernel. Wi-Fi, Freedreno rendering, native DSI output,
touch and Phosh have device reports. A saved desktop archive has been reloaded
successfully. See [project history](history.md) for the milestones.

## Working path

`make pmos-touch` builds the board image. `pmos-load` reads a checked NTFS USB
archive into RAM, then prepares firmware and network selection. `pmos-enter`
opens the chroot, and `phosh-start` launches the desktop. Installation and save
instructions are in [pmos-phosh.md](pmos-phosh.md).

The rootfs is volatile. Save it explicitly before rebooting, and keep the USB
stick connected until the save helper reports a successful unmount. USB partition
names can change after reconnecting. A dirty NTFS volume should be checked and
repaired rather than mounted with `force`.

## Native boot experiment

The separate `make pmos-native` image attempts `switch_root` into the rootfs's
init and OpenRC services. The latest phone test did not establish a successful
native boot. Details and recovery instructions are in
[pmos-native.md](pmos-native.md). Host tests are not hardware validation.

## Porting boundaries

The generic userspace is not an upstream munch device package. The board kernel,
DT, signed GPU firmware and panel/touch drivers remain device-specific. The
related alioth reference is useful evidence, not an interchangeable boot image.
Internal UFS stays disabled and testing uses temporary `fastboot boot` images.
A complete port still needs reliable native sessions, power management, thermal
control and remaining phone hardware support.
