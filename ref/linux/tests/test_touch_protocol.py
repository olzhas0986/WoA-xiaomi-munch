"""Execute the exact kernel wire decoder with recorded-format boundary frames."""
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class TouchProtocolTests(unittest.TestCase):
    def test_high_resolution_crc_and_malformed_frames(self):
        code = r'''
#include <assert.h>
#include <string.h>
#include "munch-touch-protocol.h"
static void point(unsigned char *p, unsigned i, unsigned id, unsigned x, unsigned y, unsigned flag) {
 unsigned b=2+i*6;
 p[b]=(flag<<6)|((x>>11)&15); p[b+1]=(x>>3)&255;
 p[b+2]=(id<<4)|((y>>11)&15); p[b+3]=(y>>3)&255;
 p[b+4]=((x&7)<<5)|((y&7)<<2)|3; p[b+5]=0x90;
}
int main(void) {
 unsigned char p[MUNCH_TOUCH_BYTES]; struct munch_touch_point out[10];
 assert(munch_touch_crc((const unsigned char *)"123456789",9)==0x6f91);
 memset(p,255,sizeof(p)); p[0]=0; p[1]=1;
 point(p,0,4,10791,23998,0);
 assert(munch_touch_decode(p,out,10799,23999)==1);
 assert(out[0].x==10791 && out[0].y==23998 && out[0].id==4);
 point(p,0,4,10800,23998,0);
 assert(munch_touch_decode(p,out,10799,23999)==-1);
 memset(p,255,sizeof(p)); p[0]=0; p[1]=0;
 assert(munch_touch_decode(p,out,10799,23999)==0);
 point(p,0,4,100,100,1);
 assert(munch_touch_decode(p,out,10799,23999)==0);
 point(p,0,4,100,100,0);
 assert(munch_touch_decode(p,out,10799,23999)==-1);
 memset(p,255,sizeof(p)); p[0]=0; p[1]=10;
 for(unsigned i=0;i<10;i++) point(p,i,i,100+i,200+i,2);
 assert(munch_touch_decode(p,out,10799,23999)==10);
 point(p,9,0,100,100,2);
 assert(munch_touch_decode(p,out,10799,23999)==-1);
 memset(p,255,sizeof(p));
 assert(munch_touch_decode(p,out,10799,23999)==-1);
 return 0;
}
'''
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp); (p/'test.c').write_text(code)
            subprocess.run(['cc','-Wall','-Wextra','-Werror','-fsanitize=undefined',
                            '-I'+str(ROOT/'kernel-drivers'),str(p/'test.c'),'-o',str(p/'test')],check=True)
            subprocess.run([str(p/'test')],check=True)
