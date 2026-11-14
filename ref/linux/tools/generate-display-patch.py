#!/usr/bin/env python3
"""Generate the L11R kernel patch from supplied stock DT and Android selection."""
import argparse
import difflib
import hashlib
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('display_audit', ROOT/'tools/audit-display-dt.py')
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)
SELECTOR = 'qcom,mdss_dsi_l11r_38_08_0a_dsc_cmd'


def header(blob, cmdline, refresh=60):
    if refresh not in (60, 120):
        raise ValueError("unreviewed refresh rate")
    fields = [x for x in cmdline.split() if x.startswith('msm_drm.dsi_display0=')]
    if len(fields) != 1 or fields[0].split('=', 1)[1].split(':', 1)[0] != SELECTOR:
        raise ValueError('Android cmdline does not select the expected L11R panel')
    nodes = audit.parse_fdt(blob)
    panels = [n for n in nodes if n.rsplit('/', 1)[-1] == SELECTOR]
    if len(panels) != 1:
        raise ValueError('expected exactly one L11R panel node')
    panel = panels[0]
    timings = [n for n, p in nodes.items() if n.startswith(panel+'/') and
               p.get('qcom,mdss-dsi-panel-framerate') == refresh.to_bytes(4, 'big')]
    if len(timings) != 1:
        raise ValueError(f'expected exactly one {refresh} Hz timing')
    p = nodes[timings[0]]
    expected = {'panel-width': 1080, 'panel-height': 2400,
                'h-front-porch': 16, 'h-pulse-width': 8, 'h-back-porch': 8,
                'v-front-porch': 600, 'v-pulse-width': 32, 'v-back-porch': 560}
    if refresh == 120:
        expected.update({'v-front-porch': 4, 'v-pulse-width': 4, 'v-back-porch': 8})
    for key, value in expected.items():
        if p.get('qcom,mdss-dsi-'+key) != value.to_bytes(4, 'big'):
            raise ValueError(f'unreviewed timing field: {key}')
    for key, value in {'slice-width':540, 'slice-height':8, 'bit-per-component':8, 'bit-per-pixel':8}.items():
        if p.get('qcom,mdss-dsc-'+key) != value.to_bytes(4, 'big'):
            raise ValueError(f'unreviewed DSC field: {key}')
    text = '// SPDX-License-Identifier: GPL-2.0-only\n'
    text += '/* Generated from user-supplied stock DT; do not edit packet bytes.\n'
    text += f' * DT SHA256: {hashlib.sha256(blob).hexdigest()}\n'
    text += f' * Android selection: {SELECTOR}\n */\n'
    for which in ('on', 'off'):
        key = 'qcom,mdss-dsi-'+which+'-command'
        if p.get(key+'-state') != b'dsi_lp_mode\0':
            raise ValueError('unreviewed command power mode')
        commands = audit.dsi_commands(p[key])
        suffix = '_120' if refresh == 120 else ''
        text += f'static const struct l11r_cmd l11r_{which}{suffix}[] = {{\n'
        for cmd in commands:
            payload = bytes.fromhex(cmd['payload'])
            if cmd['type'] not in (5, 57) or cmd['channel'] != 0 or cmd['ack'] != 0 or not 0 < len(payload) <= 129:
                raise ValueError('unreviewed command packet')
            values = ', '.join(f'0x{x:02x}' for x in payload)
            text += f' {{ 0x{cmd["type"]:02x}, {cmd["channel"]}, {cmd["ack"]}, {cmd["delay_ms"]}, {len(payload)}, {{ {values} }} }},\n'
        text += '};\n'
    return text


def extension_patch(source, generated_120):
    """Extend the frozen 60 Hz patch without changing baseline source exports."""
    files = {
        'drivers/gpu/drm/panel/panel-xiaomi-munch-l11r.c': (ROOT/'kernel-drivers/panel-xiaomi-munch-l11r.c').read_text(),
        'drivers/gpu/drm/panel/munch-l11r-120.h': generated_120,
    }
    return diff_files(source, files)


def diff_files(source, files):
    output = ''
    for name, content in files.items():
        path = source/name
        before = path.read_text() if path.exists() else ''
        output += f'diff --git a/{name} b/{name}\n'
        output += ''.join(difflib.unified_diff(before.splitlines(True), content.splitlines(True),
                       fromfile='a/'+name if path.exists() else '/dev/null', tofile='b/'+name))
    return output


def patch_for(source, generated, generated_120):
    files = {
        'drivers/gpu/drm/panel/panel-xiaomi-munch-l11r.c': (ROOT/'kernel-drivers/panel-xiaomi-munch-l11r.c').read_text(),
        'drivers/gpu/drm/panel/munch-l11r-init.h': generated,
        'drivers/gpu/drm/panel/munch-l11r-120.h': generated_120,
    }
    kconfig = 'drivers/gpu/drm/panel/Kconfig'
    old = (source/kconfig).read_text()
    section = '''
config DRM_PANEL_XIAOMI_MUNCH_L11R
	tristate "POCO F4 L11R 38:08:0a DSC panel (experimental)"
	depends on OF && DRM_MIPI_DSI && BACKLIGHT_CLASS_DEVICE
	select DRM_DISPLAY_DSC_HELPER
	help
	  Experimental fixed 60 or 120 Hz driver based on stock munch commands.
'''
    prefix, suffix = old.rsplit('endmenu', 1)
    files[kconfig] = prefix+section+'\nendmenu'+suffix
    makefile = 'drivers/gpu/drm/panel/Makefile'
    files[makefile] = (source/makefile).read_text()+'\nobj-$(CONFIG_DRM_PANEL_XIAOMI_MUNCH_L11R) += panel-xiaomi-munch-l11r.o\n'
    return diff_files(source, files)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dtb', type=Path, required=True)
    parser.add_argument('--cmdline', type=Path, required=True)
    parser.add_argument('--kernel-source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--extension', action='store_true', help='extend an existing 60 Hz source tree (patch 0008)')
    args = parser.parse_args()
    try:
        blob, cmdline = args.dtb.read_bytes(), args.cmdline.read_text()
        generated_120 = header(blob, cmdline, 120)
        if args.extension:
            result = extension_patch(args.kernel_source, generated_120)
        else:
            result = patch_for(args.kernel_source, header(blob, cmdline), generated_120)
        with args.output.open('x') as handle:
            handle.write(result)
        print(args.output)
    except (OSError, ValueError) as error:
        parser.exit(1, f'display-patch: {error}\n')

if __name__ == '__main__':
    main()
