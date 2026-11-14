# Embedded postmarketOS/Nura userspace in RAM (Q)

Build: `make pmos-ram`. Requires the confirmed P kernel/DT and the inspected
export in out/pmos-rootfs. Boot only:

```
fastboot boot out/pmos-ram/munch-boot.img
```

The boot image is about 154 MiB and remains within the unchanged 256 MiB loader
container contract. No addresses, reserved-memory map or bootloader limits were
raised. Actual bootloader acceptance of this larger image still needs hardware
validation. It includes the compressed rootfs; the USB stick is not required.

Wait for `PMOS READY in RAM. Run: pmos-enter`, then type:

```
pmos-enter
cat /etc/os-release
apk --version
uname -a
exit
```

The local keyboard or existing PC ACM shell can run the command. BusyBox remains
PID1; pmos-enter starts Bash in a chroot with runtime mounts. exit returns to the
bootstrap shell. Services, OpenRC boot and graphical UI are not started. This is
a userspace test under the existing board kernel, not a standalone device port.
Package downloads are not available until a network interface is configured.

The archive identifies itself as Nura edge (ID=nura). This matches the pinned
pmaports os-release file exactly; the project announced the rename on 2026-09-27:
https://nura.eco/blog/2026/09/27/nura-rename/
Do not rewrite the distro identity to disguise the change.

Archive: 149555353 compressed bytes, 448281641 regular-file bytes, 6139 members.
SHA256: 5be1f8db7ca7cbe4ac5e278f4e7a5fe78ab6567fab9f55b5a282b8f5b4c0fbf8.
The stream was inspected without extracting/executing on the host: path and
symlink-ancestor checks passed and no device nodes/FIFOs were found. AArch64 ELF
headers were checked for bash, BusyBox and apk. Inspection: out/pmos-rootfs/inspection.json.
The generic Trailblazer kernel/boot files are excluded by the export recipe;
its package metadata remains, so the archive must not be treated as a munch
installation image or have generic kernel upgrades applied to our boot chain.

pmos-prepare verifies the embedded archive's exact hash, requires at least
1.5 GiB MemAvailable and extracts into a capped 1 GiB tmpfs at /pmos. Both the
compressed file and extracted root coexist in RAM. No storage is mounted or
written. Extraction failure leaves the bootstrap shell and partial RAM root
available for diagnosis; reboot is the clean retry. pmos-enter refuses a root
that is not marked ready on the expected tmpfs. The chroot has /dev access for
terminals and is not a security sandbox.

Host validation: 16 tests passed, shell syntax checked, embedded rootfs/init
hashes matched the inputs and packed kernel matched confirmed P. Original P
fallback image unchanged. Boot image SHA256:
909cabee151f72602b2e6a064c7aff6f727faf3927b21ae59911b7f1b36d2e36.
Hardware userspace result: confirmed by user. pmos-enter opens Bash 5.3;
os-release reports Nura edge (ID=nura); apk-tools 3.0.8-r0 reports aarch64;
uname reports our Linux 7.3.0-rc7 SMP PREEMPT aarch64 kernel. This confirms the
RAM extraction and basic musl/userspace execution, not full service/PID1 boot,
network access, GUI, or hardware acceleration.

A fallback copy and hashes are preserved in out/baseline-pmos-ram. The next
standalone boot experiment must keep this image intact and audit the generic
rootfs init scripts, fstab and runlevels before running OpenRC as the system
init. Do not start generic storage/mount services or change Android partitions
merely because the chroot works.
