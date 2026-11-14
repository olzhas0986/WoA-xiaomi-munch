# Native pmOS init from a RAM rootfs (experimental)

**Status:** native Phosh and Wi-Fi internet through the shade are confirmed
on two boots with the [modular Wi-Fi image](wifi-modular.md). Default services start
asynchronously so a stalled graphical service cannot prevent recovery consoles
from opening. Collect userspace logs before changing renderer or seat settings.

This separate boot image hands PID1 from the bootstrap shell to the RAM rootfs's
`/sbin/init` using BusyBox `switch_root`. The rootfs uses Alpine BusyBox init with
OpenRC runlevels; OpenRC itself is not a persistent PID1 daemon. This is no longer
a chroot session. The kernel, native DSI/Adreno/touch DT and Android partition
layout are unchanged. Internal UFS remains disabled. Only `fastboot boot` is used.

## Before testing on the phone

Keep the known-working `out/pmos-touch/munch-boot.img` and the saved desktop
archive as recovery copies. In the **working pmOS session**, install the standalone
seat broker (the previous session only required `seatd-launch`):

```sh
apk add seatd
command -v seatd phoc nmtui
```

If APK reports the already-known `No kernel found in /boot` trigger failure,
check that `seatd` actually installed. Do not invent a kernel in `/boot`.
Save this session to the USB stick with the working save helper, and wait for
`PMOS SAVED`. The stick root must contain `postmarketos-desktop.tar.gz` and its
matching `.sha256`. Keep the earlier archive outside that filename as a backup.
The phone's saved archive is the input; the smaller host console archive does
not contain the subsequently installed desktop packages.

On the host, with the existing touch build available:

```sh
make pmos-native
fastboot boot out/pmos-native/munch-boot.img
```

After fastboot hands over, attach OTG and the stick within 10 seconds. The native
bootstrap discovers a USB-backed NTFS partition containing a supported rootfs
archive, without assuming `sda1` versus `sdb1`. It mounts the stick read-only,
verifies the SHA256, loads the rootfs into the same 2 GiB RAM filesystem and
unmounts the stick. Dirty NTFS volumes are not forced. There is an additional
countdown when the shared archive loader starts.

Preflight requires the known AArch64 musl/BusyBox init, OpenRC, eudev, D-Bus,
NetworkManager, nmtui, seatd, Phoc, Phosh, Squeekboard and existing `pmos` user.
The signed munch ZAP firmware is copied from initramfs before it is discarded.
Missing prerequisites stop in a local RAM recovery shell rather than launching
an incompatible init. Before handoff, `pmos-enter` can inspect the unpacked RAM
rootfs; the archived rootfs on the stick has not been modified.

## What starts

The bootstrap temporarily bind-mounts `/dev` into the new root before preflight
(including `/dev/null` for command checks) and unmounts that bind on success or
failure. Missing runtime directories, including `/tmp` and `/var/tmp`, are
recreated before configuration. Preflight errors are copied to the kernel log
with a `pmos-munch: preflight:` prefix. The success path starts no background
shells, monitors or daemons before handoff. On failure only, a USB ACM recovery
shell is started alongside the local shell; reconnect the PC to collect `dmesg`.
It prepares an explicit profile in the unpacked RAM rootfs and backs up the
original `inittab`, `fstab`, `rc.conf` and runlevels under
`/etc/pmos-munch/before-native/`. It moves `/dev`, `/sys` (including configfs/debugfs)
and `/proc`, mounts a new `/run`, and execs `switch_root` from PID1.

OpenRC runs eudev, D-Bus and NetworkManager. A one-shot firmware service sets the
**new-root** firmware path and retries QCA6390's initially firmware-less probe.
The separate seatd service grants the video group access; Phoc/Phosh/Squeekboard
run as user **pmos**, with their own runtime directory and shared session bus.
The already-tested separate KMS/render selection and `SEATD_VTBOUND=0` remain.

