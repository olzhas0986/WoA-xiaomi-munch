#include <stdint.h>
#include "fb.h"
#define PAYLOAD_OFFSET 0x100000UL
#define MAX_BLOB 0x10000000UL /* explicit 256 MiB v1 container limit */
#define MAGIC 0x313048434e554d50UL /* little-endian "PMUNCH01" */
struct item { uint64_t dest, size, memory_size, offset; };
struct header {
 uint64_t magic, version, count, total, entry, dtb;
 struct item items[3];
};
extern char _start[], __end[];
extern void kernel_enter(uint64_t dtb, uint64_t entry) __attribute__((noreturn));
static void halt(uint64_t code) __attribute__((noreturn));
static void halt(uint64_t code)
{
 const char *reason[] = {"UNKNOWN ERROR", "INVALID PAYLOAD HEADER",
  "INVALID PAYLOAD LENGTH", "LOADER OVERLAPS PAYLOAD", "INVALID BOOT ADDRESSES",
  "INVALID PAYLOAD ITEM", "DESTINATION OVERLAPS LOADER",
  "PAYLOAD ITEMS OVERLAP", "INVALID ARM64 KERNEL IMAGE", "INVALID DEVICE TREE",
  "RAM COPY VERIFICATION FAILED"};
 fb_error(code < sizeof(reason)/sizeof(reason[0]) ? reason[code] : "CPU EXCEPTION");
 fb_puts("ERROR CODE: "); fb_hex(code);
 for (;;) __asm__ volatile("wfe");
}
void loader_exception(uint64_t esr, uint64_t elr, uint64_t far)
{ fb_error("CPU EXCEPTION"); fb_puts("ESR: "); fb_hex(esr); fb_puts("ELR: "); fb_hex(elr); fb_puts("FAR: "); fb_hex(far); halt(0xee); }
static int overlap(uint64_t a, uint64_t n, uint64_t b, uint64_t m)
{ return a < b+m && b < a+n; }
static uint64_t le64(const uint8_t *p)
{ uint64_t v=0; for (unsigned i=0;i<8;i++) v |= (uint64_t)p[i]<<(8*i); return v; }
static uint32_t be32(const uint8_t *p)
{ return (uint32_t)p[0]<<24 | (uint32_t)p[1]<<16 | (uint32_t)p[2]<<8 | p[3]; }
static void clean(uint64_t start, uint64_t size)
{
 uint64_t ctr;
 __asm__ volatile("mrs %0, ctr_el0" : "=r"(ctr));
 uint64_t line = 4UL << ((ctr >> 16)&15);
 for (uint64_t p=start & ~(line-1); p<start+size; p+=line)
  __asm__ volatile("dc cvac, %0" :: "r"(p) : "memory");
 __asm__ volatile("dsb sy" ::: "memory");
}
void loader_main(uint64_t firmware_dtb)
{
 (void)firmware_dtb;
 fb_init();
 /* start.S has already rejected non-EL1, MMU-on or D-cache-on entry. */
 fb_puts("Booting linux...\n");
 const struct header *h=(const void *)(_start+PAYLOAD_OFFSET);
 if (h->magic!=MAGIC || h->version!=1 || (h->count!=2 && h->count!=3)) halt(1);
 uint64_t base=(uint64_t)_start, source=base+PAYLOAD_OFFSET;
 if (h->total<4096 || h->total>MAX_BLOB || source<base || source+h->total<source) halt(2);
 uint64_t live_end=source+h->total;
 if ((uint64_t)__end>source) halt(3);
 /* Fixed destination windows are a deliberately narrow board contract.
  * Packer also checks final DT memory/reservations; never accept arbitrary writes.
  */
 const uint64_t lower[3]={0xc0200000,0xc8000000,0xc8400000};
 const uint64_t upper[3]={0xc8000000,0xc8200000,0xffc00000};
 if (h->entry!=lower[0] || h->dtb!=lower[1]) halt(4);
 for (uint64_t i=0;i<h->count;i++) {
  const struct item *e=&h->items[i];
  if (e->dest!=lower[i] || !e->size || e->memory_size<e->size ||
      e->memory_size>upper[i]-e->dest || e->offset<4096 || (e->offset&4095) ||
      e->offset>h->total || e->size>h->total-e->offset) halt(5);
  if (overlap(e->dest,e->memory_size,base,live_end-base)) halt(6);
  for (uint64_t j=0;j<i;j++)
   if (overlap(e->offset,e->size,h->items[j].offset,h->items[j].size)) halt(7);
 }
 const uint8_t *image=(const void *)(source+h->items[0].offset);
 if (h->items[0].size<64 || be32(image+56)!=0x41524d64 ||
     !le64(image+16) || le64(image+16)!=h->items[0].memory_size ||
     le64(image+8)>h->entry || ((h->entry-le64(image+8))&0x1fffff) ||
     (le64(image+24)&1) || !(le64(image+24)&8)) halt(8);
 const uint8_t *dt=(const void *)(source+h->items[1].offset);
 if (h->items[1].size<40 || be32(dt)!=0xd00dfeed || be32(dt+4)!=h->items[1].size) halt(9);
 for (uint64_t i=0;i<h->count;i++) {
  const struct item *e=&h->items[i];
  const volatile uint8_t *s=(const void *)(source+e->offset);
  volatile uint8_t *d=(void *)e->dest;
  /* All starts are 4K aligned; use aligned words with an exact byte tail. */
  uint64_t words=e->size/8;
  volatile uint64_t *dw=(void *)e->dest;
  const volatile uint64_t *sw=(const void *)(source+e->offset);
  for (uint64_t j=0;j<words;j++) dw[j]=sw[j];
  for (uint64_t j=words*8;j<e->size;j++) d[j]=s[j];
  for (uint64_t j=0;j<e->size;j++) if (d[j]!=s[j]) halt(10);
  clean(e->dest,e->size);
 }
 kernel_enter(h->dtb,h->entry);
}
