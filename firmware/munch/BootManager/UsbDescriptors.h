/* SPDX-License-Identifier: APSL-2.0
 * USB descriptors and protocol sequence adapted from the UMI loader at
 * commit 6b6fb2b0c5a1720496ec71e88c95d2a45a0046a4. The original repository
 * location must be recovered before this file is redistributed independently;
 * see THIRD_PARTY.md.
 * The probe accepts only information queries, ping, and reboot.
 */


static const UINT8 probe_device[18] = {18,1,0x10,2,0,0,0,64,0xd1,0x18,0x0d,0xd0,0,1,1,2,3,1};
static const UINT8 probe_ss_device[18] = {18,1,0,3,0,0,0,9,0xd1,0x18,0x0d,0xd0,0,1,1,2,3,1};
static const UINT8 probe_config[32] = {
    9,2,32,0,1,1,0,0x80,0x50, 9,4,0,0,2,0xff,0x42,3,4,
    7,5,0x81,2,0,2,0, 7,5,1,2,0,2,0
};
static const UINT8 probe_ss_config[44] = {
    9,2,44,0,1,1,0,0x80,0x10, 9,4,0,0,2,0xff,0x42,3,4,
    7,5,0x81,2,0,4,0, 6,0x30,4,0,0,0,
    7,5,1,2,0,4,0, 6,0x30,4,0,0,0
};
static const UINT8 probe_qualifier[10] = {10,6,0,2,0xff,0xff,0xff,64,1,0};
static const UINT8 probe_bos[] = {
    5,0x0f,42,0,3, 7,0x10,2,6,0,0,0,
    10,0x10,3,0,0x0e,0,1,7,0x65,0,
    20,0x10,0x0a,0,1,0,0,0,0,0x11,0,0,0x30,0x40,0x0a,0,0xb0,0x40,0x0a,0
};
_Static_assert(sizeof(probe_bos) == 42, "BOS descriptor length mismatch");
static const UINT8 probe_language[4] = {4,3,9,4};
static const UINT8 probe_manufacturer[8] = {8,3,'X',0,'N',0,'U',0};
static const UINT8 probe_product[22] = {22,3,'m',0,'u',0,'n',0,'c',0,'h',0,'p',0,'r',0,'o',0,'b',0,'e',0};
static const UINT8 probe_serial[22] = {22,3,'M',0,'U',0,'N',0,'C',0,'H',0,'P',0,'R',0,'O',0,'B',0,'E',0};
static const UINT8 probe_interface[18] = {18,3,'f',0,'a',0,'s',0,'t',0,'b',0,'o',0,'o',0,'t',0};

