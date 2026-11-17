# PEP test on the previous port's firmware

The previous bring-up (`~/workspace/win11`, own Mu-Silicium platform
`munchFreshPkg`) has a DSDT with the Kona BSP numbering, staged driver
packages for SCM, RPEN, SPMI, PMIC and PEP, and a signed late-load test for
a patched `qcpep8250`. Its firmware and packages are pinned to its own
partition layout: ESP entry 35, MSR 36, Windows 37, fixed partition GUIDs,
and the SHA-256 of the 64-entry partition array (`fcd05950…`).

## Layout

This repository's installer can reproduce that layout exactly:

```sh
tools/make_installer.py --gpt out/sda-gpt-after.bin \
    --target esp --target win --target msr \
    --match-table ~/workspace/win11/out/munch-fresh/repartition32/primary-table.new.bin
```

It reuses the reference GUIDs, numbers ESP/MSR/Windows 35/36/37 and refuses
to build unless the resulting partition array is byte-identical to the
reference. The BCD is generated for those GUIDs. With that, the previous
port's `munch-uefi-windows31-ctpm.img` (which checks the GUIDs, LBAs, entry
count and a 4Kn NTFS volume) and its TWRP packages (which check the array
hash) apply without changes.

## Driver for the test

```sh
tools/patch_qcpep_display_tcs.py qcpep8250.sys --with-lmh -o out/qcpep/qcpep8250-lmh-disptcs.sys
tools/package_pep_disptcs.py ~/workspace/win11/out/kona-gpu/munch-pep-lmh-test.zip \
    out/qcpep/qcpep8250-lmh-disptcs.sys -o out/qcpep/munch-pep-lmh-disptcs-test.zip
```

The result is the previous `MunchPepLmh` package with the display TCS fix
added to its diagnostic driver (see [rpmh-config.md](rpmh-config.md)).

## Sequence

1. Recovery: flash the installer zip (image on the USB drive), finish the
   first Windows boot with this repository's UEFI.
2. Recovery: flash the previous port's stage packages in order:
   `munch-gpu-scm`, `-rpen`, `-spmi`, `-pmic` bootstrap zips and
   `munch-gpu-pep-prep`. They only copy files to `ESP\MUNCH\GPU23…27`.
3. `fastboot boot munch-uefi-windows31-ctpm.img`. It boots Windows on its own;
   when it prints `Auto Windows: disconnect PC cable`, unplug the PC cable
   within 10 s, then attach the OTG keyboard/mouse once Windows is up (the
   firmware switches the port to host and keeps VBUS on only if the PC
   cable is gone at that moment).
4. Administrator PowerShell: `mountvol S: /S`, run each `S:\MUNCH\GPU2x\setup.cmd`
   in order and check that the four services report code 0.
5. PEP package: `munch-pep-gpu28e.zip` (`tools/package_pep_install_disabled.py`),
   run `GPU28E\setup.cmd`. It is GPU28D up to the verified policy; instead of
   enabling the device it sets `qcpep` Start = 4, so the original driver,
   which stops at the display TCS gate, never starts. Stage 27 is a
   diagnostic DSDT check pinned to an older DSDT and is skipped.
6. Extract `munch-pep-lmh-disptcs-test.zip`, then `prepare.cmd` → reboot with
   the same firmware → `status.cmd` (expect Start 4, problem 22, Stopped) →
   `start.cmd`. Its `late.ps1` requires active test signing, a page file
   and crash dumps enabled. If it returns, run `collect.cmd`.

## Recovery after a crash

Boot `munch-uefi-windows28-pep.img` from the previous port. Its tables lack
PEPH, so qcpep fails early (code 31) and Windows reaches the desktop. Then,
as administrator:

```bat
sc.exe config qcpep start= disabled
pnputil.exe /disable-device "ACPI\QCOM2519\0" /force
```

and in the `MunchPepLmh` folder `collect.cmd`, then `rollback.cmd` (restores
the original ImagePath, keeps Start = 4), then reboot. `GPU28E\setup.cmd
rollback` is different: it removes the PEP package.

If Windows28 does not boot either, set `Start = 4` offline from WinPE
(`reg load` of `\Windows\System32\config\SYSTEM`, `ControlSet00N\Services\qcpep`).
The previous port's `tools/collect-windows-setup-logs.py` reads minidumps
and logs from root TWRP (`--full-dump` for MEMORY.DMP).

