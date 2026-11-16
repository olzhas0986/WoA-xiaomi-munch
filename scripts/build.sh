#!/usr/bin/env bash
# Build the UEFI boot.img for POCO F4 / Redmi K40S (munch) on top of Mu-Silicium.
#
#   scripts/build.sh [--xbl xbl.img | --payload payload.bin]
#                    [--dtb munch-live.dtb]
#                    [--model 0|1] [--debug]
#
# Steps:
#   1. clone Mu-Silicium at a pinned revision into work/Mu-Silicium;
#   2. extract drivers from the XBL (a ready xbl.img or payload.bin),
#      patch them and lay them out as Binaries/munch;
#   3. overlay munchPkg, munch.toml and the DTB;
#   4. run the stock build_uefi.py.
# Result: out/Mu-munch-<model>.img
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MU_URL="https://github.com/Project-Silicium/Mu-Silicium.git"
MU_REV="fb4efb37b4ac289ce83ad94c7acb73defb87955c"   # 2026-11-12, alioth = Active
WORK="$ROOT/work"
MU="$WORK/Mu-Silicium"
OUT="$ROOT/out"

XBL="" PAYLOAD="" DTB="$ROOT/munch-live.dtb" MODEL=0 MODE=RELEASE
while [[ $# -gt 0 ]]; do
  case "$1" in
    --xbl)     XBL="$2"; shift 2 ;;
    --payload) PAYLOAD="$2"; shift 2 ;;
    --dtb)     DTB="$2"; shift 2 ;;
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

for tool in git python3 dtc clang lld-link make iasl; do
  command -v "$tool" >/dev/null || { echo "missing tool: $tool" >&2; exit 2; }
done

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
python3 -I "$ROOT/tools/check_memmap.py" \
        --cfg "$OUT/xbl-fv/uefiplat.cfg/uefiplat.cfg.raw" --dtb "$DTB" | tail -1

echo "==> overlaying the port"
rm -rf "$MU/Platforms/Xiaomi/munchPkg"
cp -r "$ROOT/port/munchPkg" "$MU/Platforms/Xiaomi/munchPkg"
cp "$ROOT/port/Resources/Configs/munch.toml" "$MU/Resources/Configs/munch.toml"
python3 -I "$ROOT/tools/prepare_dtb.py" "$DTB" -o "$MU/Resources/DTBs/munch.dtb"

echo "==> Python environment"
if [[ ! -x "$WORK/venv/bin/python" ]]; then
  python3 -m venv "$WORK/venv"
  "$WORK/venv/bin/pip" install --quiet --upgrade pip
  "$WORK/venv/bin/pip" install --quiet -r "$MU/pip-requirements.txt"
fi

echo "==> build ($MODE, model $MODEL)"
cd "$MU"
PATH="$WORK/venv/bin:$PATH" python3 build_uefi.py -d munch -m "$MODEL" -r "$MODE"
cp "Mu-munch-$MODEL.img" "$OUT/"
sha256sum "$OUT/Mu-munch-$MODEL.img"
