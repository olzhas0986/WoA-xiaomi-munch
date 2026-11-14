#!/usr/bin/env python3
"""Prepare/export a console userspace smoke-test rootfs; never flash a device."""
import argparse
import configparser
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'out/pmos-rootfs'
PMB = ROOT / 'out/pmbootstrap'
APORTS = ROOT / 'out/pmaports'
WORK = OUT / 'work'
CONFIG = OUT / 'pmbootstrap.cfg'
DEVICE = 'postmarketos-trailblazer'
PINS = {
    PMB: '7d23010a125ca7386fec4e390d14128b6c24d266',
    APORTS: 'f3f926903c1be144b0f92e1a8f3b88383911ad80',
}


# Pinned pmbootstrap 3.12.1: pmb/config/init.py::ask_for_work_path creates
# these three items. Initialize only new/empty workdirs; never migrate or zap.
WORK_VERSION = '8'


def initialize_work():
    version = WORK/'version'
    if version.exists():
        if version.read_text().strip() != WORK_VERSION:
            raise RuntimeError(f'{WORK}: incompatible work version; refusing to migrate automatically')
    else:
        if WORK.exists() and any(WORK.iterdir()):
            raise RuntimeError(f'{WORK}: nonempty unversioned workdir; refusing to adopt it')
        WORK.mkdir(mode=0o700, parents=True, exist_ok=True)
        with version.open('x') as handle:
            handle.write(WORK_VERSION+'\n')
    (WORK/'cache_git').mkdir(mode=0o700, exist_ok=True)


def prepare():
    for repo, expected in PINS.items():
        actual = subprocess.check_output(['git', '-C', str(repo), 'rev-parse', 'HEAD'], text=True).strip()
        if actual != expected:
            raise RuntimeError(f'{repo}: source revision changed; review before updating this recipe')
    config = configparser.ConfigParser()
    config['pmbootstrap'] = {
        'aports': str(APORTS), 'work': str(WORK),
        'device': DEVICE, 'kernel': 'mainline', 'ui': 'console',
        'service_manager': 'openrc', 'user': 'pmos',
        'hostname': 'munch-ram', 'timezone': 'UTC',
        'ssh_keys': 'False', 'ui_extras': 'False',
    }
    config['providers'] = {}
    OUT.mkdir(parents=True, exist_ok=True)
    if CONFIG.exists():
        existing = configparser.ConfigParser()
        existing.read(CONFIG)
        if dict(existing['pmbootstrap']) != dict(config['pmbootstrap']):
            raise RuntimeError(f'{CONFIG} differs from recipe; refusing to overwrite it')
    else:
        with CONFIG.open('x') as handle:
            os.chmod(CONFIG, 0o600)
            config.write(handle)
    initialize_work()
    print(f'Config: {CONFIG}', flush=True)
    print('Generic ARM64 userspace only; not a munch board port or boot image.', flush=True)


def pmb(*args):
    subprocess.run([sys.executable, str(PMB/'pmbootstrap.py'),
                    '-c', str(CONFIG), '-p', str(APORTS), '-w', str(WORK),
                    *args], cwd=ROOT, check=True)


def build():
    prepare()
    required = ['git', 'kpartx', 'losetup', 'openssl', 'ps', 'tar', 'chroot', 'sh', 'sudo']
    missing = [name for name in required if not shutil.which(name)]
    if missing:
        raise RuntimeError('Missing host programs: '+', '.join(missing)+'. Install host dependencies, then retry.')
    # pmbootstrap obtains packages and creates privileged host build chroots.
    # No --disk, recovery ZIP or flasher command is used.
    pmb('install', '--no-image', '--no-recommends', '--no-sshd', '--no-firewall', '--add', 'bash')
    print('Rootfs built. Next: python3 tools/pmos-rootfs.py export')


