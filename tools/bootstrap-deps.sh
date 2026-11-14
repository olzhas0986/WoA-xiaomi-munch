#!/usr/bin/env bash
set -euo pipefail
root=$(cd "$(dirname "$0")/.." && pwd)
mu="$root/Mu-Silicium"
commit=42fe563791e51bf5500c2e470ed294ca0c94b97c

for command in git python3 clang llvm-objcopy iasl fdtget mkbootimg; do
    command -v "$command" >/dev/null || {
        echo "Missing host command: $command (see BUILDING.md)" >&2
        exit 1
    }
done

if [[ ! -d "$mu/.git" ]]; then
    git clone --recursive https://github.com/Project-Silicium/Mu-Silicium.git "$mu"
fi
git -C "$mu" fetch origin "$commit"
git -C "$mu" checkout --detach "$commit"
git -C "$mu" submodule update --init --recursive

python3 -m venv "$root/.venv"
"$root/.venv/bin/pip" install --upgrade pip
"$root/.venv/bin/pip" install -r "$mu/pip-requirements.txt" -r "$root/requirements.txt"
echo "Dependencies are pinned and ready. Next: make inputs XBL=... DTB=..."
