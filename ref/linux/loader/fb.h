#pragma once
#include <stdint.h>
void fb_puts(const char *s);
void fb_hex(uint64_t v);
void fb_init(void);
void fb_status(const char *s);
void fb_error(const char *s);
