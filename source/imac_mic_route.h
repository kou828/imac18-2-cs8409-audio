/* SPDX-License-Identifier: GPL-2.0-or-later */
#ifndef IMAC_MIC_ROUTE_H
#define IMAC_MIC_ROUTE_H

/* Pure capture-routing helpers shared with the host-side tests. */
enum imac_mic_capture_route {
	IMAC_MIC_ROUTE_INVALID = -1,
	IMAC_MIC_ROUTE_GENERIC = 0,
	IMAC_MIC_ROUTE_APPLE = 1,
};

static inline int
imac_mic_resolve_adc_index(unsigned int mux,
			   unsigned int mux_slots,
			   int input_mux_items,
			   const unsigned int *dyn_adc_idx,
			   unsigned int dyn_adc_slots,
			   int num_all_adcs,
			   unsigned int adc_slots,
			   unsigned int *adc_index)
{
	unsigned int index;

	if (!dyn_adc_idx || !adc_index || input_mux_items <= 0 ||
	    num_all_adcs <= 0 || mux >= mux_slots ||
	    mux >= (unsigned int)input_mux_items || mux >= dyn_adc_slots)
		return -1;

	index = dyn_adc_idx[mux];
	if (index >= (unsigned int)num_all_adcs || index >= adc_slots)
		return -1;

	*adc_index = index;
	return 0;
}

static inline enum imac_mic_capture_route
imac_mic_route_for_adc(unsigned int adc_nid, unsigned int internal_mic_nid)
{
	return adc_nid == internal_mic_nid ? IMAC_MIC_ROUTE_APPLE :
		IMAC_MIC_ROUTE_GENERIC;
}

typedef int (*imac_mic_prepare_callback)(void *context);
enum { IMAC_MIC_DISPATCH_INVALID = -4096 };

/* Invoke exactly one path and preserve the callback's return value. */
static inline int
imac_mic_dispatch_prepare(enum imac_mic_capture_route route,
			  imac_mic_prepare_callback generic_prepare,
			  imac_mic_prepare_callback apple_prepare,
			  void *context)
{
	if (route == IMAC_MIC_ROUTE_APPLE)
		return apple_prepare ? apple_prepare(context) : IMAC_MIC_DISPATCH_INVALID;
	if (route == IMAC_MIC_ROUTE_GENERIC)
		return generic_prepare ? generic_prepare(context) : IMAC_MIC_DISPATCH_INVALID;
	return IMAC_MIC_DISPATCH_INVALID;
}

#endif
