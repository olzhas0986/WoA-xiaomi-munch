#!/usr/bin/env python3
"""Optionally seed a separate kernel O= directory without hard-linking old artifacts."""
import argparse
from pathlib import Path
import subprocess
import tempfile

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--source', type=Path, required=True)
p.add_argument('--output', type=Path, required=True)
a = p.parse_args()
if a.output.exists() or not (a.source/'.config').is_file():
    raise SystemExit(0)
a.output.parent.mkdir(parents=True, exist_ok=True)
# Publish only a complete copy. Failed copies leave no half-seeded build directory.
with tempfile.TemporaryDirectory(dir=a.output.parent, prefix='kernel-cache-') as temporary:
    staged = Path(temporary)/'kernel'
    subprocess.run(['cp', '-a', '--reflink=auto', str(a.source), str(staged)], check=True)
    # Force profile validation and regenerate the wrapper with the new KBUILD_OUTPUT.
    for name in ['.config', 'Makefile']:
        (staged/name).unlink(missing_ok=True)
    staged.rename(a.output)
print('Seeded independent kernel cache:', a.output)