The previous port's Mu-Silicium tree (commit 42fe563) is at
`~/win11/Mu-Silicium`; Windows31 is built with
`MUNCH_GPU_FOUNDATION=6 MUNCH_USB_ACPI=1 MUNCH_UFS_ACPI=1`. The test does not
need a rebuild.

## Open points

- Active requests to the display RSC without dedicated active TCSs: the
  driver accepts the configuration, its runtime behaviour is untested.

## Result 1: display TCS fix

With the LMH + display TCS copy the driver passed the RPMh initialisation
and stopped later with bugcheck 0x14E (SOC_CRITICAL_DEVICE_REMOVED,
parameter 1 `'qpe0'`). The dump was still in `pagefile.sys` (Windows copies
it out only on the next boot) and was read from recovery with
`tools/win_logs.sh 37`. Stack: `+0x212e8c → +0x214fbc → +0x1db000`, which
calls `KeBugCheckEx(0x14E)` when `InitializePppFramework` (RVA 0x115288)
returns an error; the saved status was `0xC0000034`
(STATUS_OBJECT_NAME_NOT_FOUND). That function first evaluates the ACPI
method `PPPM`, which the previous port's SSDT did not define.

`port/prev-port/0001-ssdt-pep-add-pppm.patch` adds `PPPM` returning the
resource list of the Qualcomm SDM8250 DSDT (alioth), limited to the 44 IDs
this driver build contains. Firmware built from the previous port with that
patch (`MUNCH_GPU_FOUNDATION=6 MUNCH_USB_ACPI=1 MUNCH_UFS_ACPI=1`):
`out/munch-uefi-windows32-pppm.img`. The unchanged rebuild reproduces the
windows31 DSDT and SSDT hashes, so the patch is the only ACPI difference.

## Result 2: PPPM present, PPRR empty

The same 0x14E stop, now with status `0xC014000F`
(STATUS_ACPI_INVALID_DATA). `InitializePppFramework` evaluates `PPRR` after
`PPPM`; the PPRR parser (RVA 0x117C78) rejects an empty package with that
status. PPRR is a flat list of triples: a `PPP_RESOURCE_RANGE_INFO_*` class
(36 known to the driver) and the first and last `PPP_RESOURCE_ID_*` of
that class.

The Xiaomi pipa DSDT in Silicium-ACPI (SM8250-AC, same PMIC set) is
written for this newer PEP generation (it has CTPM and PEPH) and carries
both lists. The patch, renamed `0001-ssdt-pep-ppp-framework.patch`, now uses
its PPPP (57 resources) and PRRP (9 triples), every name checked against
the driver's tables. Firmware: `out/munch-uefi-windows33-pprr.img`.

## Result 3: PPRR accepted

Same 0x14E, status now `0xC0000001` (`tools/pep_dump_status.py` reads it
from the dump). PPPM and PPRR parse; the failure is in the next steps of
`InitializePppFramework`:

- RVA 0x1177A8 classifies every registered resource. GPIO DV ranges get
  type 1 or 2; others are looked up (RVA 0x11EA10, 0x11F1B8; apparently the
  RPMh command DB) and get type 1 or 5.
- RVA 0x116008 walks a table of three required types (1, 5, 2 at RVA
  0x1A0030), and for each match calls a handler (RVA 0x11F780, 0x11DA20,
  0x123860). Its status starts as `0xC0000001` and is returned unchanged if
  no resource matches; a handler can also fail.
- RVA 0x1162C8 follows.

The triage dump does not show which of these failed: the driver's state and
its WPP in-flight log are not in it, and qcpep's own dump callback faults
(`+0x46408 → +0xF3E8C`) while the dump is written.

## Attempt 4: full pipa PEP0 configuration

Instead of adding PEP0 methods one crash at a time,
`tools/import_pipa_pep0.py` copies all 58 PEP0 objects the SSDT lacks from
the pipa DSDT (device power configurations, DCVS, CPU/GPU/camera/PCIe
settings, resource-to-device maps) plus the eleven `\_SB` names they use
(PSUB, SOID, PLST, SVMJ, STOR, PUS3, DPP0/1, MPP0/1, BSID). THTZ (40 thermal
zones) and NPUR (AGR0) are left out because what they reference does not
exist. Device paths inside the packages are strings, so absent devices do
not break compilation.

