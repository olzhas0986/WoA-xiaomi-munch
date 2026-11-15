# Munch firmware research baseline

Базовые драйверы готовы. Следующий этап — ACPI-контракт и запуск Qualcomm PEP QCOM2519.

Confirmed hardware and boot instructions are in [STATUS.md](../../STATUS.md)
and [README.md](../../README.md). PEP startup is not validated; GPU acceleration
and Windows touch do not work. Shutdown/power management and OTG hot detach
remain unstable. USB keyboard support on the latest profile is unconfirmed.

## Source boundaries

- `BootManager/`: retain automatic Windows boot, cable/VBUS wait, USB host
  preparation, UFS/partition access, diagnostic fastboot fallback and FACS
  installation. FACS is needed by Windows hardware-configuration queries even
  on this reduced ACPI platform; it is independent of the PEP board contract.
- `Acpi/DSDT-pep-prep.asl`: preserve USB/UFS resources and eight CPU UIDs in
  the preparation namespace. No processor idle states or PEP device are added.
- `Acpi/SSDT-GPU-PMIC.asl`: four foundation devices used by `make stable`.
  Earlier SCM/RPEN/SPMI tables remain useful for isolated foundation checks.
- `Acpi/SSDT-GPU-PEP.asl`: unfinished initial reference contract used only by
  `make pep`. Board resources and driver startup still require research.
- `GpuBootstrap`, `GpuRpen`, `GpuSpmi`, `GpuPmic`: retain individual foundation
  package sources, guards, reports and owned-package rollback.
- `GpuPepPrep`: retain the read-only CPU namespace/foundation readiness check.
- `GpuPep`: retain initial driver installer/policy/rollback scaffolding and its
  defensive install-state checks. These are not called by the firmware build.
- `Recovery/`, `Serial/`, `bootshim.S`: retain recovery, console and image
  hand-off sources. Recovery deployment is separate from temporary boot.

The root history has four import/documentation commits. The firmware import
`c29ba59` and package import `1cbcdc6` combine several development stages, so
this baseline was prepared by reviewing source dependencies rather than
reverting either whole commit. Boot/USB/foundation code and original notices
are preserved. See [docs/PEP.md](../../docs/PEP.md) for the next research steps.

`tools/prepare-munch.py` generates the dependency platform overlay and local
vendor copies from these sources and the pinned inputs. `make clean` removes
those copies and build outputs; it retains dependency source repositories,
inputs, environments and vendor metadata templates.
