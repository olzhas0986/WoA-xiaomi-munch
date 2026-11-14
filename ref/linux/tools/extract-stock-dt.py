#!/usr/bin/env python3
"""Extract supplied stock DTs offline and resolve munch USB2 supply references."""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import subprocess


def require(condition, message):
    if not condition:
        raise ValueError(message)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--vendor-boot', type=Path, default=Path('vendor_boot.img'))
    p.add_argument('--dtbo', type=Path, default=Path('dtbo.img'))
    p.add_argument('--out', type=Path, default=Path('out/stock-usb-evidence'))
    a = p.parse_args()
    require(not a.out.exists(), 'output exists; select a new --out directory')
    vendor, overlays = a.vendor_boot.read_bytes(), a.dtbo.read_bytes()
    require(len(vendor) >= 2112 and vendor[:8] == b'VNDRBOOT', 'vendor boot header')
    version, page = struct.unpack_from('<II', vendor, 8)
    require(version == 3 and page >= 2048 and page & (page-1) == 0, 'requires vendor boot v3')
    ramdisk_size = struct.unpack_from('<I', vendor, 24)[0]
    header_size, dtb_size = struct.unpack_from('<II', vendor, 2096)
    require(header_size == 2112, 'unexpected v3 header size')
    align = lambda n: (n+page-1)//page*page
    start = align(header_size)+align(ramdisk_size)
    require(dtb_size > 0 and start+dtb_size <= len(vendor), 'DTB section bounds')
    require(len(overlays) >= 32, 'DT table header truncated')
    magic, total, header, entry, count, table, _, ver = struct.unpack_from('>8I', overlays)
    require(magic == 0xd7b7ab1e and ver == 0 and header >= 32 and entry >= 32,
            'unsupported DT table')
    require(header <= table <= total <= len(overlays) and table+count*entry <= total,
            'DT table bounds')
    a.out.mkdir(parents=True)

    def fdt(path, data):
        require(len(data) >= 40 and data[:4] == b'\xd0\x0d\xfe\xed' and
                struct.unpack_from('>I', data, 4)[0] == len(data), 'invalid FDT')
        path.write_bytes(data)

    def get(path, node, prop, kind='s'):
        return subprocess.check_output(['fdtget', '-t', kind, str(path), node, prop],
                                       text=True).strip()

    entries, selected = [], []
    for i in range(count):
        size, offset, ident, rev, *custom = struct.unpack_from('>8I', overlays, table+i*entry)
        require(offset >= table+count*entry and size <= total-offset, 'overlay bounds')
        path = a.out/f'overlay-{i}.dtbo'
        fdt(path, overlays[offset:offset+size])
        model = get(path, '/', 'model')
        entries.append(dict(index=i, id=ident, rev=rev, custom=custom, model=model))
        if model.endswith('xiaomi munch'):
            selected.append(path)
    require(len(selected) == 1, 'expected exactly one munch overlay')
    overlay = selected[0]
    results, blob = [], vendor[start:start+dtb_size]
    offset = index = 0
    while offset < len(blob) and any(blob[offset:]):
        require(offset+40 <= len(blob), 'truncated concatenated DTB')
        size = struct.unpack_from('>I', blob, offset+4)[0]
        require(40 <= size <= len(blob)-offset, 'base DTB bounds')
        path = a.out/f'base-{index}.dtb'
        fdt(path, blob[offset:offset+size])
        offset += size
        index += 1
        soc = subprocess.run(['fdtget', '-t', 'x', str(path), '/', 'qcom,msm-id'],
                             text=True, capture_output=True)
        if soc.returncode:  # RTIC metadata is a standalone FDT, not a SoC base.
            continue
        merged = a.out/f'munch-base-{index-1}.dtb'
        subprocess.run(['fdtoverlay', '-i', str(path), '-o', str(merged), str(overlay)], check=True)
        phy = get(merged, '/__symbols__', 'usb2_phy0')
        supplies = []
        for prop, symbol in [('vdd-supply', 'pm8150_l5'), ('vdda18-supply', 'pm8150_l12'),
                             ('vdda33-supply', 'pm8150_l2')]:
            node = get(merged, '/__symbols__', symbol)
            require(get(merged, phy, prop, 'x') == get(merged, node, 'phandle', 'x'),
                    f'{prop} does not resolve to {symbol}')
            supplies.append(dict(property=prop, node=node, name=get(merged, node, 'regulator-name'),
                                 resource=get(merged, node.rsplit('/', 1)[0], 'qcom,resource-name'),
                                 min_uv=int(get(merged, node, 'regulator-min-microvolt', 'u')),
                                 max_uv=int(get(merged, node, 'regulator-max-microvolt', 'u'))))
        results.append(dict(base=path.name, msm_id=soc.stdout.strip(), phy=phy, supplies=supplies))
    require(results and all(r['supplies'] == results[0]['supplies'] for r in results),
            'USB supply evidence differs across SoC bases')
    report = dict(inputs={str(a.vendor_boot): hashlib.sha256(vendor).hexdigest(),
                          str(a.dtbo): hashlib.sha256(overlays).hexdigest()},
                  overlays=entries, selected_overlay=overlay.name,
                  overlay_board_id=get(overlay, '/', 'qcom,board-id', 'x'), bases=results,
                  limitation='Actual bootloader SoC revision/overlay selection is not captured.')
    (a.out/'usb-supplies.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
