"""Exercise the actual diagnostic header parser on synthetic frames."""
import ctypes
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(shutil.which('cc'), 'host C compiler required')
class WifiRxProbeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        path = Path(cls.tmp.name)
        source = path / 'probe.c'
        source.write_text('''#include <stdbool.h>
#include "pmos_munch_rx_classify.h"
int classify(const unsigned char *p, unsigned int n, bool eth, bool clear) {
 return pmos_rx_classify(p, n, eth, clear);
}
''')
        library = path / 'probe.so'
        subprocess.run(['cc', '-shared', '-fPIC', '-std=c99', '-Wall', '-Wextra',
                        '-Werror', '-I'+str(ROOT/'diagnostics/wifi-rx'),
                        str(source), '-o', str(library)], check=True)
        cls.library = ctypes.CDLL(str(library))
        cls.parse = cls.library.classify
        cls.parse.argtypes = [ctypes.POINTER(ctypes.c_ubyte), ctypes.c_uint,
                              ctypes.c_bool, ctypes.c_bool]
        cls.parse.restype = ctypes.c_int

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def classify(self, packet, ethernet=False, iv_stripped=False):
        buf = (ctypes.c_ubyte * len(packet)).from_buffer_copy(packet)
        before = bytes(buf)
        result = self.parse(buf, len(packet), ethernet, iv_stripped)
        self.assertEqual(bytes(buf), before, 'probe must not mutate packets')
        return result

    def frame(self, qos=False, four_addr=False, htc=False):
        header = bytearray(24 + 6*four_addr + 2*qos + 4*(qos and htc))
        header[0] = 0x88 if qos else 0x08
        header[1] = (3 if four_addr else 0) | (0x80 if htc else 0)
        return header + bytes.fromhex('aaaa03000000888e')

    def test_ethernet_and_all_truncated_headers(self):
        frame = bytes(12) + bytes.fromhex('888e')
        self.assertEqual(self.classify(frame, ethernet=True), 3)
        for n in range(14):
            self.assertEqual(self.classify(frame[:n], ethernet=True), 0)
        self.assertEqual(self.classify(bytes(12)+bytes.fromhex('0800'), True), 2)

    def test_native_qos_four_address_and_htc_headers(self):
        for qos in (False, True):
            for four_addr in (False, True):
                for htc in (False, True):
                    frame = self.frame(qos, four_addr, htc)
                    self.assertEqual(self.classify(frame), 3)
                    # Every truncated form must be safe and must not claim EAPOL.
                    for n in range(len(frame)):
                        self.assertNotEqual(self.classify(frame[:n]), 3)

    def test_management_null_encrypted_and_amsdu_are_not_eapol(self):
        frame = self.frame()
        for kind in (0x80, 0x48, 0xc8):
            changed = bytearray(frame); changed[0] = kind
            self.assertEqual(self.classify(changed), 1)
        frame[1] |= 0x40
        self.assertEqual(self.classify(frame), 2)
        self.assertEqual(self.classify(frame, iv_stripped=True), 3)
        frame = self.frame(qos=True); frame[24] |= 0x80
        self.assertEqual(self.classify(frame), 2)

    def test_llc_must_match_and_bridge_tunnel_is_supported(self):
        frame = self.frame()
        frame[29] = 0xf8
        self.assertEqual(self.classify(frame), 3)
        for offset in (24, 25, 26, 27, 28, 29, 30, 31):
            changed = bytearray(self.frame()); changed[offset] ^= 0x10
            self.assertEqual(self.classify(changed), 2)

    def test_bounds_under_address_and_undefined_sanitizers(self):
        path = Path(self.tmp.name)
        source = path / 'bounds.c'
        source.write_text('''#include <stdbool.h>
#include <stdlib.h>
#include <string.h>
#include "pmos_munch_rx_classify.h"
int main(void) {
 unsigned int n, i;
 volatile int result = 0;
 for (n = 0; n <= 64; n++) {
  unsigned char *p = malloc(n ? n : 1);
  if (!p) return 1;
  for (i = 0; i < 65536; i++) {
   memset(p, 0xaa, n);
   if (n) p[0] = i >> 8;
   if (n > 1) p[1] = i;
   result = pmos_rx_classify(p, n, false, false);
   result = pmos_rx_classify(p, n, false, true);
   result = pmos_rx_classify(p, n, true, false);
  }
  free(p);
 }
 (void)result;
 return 0;
}
''')
        binary = path / 'bounds'
        subprocess.run(['cc', '-std=c99', '-O1', '-g',
                        '-fsanitize=address,undefined', '-fno-omit-frame-pointer',
                        '-I'+str(ROOT/'diagnostics/wifi-rx'), str(source),
                        '-o', str(binary)], check=True)
        subprocess.run([str(binary)], check=True, timeout=30)
