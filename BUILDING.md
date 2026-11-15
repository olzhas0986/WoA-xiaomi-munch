# Reproducible build

Базовые драйверы готовы. Следующий этап — ACPI-контракт и запуск Qualcomm PEP QCOM2519.

## Supported host

A recent x86-64 Linux distribution is expected. Arch Linux package names:

```sh
sudo pacman -S --needed base-devel git python python-pip clang llvm lld \
  acpica dtc android-tools mkbootimg
```

On Debian/Ubuntu install the equivalent packages: `build-essential`, `git`,
`python3`, `python3-venv`, `clang`, `llvm`, `lld`, `acpica-tools`,
`device-tree-compiler`, `android-sdk-platform-tools`, and `mkbootimg`.
Package names vary by release. `tools/bootstrap-deps.sh` stops and names any
missing command before downloading dependencies.

## 1. Clone and bootstrap

```sh
git clone <this-repository-url> munch-windows-arm64
cd munch-windows-arm64
make deps
```

This checks out Mu-Silicium commit
`42fe563791e51bf5500c2e470ed294ca0c94b97c` with its submodules and creates a
local `.venv`. No dependency checkout is committed into this repository.

## 2. Supply device inputs

Obtain `xbl.img` from the same stock firmware revision as the tested phone and
obtain the live `munch` DTB from a known-good Android or Linux boot image. Then:

```sh
make inputs XBL=/absolute/path/xbl.img DTB=/absolute/path/munch-live.dtb
```

Accepted SHA-256 values:

| File | SHA-256 |
|---|---|
| `xbl.img` | `696eaefeb4798b6c3427740232ae71006070b6bab079343cfe2a661363073c3b` |
| `munch-live.dtb` | `8b2beab345ca8c35ff7c39c7e3e526708c2da37ffa5af55d3784b42a1552d366` |

The strict check is intentional: addresses, protocol revisions and embedded
drivers can change between firmware releases. The importer extracts the needed
XBL modules locally and verifies every module during each build.

## 3. Build and verify

```sh
make stable
make verify
sha256sum out/munch-fresh/munch-uefi.img
```

`stable` enables the tested USB/UFS ACPI path and Qualcomm foundation through
PMIC/CPU preparation, but does not expose the unfinished `QCOM2519` PEP device.
SCM, RPEN, SPMI and core PMIC have reached Running / Code 0 on the phone.
PEP startup and GPU acceleration are not validated.
The image is an Android boot-header-v1 container holding an ARM64 relocation
shim, a 3 MiB UEFI FD and the verified live DTB.

`make verify` parses the final compressed firmware volume, checks unchanged
vendor-module hashes, ACPI checksums/resources, ARM64 PE machine types and then
executes the relocation shim under Unicorn.

For the unfinished initial PEP ACPI profile, use `make pep` followed by
`make verify-pep`; see [docs/PEP.md](docs/PEP.md). Build and verify each profile
before switching: both use the same generated firmware directory. Host
verification does not establish that a driver works on the phone.

## 4. Boot without flashing

```sh
fastboot devices
fastboot boot out/munch-fresh/munch-uefi.img
```

Immediately after the image transfer completes, disconnect the PC cable from
the phone. This must remove both data and VBUS: disconnecting data while leaving
the phone externally powered is insufficient. The current firmware attempts
the installed Windows boot automatically, waits up to about ten seconds for
external USB power to disappear, switches the port to host mode, and hands it
to Windows. Attach the OTG mouse after the Windows logo appears.

If the PC remains connected, USB host preparation is intentionally rejected;
Windows boot returns and the diagnostic fastboot endpoint starts. It is a
fallback, not the normal boot UI. At that endpoint logs can be collected with:

```sh
bash tools/collect-fastboot-log.sh
```

To retry booting the installed Windows partition from that fallback endpoint:

```sh
fastboot oem windows
```

Once the command returns `OKAY`, immediately remove the PC cable and connect
OTG within ten seconds. A disconnect after `OKAY` is explicitly preserved by
the firmware even if the USB acknowledgement completion event has not arrived.

## Windows installation

Windows deployment is intentionally separate from firmware compilation because
it repartitions and writes internal storage. Read
[docs/WINDOWS-INSTALL.md](docs/WINDOWS-INSTALL.md) completely before using the
recovery packages. The tested layout uses a dedicated 32 GiB Windows partition
and a 512 MiB ESP. Back up userdata and the stock partition table first.

## Clean rebuild

```sh
make clean
make stable
make verify
```

`python3 tools/clean-build.py` previews exact cleanup paths. `make clean`
checks for tracked files and nested repositories before deleting `out/`,
`Mu-Silicium/Build/`, the generated `munchFreshPkg` overlay and vendor copies,
generated ACPI AML and Python caches outside `.venv`. Imported device inputs
(including extracted XBL), dependency sources and their `.git`, `.venv`, and
vendor templates are retained. Cleanup refuses paths containing tracked files.

Shutdown and power management remain unstable. USB keyboard support has not
been confirmed on the latest profile; OTG hot detach in Windows is unstable.
