# Small boot image with delayed NTFS-to-RAM loading (R)

Build `make pmos-usb`. This reuses the confirmed P kernel/board DT and adds a
small BusyBox initramfs. The rootfs is absent from the boot image. The existing
confirmed embedded-rootfs Q image remains in out/baseline-pmos-ram.

Copy `out/pmos-rootfs/postmarketos-aarch64-console.tar.gz` to the root of the
existing NTFS USB partition, without extracting or formatting it. The loader
also accepts the same archive renamed rootfs.tar.gz. It checks the exact SHA256
of the confirmed Q rootfs, so a different archive requires deliberate inspection
and an updated hash; a filename match alone is insufficient.

```
fastboot boot out/pmos-usb/munch-boot.img
```

Nothing is mounted or extracted automatically. At the bootstrap prompt run:

```
pmos-load
```

The command launches a separate session, returns immediately, and the worker
waits 10 seconds. Connect the OTG hub, keyboard and NTFS stick during this time.
The default partition is /dev/sda1; an optional argument selects another USB sd
partition, for example `pmos-load /dev/sdb1`. The worker's console IO and session
are detached from the PC ACM terminal, so disconnecting that cable does not
send the worker its terminal hangup. Output is on the phone and also stored in
/run/pmos-load.log. A lock prevents duplicate concurrent loads.

After `PMOS READY in RAM`:

```
pmos-enter
cat /etc/os-release
apk --version
```

The worker checks USB ancestry, available RAM and the archive hash. NTFS3 is
mounted ro,nosuid,nodev,noexec, without force or repair. It streams extraction
into a 1 GiB tmpfs at /pmos and unmounts the stick on success. The archive itself
stays on the stick; it is not copied wholesale into RAM. Slow USB can still make
the hash/extraction passes take several minutes. Bash enters the same confirmed
Nura/postmarketOS userspace; BusyBox stays PID1 and services are not started.

For errors:

```
cat /run/pmos-load.log
cat /run/pmos-load.status
```

Status 0 means the worker succeeded. Error cleanup releases the lock and
unmounts the USB partition when possible. If extraction has started, partial
RAM contents remain and a reboot is required to retry; failures before that
point can be retried with pmos-load. A missing /dev/sda1 after the 10-second
pause reports an error instead of scanning or mounting unrelated devices.
Android/UFS partitions are not accessed.

Host validation: 21 tests passed, including 10-second ordering, read-only mount,
archive/hash failure cleanup and a real detached-process test that sends SIGHUP
to the parent session while the simulated load continues. Packaged init and
BusyBox match their inputs; no rootfs file is present; kernel is unchanged from
P. Actual phone USB load/disconnect test is pending.

Boot image SHA256:
0f9d5b04c4ad6b91c1ef55b214cf9e7dfee80dab003294cef0531ed638c78994.

Hardware report: R successfully verified SHA256, extracted rootfs into RAM,
unmounted the NTFS stick, and printed PMOS READY. Native Wi-Fi follow-up:
[pmos-wifi.md](pmos-wifi.md).