```sh
tools/import_pipa_pep0.py pipa/Decompiled/DSDT.dsl <SSDT with 0001 applied> -o SSDT-GPU-PEP.asl
```

Firmware: `out/munch-uefi-windows34-pep0.img`. Rollback: the windows33
firmware (`out/munch-uefi-windows33-pprr.img`), whose SSDT is the 0001 patch
alone.

## Result 4: same status with the full PEP0

windows34 (full pipa PEP0) stopped the same way: 0x14E, `InitializePppFramework`,
status `0xC0000001`. The missing PEP0 configuration is therefore not the cause.
`pep_dump_status.py` now derives the driver base from the return addresses on
the captured stack instead of assuming the low bits match the RVA.

## Attempt 5: tagged STATUS_UNSUCCESSFUL sites

33 instructions between RVA 0x100000 and 0x130000 load `0xC0000001`. With
`--tag-unsuccessful` each gets its own failure value (an ORR bitmask
immediate with bit 31 set; none of the 33 values occurs anywhere in the
original driver, so no comparison changes):

```sh
tools/patch_qcpep_display_tcs.py qcpep8250.sys --with-lmh \
    --tag-unsuccessful out/qcpep/unsuccessful-tags.json -o out/qcpep/qcpep8250-lmh-disptcs-tagged.sys
tools/package_pep_disptcs.py munch-pep-lmh-test.zip out/qcpep/qcpep8250-lmh-disptcs-tagged.sys \
    --tags out/qcpep/unsuccessful-tags.json -o out/qcpep/munch-pep-lmh-disptcs-tagged-test.zip
tools/pep_dump_status.py pep.dmp --tags=out/qcpep/unsuccessful-tags.json
```

The next dump names the exact site that produced the failing status.

## Result 5: the failing site is the Command DB lookup

The tagged driver stopped with status `0xF0000007`, the tag of RVA 0x11F384.
That is the end of RVA 0x11F1B8, called from the resource classification
(RVA 0x117910) for every non-GPIO resource in PPPM. It derives a Command DB
name from the resource (RVA 0x11EA10: `smpa1`, `ldoc5`, `bobc1`, `lnbclka2`,
`rfclka1`, `divclkc1`, ...), queries the Command DB (RVA 0x114600; the DB
address is read from AOP message RAM at 0x0C3F000C, as in Linux) and returns
STATUS_UNSUCCESSFUL unless the entry exists, its slave version is 1.x and its
aux data is 4 bytes long.

So at least one PPPM resource from the pipa list has no such entry on
munch. Linux SM8250 only uses `rfclka1`/`rfclka3` and no `divclk*`, which
makes RFCLK2_A, DIVCLK1/2_A and DIVCLK1_C the first suspects, but the real
Command DB decides:

```sh
adb shell 'mount -t debugfs none /sys/kernel/debug; cat /sys/kernel/debug/cmd-db' > out/cmd-db.txt
tools/cmd_db_check.py out/cmd-db.txt work/prev-port/firmware/munch/Acpi/SSDT-GPU-PEP.asl
```

Resources reported as MISSING or FAIL are dropped from PPPP (and the PPRR
ranges narrowed if needed).

## Result 6: Command DB on munch

`RpmhPeek` saved the Command DB (`\cmddb.bin`). `tools/cmd_db_check.py`
shows 8 of the 51 non-GPIO pipa resources have no entry on munch:
`smpa1`, `smpa2`, `smpc2`, `smpc5`, `ldoa8`, `rfclka2`, `divclka1`,
`divclka2`. All others are VRM v1.0 with 4 bytes of aux data, as qcpep
requires. `smpa1` is the first resource classified, which is where init
stopped.

`port/prev-port/0002-ssdt-pep-drop-resources-missing-from-cmd-db.patch`
(on top of 0001, without the pipa PEP0 import) removes them from PPPP.
Firmware: `out/munch-uefi-windows35-cmddb.img`.

## Result 7: past initialisation, CLOCK_WATCHDOG_TIMEOUT

With windows35 the 0x14E is gone: qcpep completes initialisation. The system
then stops with CLOCK_WATCHDOG_TIMEOUT (0x101, a processor stopped
answering clock interrupts) and the dump hangs at 0%, so `pagefile.sys`
stays empty and the ETW buffers of the test are never flushed.

