# Isolated PEP fixed-register diagnostic

> Historical binary-patch diagnostic, not a fix or a supported boot path. The
> numbered image below records the experiment that produced the evidence.

This is a single manual late-load experiment for POCO F4 munch, Windows31
firmware, qcpep8250 1.0.2140.0. It is not a GPU installer or a daily-use PEP.
The observed CPU6 stack includes writes through helper RVA5c50 to physical
18358800/18350800. CPU6 did not provide a stopped register context, so the
causal instruction remains unproven. This experiment tests the hypothesis.

Only two BL instructions calling helper5c50 are changed to ARM64 NOP:
1df358 (initialization),21555c (paired later path). PE checksum is rebuilt;
the original trailing embedded certificate is removed from the diagnostic
copy. Original driver SHA256 must match39fafcd60536c7d36dd95187dc9f51bfc4af661b614bce4a5e9ec0729fe24e01.
Patch manifest records byte offsets, before/after instructions and hashes.

On the phone a clearly named private, non-exportable test key is generated
in LocalMachine/My; its public certificate is trusted in LocalMachine/Root.
PowerShell embeds a SHA256 Authenticode signature. The unsigned package copy
is never selected as a service image. Active kernel TESTSIGN mode is checked
using NtQuerySystemInformation(SystemCodeIntegrityInformation), then signature
status and signer are checked before changing qcpep ImagePath. No BCD or
integrity settings are changed. DriverStore, original SYS, INF, CAT and service
start flags/policy are not replaced. qcpep auto-start stays4 except while the
existing traced late-load helper temporarily sets demand3, restoring4 when it
returns. A crash prevents finally: recover with Windows28, explicitly set
qcpep startup disabled, and run rollback.cmd before any further normal tests.

Workflow (administrator PowerShell):
1. Extract MunchPepLmh to Desktop; run prepare.cmd with qcpep Start4.
   It saves native ImagePath and disables the exact PEP device; 3010 allowed.
2. Boot out/munch-fresh/munch-uefi-windows31-ctpm.img, with startup still4.
3. Run start.cmd from this folder. It requires device problem22 and driver
   Stopped, validates live patched SOSI, signs a separate SYS, selects that
   path, and invokes one fresh traced activation attempt.
4. Run collect.cmd if it returns; after a crash recover/disable first and
   then collect. Rollback before additional experiments. No forced reboot.

rollback.cmd restores the saved native ImagePath and Start4, requests device
22, and leaves the diagnostic image/certificate/logs for inspection. Reboot
unloads a previously loaded diagnostic driver. It does not delete files or
certificates during rollback, nor enable the native driver automatically.
The test deliberately skips a hardware-initialization path; power/thermal
behavior is unvalidated. Do not use it for sustained workloads.

Windows-side signing/run behavior has not been exercised on the phone yet.
The package builder validates the pinned input, branch targets, changed byte
allowlist, checksum, ZIP integrity, and unchanged BSP input on the host.

Microsoft documentation:
- https://learn.microsoft.com/en-us/windows-hardware/drivers/install/kernel-mode-code-signing-requirements--windows-vista-and-later-
- https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.security/set-authenticodesignature?view=powershell-5.1

Windows31 adds CTPM Package(CORE_TOPOLOGY,8) after the diagnostic copy reached
Idle_CoreTopology.c:169 and asserted. The Windows script requires that live
resource before another attempt. A rolled-back state is archived, not erased.
