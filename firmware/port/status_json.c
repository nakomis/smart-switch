// The /status JSON. See status_json.h.
#include "status_json.h"

#include <math.h>
#include <stdarg.h>
#include <stdio.h>

typedef struct
{
    char *out;
    size_t cap, len;
    bool ok;
} sink;

static void put(sink *s, const char *fmt, ...)
{
    if (!s->ok)
        return;
    va_list ap;
    va_start(ap, fmt);
    int n = vsnprintf(s->out + s->len, s->cap - s->len, fmt, ap);
    va_end(ap);
    if (n < 0 || (size_t)n >= s->cap - s->len)
        s->ok = false;
    else
        s->len += (size_t)n;
}

static void put_string(sink *s, const char *str)
{
    if (str == NULL)
    {
        put(s, "null");
        return;
    }
    put(s, "\"");
    for (; *str; str++)
    {
        unsigned char c = (unsigned char)*str;
        if (c == '"' || c == '\\')
            put(s, "\\%c", c);
        else if (c < 0x20)
            put(s, "\\u%04x", c);
        else
            put(s, "%c", c);
    }
    put(s, "\"");
}

static void put_bool(sink *s, bool b)
{
    put(s, b ? "true" : "false");
}

// A number, or null when it isn't known (or isn't finite: JSON has no NaN).
static void put_number(sink *s, bool have, const char *fmt, double v)
{
    if (have && isfinite(v))
        put(s, fmt, v);
    else
        put(s, "null");
}

int status_json(char *out, size_t cap, const status_view *v)
{
    if (out == NULL || cap == 0 || v == NULL)
        return -1;
    sink s = {out, cap, 0, true};
    put(&s, "{\"mode\":");
    put_string(&s, ctl_mode_name(v->mode));
    put(&s, ",\"relay\":");
    put_bool(&s, v->relay);
    put(&s, ",\"trip\":");
    put_string(&s, ctl_trip_name(v->trip));
    put(&s, ",\"remote\":");
    put_bool(&s, v->remote);
    put(&s, ",\"bench\":");
    put_bool(&s, v->bench);
    put(&s, ",\"cycle\":");
    if (v->cycle_active)
        put(&s, "{\"done\":%lu,\"n\":%lu}", (unsigned long)v->cycle_done, (unsigned long)v->cycle_n);
    else
        put(&s, "null");
    put(&s, ",\"meter_ok\":");
    put_bool(&s, v->meter_ok);
    put(&s, ",\"volts\":");
    put_number(&s, v->have_meter, "%.2f", v->volts);
    put(&s, ",\"amps\":");
    put_number(&s, v->have_meter, "%.4f", v->amps);
    put(&s, ",\"watts\":");
    put_number(&s, v->have_meter, "%.2f", v->watts);
    put(&s, ",\"energy_kwh\":");
    put_number(&s, true, "%.6f", v->energy_kwh);
    put(&s, ",\"board_c\":");
    put_number(&s, v->have_temp, "%.1f", v->board_c);
    put(&s, ",\"zx_hz\":");
    put_number(&s, v->have_zx, "%.1f", v->zx_hz);
    put(&s, ",\"trip_amps\":");
    put_number(&s, true, "%.2f", v->trip_amps);
    put(&s, ",\"trip_amps_temporary\":");
    put_bool(&s, v->trip_amps_temporary);
    put(&s, ",\"trips_enforced\":");
    put_bool(&s, v->trips_enforced);
    put(&s, ",\"stress_s\":");
    if (v->stress)
        put(&s, "%lu", (unsigned long)v->stress_left_s);
    else
        put(&s, "null");
    put(&s, ",\"rssi\":");
    if (v->have_rssi)
        put(&s, "%d", v->rssi);
    else
        put(&s, "null");
    put(&s, ",\"uptime_s\":%lu,\"reason\":", (unsigned long)v->uptime_s);
    put_string(&s, report_reason_name(v->reason));
    put(&s, ",\"version\":");
    put_string(&s, v->version);
    put(&s, "}");
    if (!s.ok)
    {
        out[0] = '\0';
        return -1;
    }
    return (int)s.len;
}
