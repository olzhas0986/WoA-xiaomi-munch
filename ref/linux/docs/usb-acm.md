# Test K: one CDC ACM gadget and ttyGS0 shell

J is confirmed: WRAP/CORE/UDC=1 and the expected not-attached/UNKNOWN output.
That message was informational, not an error. K now binds one gadget to that UDC.

## Scope

Keep J's exact board DTS, command line, hardware clock/PHY/SMMU settings and
kernel patches. Add configfs/libcomposite and the ACM/U_SERIAL function symbols.
No storage, networking, ADB, USB quirks or analog tuning changes.
The separate BusyBox build adds only ln for a configfs function symlink.

Init mounts configfs and prepares one configuration with acm.usb0. All strings,
class fields and the function link are populated before writing UDC. It checks
for exactly one UDC, ttyGS0 and successful binding. Failure retains local console.
USB bcdUSB=0200, IAD class EF/02/01; the mainline ACM function provides standard
CDC control/data descriptors. MaxPower=100 mA advertises bus power only, not a
PMIC charging command. Linux Foundation 1d6b:0104 is used as a local development
identity, not a VID/PID allocation for distributing this project as a product.

A background shell opens ttyGS0 after setsid to acquire that controlling terminal,
initializes termios, and runs sh -i with PS1=munch#. It restarts after shell exit.
It does not use cttyhack, which would select console=tty0 on this platform.
The local framebuffer shell remains available. The USB shell is root without a
login challenge, intended for this temporary physical bring-up connection.

A single delayed (3 second) screen snapshot prints UDC state/current_speed and
maximum_speed, plus /run/dmesg.usb. An initial not-attached value before the host
configures the gadget is not by itself a failure. ACM=1 means configfs binding,
not host enumeration. configured plus high-speed supports enumeration success;
a usable terminal still needs to be tested separately.

TEMPORARY WORKAROUND: prior clk_ignore_unused, always-on output LDOs and
UPSTREAM=UNMODELED remain. Do not treat K as a finished regulator/PM design.

## Build and test

```sh
make usb-acm
fastboot boot out/usb-acm/munch-boot.img
```

Expect prior provider fields, UDC=1 and K ACM=1. Keep the USB cable connected to
Windows. Check Device Manager for a new COM port, open it in an available serial
terminal (115200, 8N1, no flow control), and press Enter for munch#.
The USB device belongs to Windows; opening it from WSL is not required.
CDC ACM is supported by Microsoft's inbox serial driver; relevant primary docs:
https://learn.microsoft.com/en-us/windows-hardware/drivers/usbcon/usb-driver-installation-based-on-compatible-ids
https://learn.microsoft.com/en-us/windows-hardware/drivers/usbcon/support-for-interface-collections

If a shell opens, run only read-only diagnostics initially:

```sh
uname -a
cat /sys/devices/system/cpu/online
cat /proc/cmdline
cat /run/dmesg.boot
cat /run/dmesg.usb
```

Report ACM, delayed state/speed/max, whether a COM port appears, and whether
munch# responds. For Code 43, report the exact Windows error and screen values.
Do not install random drivers or add PHY/LPM quirks before diagnosing. For setup
failure or zero fields, report preceding errors. Full logs stay in RAM; J remains
unchanged as the fallback. No partition write or flash command is involved.

## Local validation

Build and repeat build succeeded with identical image SHA. All ten existing
tests, shell syntax and whitespace checks passed. Config delta is exactly
CONFIGFS_FS, USB_CONFIGFS, USB_CONFIGFS_ACM, USB_LIBCOMPOSITE, USB_U_SERIAL,
USB_F_ACM. Every previous enabled kernel setting remains unchanged. BusyBox
adds exactly CONFIG_LN in its isolated output, leaving the shared build untouched.
Loader and DTB bytes match J, and J's boot-image hash remains unchanged.
A host PTY check confirmed the setsid-then-open sequence acquires a controlling
terminal and supports a write to /dev/tty; this is not an ARM/USB hardware test.
Gadget enumeration and interactive ttyGS0 on the phone remain pending.
Packer validation passed. GCC16 BusyBox qualifier warnings remain in build logs;
they were not suppressed. Logs: out/usb-acm/logs/.

Image SHA-256:

