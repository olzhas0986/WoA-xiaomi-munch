# Qualcomm PEP research starting point

Базовые драйверы готовы. Следующий этап — ACPI-контракт и запуск Qualcomm PEP QCOM2519.

The confirmed foundation is SCM (`qcscm`), RPEN (`QCRPEN`), SPMI (`qcspmi`)
and core PMIC (`qcpmic`), each Running / Code 0 on POCO F4 / munch. Windows 11
ARM64 boots to the desktop with eight CPUs, RAM, framebuffer/GOP, UFS, USB
mouse and USB storage. Keyboard support on the latest profile is unconfirmed.
PEP startup, GPU acceleration and Windows touch are not established. Shutdown,
power management and OTG hot detach remain unstable.

## Profiles and retained sources

- `make stable` / `make verify`: foundation profile 5. Includes the four
  foundation devices and `DSDT-pep-prep.asl` CPU paths, without `QCOM2519`.
- `make pep` / `make verify-pep`: unfinished profile 6. Adds `PEP0/QCOM2519`
  with reference interrupts, `INTR`, `GEPT` and optional query defaults in
  `SSDT-GPU-PEP.asl`. These are research inputs, not a completed board contract.
  Both profiles share a build directory; verify immediately after each build.
- `firmware/munch/GpuPepPrep`: read-only CPU namespace / foundation check.
- `firmware/munch/GpuPep`: initial driver installer, policy and rollback
  scaffolding. Its installation guards are retained, but it needs review and
  device validation before use. It is not invoked by either firmware build.
- `GpuBootstrap`, `GpuRpen`, `GpuSpmi`, `GpuPmic`: individual foundation
  installation tools and original package provenance.
- `tools/audit-kona-pep.py`: extracts native resource contracts from the pinned
  local BSP and inventories the upstream ACPI reference, including separate
  scopes. It does not install or patch drivers.

## Next work

Review the native INF resources and the full reference namespace against the
munch DTB. Check CPU path requirements, PEP interrupt ordering and triggers,
IPC binding, shared memory, thermal callbacks, firmware libraries, board clocks
and rails, and processor/system idle policy. Do not infer compatibility from
another board's identifiers or successful foundation startup. GPU/SMMU and
panel contracts require separate work.

The optional tools expect a local checkout at
`reference/windows_silicon_qcom_kona`, commit
`22221a09e02cb7054792427af60299b1c34d3c3e` from
[WOA-Project/windows_silicon_qcom_kona](https://github.com/WOA-Project/windows_silicon_qcom_kona).
This BSP is not required by `make stable` or `make pep`; it is not included in
the firmware image or redistributed here. `make deps` prepares Mu-Silicium and
host tools, not this optional checkout. Keep its files and license unchanged.

Before a driver startup test, prepare an offline recovery method for disabling
`qcpep` (`Start=4`) and keep Android/recovery bootable. Review the installer's
registry, provisioning and signing changes; its reduced policy is not proof
that initialization is inert. Change one contract at a time and record the
profile, input hashes and live device status. Host ACPI/package checks cannot
validate driver startup or power transitions.

Normal boot uses `fastboot boot out/munch-fresh/munch-uefi.img`, immediate PC
cable/VBUS removal after `OKAY`/`Finished`, then OTG mouse after the Windows
logo. UEFI automatically attempts Windows and waits about ten seconds during
host preparation. `fastboot oem windows` is a fallback diagnostic retry only.
