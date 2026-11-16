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
