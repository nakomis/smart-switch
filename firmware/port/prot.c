// Petro's protection. See prot.h.
#include "prot.h"

#include <math.h>
#include <string.h>

prot_config prot_defaults(void)
{
    prot_config c = {
        .sustain_ms = PROT_SUSTAIN_MS,
        .overtemp_c = PROT_OVERTEMP_C,
        .overtemp_ms = PROT_OVERTEMP_MS,
        .clear_margin_c = PROT_CLEAR_MARGIN_C,
        .stale_ms = PROT_STALE_MS,
    };
    return c;
}

void prot_init(prot_t *p, const prot_config *cfg, int64_t now_ms)
{
    memset(p, 0, sizeof(*p));
    p->cfg = *cfg;
    p->boot_ms = now_ms;
}

void prot_meter_init(prot_t *p, bool ok)
{
    p->meter_init = ok;
}

void prot_frame(prot_t *p, double amps_a, double amps_b, double trip_amps, int64_t now_ms)
{
    p->have_frame = true;
    p->frame_ms = now_ms;
    p->amps = isnan(amps_a) || isnan(amps_b) ? NAN : fmax(amps_a, amps_b);
    // NaN is over: a frame that can't be read as a current isn't one to trust as "below".
    bool over = !(amps_a <= trip_amps) || !(amps_b <= trip_amps);
    if (over && !p->amps_over)
        p->amps_over_ms = now_ms;
    p->amps_over = over;
}

void prot_temp(prot_t *p, bool have, double celsius, int64_t now_ms)
{
    if (!have || !isfinite(celsius))
        return;  // the last good reading ages (prot_healthy)
    p->have_temp = true;
    p->temp_ms = now_ms;
    p->temp_c = celsius;
    bool over = celsius >= p->cfg.overtemp_c;
    if (over && !p->temp_over)
        p->temp_over_ms = now_ms;
    p->temp_over = over;
}

void prot_oc(prot_t *p, bool active, bool relay_closed)
{
    p->oc_active = active;
    p->oc_relay_closed = relay_closed;
}

void prot_oc_armed(prot_t *p, bool armed)
{
    p->oc_armed = armed;
}

static bool fresh(bool have, int64_t at_ms, int64_t now_ms, uint32_t stale_ms);

// A fresh frame with both channels under PROT_ARM_MAX_AMPS (NaN isn't).
static bool no_current(const prot_t *p, int64_t now_ms)
{
    return fresh(p->have_frame, p->frame_ms, now_ms, p->cfg.stale_ms) && p->amps < PROT_ARM_MAX_AMPS;
}

bool prot_may_arm_oc(const prot_t *p, bool configured, bool relay_open, int64_t now_ms)
{
    return configured && relay_open && no_current(p, now_ms);
}

ctl_trip_cause prot_oc_cause(const prot_t *p, int64_t now_ms)
{
    return !p->oc_relay_closed && no_current(p, now_ms) ? CTL_TRIP_METER_FAULT : CTL_TRIP_OVERCURRENT_INSTANT;
}

bool prot_oc_release_due(ctl_trip_cause before, ctl_trip_cause after)
{
    return before != CTL_TRIP_NONE && after == CTL_TRIP_NONE;
}

static bool fresh(bool have, int64_t at_ms, int64_t now_ms, uint32_t stale_ms)
{
    return have && now_ms - at_ms <= (int64_t)stale_ms;
}

bool prot_healthy(const prot_t *p, int64_t now_ms)
{
    return p->meter_init && p->oc_armed && fresh(p->have_frame, p->frame_ms, now_ms, p->cfg.stale_ms) &&
           fresh(p->have_temp, p->temp_ms, now_ms, p->cfg.stale_ms);
}

bool prot_starting(const prot_t *p, int64_t now_ms)
{
    return p->meter_init && now_ms - p->boot_ms < (int64_t)p->cfg.stale_ms && !prot_healthy(p, now_ms);
}

ctl_trip_cause prot_check(const prot_t *p, bool relay_wanted, int64_t now_ms)
{
    if (p->oc_active)
        return prot_oc_cause(p, now_ms);
    if (p->amps_over && now_ms - p->amps_over_ms >= (int64_t)p->cfg.sustain_ms)
        return CTL_TRIP_OVERCURRENT;
    if (p->temp_over && now_ms - p->temp_over_ms >= (int64_t)p->cfg.overtemp_ms)
        return CTL_TRIP_OVERTEMP;
    if (relay_wanted && !prot_healthy(p, now_ms) && !prot_starting(p, now_ms))
        return CTL_TRIP_METER_FAULT;
    return CTL_TRIP_NONE;
}

bool prot_clear_blocked(const prot_t *p, ctl_trip_cause latched, int64_t now_ms)
{
    if (p->oc_active || p->amps_over)
        return true;
    if (fresh(p->have_temp, p->temp_ms, now_ms, p->cfg.stale_ms))
        return p->temp_c > p->cfg.overtemp_c - p->cfg.clear_margin_c;
    return latched == CTL_TRIP_OVERTEMP;
}

uint32_t prot_fast_rms_ctrl(double amps, double counts_per_amp)
{
    double th = amps * counts_per_amp / 256.0;
    if (!(th >= 1.0))
        return 1;
    if (th > 0x7FFF)
        return 0x7FFF;
    return (uint32_t)lround(th);
}

double prot_ntc_limit(double room_c, double hot_limit_c, double ratio)
{
    return room_c + (hot_limit_c - room_c) / ratio;
}
