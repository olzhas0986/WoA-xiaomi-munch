# Project history

pmos-munch develops a postmarketOS port for the Xiaomi POCO F4. These milestones
summarize the work and distinguish device results from unfinished experiments.

## Establishing the boot path

The first milestone was entering Linux at EL1 with a small custom loader,
validated RAM destinations and an inherited framebuffer. The minimal profile
reached BusyBox with all eight CPUs online. Pinned kernel sources and isolated
build directories made the following hardware stages reproducible.

## Bringing up USB

Clock, power-domain, interconnect, regulator, PHY and IOMMU stages established
USB ACM access. Later stages added Type-C role switching, a phone-powered OTG
hub, keyboard and mouse input, and USB mass storage. The single USB port changes
between the PC console and OTG host roles; the hub does not make them simultaneous.

## Loading postmarketOS into RAM

A generic AArch64 postmarketOS userspace was built with pmbootstrap and loaded
under the board kernel. USB-to-RAM extraction kept the boot image small. NTFS
archives gained SHA256 checks, and a save helper made installed packages survive
reboots through explicit rootfs backups. The working path keeps BusyBox as PID1
and enters the userspace through chroot.

## Adding networking and graphics

QCA6390 Wi-Fi reached association, DHCP and internet access. Adreno 650 exposed
a render node, and Mesa reported Freedreno FD650 hardware rendering. The native
DSI panel then provided a 1080×2400 output at 60 Hz, allowing Weston and later
Phosh to run on the phone's own screen.

## Touch and the mobile desktop

The FT3658U SPI driver produced real touch events, including independent tracking
of two contacts. Correcting the advertised coordinate range aligned touches
with the display. Phosh and Squeekboard were confirmed after arranging shared
memory and a common session bus. The resulting desktop was saved and reloaded
from the USB archive successfully.

## Current experiment: native init

The next stage replaces the chroot bootstrap with a PID1 handoff to the rootfs's
BusyBox init and OpenRC. It has a separate boot image, explicit runlevels,
NetworkManager and an unprivileged Phosh service. The first phone attempt stopped
in preflight because `/dev/null` was unavailable inside the new root. A temporary
`/dev` bind addresses that specific failure. Subsequent testing exposed missing
temporary directories in saved archives; preparation now recreates them and
provides USB recovery plus kernel-log diagnostics on failure. The phone has now reached OpenRC's Phosh startup, but a working native desktop
was initially unconfirmed; independent recovery consoles and a diagnostic report are
available to investigate it. Keep using the chroot image as the recovery path.

Native diagnostics confirmed PID1 handoff, OpenRC, D-Bus, seatd and Wi-Fi startup.
Phosh exited before creating its log: supervise-daemon opens logs after changing
to the desktop user. The service now prepares a writable log before that change;
the phone subsequently confirmed native Phosh startup. Wi-Fi controls exposed
missing session authorization, so the native profile now installs a PolicyKit
allowlist for the desktop user's network actions.

Building ath11k, mac80211 and cfg80211 as modules and loading them after the RAM
rootfs firmware is available resolved the observed native Wi-Fi failure. The
user confirmed connection through Phosh and internet access on two boots.
A separate image now tests stock L11R 120 Hz commands and BQ27Z561 battery
telemetry; those additions still await device results.

Further priorities are native boot reliability, user-session integration,
thermal management, battery and charging support, and suspend/resume.
