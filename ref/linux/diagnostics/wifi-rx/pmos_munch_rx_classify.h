/* SPDX-License-Identifier: GPL-2.0-only */
/* Header-only classification for the isolated RX probe. No packet mutation. */
#ifndef PMOS_MUNCH_RX_CLASSIFY_H
#define PMOS_MUNCH_RX_CLASSIFY_H

enum pmos_rx_kind {
	PMOS_RX_UNKNOWN,
	PMOS_RX_OTHER,
	PMOS_RX_DATA,
	PMOS_RX_EAPOL,
};

static inline enum pmos_rx_kind
pmos_rx_classify(const unsigned char *p, unsigned int len,
		 bool ethernet, bool iv_stripped)
{
	unsigned int hlen;

	if (ethernet) {
		if (len < 14)
			return PMOS_RX_UNKNOWN;
		return p[12] == 0x88 && p[13] == 0x8e ?
			PMOS_RX_EAPOL : PMOS_RX_DATA;
	}
	if (len < 2)
		return PMOS_RX_UNKNOWN;
	/* Data with payload, excluding null-data subtypes and nonzero versions. */
	if ((p[0] & 0x4f) != 0x08)
		return PMOS_RX_OTHER;
	hlen = 24;
	if ((p[1] & 3) == 3)
		hlen += 6;
	if (p[0] & 0x80) {
		hlen += 2;
		if (p[1] & 0x80)
			hlen += 4;
	}
	if (len < hlen)
		return PMOS_RX_UNKNOWN;
	/* Do not interpret an encrypted body or an A-MSDU as an LLC header. */
	if ((p[1] & 0x40) && !iv_stripped)
		return PMOS_RX_DATA;
	if ((p[0] & 0x80) && (p[(p[1] & 3) == 3 ? 30 : 24] & 0x80))
		return PMOS_RX_DATA;
	if (len < hlen + 8)
		return PMOS_RX_DATA;
	p += hlen;
	if (p[0] == 0xaa && p[1] == 0xaa && p[2] == 3 &&
	    p[3] == 0 && p[4] == 0 && (p[5] == 0 || p[5] == 0xf8) &&
	    p[6] == 0x88 && p[7] == 0x8e)
		return PMOS_RX_EAPOL;
	return PMOS_RX_DATA;
}
#endif
