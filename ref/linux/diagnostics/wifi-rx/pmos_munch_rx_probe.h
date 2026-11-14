/* SPDX-License-Identifier: GPL-2.0-only */
/* Diagnostic build only: read-only cumulative counters, no packet logging. */
#ifndef PMOS_MUNCH_RX_PROBE_H
#define PMOS_MUNCH_RX_PROBE_H

#include <linux/atomic.h>
#include <linux/moduleparam.h>
#include <net/mac80211.h>
#include <net/pmos_munch_rx_classify.h>

static int pmos_rx_probe_get(char *buf, const struct kernel_param *kp)
{
	return scnprintf(buf, PAGE_SIZE, "%lld\n",
			 (long long)atomic64_read(kp->arg));
}

static const struct kernel_param_ops pmos_rx_probe_ops = {
	.get = pmos_rx_probe_get,
};

#define PMOS_RX_COUNTER(name) \
	static atomic64_t name = ATOMIC64_INIT(0); \
	module_param_cb(name, &pmos_rx_probe_ops, &name, 0444)

PMOS_RX_COUNTER(rx_probe_total);
PMOS_RX_COUNTER(rx_probe_data);
PMOS_RX_COUNTER(rx_probe_eapol);
PMOS_RX_COUNTER(rx_probe_unknown);

static void pmos_rx_probe_count(struct sk_buff *skb)
{
	struct ieee80211_rx_status *status = IEEE80211_SKB_RXCB(skb);
	unsigned char scratch[64];
	const unsigned char *p;
	unsigned int len = min_t(unsigned int, skb->len, sizeof(scratch));
	enum pmos_rx_kind kind = PMOS_RX_UNKNOWN;

	atomic64_inc(&rx_probe_total);
	/* Radiotap prefixes are not an Ethernet or 802.11 MAC header. */
	if (status->flag & (RX_FLAG_RADIOTAP_HE | RX_FLAG_RADIOTAP_HE_MU |
			    RX_FLAG_RADIOTAP_LSIG))
		goto unknown;
	p = skb_header_pointer(skb, 0, len, scratch);
	if (p)
		kind = pmos_rx_classify(p, len, status->flag & RX_FLAG_8023,
				       status->flag & RX_FLAG_IV_STRIPPED);
	if (kind == PMOS_RX_DATA || kind == PMOS_RX_EAPOL)
		atomic64_inc(&rx_probe_data);
	if (kind == PMOS_RX_EAPOL)
		atomic64_inc(&rx_probe_eapol);
unknown:
	if (kind == PMOS_RX_UNKNOWN)
		atomic64_inc(&rx_probe_unknown);
}
#endif
