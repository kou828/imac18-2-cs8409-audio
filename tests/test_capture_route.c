/* SPDX-License-Identifier: GPL-2.0-or-later */
#include <assert.h>
#include <stdio.h>

#include "../source/imac_mic_route.h"

struct calls {
	int generic;
	int apple;
	int generic_result;
	int apple_result;
};

static int generic_prepare(void *opaque)
{
	struct calls *calls = opaque;
	calls->generic++;
	return calls->generic_result;
}

static int apple_prepare(void *opaque)
{
	struct calls *calls = opaque;
	calls->apple++;
	return calls->apple_result;
}

static void test_adc_resolution(void)
{
	const unsigned int dynamic[] = { 1, 0, 2 };
	unsigned int adc = 99;

	assert(imac_mic_resolve_adc_index(0, 3, 3, dynamic, 3, 3, 3,
					  &adc) == 0);
	assert(adc == 1);
	assert(imac_mic_resolve_adc_index(2, 3, 3, dynamic, 3, 3, 3,
					  &adc) == 0);
	assert(adc == 2);
	assert(imac_mic_resolve_adc_index(3, 3, 4, dynamic, 4, 4, 4,
					  &adc) == -1);
	assert(imac_mic_resolve_adc_index(2, 3, 2, dynamic, 3, 3, 3,
					  &adc) == -1);
	assert(imac_mic_resolve_adc_index(2, 3, 3, dynamic, 2, 3, 3,
					  &adc) == -1);
	assert(imac_mic_resolve_adc_index(0, 3, 3, dynamic, 3, 1, 3,
					  &adc) == -1);
	assert(imac_mic_resolve_adc_index(0, 3, 3, dynamic, 3, 3, 1,
					  &adc) == -1);
	assert(imac_mic_resolve_adc_index(0, 3, 3, NULL, 3, 3, 3,
					  &adc) == -1);
	assert(imac_mic_resolve_adc_index(0, 3, 3, dynamic, 3, 3, 3,
					  NULL) == -1);
}

static void test_route_selection_and_dispatch(void)
{
	struct calls calls = { .generic_result = -1, .apple_result = -7 };
	enum imac_mic_capture_route route;

	route = imac_mic_route_for_adc(0x23, 0x23);
	assert(route == IMAC_MIC_ROUTE_APPLE);
	assert(imac_mic_dispatch_prepare(route, generic_prepare,
					 apple_prepare, &calls) == -7);
	assert(calls.apple == 1 && calls.generic == 0);

	route = imac_mic_route_for_adc(0x22, 0x23);
	assert(route == IMAC_MIC_ROUTE_GENERIC);
	assert(imac_mic_dispatch_prepare(route, generic_prepare,
					 apple_prepare, &calls) == -1);
	assert(calls.apple == 1 && calls.generic == 1);

	assert(imac_mic_dispatch_prepare(IMAC_MIC_ROUTE_INVALID,
					 generic_prepare, apple_prepare,
					 &calls) == IMAC_MIC_DISPATCH_INVALID);
	assert(calls.apple == 1 && calls.generic == 1);
	assert(imac_mic_dispatch_prepare(IMAC_MIC_ROUTE_APPLE,
					 generic_prepare, NULL, &calls) == IMAC_MIC_DISPATCH_INVALID);
	assert(calls.apple == 1 && calls.generic == 1);
}

int main(void)
{
	test_adc_resolution();
	test_route_selection_and_dispatch();
	puts("capture route tests: PASS");
	return 0;
}
