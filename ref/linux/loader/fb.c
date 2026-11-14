#include "fb.h"
/* Inherited 1080x2400 ARGB framebuffer only; no display registers touched.
 * Original 5x7 font, scaled 3x. Lowercase glyphs cover the plain boot message.
 */
#define BG 0xff000000U
#define FG 0xffffffffU
static const uint8_t glyphs[128][7] = {
 ['0'] = {14,17,19,21,25,17,14},
 ['1'] = {4,12,4,4,4,4,14},
 ['2'] = {14,17,1,2,4,8,31},
 ['3'] = {30,1,1,14,1,1,30},
 ['4'] = {2,6,10,18,31,2,2},
 ['5'] = {31,16,16,30,1,1,30},
 ['6'] = {14,16,16,30,17,17,14},
 ['7'] = {31,1,2,4,8,8,8},
 ['8'] = {14,17,17,14,17,17,14},
 ['9'] = {14,17,17,15,1,1,14},
 ['A'] = {14,17,17,31,17,17,17},
 ['B'] = {30,17,17,30,17,17,30},
 ['C'] = {14,17,16,16,16,17,14},
 ['D'] = {30,17,17,17,17,17,30},
 ['E'] = {31,16,16,30,16,16,31},
 ['F'] = {31,16,16,30,16,16,16},
 ['G'] = {14,17,16,23,17,17,15},
 ['H'] = {17,17,17,31,17,17,17},
 ['I'] = {14,4,4,4,4,4,14},
 ['J'] = {7,2,2,2,18,18,12},
 ['K'] = {17,18,20,24,20,18,17},
 ['L'] = {16,16,16,16,16,16,31},
 ['M'] = {17,27,21,21,17,17,17},
 ['N'] = {17,25,21,19,17,17,17},
 ['O'] = {14,17,17,17,17,17,14},
 ['P'] = {30,17,17,30,16,16,16},
 ['Q'] = {14,17,17,17,21,18,13},
 ['R'] = {30,17,17,30,20,18,17},
 ['S'] = {15,16,16,14,1,1,30},
 ['T'] = {31,4,4,4,4,4,4},
 ['U'] = {17,17,17,17,17,17,14},
 ['V'] = {17,17,17,17,17,10,4},
 ['W'] = {17,17,17,21,21,21,10},
 ['X'] = {17,17,10,4,10,17,17},
 ['Y'] = {17,17,10,4,4,4,4},
 ['Z'] = {31,1,2,4,8,16,31},
 ['o'] = {0,0,14,17,17,17,14},
 ['t'] = {4,4,14,4,4,4,3},
 ['i'] = {4,0,12,4,4,4,14},
 ['n'] = {0,0,30,17,17,17,17},
 ['g'] = {0,0,15,17,15,1,14},
 ['l'] = {12,4,4,4,4,4,14},
 ['u'] = {0,0,17,17,17,19,13},
 ['x'] = {0,0,17,10,4,10,17},
 ['['] = {14,8,8,8,8,8,14},
 [']'] = {14,2,2,2,2,2,14},
 ['-'] = {0,0,0,31,0,0,0},
 [':'] = {0,4,4,0,4,4,0},
 ['.'] = {0,0,0,0,0,4,4},
 ['/'] = {1,2,2,4,8,8,16},
 ['?'] = {14,17,1,2,4,0,4},
};
static unsigned col, row;
static uint32_t ink = FG;
static void rectangle(unsigned x0, unsigned y0, unsigned w, unsigned h, uint32_t color)
{
 volatile uint32_t *fb = (volatile uint32_t *)0x9c000000UL;
 for (unsigned y=y0; y<y0+h; y++)
  for (unsigned x=x0; x<x0+w; x++) fb[y*1080+x]=color;
}
static void character(char c)
{
 if (c == '\n') { col=0; row++; return; }
 if (col == 54) { col=0; row++; }
 if (row >= 64) row=0;
 unsigned g=(unsigned char)c;
 unsigned present=0;
 if (g < 128)
  for (unsigned y=0; y<7; y++) present |= glyphs[g][y];
 if (g >= 128 || (c != ' ' && !present)) g='?';
 rectangle(54+col*18, 132+row*30, 18, 30, BG);
 for (unsigned y=0; y<7; y++)
  for (unsigned x=0; x<5; x++)
   if (glyphs[g][y] & (1U << (4-x)))
    rectangle(54+col*18+x*3,132+row*30+y*3,3,3,ink);
 col++;
}
void fb_puts(const char *s) { while (*s) character(*s++); }
void fb_init(void)
{
 col=row=0;
 rectangle(0,0,1080,2400,BG);
 ink=FG;
}
void fb_status(const char *s)
{
 ink=FG; fb_puts("[ ");
 ink=0xff00ff00U; fb_puts("OK");
 ink=FG; fb_puts(" ] ");
 ink=FG; fb_puts(s); fb_puts("\n");
}
void fb_error(const char *s)
{
 ink=0xffff8791U; fb_puts("\n[FAIL] "); fb_puts(s); fb_puts("\n");
}
void fb_hex(uint64_t v)
{
 for (int i=15; i>=0; i--) character("0123456789ABCDEF"[(v>>(i*4))&15]);
 character('\n');
}
