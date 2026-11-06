// Zero-cross switching. See zx.h.
#include "zx.h"

int64_t zx_period_us(const zx_edges *z, int64_t now_us)
{
    if (z->n < 3 || now_us - z->t[2] > ZX_STALE_US)
        return 0;
    int64_t period = z->t[2] - z->t[0];
    int64_t half = z->t[2] - z->t[1];
    if (period < ZX_MIN_PERIOD_US || period > ZX_MAX_PERIOD_US)
        return 0;
    // The two halves may differ, but not by more than half again.
    if (half * 4 < period || half * 4 > period * 3)
        return 0;
    return period;
}

// The first base + k * period (k >= 0) at or after earliest.
static int64_t next_at(int64_t base, int64_t period, int64_t earliest)
{
    if (base >= earliest)
        return base;
    int64_t k = (earliest - base + period - 1) / period;
    return base + k * period;
}

int64_t zx_switch_at(const zx_edges *z, int64_t now_us, int64_t actuate_us)
{
    int64_t period = zx_period_us(z, now_us);
    if (period == 0 || actuate_us < 0)
        return -1;
    int64_t earliest = now_us + ZX_LEAD_US + actuate_us;  // the soonest the contacts can move
    int64_t a = next_at(z->t[1], period, earliest);
    int64_t b = next_at(z->t[2], period, earliest);
    return (a < b ? a : b) - actuate_us;
}