def wifi_build(show_next=True):
    prepare()
    source = WORK / ('chroot_rootfs_'+DEVICE)
    if not (source/'etc/os-release').exists():
        raise RuntimeError('Build the base rootfs first')
    # Install into the host build chroot, not the phone's internal storage.
    pmb('chroot', '-r', '--', 'apk', 'add',
        'linux-firmware-ath11k', 'wireless-regdb', 'iw',
        'wpa_supplicant', 'iproute2', 'pciutils')
    if show_next:
        print('Next: python3 tools/pmos-rootfs.py wifi-export')


def gpu_build():
    wifi_build(show_next=False)
    pmb('chroot', '-r', '--', 'apk', 'add',
        'firmware-qcom-adreno-a650', 'mesa-dri-gallium',
        'mesa-egl', 'mesa-gbm', 'mesa-utils', 'libdrm-tests')
    print('Next: python3 tools/pmos-rootfs.py gpu-export (validated munch ZAP is embedded in the GPU boot image)')


def export(wifi=False, gpu=False):
    prepare()
    source = WORK / ('chroot_rootfs_'+DEVICE)
    if not (source/'etc/os-release').exists():
        raise RuntimeError('Rootfs not built; run the build step first')
    # Stop/unmount chroots before archiving; never archive live host bind mounts.
    pmb('shutdown')
    destination = OUT/'gpu' if gpu else OUT/'wifi' if wifi else OUT
    destination.mkdir(parents=True, exist_ok=True)
    if wifi:
        firmware = source/'usr/lib/firmware/ath11k/QCA6390/hw2.0'
        if not firmware.is_dir():
            firmware = source/'lib/firmware/ath11k/QCA6390/hw2.0'
        if not firmware.is_dir() or not any(firmware.iterdir()):
            raise RuntimeError('QCA6390 firmware missing; run wifi-build first')
    target = destination/'postmarketos-aarch64-console.tar.gz'
    partial = target.with_suffix('.gz.part')
    if target.exists() or partial.exists():
        raise RuntimeError(f'Export already exists ({target} or {partial}); refusing to overwrite')
    # The generic kernel/modules are not for munch. Package database metadata
    # remains untouched: this tar is a userspace smoke test, not an install image.
    partial.touch(mode=0o600, exist_ok=False)
    subprocess.run(['sudo', 'tar', '--one-file-system', '--numeric-owner',
                    '--exclude=./boot', '--exclude=./usr/lib/modules',
                    '--exclude=./dev/*', '--exclude=./proc/*',
                    '--exclude=./sys/*', '--exclude=./run/*',
                    '-czf', str(partial), '-C', str(source), '.'], check=True)
    partial.rename(target)
    with target.open('rb') as handle:
        digest = hashlib.file_digest(handle, 'sha256').hexdigest()
    target.with_suffix('.gz.sha256').write_text(digest+'  '+target.name+'\n')
    (destination/'sources.json').write_text(json.dumps({
        'sources': {str(repo.relative_to(ROOT)): commit for repo, commit in PINS.items()},
        'device_profile': DEVICE, 'service_manager': 'openrc',
        'purpose': 'AArch64 userspace smoke test under the existing munch kernel',
        'wifi_packages': wifi, 'gpu_packages': gpu, 'archive': target.name, 'sha256': digest, 'bytes': target.stat().st_size,
    }, indent=2)+'\n')
    print(f'Exported: {target}\nSHA256: {digest}')
    print('Inspect archive contents/size before producing a phone boot image.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['prepare', 'build', 'export', 'wifi-build', 'wifi-export', 'gpu-build', 'gpu-export'])
    args = parser.parse_args()
    try:
        {'prepare': prepare, 'build': build, 'export': export,
         'wifi-build': wifi_build, 'wifi-export': lambda: export(wifi=True),
         'gpu-build': gpu_build, 'gpu-export': lambda: export(wifi=True, gpu=True)}[args.action]()
    except (OSError, RuntimeError, subprocess.CalledProcessError) as error:
        parser.exit(1, f'pmos-rootfs: {error}\n')

if __name__ == '__main__':
    main()
