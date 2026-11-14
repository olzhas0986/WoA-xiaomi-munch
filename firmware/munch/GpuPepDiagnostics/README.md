# PEP recovery-state diagnostics

Run collect.cmd as administrator in the recovered Windows28 with qcpep startup
still disabled. The collector does not start/enable/install a driver, change
BCD or registry settings, or start/stop an ETW session. It writes a temporary
collection and a ZIP on the current user's Desktop.

Included: five-device status/properties, service configuration, actual driver
hashes, selected PEP registry parameters, prior installer logs, SetupAPI log,
System/Kernel-PnP event exports, registered trace-provider list, PEP device-stack
query and available existing PEP ETL files. Firmware-table snapshots describe
the current recovery boot, not the earlier hung boot. Optional errors are
recorded rather than aborting all collection. Trace copies are bounded to their
initial size (64MiB/file, 128MiB aggregate copied-file budget) and can contain
an unfinished ETL tail if a logger still owns them. No new hang is requested.

Copy the Desktop munch-pep-diag-*.zip to the Linux project under out/kona-gpu/.
Host packaging checks file integrity; Windows cmdlets still run on the phone.