First hypothesis: once PEP is up, Windows starts using the processor idle
states it manages, and a core that enters power collapse does not come
back. Test: the same run with idle states disabled
(`powercfg` SUB_PROCESSOR IDLEDISABLE = 1). If the hang disappears, the idle
state description (CPU `_LPI`, CTPM) or PSCI is the next target; if not,
the RPMh path (display RSC without active TCS) is.

The idle test did not change anything (IDLEDISABLE = 1 confirmed with
`powercfg /qh`; `start.cmd` prints, the phone hangs for a while, then 0x101).
The previous port's 0x101 dump (`out/kona-gpu/watchdog-full`) had CPU6 hung
with a PEP frame chain through the LMh helper 0x5C50 and a pending write of
0x3A to the block mapped at 0x18350800. The driver maps two LMh blocks,
0x18350800 and 0x18358800 (the SM8150 layout; its PDB is `qcpep8180.pdb`),
and munch's DT has no LMh there. Besides 0x5C50, three more functions touch
them: 0x5520 (status read, result unused), 0x5B20 and 0x5B88 (writes),
reached from eight call sites, so the two NOPs of `--with-lmh` do not cover
the runtime paths.

## Attempt 8: no LMh MMIO

`--no-lmh-mmio` makes all four functions return immediately:

```sh
tools/patch_qcpep_display_tcs.py qcpep8250.sys --with-lmh --no-lmh-mmio \
    --tag-unsuccessful out/qcpep/unsuccessful-tags.json -o out/qcpep/qcpep8250-lmh-disptcs-nolmh.sys
tools/package_pep_disptcs.py munch-pep-lmh-test.zip out/qcpep/qcpep8250-lmh-disptcs-nolmh.sys \
    --tags out/qcpep/unsuccessful-tags.json --no-lmh-mmio -o out/qcpep/munch-pep-lmh-disptcs-nolmh-test.zip
```

Firmware stays windows35.

Result: same 0x101, dump stuck at 0%. The ETL files hold only the logfile
header although the session flushes every second, so the whole system stops
almost at once and nothing reaches the disk.

## Attempt 9: bisect with a breakpoint

`--brk-at RVA` puts `brk #0xF000` at RVA; reaching it gives
KMODE_EXCEPTION_NOT_HANDLED (0x1E) and a normal dump. First point: RVA
0x215230, the success branch after the core init 0x1DB000 (which contains
InitializePppFramework) in the PEP start routine 0x214C18. 0x1E means the
hang is after it (0x20ACB0, 0x7F9F8, ... or the runtime), 0x101 that it is
inside 0x1DB000 after the PPP framework.

```sh
tools/patch_qcpep_display_tcs.py qcpep8250.sys --with-lmh --no-lmh-mmio --brk-at 215230 \
    --tag-unsuccessful out/qcpep/unsuccessful-tags.json -o out/qcpep/qcpep8250-brk215230.sys
tools/package_pep_disptcs.py munch-pep-lmh-test.zip out/qcpep/qcpep8250-brk215230.sys \
    --tags out/qcpep/unsuccessful-tags.json --no-lmh-mmio --brk-offset 203a30 \
    -o out/qcpep/munch-pep-brk215230-test.zip
```

Result: 0x101 again, so the hang is inside 0x1DB000 after the PPP framework.
(The previous port's 0x101 was different: one core hung in the LMh helper
and the dump completed; now the whole system stops and the dump does not
start.) Next point: RVA 0x1DBA24, between 0x1F990 and 0x1D148, which splits
the about twenty remaining calls of 0x1DB000 in half
(`out/qcpep/munch-pep-brk1dba24-test.zip`).

Result: 0x101 with the breakpoint at 0x1DBA24 and at 0x1DB7DC, so the hang
is in one of the first two calls after the PPP framework: 0x72848 or
0xF2490. 0x72848 creates two RPMh clients from the table at RVA 0x1C0710,
`vdd_arc_hlos` on the apps RSC (id 2) and `vdd_arc_display` on the display
RSC (id 9, the controller whose TCS requirement was lowered from 4 to 2),
resolves `cx.lvl`, `mx.lvl`, `xo.lvl`, `mmcx.lvl` in the Command DB and
registers them (0x105EF8, 0x25268). Next point: 0x1DB56C, between the two
calls (`out/qcpep/munch-pep-brk1db56c-test.zip`).
