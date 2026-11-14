/* SPDX-License-Identifier: GPL-2.0-only */
/* FT3658U wire decoding, from Xiaomi munch-s-oss focaltech_spi. */
#define MUNCH_TOUCH_POINTS 10
#define MUNCH_TOUCH_BYTES 62
struct munch_touch_point { unsigned int x, y, id, area; };
static inline unsigned int munch_touch_crc(const unsigned char *p, unsigned int n)
{
 unsigned int crc = 0xffff, i;
 while (n--) {
  crc ^= *p++;
  for (i = 0; i < 8; i++)
   crc = (crc >> 1) ^ ((crc & 1) ? 0x8408 : 0);
 }
 return crc;
}
/* Return active contacts or -1 for malformed frames; never report a partial frame. */
static inline int munch_touch_decode(const unsigned char *p,
                                    struct munch_touch_point *out,
                                    unsigned int max_x, unsigned int max_y)
{
 unsigned int i, count = p[1] & 15, seen = 0, n = 0;
 if (count > MUNCH_TOUCH_POINTS)
  return -1;
 for (i = 0; i < MUNCH_TOUCH_POINTS; i++) {
  unsigned int b = 2 + i * 6, id = p[b + 2] >> 4, flag = p[b] >> 6;
  unsigned int x, y;
  if (id == 15)
   break;
  if (id >= MUNCH_TOUCH_POINTS || (seen & (1U << id)) || flag == 3)
   return -1;
  seen |= 1U << id;
  if (flag == 1)
   continue;
  x = ((p[b] & 15) << 11) | (p[b + 1] << 3) | (p[b + 4] >> 5);
  y = ((p[b + 2] & 15) << 11) | (p[b + 3] << 3) | ((p[b + 4] >> 2) & 7);
  if (!count || x > max_x || y > max_y)
   return -1;
  out[n++] = (struct munch_touch_point){ x, y, id, p[b + 5] >> 4 };
 }
 if (n != count)
  return -1;
 return n;
}
