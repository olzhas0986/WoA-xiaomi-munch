#!/usr/bin/env python3
"""Apply an explicit config seed and reject silently dropped requirements."""
import argparse
import os
from pathlib import Path
import subprocess

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--source', type=Path, required=True)
p.add_argument('--out', type=Path, required=True)
p.add_argument('--fragment', type=Path, required=True)
p.add_argument('--busybox', action='store_true')
p.add_argument('--extra-fragment', type=Path)
a = p.parse_args()
a.out.mkdir(parents=True, exist_ok=True)
base = ['make', '-C', str(a.source), 'O='+str(a.out), 'ARCH=arm64', 'CROSS_COMPILE='+os.environ.get('CROSS_COMPILE', 'aarch64-linux-gnu-')]
fragment = a.fragment.read_text()
if a.extra_fragment:
    if a.busybox:
        p.error('--extra-fragment is supported for kernel only')
    fragment += '\n'+a.extra_fragment.read_text()
seed = a.out/'seed.config'
seed.write_text(fragment)
if a.busybox:
    subprocess.run(base+['allnoconfig'], check=True)
    config = (a.out/'.config').read_text().splitlines()
    wanted = {line.split('=')[0]: line for line in fragment.splitlines() if line.startswith('CONFIG_')}
    config = [wanted.pop(line.split('=')[0], line) if line.startswith('CONFIG_') else
              wanted.pop(line.split()[1], line) if line.startswith('# CONFIG_') else line for line in config]
    (a.out/'.config').write_text('\n'.join(config+list(wanted.values()))+'\n')
    subprocess.run(base+['oldconfig'], input=b'', check=True)
else:
    subprocess.run(base+['KCONFIG_ALLCONFIG='+str(seed), 'allnoconfig'], check=True)
actual = set((a.out/'.config').read_text().splitlines())
required = [line for line in fragment.splitlines() if line.startswith('CONFIG_') or line.startswith('# CONFIG_')]
missing = [line for line in required if line not in actual]
if missing:
    (a.out/'.config').unlink()
    raise SystemExit('Config requirements not satisfied:\n'+'\n'.join(missing))
