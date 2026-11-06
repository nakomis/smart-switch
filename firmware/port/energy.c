// The energy total. See energy.h.
#include "energy.h"

#include <math.h>
#include <string.h>

void energy_init(energy_t *e, uint64_t stored_mwh, double pulses_per_kwh, int64_t now_ms)
{
    memset(e, 0, sizeof(*e));
    e->pulses_per_kwh = pulses_per_kwh;
    e->base_mwh = stored_mwh;
    e->saved_mwh = stored_mwh;
    e->saved_ms = now_ms;
}

bool energy_update(energy_t *e, uint32_t cf_cnt, int64_t now_ms)
{
    cf_cnt &= ENERGY_CF_MASK;
    if (!e->have_last)
    {
        e->have_last = true;
        e->last_cnt = cf_cnt;
        e->last_ms = now_ms;
        return true;
    }
    uint32_t delta = (cf_cnt - e->last_cnt) & ENERGY_CF_MASK;
    double elapsed_h = (double)(now_ms - e->last_ms) / 3.6e6;
    if (elapsed_h < 0)
        elapsed_h = 0;
    // The most pulses ENERGY_MAX_WATTS could make since the last reading, plus two for timing.
    double max = ENERGY_MAX_WATTS / 1000.0 * elapsed_h * e->pulses_per_kwh + 2.0;
    e->last_cnt = cf_cnt;
    e->last_ms = now_ms;
    if ((double)delta > max)
    {
        e->rejected++;
        return false;
    }
    e->pulses += delta;
    return true;
}

uint64_t energy_mwh(const energy_t *e)
{
    if (!(e->pulses_per_kwh > 0))
        return e->base_mwh;
    return e->base_mwh + (uint64_t)floor((double)e->pulses * 1e6 / e->pulses_per_kwh);
}

double energy_kwh(const energy_t *e)
{
    return (double)energy_mwh(e) / 1e6;
}

bool energy_save_due(const energy_t *e, int64_t now_ms)
{
    uint64_t now_mwh = energy_mwh(e);
    if (now_mwh <= e->saved_mwh)
        return false;
    int64_t since = now_ms - e->saved_ms;
    if (since >= ENERGY_SAVE_INTERVAL_MS)
        return true;
    return now_mwh - e->saved_mwh >= ENERGY_SAVE_BIG_MWH && since >= ENERGY_SAVE_BIG_INTERVAL_MS;
}

void energy_saved(energy_t *e, uint64_t mwh, int64_t now_ms)
{
    e->saved_mwh = mwh;
    e->saved_ms = now_ms;
}
