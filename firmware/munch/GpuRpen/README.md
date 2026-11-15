# RPEN foundation

Confirmed on POCO F4 / munch: SCM (`qcscm`), RPEN (`QCRPEN`), SPMI (`qcspmi`)
and core PMIC (`qcpmic`) have reached Running / Code 0. This directory retains
the individual RPEN installer (`QCRPEN`, `QCOM2533`). Startup does not
validate every driver operation or GPU/power support.

Базовые драйверы готовы. Следующий этап — ACPI-контракт и запуск Qualcomm PEP QCOM2519.
See [docs/PEP.md](../../../docs/PEP.md). The normal firmware is built with
`make stable` and `make verify`; it exposes all four foundation devices,
without an active PEP device. GPU acceleration and Windows touch do not work.
Shutdown/power management and OTG hot detach remain unstable; keyboard support
on the latest profile is unconfirmed.

## Source and ACPI

Source BSP: [WOA-Project/windows_silicon_qcom_kona](https://github.com/WOA-Project/windows_silicon_qcom_kona),
commit `22221a09e02cb7054792427af60299b1c34d3c3e`.
The ARM64 driver version is 1.0.2100.0000. INF/CAT/SYS are copied unchanged,
with the original BSP license and public WOA KMCI catalog certificate
`946CF507369A80E65F2B58BEBF5D02CC159A484D`. No private signing key is used.
The optional local BSP checkout is described in docs/PEP.md.

The device follows the reference reset-protection node without MMIO,
interrupts or configuration methods. The current BSP matches QCOM2533; do not
reuse the older reference QCOM25E1 ID.

## Individual installation tool

`python3 tools/prepare-kona-gpu-bootstrap.py --stage rpen` creates
`out/kona-gpu/munch-gpu-rpen-bootstrap-twrp.zip`. Install only with the ESP
unmounted; the recovery installer checks device, GPT, geometry and hashes,
then copies to the legacy `ESP/MUNCH/GPU24` folder. It does not install a
Windows driver or replace EFI/BCD. Differing existing files stop installation.

Follow the root [README boot sequence](../../../README.md): immediately remove
the PC cable/VBUS after `fastboot boot` finishes, allow automatic Windows boot,
then connect OTG mouse after the Windows logo. The diagnostic `fastboot oem
windows` command is a fallback only.

In administrator Windows, mount the ESP with `mountvol S: /S` (choose an unused
letter) and run `S:\MUNCH\GPU24\setup.cmd`. It requires active test signing,
the existing publisher certificate and Code 0 for SCM. It changes
neither BCD nor certificate stores.

`setup.cmd report` records status; `setup.cmd rollback` removes only an owned,
unshared package. SCM rollback also restores signing settings it changed;
other foundation packages leave prerequisite drivers/signing intact. No
automatic shutdown or reboot is requested. Recovery/offline removal may be
needed if Windows cannot boot. The read-only recovery log collector retrieves
the install reports. These tools are optional and are not run by `make stable`.
