# PEP boot trace preparation

Windows29 boots with qcpep disabled; Windows29 previously hung when qcpep
was boot-start. The recovery snapshot confirmed the original driver hash,
CPU/idle override values and disabled service. It contained no ETL: the native
qcpep-rpmh AutoLogger uses LogFileMode 0x400 (memory buffering).

prepare.cmd requires administrator and qcpep Start=4. It creates only its
own MunchPepBoot AutoLogger configuration and local diagnostic files. It does
not start/enable/install qcpep or change BCD, firmware or PEP policy. The native
Qualcomm logger is retained unchanged. Existing unrelated MunchPepBoot config
is rejected; a GUID/ownership record guards repeated setup and rollback.

Boot logger: sequential disk mode 1, 64KiB buffers, 4..32 buffers, 1s flush,
16MiB/file, FileMax 4. FileCounter is never modified. Multiple boot files keep
the hung boot available after returning to recovery Windows. Providers:

* Microsoft-Windows-Kernel-Pep, GUID 5412704E-B2E1-4624-8FFD-55777B8F7373,
  confirmed in the device's logman provider listing.
* Microsoft-Windows-Kernel-PnP, GUID 9C205A39-1250-487D-ABD7-E831C6290539,
  confirmed in its event records.
* Kona RPMH WPP GUID 2C89C855-6301-41F9-BF56-63416DFE9CA9, from the pinned
  qcpep.wd8250.inf's native AutoLogger definition.

The two manifest providers request event stack traces. RPMH is a classic WPP
provider with all legacy enable flags; formatted WPP messages may still require
private symbols. The preparation starts/queries/stops a uniquely named live
file-trace test with logman -ets and verifies a nonempty ETL file while PEP
stays disabled. This tests runtime file tracing, not early-boot logger activation
or a guaranteed flushed trace during a hard hang. Disk drivers may not be ready
when early boot tracing begins. Boot activation requires separate verification.

Use prepare.cmd status after the next normal Windows boot to query the actual
MunchPepBoot session and list its ETL files. Do not enable PEP during preparation.
prepare.cmd rollback stops only this owned trace if active and removes only
its registry key. Existing trace files and PEP settings are retained.

collect.cmd is the updated read-only collector. It includes .etl.NNNN boot-file
suffixes, preparation logs and canonicalizes the TEMP path before producing its
manifest (Windows short/long paths differed in the first collection).

Sources:
https://learn.microsoft.com/en-us/windows/win32/etw/configuring-and-starting-an-autologger-session
https://learn.microsoft.com/en-us/windows-server/administration/windows-commands/logman-create-trace

Readback correction: EnableFlags=FFFFFFFF is written as signed -1 but can be
returned as UInt32 4294967295 by the Windows registry provider. DWORD readback
now compares the low 32 bits of both values, retaining mismatch detection.
The existing owned, partially prepared configuration can be completed by
rerunning prepare.cmd; no state or trace files need to be removed.
