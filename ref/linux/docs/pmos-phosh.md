# Phosh in the RAM rootfs

The user has started Phoc 0.57 / Phosh on the native DSI screen with the Adreno
render node, and confirmed Squeekboard after mounting `/dev/shm` and joining the
same session bus. These helper scripts automate that working sequence. They
remain a manual root bring-up session with BusyBox as PID1, not a complete
pmOS login/service stack. Battery, audio, suspend, NetworkManager integration
and lock-screen authentication are separate work.

## Install into the current session without rebooting

On the computer: `python3 tools/build-phosh-tools.py`. Copy
`out/phosh-tools.tar.gz` and its `.sha256` file to the NTFS USB stick.
Inside **pmOS Bash**, attach the stick and run:

```sh
mkdir -p /mnt/phosh-tools
mount -t ntfs3 -o ro,nosuid,nodev,noexec /dev/sda1 /mnt/phosh-tools
(cd /mnt/phosh-tools && sha256sum -c phosh-tools.tar.gz.sha256) &&
    tar -xzpf /mnt/phosh-tools/phosh-tools.tar.gz -C /
umount /mnt/phosh-tools
```

The archive contains five reviewed files under `/usr/local`, no OS image.
Stop the manually started Phoc (and any standalone Squeekboard) before the
first helper launch. `kill -TERM $(pidof phoc)` stops that compositor; close
the graphical clients first if their content matters. Stop a standalone
keyboard with `kill -TERM $(pidof squeekboard)` if present. Then:

```sh
phosh-start
```

It detaches from PuTTY, prepares GPU firmware, discovers the DSI card, mounts
shared memory, triggers udev with writable sysfs, creates system D-Bus if
absent, waits 10 seconds, then starts Phoc. Phosh and Squeekboard are children
of one session bus and use Phoc's supplied Wayland socket. There is no socket
name guess, second PuTTY session or separate keyboard bus. The compositor
uses GLES2 on renderD128 and KMS on the connected DSI card, scale 3.
Logs: `/tmp/phosh.log`, `/tmp/squeekboard.log` inside pmOS. The launcher refuses
to start alongside an existing compositor and holds a lock until it exits.

Required packages (install only while Wi-Fi is already working):

```sh
apk add phosh phoc squeekboard dbus seatd-launch eudev \
    firmware-qcom-adreno-a650 mesa-dri-gallium mesa-egl mesa-gbm
```

## Camera cutout

Phosh's documented mechanism is a gmobile panel JSON supplied through
`G_RESOURCE_OVERLAYS`, with `sm.puri.phosh shell-layout` set to `device`.
See <https://phosh.mobi/posts/notch-support/>. The helper supplies a
`xiaomi,munch` profile matching the DT compatible, using the known 1080x2400
resolution. Its central guard rectangle covers x=480..600, y=0..96 physical
pixels. **This is a conservative trial guard, not a measured camera outline.**
It should cause the clock to avoid the center; its actual placement must be
checked on the phone. No corner-radius data is invented. Edit
`/usr/local/share/pmos-munch/display-panels/xiaomi,munch.json` to refine the guard,
then restart Phosh/Phoc. Set `PHOC_DEBUG=cutouts` manually for a visual check
if supported by the installed Phoc; the launcher leaves that debug overlay off.

## Touch calibration and persistence

The old image required a temporary 1.25 libinput calibration. The corrected DT
has 8640x19200 axes. Never apply both fixes. The helper detects the corrected
DT and refuses startup if the known temporary rule is still installed; remove
`/etc/udev/rules.d/99-munch-touch-calibration.rules`, reload udev rules and
trigger input discovery before restarting. Keep the temporary rule when
running the old DT.

`make pmos-touch` includes these five files in the small boot image and
installs a BusyBox `phosh-start` wrapper. It copies the helpers to the loaded
rootfs and launches them through `pmos-enter`. The desktop rootfs loader now
uses a 2 GiB tmpfs limit (the installed Phosh rootfs already exceeded 1 GiB)
and checks for at least 2.5 GiB available RAM first. Save the current rootfs
before rebooting if you want to keep installed packages; see pmOS display docs.
Saving packages is not equivalent to saving running services or Wi-Fi sessions.

## Automatic load and Wi-Fi onboarding

The new `pmos-load` extracts the rootfs, installs the bundled phone tools,
prepares Adreno and QCA6390, then starts a network chooser and a Bash shell.
From a local console it stays in the foreground. From USB ACM it detaches and
continues on the phone console after USB/OTG reconnection. The init shell loop
tracks its local shell and yields that console to onboarding. No password is
requested over the detached log stream. Network selection needs a local
keyboard; the framebuffer text console has no touch keyboard.

The chooser displays numbered scan results, hides password entry, waits for
association and obtains a DHCP lease. `r` rescans and `0` skips to Bash. Open
and WPA2-PSK networks (including WPA2/WPA3 transition networks with PSK) are
supported; WPA3-only SAE, enterprise and hidden SSIDs require manual setup.
Passwords and PSKs are sent through supplicant control stdin, never command
arguments or credential files; supplicant configuration
and scan state live under `/run` and are excluded from rootfs saves.

`pmos-save-current [/dev/sda1]` inside pmOS waits 10 seconds and saves the
current rootfs as `postmarketos-desktop.tar.gz` plus SHA256 on verified NTFS USB
storage. In BusyBox the equivalent command is `pmos-save [/dev/sda1]`.
It detaches from PuTTY; the log is `/tmp/pmos-save.log` inside pmOS. Wait for
`PMOS SAVED` and successful unmount. Previous desktop archives are renamed
`postmarketos-desktop.previous-N.tar.gz`; partial saves are never overwritten.
Finish package operations first. Close apps that are actively changing files
for a consistent snapshot; running processes themselves are not saved.

The loader now displays only `Booting linux...` during normal operation.
Payload/header/bounds/copy checks still run and failures still display errors.

## Refresh an exported rootfs on the host

```sh
python3 tools/update-pmos-rootfs.py --gpu-firmware out/munch-zap-android
```

This streams the existing Wi-Fi rootfs into
`out/pmos-rootfs/current/postmarketos-desktop.tar.gz`, adds public APK keys
from the pinned pmbootstrap checkout and the current phone helpers, and removes
the unavailable host build repository. The optional firmware directory supplies
the user's A650 SQE/GMU files; hashes are recorded in the adjacent JSON manifest.
The original archive is preserved and an existing output is never overwritten.
This refresh preserves the base archive's packages; it cannot recover Phosh
packages or settings lost from an unsaved RAM session. Copy the new archive and
its SHA256 sidecar to the stick root; `pmos-load` prefers this filename.