```text
be5eaee7b622fb96d761c04e22ba462155978925ee4e455be1a3f227cc2fa5c6
```

## First K hardware result (2026-10-18)

Photo IMG_20261018_194054.jpg, SHA-256
`e97415f1c8824593dc8a31e1b93f8b9176071273c7da15ecb219ddd7eb7e0f02`, shows:

```text
K CPU=8 RPMH=1 IPCC=1 AOSS=1 CLK=1 GCC=1 PDC=1
K BCM=1 A1=1 MC=1 GEM=1 CN=1 SMMU=1
K L5=1 L12=1 L2=1 PHY=1 UPSTREAM=UNMODELED
K WRAP=1 CORE=1 UDC=1
K ACM=1
K USB state=configured speed=full-speed max=high-speed
```

The user reports Windows sees a composite USB device. The host configured the
gadget at Full Speed; High Speed did not negotiate despite being the allowed
maximum. COM child creation and usable shell are not yet confirmed. Do not
confuse the initial not-attached snapshot with the later configured state.

Photo also shows repeated Hangup and `dwc3 a600000.usb: remote wakeup not
configured` (including a burst around 193 seconds). This is not a clean stable
shell result. Do not suppress the error, change descriptors, enable remote-wakeup
advertising, or add PHY quirks without separating causes.

Pinned gadget.c emits that message when wakeup_configured is false.
u_serial.c can request wake from gs_write/gs_flush_chars while suspended, and
from gserial_suspend for outstanding transfers. This identifies candidate call
paths, not the actual caller/trigger on this phone. Hangup alone does not prove
DTR toggles, a specific Windows driver, or a physical disconnect.

Next read-only Windows check (PowerShell):

```powershell
Get-CimInstance Win32_PnPEntity | Where-Object { $_.PNPDeviceID -like 'USB\VID_1D6B&PID_0104*' } | Format-List Name,PNPClass,Service,ConfigManagerErrorCode,PNPDeviceID
```

This lists composite parent and matching child interfaces, service and problem
code. A composite parent alone does not establish whether usbser/COM bound.
Agent-side Windows execution still fails with WSL UtilBindVsockAnyPort; the
user must run this on the Windows host. No new image has been created for this
observation. Preserve current K and photo until host child status is recorded.

## Windows ACM child confirmed

User supplied Windows PnP output: the composite parent binds usbccgp, and its
MI_00 child is a Ports-class USB serial device on COM3 binding usbser. Both have
ConfigManagerErrorCode=0. Thus Windows enumeration and ACM driver binding are
confirmed; installing/replacing drivers or changing descriptors is unwarranted.
Interactive input/output remains pending. The prior Full Speed observation and
remote-wakeup/Hangup errors are not resolved merely by successful PnP binding.

Next test uses the same K image. Open COM3 in a Windows serial terminal with
115200 baud, 8 data bits, no parity, 1 stop bit and no flow control; enable DTR
if the terminal provides that setting. Press Enter and check munch#. Run
uname -a, cat /sys/devices/system/cpu/online, and dmesg. Report whether output
and keyboard input work, whether the port disconnects, and any terminal error.
Do not open the port simultaneously in multiple applications. No new image or
hardware parameter change is needed for this test.

## Interactive shell milestone confirmed (2026-10-18)

The user supplied a working COM terminal transcript: the banner, munch# prompt,
uname -a, ls, CPU online list 0-7 and dmesg all return. This confirms bidirectional
interactive ACM shell, not only enumeration. The log explicitly reports all CPUs
started at EL1, 8 processors activated, and 5690200K/6238208K available at boot.
DWC3 joined IOMMU group 1; translated/strict IOMMU policy is active. Each CI CPU
callback 0-7 completed successfully. Early -517 probes for CPU domains/PHY/DWC3
later succeeded; these specific early deferrals are not terminal failures.

The same log retains PSCI failed-to-set-PC-mode -3, unbound GPU SMMU and pending
sync_state consumers. Do not hide or generalize those away. The command line
still contains clk_ignore_unused; no claim of fully resolved power management,
High Speed USB, repeated reconnect reliability or long-term stability is made.
Some pasted log lines are visibly incomplete; preserve original terminal captures
if needed rather than treating this transcript as a byte-perfect full dump.

