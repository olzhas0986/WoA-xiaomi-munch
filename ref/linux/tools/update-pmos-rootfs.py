#!/usr/bin/env python3
"""Refresh an exported RAM rootfs without modifying the privileged build chroot."""
import argparse
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import tarfile

ROOT = Path(__file__).resolve().parents[1]
PIN = '7d23010a125ca7386fec4e390d14128b6c24d266'


def refresh(source, target, firmware=None):
    repo = ROOT/'out/pmbootstrap'
    revision = subprocess.check_output(['git', '-C', str(repo), 'rev-parse', 'HEAD'], text=True).strip()
    if revision != PIN:
        raise ValueError('pmbootstrap key source revision changed; review it first')
    overlay = {}
    for key in sorted((repo/'pmb/data/keys').glob('*.pub')):
        overlay['etc/apk/keys/'+key.name] = (key.read_bytes(), 0o644)
    if not overlay:
        raise ValueError('no trusted public keys found')
    spec = importlib.util.spec_from_file_location('phone_bundle', ROOT/'tools/build-phosh-tools.py')
    bundle = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bundle)
    for target_name, (name, mode) in bundle.FILES.items():
        overlay[target_name] = ((ROOT/'phone'/name).read_bytes(), mode)
    if firmware:
        for name in ('a650_sqe.fw', 'a650_gmu.bin'):
            data = (firmware/name).read_bytes()
            if not data:
                raise ValueError('empty GPU firmware: '+name)
            overlay['usr/lib/firmware/qcom/'+name] = (data, 0o644)
    target.parent.mkdir(parents=True, exist_ok=True)
    partial = target.with_name(target.name+'.partial')
    if target.exists() or partial.exists():
        raise ValueError('output already exists; choose a new destination')
    # Stream members, preserving metadata and links. Never extract as host root.
    with partial.open('xb') as output:
        with tarfile.open(source, 'r|gz') as old, tarfile.open(fileobj=output, mode='w|gz', compresslevel=3) as new:
            for member in old:
                name = member.name.removeprefix('./').rstrip('/')
                if name in overlay or name == '.pmos-munch-ready':
                    continue
                if name == 'etc/apk/repositories':
                    repos = old.extractfile(member).read().decode()
                    repos = '\n'.join(line for line in repos.splitlines()
                                      if not line.strip().startswith('/mnt/pmbootstrap/'))+'\n'
                    overlay[name] = (repos.encode(), 0o644)
                    continue
                new.addfile(member, old.extractfile(member) if member.isfile() else None)
            for name, (data, mode) in sorted(overlay.items()):
                item = tarfile.TarInfo('./'+name)
                item.size, item.mode = len(data), mode
                new.addfile(item, io.BytesIO(data))
    partial.rename(target)
    with target.open('rb') as handle:
        digest = hashlib.file_digest(handle, 'sha256').hexdigest()
    target.with_name(target.name+'.sha256').write_text(digest+'  '+target.name+'\n')
    target.with_name(target.name+'.json').write_text(json.dumps({
        'base': str(source), 'pmbootstrap_revision': revision,
        'overlay_sha256': {name: hashlib.sha256(data).hexdigest()
                           for name, (data, _) in overlay.items()},
        'gpu_firmware_source': str(firmware) if firmware else None,
        'hardware_verified': False,
    }, indent=2)+'\n')
    print(target)
    print('SHA256:', digest)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=ROOT/'out/pmos-rootfs/wifi/postmarketos-aarch64-console.tar.gz')
    parser.add_argument('--output', type=Path, default=ROOT/'out/pmos-rootfs/current/postmarketos-desktop.tar.gz')
    parser.add_argument('--gpu-firmware', type=Path, help='directory with user-supplied A650 SQE/GMU firmware')
    args = parser.parse_args()
    refresh(args.source, args.output, args.gpu_firmware)
