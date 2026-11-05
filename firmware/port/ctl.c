// Petro's control logic. See ctl.h.
#include "ctl.h"

#include <string.h>

#include "console_parse.h"

void ctl_init(ctl_t *c, bool have_stored, int stored_mode)
{
    memset(c, 0, sizeof(*c));
    c->mode = CTL_MODE_OFF;
    if (have_stored && (stored_mode == CTL_MODE_ON || stored_mode == CTL_MODE_AUTO))
        c->mode = (ctl_mode)stored_mode;
    c->trip_amps = CTL_TRIP_AMPS_DEFAULT;
}

// Anything that takes control from a cycle or the bench: both end, the relay off.
static void interrupt(ctl_t *c)
{
    c->cycle.active = false;
    c->bench = false;
}

void ctl_press(ctl_t *c)
{
    interrupt(c);
    c->want = false;
    if (c->trip != CTL_TRIP_NONE)
    {
        c->trip = CTL_TRIP_NONE;
        c->mode = CTL_MODE_OFF;
        return;
    }
    c->mode = c->mode == CTL_MODE_OFF ? CTL_MODE_ON : c->mode == CTL_MODE_ON ? CTL_MODE_AUTO : CTL_MODE_OFF;
}

bool ctl_accepts_remote(const ctl_t *c)
{
    return c->trip == CTL_TRIP_NONE && c->mode == CTL_MODE_AUTO;
}

static ctl_result remote_ok(const ctl_t *c)
{
    if (c->trip != CTL_TRIP_NONE)
        return CTL_ERR_TRIPPED;
    if (c->mode != CTL_MODE_AUTO)
        return CTL_ERR_NOT_AUTO;
    return CTL_OK;
}

ctl_result ctl_remote_relay(ctl_t *c, bool on)
{
    ctl_result r = remote_ok(c);
    if (r != CTL_OK)
        return r;
    interrupt(c);
    c->want = on;
    return CTL_OK;
}

ctl_result ctl_set_mode(ctl_t *c, ctl_mode mode)
{
    if (mode != CTL_MODE_OFF && mode != CTL_MODE_ON && mode != CTL_MODE_AUTO)
        return CTL_ERR_INVALID;
    if (c->trip != CTL_TRIP_NONE)
    {
        if (mode != CTL_MODE_OFF)
            return CTL_ERR_TRIPPED;
        c->trip = CTL_TRIP_NONE;  // off clears it, as a press does
    }
    else if (mode == c->mode)
        return CTL_OK;  // nothing to change: a running cycle or the bench carries on
    interrupt(c);
    c->want = false;
    c->mode = mode;
    return CTL_OK;
}

bool ctl_cycle_valid(uint32_t n, uint32_t on_ms, uint32_t off_ms)
{
    if (n < 1 || n > CONSOLE_CYCLE_MAX_N)
        return false;
    if (on_ms < CONSOLE_CYCLE_MIN_MS || on_ms > CONSOLE_CYCLE_MAX_MS || off_ms < CONSOLE_CYCLE_MIN_MS ||
        off_ms > CONSOLE_CYCLE_MAX_MS)
        return false;
    return (uint64_t)n * ((uint64_t)on_ms + off_ms) <= CONSOLE_CYCLE_MAX_TOTAL_MS;
}

static void start_cycle(ctl_t *c, bool console, uint32_t n, uint32_t on_ms, uint32_t off_ms, int64_t now_ms)
{
    interrupt(c);
    c->want = false;
    c->cycle.active = true;
    c->cycle.from_console = console;
    c->cycle.on_phase = true;
    c->cycle.n = n;
    c->cycle.on_ms = on_ms;
    c->cycle.off_ms = off_ms;
    c->cycle.done = 0;
    c->cycle.phase_start_ms = now_ms;
}

ctl_result ctl_remote_cycle(ctl_t *c, uint32_t n, uint32_t on_ms, uint32_t off_ms, int64_t now_ms)
{
    ctl_result r = remote_ok(c);
    if (r != CTL_OK)
        return r;
    if (!ctl_cycle_valid(n, on_ms, off_ms))
        return CTL_ERR_INVALID;
    start_cycle(c, false, n, on_ms, off_ms, now_ms);
    return CTL_OK;
}

