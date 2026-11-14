#!/usr/bin/env python3
"""Offline stock display evidence; never select a physical panel from an inventory."""
import argparse
import hashlib
import json
from pathlib import Path
import struct


def parse_fdt(data):
    if len(data) < 40:
        raise ValueError('truncated FDT header')
    magic, total, start, strings, _, version, _, _, strsize, size = struct.unpack_from('>10I', data)
    if magic != 0xd00dfeed or not 16 <= version <= 17 or total > len(data):
        raise ValueError('unsupported FDT')
    if start+size > total or strings+strsize > total:
        raise ValueError('FDT block outside blob')
    names = data[strings:strings+strsize]
    cursor, end, stack, nodes = start, start+size, [], {}
    while cursor+4 <= end:
        token = struct.unpack_from('>I', data, cursor)[0]
        cursor += 4
        if token == 1:
            stop = data.find(b'\0', cursor, end)
            if stop < 0:
                raise ValueError('unterminated node')
            stack.append(data[cursor:stop].decode())
            cursor = (stop+4) & ~3
            path = '/'+('/'.join(stack[1:]))
            if path in nodes:
                raise ValueError('duplicate node')
            nodes[path] = {}
        elif token == 2:
            if not stack:
                raise ValueError('unbalanced nodes')
            stack.pop()
        elif token == 3:
            if not stack or cursor+8 > end:
                raise ValueError('property outside node')
            length, offset = struct.unpack_from('>II', data, cursor)
            cursor += 8
            stop = names.find(b'\0', offset)
            if stop < 0 or cursor+length > end:
                raise ValueError('invalid property bounds')
            name = names[offset:stop].decode()
            nodes['/'+('/'.join(stack[1:]))][name] = data[cursor:cursor+length]
            cursor = (cursor+length+3) & ~3
        elif token == 4:
            continue
        elif token == 9:
            if stack:
                raise ValueError('unclosed nodes')
            return nodes
        else:
            raise ValueError(f'unknown FDT token {token}')
    raise ValueError('missing FDT end')


def dsi_commands(blob):
    """Qualcomm MDSS DSI packet header: type,last,VC,ACK,wait,len_be16."""
    result, pos = [], 0
    while pos < len(blob):
        if pos+7 > len(blob):
            raise ValueError('truncated MDSS command header')
        kind, last, channel, ack, wait = blob[pos:pos+5]
        length = int.from_bytes(blob[pos+5:pos+7], 'big')
        pos += 7
        if pos+length > len(blob):
            raise ValueError('truncated MDSS command payload')
        result.append(dict(type=kind, last=last, channel=channel, ack=ack,
                           delay_ms=wait, payload=blob[pos:pos+length].hex()))
        pos += length
    return result


def describe(value):
    result = {'hex': value.hex()}
    if value and len(value) % 4 == 0:
        result['cells'] = list(struct.unpack('>'+str(len(value)//4)+'I', value))
    if value.endswith(b'\0'):
        try:
            strings = value[:-1].decode().split('\0')
            if all(s and s.isprintable() for s in strings):
                result['strings'] = strings
        except UnicodeDecodeError:
            pass
    return result


def report(data):
    nodes = parse_fdt(data)
    handles = {int.from_bytes(p['phandle'], 'big'): n for n, p in nodes.items() if len(p.get('phandle', b'')) == 4}
    def reference(value):
        path = handles.get(int.from_bytes(value, 'big')) if len(value) == 4 else None
        if path is None:
            return {'unresolved': value.hex()}
        props = nodes[path]
        return {'node': path, 'properties': {k: describe(v) for k, v in props.items()
                 if k.startswith(('regulator-', 'qcom,supply-', 'qcom,resource-'))}}
    inventory, candidates, defaults, controllers = [], [], [], []
    for node, props in nodes.items():
        if 'qcom,mdss-dsi-panel-name' in props:
            inventory.append({'node': node, 'name': describe(props['qcom,mdss-dsi-panel-name'])})
        if 'qcom,dsi-default-panel' in props:
            defaults.append({'display': node, 'reference': reference(props['qcom,dsi-default-panel'])})
        if ('qcom,mdss-dsi-panel-name' in props and 'l11r' in node.rsplit('/', 1)[-1].lower()) or props.get('mi,panel-id', b'').startswith(b'L11R'):
            selected = {}
            for path, fields in nodes.items():
                if path != node and not path.startswith(node+'/'):
                    continue
                entry = {}
                for key, value in fields.items():
                    if key in ('qcom,mdss-dsi-on-command', 'qcom,mdss-dsi-off-command', 'qcom,mdss-dsi-timing-switch-command', 'qcom,mdss-dsi-post-mode-switch-on-command'):
                        entry[key] = {'bytes': len(value), 'sha256': hashlib.sha256(value).hexdigest(), 'packets': dsi_commands(value)}
                    elif key.startswith(('qcom,mdss-dsi-', 'qcom,mdss-dsc-', 'qcom,platform-', 'qcom,panel-supply', 'mi,panel-id')):
                        entry[key] = describe(value)
                selected[path] = entry
            supplies = None
            if 'qcom,panel-supply-entries' in props:
                supplies = reference(props['qcom,panel-supply-entries'])
                root = supplies.get('node')
                if root:
                    supplies['entries'] = {p: {k: describe(v) for k, v in f.items()} for p, f in nodes.items() if p.startswith(root+'/')}
            candidates.append({'node': node, 'properties': selected, 'panel_supplies': supplies})
        if any(word in node for word in ('dsi_ctrl', 'dsi_phy', 'dsi-ctrl', 'dsi-phy', 'mdss_mdp', 'dsi-display')):
            supply = {k: reference(v) for k, v in props.items() if k.endswith('-supply')}
            if supply:
                controllers.append({'node': node, 'supplies': supply})
    return {'sha256': hashlib.sha256(data).hexdigest(), 'panel_inventory': inventory,
            'default_panel_references': defaults, 'l11r_candidates': candidates,
            'controller_supplies': controllers,
            'limitation': 'Inventory and static defaults do not establish the bootloader-selected physical panel. Need Android cmdline/bootconfig or active panel identification.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dtb', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    try:
        result = report(args.dtb.read_bytes())
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open('x') as handle:
            json.dump(result, handle, indent=2)
            handle.write('\n')
        print(f"Panels: {len(result['panel_inventory'])}; L11R nodes: {len(result['l11r_candidates'])}; evidence: {args.output}")
    except (OSError, ValueError, UnicodeDecodeError, struct.error) as error:
        parser.exit(1, f'display-audit: {error}\n')

if __name__ == '__main__':
    main()
