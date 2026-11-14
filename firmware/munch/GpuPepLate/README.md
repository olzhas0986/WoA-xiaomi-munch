# Late PEP activation test

The supplied 040124-13203-01.dmp is a triage dump for old bugcheck 101,
parameters 18/0/ffff9781dcca2980/6, not the reported PAGE_FAULT_IN_NONPAGED_AREA.
The new ETL archive has two capped 16MiB traces for disabled PEP boots and
an unfinalized recovery trace. All 207 physical buffers of the latter were
recovered (8586 records, no malformed-buffer errors). It shows the old
C000000E AddDevice rejection. No current 0x50 dump or exact faulting PC was
established. The likely early-boot timing limitation remains an inference.

This test separates boot from PEP AddDevice: leave service disabled, persist
the PEP device's disabled state, boot Windows29 to desktop, then explicitly
activate PEP with a fresh live ETL session and active pagefile/dump settings.
No driver is reinstalled and no binary/firmware/PEP policy is patched.

1. Run prepare.cmd as administrator. It requires qcpep Start=4, requests
   pnputil /disable-device ACPI\QCOM2519\0 /force if needed, and reports status.
2. Boot the existing Windows29 image with fastboot boot, then run status.cmd.
   Require Start=4, device problem 22 and stopped PEP before the next phase.
3. Run start.cmd only for the requested live test. It validates Windows29's
   PEPH contract, the saved CPU/idle test policy, four ready prerequisite
   services, an active pagefile and enabled crash dumping. A fresh 32MiB
   sequential trace is started/queried before changing service startup to
   demand and enabling this one PEP device. This avoids early boot activation.
4. If Windows remains running, startup is restored to disabled and the live
   trace is stopped/flushed in finally. This block cannot execute after a
   kernel crash or hard hang. In that case boot Windows28, set qcpep Start=4
   with sc.exe config qcpep start= disabled, then collect logs/dumps.
5. collect.cmd copies logs, ETL files, crash-control configuration and available
   minidumps into a Desktop ZIP. Minidump contents must be checked; date-based
   filenames alone do not establish which crash they belong to.

The fresh live trace uses the same Kernel-Pep, Kernel-PnP and native Kona RPMH
provider GUIDs already tested on this phone, with a 1s flush interval. Unlike
boot AutoLogger configuration it does not request event stack extensions;
a real crash dump is still needed to establish a faulting instruction. A
nonempty trace or enabled dump setting does not guarantee a captured crash.
If enabling requests reboot, the script restores disabled startup and asks
for collection rather than repeating the early-boot test.
