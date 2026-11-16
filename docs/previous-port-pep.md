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
3. `fastboot boot munch-uefi-windows31-ctpm.img`, then `fastboot oem windows`
   and swap the cable for the OTG keyboard/mouse within 10 s (that firmware
   switches the port to host and keeps VBUS on for Windows).
4. Administrator PowerShell: `mountvol S: /S`, run each `S:\MUNCH\GPU2x\setup.cmd`
   in order and check that the four services report code 0.
5. PEP package (`GPU28D`, from `munch-pep-fix-windows.zip`) installs the
   original `qcpep8250` and enables it. The original driver stops at the
   display TCS gate (bugcheck 0x14B), so expect a crash here; PEP must then
   be disabled (`Start = 4`, device code 22) before going on.
6. Extract `munch-pep-lmh-disptcs-test.zip`, then `prepare.cmd` → reboot with
   the same firmware → `start.cmd` → `collect.cmd`; `rollback.cmd` restores
   the native driver path. See `MunchPepLmh/README.md` in the package.

## Open points

- How the previous run disabled PEP after step 5 (the notes mention a
  recovery with the Windows28 firmware); not reproduced here.
- Whether the stage-27 check accepts the windows31 DSDT (it pins a DSDT
  hash from stage 27).
- Active requests to the display RSC without dedicated active TCSs: the
  driver accepts the configuration, its runtime behaviour is untested.
