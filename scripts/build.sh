#!/usr/bin/env bash
# Build the UEFI boot.img for POCO F4 / Redmi K40S (munch) on top of Mu-Silicium.
#
#   scripts/build.sh [--xbl xbl.img | --payload payload.bin]
#                    [--dtb munch-live.dtb | --raw-dtb vendor_boot.dtb]
#                    [--model 0|1] [--debug]
#
# Steps:
#   1. clone Mu-Silicium at a pinned revision into work/Mu-Silicium;
#   2. extract drivers from the XBL (a ready xbl.img or payload.bin),
#      patch them and lay them out as Binaries/munch;
#   3. overlay munchPkg, munch.toml and the DTB;
#   4. set up the edk2 environment and run the stock build_uefi.py.
# Result: out/Mu-munch-<model>.img
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MU_URL="https://github.com/Project-Silicium/Mu-Silicium.git"
MU_REV="fb4efb37b4ac289ce83ad94c7acb73defb87955c"   # 2026-11-12, alioth = Active
WORK="$ROOT/work"
MU="$WORK/Mu-Silicium"
OUT="$ROOT/out"

XBL="" PAYLOAD="" DTB="$ROOT/munch-live.dtb" DTB_RAW="" MODEL=0 MODE=RELEASE
while [[ $# -gt 0 ]]; do
  case "$1" in
    --xbl)     XBL="$2"; shift 2 ;;
    --payload) PAYLOAD="$2"; shift 2 ;;
    --dtb)     DTB="$2"; shift 2 ;;
    --raw-dtb) DTB="$2"; DTB_RAW="--raw"; shift 2 ;;
    --model)   MODEL="$2"; shift 2 ;;
    --debug)   MODE=DEBUG; shift ;;
    -h|--help) awk 'NR>1 && /^#/ {sub(/^# ?/, ""); print; next} NR>1 {exit}' "$0"; exit 0 ;;
    *) echo "unknown option: $1" >&2; exit 2 ;;
  esac
done

# Default to whatever sits in the repository root
if [[ -z "$XBL" && -z "$PAYLOAD" ]]; then
  if   [[ -f "$ROOT/xbl.img"     ]]; then XBL="$ROOT/xbl.img"
  elif [[ -f "$ROOT/payload.bin" ]]; then PAYLOAD="$ROOT/payload.bin"
  else echo "xbl.img or payload.bin is required (see --help)" >&2; exit 2; fi
fi
[[ -f "$DTB" ]] || { echo "DTB not found: $DTB" >&2; exit 2; }

# mono runs NuGet, which edk2 uses to fetch mu_nasm and the BaseTools binaries
missing=()
for tool in git python3 dtc clang lld-link llvm-objcopy make iasl mono; do
  command -v "$tool" >/dev/null || missing+=("$tool")
done
if [[ ${#missing[@]} -gt 0 ]]; then
  echo "missing tools: ${missing[*]}" >&2
  echo "Arch/CachyOS: sudo pacman -S --needed mono clang lld llvm dtc acpica nasm" >&2
  echo "Debian/Ubuntu: sudo apt install mono-devel ca-certificates-mono clang lld llvm device-tree-compiler acpica-tools nasm" >&2
  exit 2
fi

mkdir -p "$WORK" "$OUT"

echo "==> Mu-Silicium @ ${MU_REV:0:12}"
if [[ ! -d "$MU/.git" ]]; then
  git clone --no-checkout "$MU_URL" "$MU"
fi
git -C "$MU" fetch --quiet origin "$MU_REV" 2>/dev/null || git -C "$MU" fetch --quiet origin
git -C "$MU" checkout --quiet --force "$MU_REV"
git -C "$MU" submodule update --init --recursive --depth 1 --jobs 4

echo "==> drivers from the XBL"
if [[ -n "$PAYLOAD" ]]; then
  python3 -I "$ROOT/tools/payload_extract.py" "$PAYLOAD" -o "$OUT/payload" -p xbl
  XBL="$OUT/payload/xbl.img"
fi
rm -rf "$OUT/xbl-fv"
python3 -I "$ROOT/tools/xbl_fv_extract.py" "$XBL" -o "$OUT/xbl-fv"
python3 -I "$ROOT/tools/make_binaries.py" "$OUT/xbl-fv" -o "$MU/Binaries/munch" \
        --raw-inc "$OUT/RAW.inc"
if ! cmp -s "$OUT/RAW.inc" "$ROOT/port/munchPkg/Include/RAW.inc"; then
  echo "RAW.inc from this XBL differs from the committed one - different firmware?" >&2
  exit 1
fi
if [[ -z "$DTB_RAW" ]]; then
  python3 -I "$ROOT/tools/check_memmap.py" \
          --cfg "$OUT/xbl-fv/uefiplat.cfg/uefiplat.cfg.raw" --dtb "$DTB" | tail -1
else
  python3 -I "$ROOT/tools/check_memmap.py" \
          --cfg "$OUT/xbl-fv/uefiplat.cfg/uefiplat.cfg.raw" | tail -1
fi

echo "==> overlaying the port"
rm -rf "$MU/Platforms/Xiaomi/munchPkg"
cp -r "$ROOT/port/munchPkg" "$MU/Platforms/Xiaomi/munchPkg"
cp "$ROOT/port/Resources/Configs/munch.toml" "$MU/Resources/Configs/munch.toml"
python3 -I "$ROOT/tools/prepare_dtb.py" "$DTB" -o "$MU/Resources/DTBs/munch.dtb" $DTB_RAW

echo "==> Python environment"
if [[ ! -x "$WORK/venv/bin/python" ]]; then
  python3 -m venv "$WORK/venv"
  "$WORK/venv/bin/pip" install --quiet --upgrade pip
  "$WORK/venv/bin/pip" install --quiet -r "$MU/pip-requirements.txt"
fi
export PATH="$WORK/venv/bin:$PATH"

# build_uefi.py skips stuart setup/update once Build/ exists, so a run that
# failed half-way (e.g. without mono) would never fetch the missing
# dependencies. Run both steps every time; they are idempotent.
echo "==> edk2 environment"
cd "$MU"
for action in --setup --update; do
  python3 Platforms/Xiaomi/munchPkg/DeviceBuild.py "$action" -t "$MODE"
done

echo "==> build ($MODE, model $MODEL)"
python3 build_uefi.py -d munch -m "$MODEL" -r "$MODE"
cp "Mu-munch-$MODEL.img" "$OUT/"
sha256sum "$OUT/Mu-munch-$MODEL.img"
