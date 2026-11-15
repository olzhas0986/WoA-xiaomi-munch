#!/usr/bin/env bash
set -euo pipefail
root=$(cd "$(dirname "$0")/.." && pwd)
mu="$root/Mu-Silicium"
[[ -d "$mu/.git" ]] || { echo "Mu-Silicium is missing; run: make deps" >&2; exit 1; }
[[ -f "$root/inputs/munch/xbl.img" && -f "$root/inputs/munch/live.dtb" ]] || {
    echo "Device inputs are missing; run: make inputs XBL=/path/xbl.img DTB=/path/munch.dtb" >&2
    exit 1
}
mkdir -p "$root/out/munch-fresh"
python3 "$root/tools/munch-acpi.py"
python3 "$root/tools/prepare-munch.py"
export WORKSPACE="$mu"
export PACKAGES_PATH="$mu/Platforms/Xiaomi:$mu/Common/Mu:$mu/Common/Mu_OEM_Sample:$mu/Mu_Basecore:$mu/Silicon/Qualcomm:$mu/Silicon/Silicium:$mu/Silicium-ACPI:$mu/Silicium-ACPI/Platforms/Xiaomi:$mu/Silicium-ACPI/Silicon/Qualcomm"
export EDK_TOOLS_PATH="$mu/Mu_Basecore/BaseTools"
export EDK_TOOLS_BIN="$EDK_TOOLS_PATH/Bin/Mu-Basetools_extdep/Linux-x86"
export PATH="$EDK_TOOLS_BIN:$EDK_TOOLS_PATH/BinWrappers/PosixLike:$PATH"
export PYTHON_COMMAND=python3
export CLANG_BIN=/usr/bin/
export CLANG_HOST_BIN=/usr/bin/
export NASM_PREFIX=/usr/bin/
export IASL_PREFIX=/usr/bin/
cd "$mu"
build -p Platforms/Xiaomi/munchFreshPkg/munch.dsc -a AARCH64 -t CLANGPDB -b DEBUG -n 4 \
    -D ENABLE_SECUREBOOT=0 -D DEVICE_MODEL=0 -D MUNCH_STORAGE=1 \
    -D FD_BASE=0x9FC00000 -D FD_SIZE=0x300000 -D FD_BLOCKS=0x300 \
    -D MEMORY_PROTECTION=TRUE -D SHIP_MODE=FALSE -D BUILDID_STRING=MUNCH-FRESH-1 \
    -y "$root/out/munch-fresh/build-report.txt"