Generic-board swap, zram, USB networking, clock and power-management services
are not enabled by this first profile. The replacement fstab contains only
`/dev/pts` and `/dev/shm`. Dependency-started fsck/localmount services therefore
have no real disk entries to act on.

The local tty2 and USB ACM consoles remain **unauthenticated root recovery
shells**, matching this project's bring-up access. This is not a production login
or lock-screen setup. A full PAM/elogind display-manager session and PolicyKit
integration are still separate work. NetworkManager is the sole Wi-Fi manager;
there is no second standalone supplicant started by the old onboarding helper.

## Check the first boot

Use PuTTY after reconnecting to the PC, or a keyboard with Ctrl+Alt+F2 locally.
The default runlevel uses the BusyBox init `once` action; init does not wait for
Phosh to finish starting before it spawns these consoles. If the screen remains
on `Starting pmos-munch-phosh`, collect the report without restarting services:

```sh
pmos-diagnose --kmsg
dmesg | tail -n 180
```

The report is also saved in `/run/pmos-munch-diagnostics.txt`. It includes bounded
OpenRC status collection, current service-state directories, device permissions
and the last lines of Phosh, seatd and OpenRC logs. It does not collect passwords
or the process environment. For manual checks:

```sh
cat /proc/1/comm
tr '\0' ' ' < /proc/1/cmdline; echo
rc-status
ps -o user,pid,comm,args
cat /proc/mounts | head
```

Expected: PID1 runs the rootfs init (BusyBox init), `/` is tmpfs, and OpenRC shows
D-Bus, NetworkManager, seatd and the Phosh service. `phoc`, `phosh` and Squeekboard
should belong to `pmos`, not root. No `/pmos` chroot prefix is needed for firmware.

Connect Wi-Fi from the root recovery console with:

```sh
nmtui connect
```

`pmos-connect` now calls that same NetworkManager UI. `phosh-start` is a wrapper
for the OpenRC service, not the detached chroot launcher:

```sh
rc-service pmos-munch-phosh status
tail -n 80 /var/log/pmos-munch-phosh.log
tail -n 60 /var/log/pmos-munch-seatd.log
rc-service pmos-munch-phosh restart
```

If handoff or graphics fails, collect the on-screen error and return with
`fastboot boot out/pmos-touch/munch-boot.img`. Do not use `fastboot flash`.
The original archive is unchanged until a later explicit save; rebooting loses
all changes made only to the native RAM session.

## Validation scope

The desktop launcher owns a separate process group created with `setsid`.
Stopping the supervised launcher signals the entire group on exit, including
Phoc, Phosh and session children. Previously OpenRC could report stopped after
only terminating `dbus-run-session`, leaving the actual desktop alive. Host
lifecycle tests cover both service termination and an early D-Bus wrapper exit.

The phone has now confirmed native Phosh startup. The seatd session does not
have logind active-session authorization; a PolicyKit rule explicitly permits
user `pmos` to scan, toggle networking/Wi-Fi, connect and manage network profiles.
It does not grant arbitrary NetworkManager or PolicyKit actions. This is a
single-user RAM-desktop policy, pending full login-session integration.

Host tests exercise the generated init boundary, shell syntax, profile install
and preflight rejection in a temporary fake root. The native image is packed
with the existing checked kernel and DT. Host tests cannot verify real PID1
handoff, OpenRC ordering, non-root GPU access, PolicyKit or seatd on the phone.
Phone diagnostics have confirmed PID1 handoff, OpenRC, D-Bus, seatd and Wi-Fi.
Wi-Fi control through Phosh is awaiting retest with the explicit network policy;
the remaining login-session checks are still pending.
The Phosh service creates its log with desktop-user ownership before the
supervisor drops privileges, preserving existing log contents. References: bundled
BusyBox 1.37 `util-linux/switch_root.c`, exported rootfs `/etc/inittab` and OpenRC
service files, and [OpenRC's service script guide](https://github.com/OpenRC/openrc/blob/master/service-script-guide.md).
