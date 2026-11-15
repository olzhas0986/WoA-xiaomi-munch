# Initial Qualcomm PEP startup scaffolding

Базовые драйверы готовы. Следующий этап — ACPI-контракт и запуск Qualcomm PEP QCOM2519.

This directory retains the initial installer, reduced policy and owned-package
rollback for the next developer. PEP startup is not validated. GPU acceleration,
CPU frequency control, thermal control and reliable power transitions are not
provided by this scaffolding. Read [docs/PEP.md](../../../docs/PEP.md) first.

The unfinished ACPI profile retains CPU paths `_SB.SYSM.CLUS.CPU0` through
`CPU7`, SCM/RPEN/SPMI/PMIC, and adds `PEP0` with `QCOM2519`, `PNP0D80`,
reference `_CRS` interrupts, `INTR`, `GEPT` and optional zero/empty queries.
Interrupt ordering, IPC, shared memory, thermal and board resources still need
validation. No GPU or SMMU device is exposed.

Original package source: WOA-Project/windows_silicon_qcom_kona, commit
`22221a09e02cb7054792427af60299b1c34d3c3e`. The optional packager copies
`qcpep.wd8250.inf/.cat`, `qcpep8250.sys` (1.0.2140.0000), and
`PPMSettings-8250Profiles.wd.ppkg` unchanged, with the BSP license and original
WOA catalog certificate. It requires the local BSP described in docs/PEP.md.
No driver binary is part of this repository.

Build the research firmware with `make pep`, then `make verify-pep`.
`python3 tools/prepare-kona-gpu-bootstrap.py --stage pep` optionally builds
`out/kona-gpu/munch-gpu-pep-bootstrap-twrp.zip` and
`out/kona-gpu/munch-pep-initial-windows.zip`. The portable ZIP contains
`GPU28D/`; that legacy folder name is retained for script/package consistency,
not as a hardware success claim. The recovery package copies only to
`ESP/MUNCH/GPU28D` with the ESP initially unmounted. It does not install a driver.
Do not run the installer until the ACPI review and recovery plan are ready.

In administrator Windows, `GPU28D/setup.cmd` attempts installation and startup;
`setup.cmd report` writes status, and `setup.cmd rollback` removes only the
owned, unshared package and restores saved provisioning/global settings. Reports
and state are under `C:\munch-gpu-pep-core`. Normal rollback requires a bootable
Windows; offline recovery is needed otherwise. Use `make stable` for the base
firmware after rollback.

The installer checks active test signing, existing publisher trust and four
Code 0 foundation devices. It records provisioning/PoFx/autologger state,
requires a disabled device before installing the original INF, checks the
stopped service, saves native parameters, and verifies explicit policy DWORDs
before enabling. It preserves resumable pre-install state and original backups.
The policy reduces CPU/system idle and performance management; it cannot
guarantee safe initialization. These guards need Windows validation and do not
complete the board contract. No automatic reboot or shutdown is requested.
