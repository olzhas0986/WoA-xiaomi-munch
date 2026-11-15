# Hardware status

Базовые драйверы готовы. Следующий этап — ACPI-контракт и запуск Qualcomm PEP QCOM2519.

Confirmed baseline: POCO F4 (`munch`), Snapdragon 870, 6 GB RAM, Mu-Silicium
UEFI and the input hashes in [BUILDING.md](BUILDING.md).

| Component | Result | Limitation |
|---|---|---|
| Windows 11 ARM64 | Desktop boots | Tested with IoT Enterprise LTSC 24H2 |
| CPU / RAM | 8 CPUs / 6 GB installed | About 5.34 GiB usable |
| Framebuffer / GOP | Working | 1080×2400; Basic Display output |
| ACPI core tables | Generated and verified | FACP, APIC, GTDT and CPU namespace |
| UFS | Working | Installation and internal Windows storage |
| USB mouse / storage | Working | Keyboard unconfirmed on the latest profile |
| SCM (`qcscm`, `QCOM250B`) | Running / Code 0 | Foundation startup confirmed |
| RPEN (`QCRPEN`, `QCOM2533`) | Running / Code 0 | Foundation startup confirmed |
| SPMI (`qcspmi`, `QCOM250C`) | Running / Code 0 | Foundation startup confirmed |
| Core PMIC (`qcpmic`, `QCOM252E`) | Running / Code 0 | Core interface; not all PMIC clients |
| PEP (`QCOM2519`) | Research starts here | ACPI contract and startup are not validated |
| GPU acceleration | Not working | No Adreno WDDM acceleration |
| Windows touch | Not working | Linux sources are reference material |
| Shutdown / power management | Unstable | Reliable power transitions are not established |
| Audio / cameras / modem / radios | Unknown | Not implemented or validated |

`make stable` exposes the four foundation devices and the preparation CPU
namespace, without a PEP device. Running / Code 0 confirms driver startup,
not every driver operation, GPU acceleration or working power management.
`make pep` is an unfinished initial ACPI profile; see [docs/PEP.md](docs/PEP.md).

Disconnect the PC cable immediately after `fastboot boot` finishes, removing
VBUS. UEFI automatically attempts Windows boot and waits about ten seconds for
external power to disappear during USB host preparation. Connect the OTG mouse
after the Windows logo. `fastboot oem windows` is only a manual retry from the
diagnostic fastboot endpoint. OTG hot detach after Windows hand-off is unstable
and can cause a reboot or crash. See [README.md](README.md) for the boot sequence.
