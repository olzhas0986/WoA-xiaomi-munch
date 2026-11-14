"""Exercise the actual boot text renderer with a host-backed framebuffer."""
import pathlib
import subprocess
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]


class LoaderFontTest(unittest.TestCase):
    def test_boot_message_renders_every_glyph(self):
        source = (ROOT / 'loader/fb.c').read_text().replace(
            '(volatile uint32_t *)0x9c000000UL', 'test_framebuffer')
        harness = '''
#include <stdint.h>
static uint32_t test_framebuffer[1080*2400];
'''+source+'''
int main(void) {
 const char *message="Booting linux...";
 fb_init(); fb_puts(message);
 for (unsigned c=0; message[c]; c++)
  for (unsigned y=0; y<7; y++)
   for (unsigned x=0; x<5; x++) {
    unsigned expected=(glyphs[(unsigned char)message[c]][y] >> (4-x)) & 1;
    unsigned actual=test_framebuffer[(132+y*3)*1080+54+c*18+x*3] == FG;
    if (actual != expected) return 1;
   }
 return 0;
}
'''
        with tempfile.TemporaryDirectory() as tmp:
            src = pathlib.Path(tmp)/'font.c'
            exe = pathlib.Path(tmp)/'font'
            src.write_text(harness)
            subprocess.run(['cc', '-I', str(ROOT/'loader'), str(src), '-o', str(exe)], check=True)
            subprocess.run([str(exe)], check=True)
