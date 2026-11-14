"""Check stock DSI decoding and reject unreviewed panel selections/timings."""
import importlib.util
from pathlib import Path
import struct
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('display_patch', ROOT/'tools/generate-display-patch.py')
display = importlib.util.module_from_spec(spec)
spec.loader.exec_module(display)


def fdt(nodes):
    names, body = bytearray(), bytearray()
    def word(*values):
        body.extend(struct.pack('>'+'I'*len(values), *values))
    def node(name, props, children):
        word(1)
        body.extend(name.encode()+b'\0')
        body.extend(b'\0'*(-len(body) % 4))
        for key, value in props.items():
            offset = len(names)
            names.extend(key.encode()+b'\0')
            word(3, len(value), offset)
            body.extend(value)
            body.extend(b'\0'*(-len(body) % 4))
        for child in children:
            node(*child)
        word(2)
    node('', {}, nodes)
    word(9)
    header = struct.pack('>10I', 0xd00dfeed, 56+len(body)+len(names),
                         56, 56+len(body), 40, 17, 16, 0, len(names), len(body))
    return header+b'\0'*16+body+names


def panel_blob(width=1080, refresh=60):
    values = {'panel-framerate':refresh, 'panel-width':width, 'panel-height':2400,
              'h-front-porch':16, 'h-pulse-width':8, 'h-back-porch':8,
              'v-front-porch':600, 'v-pulse-width':32, 'v-back-porch':560}
    if refresh == 120:
        values.update({'v-front-porch':4, 'v-pulse-width':4, 'v-back-porch':8})
    props = {'qcom,mdss-dsi-'+k: struct.pack('>I', v) for k, v in values.items()}
    props.update({'qcom,mdss-dsc-'+k:struct.pack('>I', v) for k, v in
                  {'slice-width':540, 'slice-height':8, 'bit-per-component':8, 'bit-per-pixel':8}.items()})
    for which in ('on', 'off'):
        props['qcom,mdss-dsi-'+which+'-command-state'] = b'dsi_lp_mode\0'
        props['qcom,mdss-dsi-'+which+'-command'] = bytes([0x39, 1, 0, 0, 90, 0, 2, 0x60, 0x10 if refresh == 120 else 0])
    return fdt([(display.SELECTOR, {}, [('timing0', props, [])])])


class DisplayTests(unittest.TestCase):
    def test_stock_120_profile_is_separate_and_timing_checked(self):
        cmdline = 'msm_drm.dsi_display0='+display.SELECTOR+':'
        text = display.header(panel_blob(refresh=120), cmdline, 120)
        self.assertIn('l11r_on_120[]', text)
        self.assertIn('{ 0x39, 0, 0, 90, 2, { 0x60, 0x10 } }', text)
        with self.assertRaisesRegex(ValueError, 'exactly one 120'):
            display.header(panel_blob(), cmdline, 120)
        with self.assertRaisesRegex(ValueError, 'unreviewed refresh'):
            display.header(panel_blob(), cmdline, 90)
        bad = panel_blob(refresh=120).replace(
            struct.pack('>I', 2400), struct.pack('>I', 2401))
        with self.assertRaisesRegex(ValueError, 'panel-height'):
            display.header(bad, cmdline, 120)

    def test_packet_preserves_long_type_and_delay(self):
        packet = bytes([0x39, 1, 0, 0, 90, 0, 2, 0x60, 0])
        decoded = display.audit.dsi_commands(packet)[0]
        self.assertEqual((decoded['type'], decoded['delay_ms'], decoded['payload']), (57, 90, '6000'))
        text = display.header(panel_blob(), 'msm_drm.dsi_display0='+display.SELECTOR+':')
        self.assertIn('{ 0x39, 0, 0, 90, 2, { 0x60, 0x00 } }', text)

    def test_truncated_packets_are_rejected(self):
        for packet in (b'\x39', bytes([0x39, 1, 0, 0, 0, 0, 2, 0x60])):
            with self.assertRaisesRegex(ValueError, 'truncated MDSS'):
                display.audit.dsi_commands(packet)

    def test_wrong_android_selection_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'does not select'):
            display.header(panel_blob(), 'msm_drm.dsi_display0=simulator:')

    def test_changed_timing_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'panel-width'):
            display.header(panel_blob(1440), 'msm_drm.dsi_display0='+display.SELECTOR+':')

    def test_fdt_bounds_are_checked(self):
        blob = panel_blob()
        for invalid in (blob[:20], blob[:-1], b'BAD!'+blob[4:]):
            with self.assertRaises(ValueError):
                display.audit.parse_fdt(invalid)

    def test_nested_node_paths(self):
        nodes = display.audit.parse_fdt(panel_blob())
        self.assertIn('/'+display.SELECTOR+'/timing0', nodes)
        self.assertEqual(len(nodes), 3)
