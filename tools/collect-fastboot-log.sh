#!/usr/bin/env bash
set -euo pipefail
root=$(cd "$(dirname "$0")/.." && pwd)
output=${1:-"$root/out/munch-fresh/fastboot-log.txt"}
mkdir -p "$(dirname "$output")"
fastboot getvar product
fastboot oem log >"$output" 2>&1
echo "Saved fastboot transcript: $output"