ctl_result ctl_bench_cycle(ctl_t *c, uint32_t n, uint32_t on_ms, uint32_t off_ms, int64_t now_ms)
{
    if (c->trip != CTL_TRIP_NONE)
        return CTL_ERR_TRIPPED;
    if (!ctl_cycle_valid(n, on_ms, off_ms))
        return CTL_ERR_INVALID;
    start_cycle(c, true, n, on_ms, off_ms, now_ms);
    return CTL_OK;
}

// A finished or stopped cycle leaves the relay off: auto's wish is off, and a console cycle leaves
// the bench override holding it off (in mode on too).
static void end_cycle(ctl_t *c)
{
    bool console = c->cycle.from_console;
    c->cycle.active = false;
    c->want = false;
    if (console)
    {
        c->bench = true;
        c->bench_on = false;
    }
}

bool ctl_cycle_stop(ctl_t *c)
{
    if (!c->cycle.active)
        return false;
    end_cycle(c);
    return true;
}

ctl_result ctl_bench_relay(ctl_t *c, bool on)
{
    if (on && c->trip != CTL_TRIP_NONE)
        return CTL_ERR_TRIPPED;
    interrupt(c);
    c->bench = true;
    c->bench_on = on;
    return CTL_OK;
}

ctl_result ctl_set_trip_amps(ctl_t *c, double amps)
{
    if (amps < 0)
    {
        c->trip_amps = CTL_TRIP_AMPS_DEFAULT;
        return CTL_OK;
    }
    // Written so that NaN fails too.
    if (!(amps >= CTL_TRIP_AMPS_MIN && amps <= CTL_TRIP_AMPS_DEFAULT))
        return CTL_ERR_INVALID;
    c->trip_amps = amps;
    return CTL_OK;
}

bool ctl_trip_amps_temporary(const ctl_t *c)
{
    return c->trip_amps != CTL_TRIP_AMPS_DEFAULT;
}

bool ctl_trip(ctl_t *c, ctl_trip_cause cause)
{
    if (cause == CTL_TRIP_NONE || c->trip != CTL_TRIP_NONE)
        return false;
    interrupt(c);
    c->want = false;
    c->trip = cause;
    return true;
}

bool ctl_relay(ctl_t *c, int64_t now_ms)
{
    if (c->trip != CTL_TRIP_NONE)
        return false;
    if (c->cycle.active)
    {
        // One step per call at most, timed from now: a late loop stretches a phase, never skips one.
        uint32_t phase_ms = c->cycle.on_phase ? c->cycle.on_ms : c->cycle.off_ms;
        if (now_ms - c->cycle.phase_start_ms >= (int64_t)phase_ms)
        {
            c->cycle.phase_start_ms = now_ms;
            if (c->cycle.on_phase)
                c->cycle.on_phase = false;
            else if (++c->cycle.done >= c->cycle.n)
                end_cycle(c);
            else
                c->cycle.on_phase = true;
        }
        if (c->cycle.active)
            return c->cycle.on_phase;
    }
    if (c->bench)
        return c->bench_on;
    return c->mode == CTL_MODE_ON || (c->mode == CTL_MODE_AUTO && c->want);
}

const char *ctl_mode_name(ctl_mode mode)
{
    switch (mode)
    {
    case CTL_MODE_OFF:
        return "off";
    case CTL_MODE_ON:
        return "on";
    case CTL_MODE_AUTO:
        return "auto";
    }
    return "?";
}

bool ctl_mode_parse(const char *name, ctl_mode *out)
{
    static const ctl_mode modes[] = {CTL_MODE_OFF, CTL_MODE_ON, CTL_MODE_AUTO};
    for (unsigned i = 0; name != NULL && i < sizeof(modes) / sizeof(modes[0]); i++)
        if (strcmp(name, ctl_mode_name(modes[i])) == 0)
        {
            *out = modes[i];
            return true;
        }
    return false;
}

const char *ctl_trip_name(ctl_trip_cause cause)
{
    switch (cause)
    {
    case CTL_TRIP_OVERCURRENT:
        return "overcurrent";
    case CTL_TRIP_OVERTEMP:
        return "overtemp";
    case CTL_TRIP_NONE:
        break;
    }
    return NULL;
}

const char *ctl_result_message(ctl_result r)
{
    switch (r)
    {
    case CTL_OK:
        return "ok";
    case CTL_ERR_NOT_AUTO:
        return "refused: the mode is a local override (on or off); set mode auto first";
    case CTL_ERR_TRIPPED:
        return "refused: tripped; press the button or set mode off to clear it";
    case CTL_ERR_INVALID:
        return "out of range";
    }
    return "?";
}
