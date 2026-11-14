#!/usr/bin/env python3
"""Reuse the reviewed bootstrap before any daemons start; hand PID1 to pmOS."""
import argparse
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]


def build(source):
    boundary = '\nacm=0\n'
    if source.count(boundary) != 1:
        raise ValueError('bootstrap daemon boundary changed; review native handoff')
    prefix = source.split(boundary)[0]
    # Never include the chroot bootstrap shell/monitor jobs after this boundary.
    return prefix+'''\n# Native mode registers ACM, but init in the new root owns its console.
setup_acm || echo 'Native: ACM unavailable; use the local console'
. /etc/pmos-munch/native/stage
'''


if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    data=build((ROOT/'initramfs/init-pmos-display').read_text())
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(data)
