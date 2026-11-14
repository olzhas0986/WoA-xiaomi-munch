#!/usr/bin/env bash
set -euo pipefail
root=$(cd "$(dirname "$0")/.." && pwd)
xbl=${1:?usage: tools/import-inputs.sh /path/to/xbl.img /path/to/munch.dtb}
dtb=${2:?usage: tools/import-inputs.sh /path/to/xbl.img /path/to/munch.dtb}
expected_xbl=696eaefeb4798b6c3427740232ae71006070b6bab079343cfe2a661363073c3b
expected_dtb=8b2beab345ca8c35ff7c39c7e3e526708c2da37ffa5af55d3784b42a1552d366

[[ -f "$xbl" && -f "$dtb" ]] || { echo "Both input files must exist" >&2; exit 1; }
[[ $(sha256sum "$xbl" | cut -d' ' -f1) == "$expected_xbl" ]] || {
    echo "Unsupported xbl.img. Expected $expected_xbl" >&2; exit 1
}
[[ $(sha256sum "$dtb" | cut -d' ' -f1) == "$expected_dtb" ]] || {
    echo "Unsupported live DTB. Expected $expected_dtb" >&2; exit 1
}
command -v fdtget >/dev/null
model=$(fdtget "$dtb" / model)
[[ "$model" == *"xiaomi munch"* ]] || { echo "DTB is not xiaomi munch: $model" >&2; exit 1; }

mkdir -p "$root/inputs/munch"
cp "$xbl" "$root/inputs/munch/xbl.img"
cp "$dtb" "$root/inputs/munch/live.dtb"
rm -rf "$root/inputs/munch/extracted-xbl"
"$root/.venv/bin/python" "$root/tools/extract-xbl.py" \
    "$root/inputs/munch/xbl.img" \
    --templates "$root/vendor-templates" \
    --output "$root/inputs/munch/extracted-xbl"
echo "Verified device inputs imported; vendor executables remain unmodified and untracked."