The verified K image and matching configs/init/DTB were copied to
out/baseline-usb-shell/ with sha256.json. Image SHA remains the recorded K SHA.
This is a local preserved artifact set, not a new image or Git tag.

### stty warning

The transcript starts with `stty ... cannot perform all requested operations`
from init's `stty sane 115200`, but the interactive shell subsequently works.
Pinned u_serial.c gs_tty_ops has no set_termios callback and initializes ttyGS
termios to B9600. tty_ioctl.c tty_set_termios calls tty_termios_copy_hw when that
callback is absent; it preserves old speed/c_cflag hardware bits. BusyBox stty.c
compares tcsetattr's requested termios with tcgetattr readback and reports this
mismatch. Thus a request for 115200 on the device is inappropriate here; USB ACM
has no physical UART baud rate to set on ttyGS0.

Before changing the initramfs, test in the current COM shell:

```sh
stty -a
stty sane
echo $?
```

Report the output and exit code; expected zero for software-only sane settings,
but this still needs confirmation on the handset. Host terminal may retain its
115200 setting. No PHY/descriptor/clock changes or rebuild are needed for this
check. The previous photo's remote-wakeup/Hangup issue is not established as
resolved by a subsequent successful shell transcript.

## Termios check passed and initramfs-only follow-up

User confirmed ttyGS reports 9600 and `stty sane` exits 0 without warning.
This supports the source diagnosis above. Init now requests only `stty sane`;
no termios error is suppressed. Host terminal baud setting may remain 115200.

```sh
make usb-acm-termios
fastboot boot out/usb-acm-termios/munch-boot.img
```

This target requires already-built K artifacts in out/usb-acm and never rebuilds
them. On a fresh checkout build make usb-acm first (which now uses corrected init).
Expected: same COM shell, without the startup stty error. Report whether startup
is clean and commands still work. No High Speed or remote-wakeup fix is implied.
Existing K and out/baseline-usb-shell images remain unchanged. Kernel/loader are
identical; archive inspection confirms /init is the sole changed cpio entry.
The packer adjusts chosen initrd end for the changed compressed size. Shell syntax,
packer validation and whitespace checks passed; hardware follow-up is pending.

New image SHA-256:
`a1293f1e0d85fce66c4a6563448bce71484936db33e66d6c516d149a33e0fb7a`.

## Corrected image hardware result

User supplied another successful boot transcript following the termios-only
image test. The USB shell starts without the stty warning, executes uname -a
and returns to munch# after dmesg. Log again confirms eight CPUs at EL1 and
successful late DWC3/PHY probes. This confirms the init fix on hardware; it does
not establish long-duration/reconnect stability or High Speed negotiation.
The corrected image SHA remains a1293f1e0d85fce66c4a6563448bce71484936db33e66d6c516d149a33e0fb7a.
It and matching init/payload manifest are preserved separately under
out/baseline-usb-shell-termios/ with sha256.json; original K is preserved too.

The pasted dmesg has terminal wrapping/padding and visibly joined/truncated
records. Do not assume all such artifacts are harmless formatting or conclude
USB byte loss without a raw host capture. A short filtered diagnostic in the
existing shell is preferable to another unlogged whole-dmesg paste:

```sh
cat /sys/class/udc/*/state
cat /sys/class/udc/*/current_speed
dmesg | grep -iE 'remote wakeup|smmu.*fault|error|failed' | tail -n 20
```

The minimal boot/initramfs/eight-CPU/interactive USB-shell milestone is achieved.
Unresolved clock ownership, input regulators, Full Speed/PM/reconnect observations
remain explicit. UFS must be a separate stage, initially discovery only, without
mounting Android filesystems or issuing writes. No new hardware changes or boot
images were made for this confirmation. Git metadata remains read-only in the
current execution environment; documentation and termios edits remain uncommitted.

## Follow-up live UDC check

User read state=configured and current_speed=full-speed through the working
shell. The requested filtered dmesg output contains the known boot-time PSCI
failed-to-set-PC-mode -3 and fserror_init calling/returned 0. fserror_init is a
substring match for "error", not an initialization failure. No remote-wakeup
messages or SMMU faults appear in that supplied filtered output for this session.
This is a bounded observation, not proof of long-term or reconnect stability,
and does not explain the earlier photo's wakeup/Hangup burst. No new workaround,
PHY tuning or descriptor change is justified by this result.
