#!/usr/bin/env python3
"""Prepare pinned, unchanged SCM, RPEN, SPMI or PMIC driver experiments for munch."""
import argparse
import hashlib
import json
import shutil
import struct
import subprocess
import tempfile
import zipfile
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
COMMIT = '22221a09e02cb7054792427af60299b1c34d3c3e'
CERTIFICATE = '946CF507369A80E65F2B58BEBF5D02CC159A484D'
REPO = ROOT / 'reference/windows_silicon_qcom_kona'
OUT = ROOT / 'out/kona-gpu'
PROFILES = {
    'pep': dict(number=28, destination='28D', folder='GpuPep', driver='qcpep8250', package='qcpep.wd8250', hid='QCOM2519',
                version='1.0.2140.0000', source='Drivers/SOC/PowerManagement', label='PEP core experiment'),
    'pmic': dict(number=26, folder='GpuPmic', driver='qcpmic8250', hid='QCOM252E',
                 source='Drivers/SOC/PMIC/Core', label='SCM + RPEN + SPMI + core PMIC'),
    'scm': dict(number=23, folder='GpuBootstrap', driver='qcscm8250', hid='QCOM250B',
                source='Drivers/SOC/System/SCM', label='SCM foundation'),
    'rpen': dict(number=24, folder='GpuRpen', driver='qcrpen8250', hid='QCOM2533',
                 source='Drivers/SOC/ResetPower/ResetProtectionEnabler', label='SCM + RPEN'),
    'spmi': dict(number=25, folder='GpuSpmi', driver='qcspmi8250', hid='QCOM250C',
                 source='Drivers/SOC/SPMI', label='SCM + RPEN + SPMI'),
}

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--stage', choices=PROFILES, default='scm')
    args = parser.parse_args()
    profile = PROFILES[args.stage]
    commit = subprocess.check_output(['git', '-C', str(REPO), 'rev-parse', 'HEAD'], text=True).strip()
    if commit != COMMIT: raise SystemExit('Unexpected BSP commit; review it before repinning')
    status = subprocess.check_output(['git', '-C', str(REPO), 'status', '--porcelain', '--untracked-files=no'], text=True)
    if status: raise SystemExit('BSP has tracked modifications')
    stage = OUT / ('bootstrap' if args.stage == 'scm' else 'bootstrap-' + args.stage)
    stage.mkdir(parents=True, exist_ok=True)
    driver, category = profile['driver'], args.stage.upper()
    package = profile.get('package', driver)
    files = {f'Drivers/{category}/{package}.{ext}': REPO / profile['source'] / f'{package}.{ext}'
             for ext in ('inf', 'cat')}
    files[f'Drivers/{category}/{driver}.sys'] = REPO / profile['source'] / f'{driver}.sys'
    if args.stage == 'pep':
        files['Drivers/PEP/PPMSettings-8250Profiles.wd.ppkg'] = REPO / profile['source'] / 'PPMSettings-8250Profiles.wd.ppkg'
        files['policy.json'] = ROOT / 'firmware/munch/GpuPep/policy.json'
    files['LICENSE.md'] = REPO / 'LICENSE.md'
    sources = ROOT / 'firmware/munch' / profile['folder']
    if args.stage != 'scm': files['README.md'] = sources / 'README.md'
    for name in ('setup.cmd', 'bootstrap.ps1'): files[name] = sources / name
    for name, source in files.items():
        dest = stage / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, dest)
        assert sha(source) == sha(dest)
    pe = (stage / 'Drivers' / category / (driver + '.sys')).read_bytes()
    off = struct.unpack_from('<I', pe, 0x3c)[0]
    assert pe[off:off+4] == b'PE\0\0' and struct.unpack_from('<H', pe, off+4)[0] == 0xaa64
    inf = (stage / 'Drivers' / category / (package + '.inf')).read_text(encoding='utf-16')
    assert profile['hid'] in inf and profile.get('version', '1.0.2100.0000') in inf
    with tempfile.TemporaryDirectory() as tmp:
        pem = Path(tmp) / 'chain.pem'
        subprocess.run(['openssl', 'pkcs7', '-inform', 'DER', '-in', str(stage / 'Drivers' / category / (package + '.cat')), '-print_certs', '-out', str(pem)], check=True)
        subprocess.run(['openssl', 'x509', '-in', str(pem), '-outform', 'DER', '-out', str(stage / 'woa-kmci.cer')], check=True)
        subject = subprocess.check_output(['openssl', 'x509', '-in', str(pem), '-noout', '-subject'], text=True)
        assert 'Windows On Andromeda KMCI Codesigning' in subject
    thumbprint = hashlib.sha1((stage / 'woa-kmci.cer').read_bytes()).hexdigest().upper()
    assert thumbprint == CERTIFICATE, 'Unexpected catalog signer; do not assume existing trust'
    names = sorted([*files, 'woa-kmci.cer'])
    manifest = {'stage': profile['label'] + '; GPU acceleration not enabled', 'bsp_commit': COMMIT,
                'certificate_thumbprint': thumbprint,
                'files': [{'path': n, 'sha256': sha(stage / n)} for n in names]}
    if args.stage == 'pep':
        manifest['provision_sha256'] = sha(stage / 'Drivers/PEP/PPMSettings-8250Profiles.wd.ppkg').upper()
        policy = json.loads((stage / 'policy.json').read_text())
        for setting in policy['settings']:
            assert setting['name'].encode('utf-16le') in pe, 'Unrecognised policy name: ' + setting['name']
    (stage / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    names += ['manifest.json']
    sums = ''.join(f'{sha(stage / n)}  {n}\n' for n in sorted(names)).encode()
    installer = (ROOT / 'firmware/munch/Recovery/install-gpu-bootstrap').read_text().replace('@SUMS_SHA@', hashlib.sha256(sums).hexdigest())
    number = str(profile['number'])
    destination = str(profile.get('destination', number))
    if args.stage != 'scm':
        installer = installer.replace('GPU23', 'GPU' + destination).replace('gpu23', 'gpu' + destination.lower()).replace('SCM package', category + ' package').replace('Boot Windows23 and run setup.cmd configure.', 'Boot Windows' + number + ' and run setup.cmd.')
    output = OUT / f'munch-gpu-{args.stage}-bootstrap-twrp.zip'
    with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as z:
        for n in names: z.write(stage / n, 'payload/' + n)
        z.writestr('payload/SHA256SUMS', sums)
        info = zipfile.ZipInfo('META-INF/com/google/android/update-binary')
        info.external_attr = 0o100755 << 16
        z.writestr(info, installer)
        z.writestr('META-INF/com/google/android/updater-script', '# GPU dependency support files only\n')
    with zipfile.ZipFile(output) as z:
        assert z.testzip() is None
        for n in names: assert z.read('payload/' + n) == (stage / n).read_bytes()
        assert '@SUMS_SHA@' not in z.read('META-INF/com/google/android/update-binary').decode()
    if args.stage == 'pep':
        portable = OUT / 'munch-pep-initial-windows.zip'
        with zipfile.ZipFile(portable, 'w', zipfile.ZIP_DEFLATED) as z:
            for n in names:
                z.write(stage / n, 'GPU' + destination + '/' + n)
        with zipfile.ZipFile(portable) as z:
            assert z.testzip() is None
            for n in names: assert z.read('GPU' + destination + '/' + n) == (stage / n).read_bytes()
        print(portable)
    print(output)
    print('SHA256:', sha(output))
if __name__ == '__main__': main()
