// The VictoriaMetrics push. See prom.h.
#include "prom.h"

#include <math.h>
#include <stdarg.h>
#include <stdio.h>
#include <string.h>

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
    {
        s->ok = false;
        return;
    }
    s->len += (size_t)n;
}

static void gauge(sink *s, const char *name, const char *fmt, double v)
{
    if (!isfinite(v))
        return;
    put(s, "%s ", name);
    put(s, fmt, v);
    put(s, "\n");
}

// A label value with \, " and newlines escaped, as the format requires.
static void label_value(sink *s, const char *v)
{
    for (; v && *v; v++)
    {
        if (*v == '\\' || *v == '"')
            put(s, "\\%c", *v);
        else if (*v == '\n')
            put(s, "\\n");
        else
            put(s, "%c", *v);
    }
}

int prom_format(char *out, size_t cap, const prom_sample *v)
{
    if (out == NULL || cap == 0 || v == NULL)
        return -1;
    sink s = {out, cap, 0, true};
    out[0] = '\0';
    if (v->have_meter)
    {
        gauge(&s, "petro_voltage_volts", "%.2f", v->volts);
        gauge(&s, "petro_current_amps", "%.4f", v->amps);
        gauge(&s, "petro_power_watts", "%.2f", v->watts);
    }
    gauge(&s, "petro_energy_kwh_total", "%.6f", v->energy_kwh);
    if (v->have_temp)
        gauge(&s, "petro_board_temperature_celsius", "%.2f", v->board_c);
    put(&s, "petro_relay_on %d\n", v->relay ? 1 : 0);
    if (v->have_zx)
        gauge(&s, "petro_zx_hz", "%.1f", v->zx_hz);
    if (v->have_rssi)
        put(&s, "petro_wifi_rssi_dbm %d\n", v->rssi);
    put(&s, "petro_uptime_seconds %lu\n", (unsigned long)v->uptime_s);
    for (size_t i = 0; i < v->resets; i++)
    {
        if (v->reset_counts[i] == 0)
            continue;
        put(&s, "petro_resets_total{reason=\"");
        label_value(&s, v->reset_names[i]);
        put(&s, "\"} %lu\n", (unsigned long)v->reset_counts[i]);
    }
    put(&s, "petro_trips_total{cause=\"overcurrent\"} %lu\n", (unsigned long)v->trips_overcurrent);
    put(&s, "petro_trips_total{cause=\"overtemp\"} %lu\n", (unsigned long)v->trips_overtemp);
    if (!s.ok)
    {
        out[0] = '\0';
        return -1;
    }
    return (int)s.len;
}

bool prom_url(const char *url, char *out, size_t cap)
{
    if (url == NULL || out == NULL || cap == 0)
        return false;
    size_t scheme;
    if (strncmp(url, "http://", 7) == 0)
        scheme = 7;
    else if (strncmp(url, "https://", 8) == 0)
        scheme = 8;
    else
        return false;
    const char *host = url + scheme;
    for (const char *p = url; *p; p++)
        if ((unsigned char)*p <= 0x20 || (unsigned char)*p >= 0x7f)
            return false;
    size_t host_len = strcspn(host, "/?#");
    if (host_len == 0)
        return false;
    const char *rest = host + host_len;
    bool no_path = *rest == '\0' || strcmp(rest, "/") == 0;
    int n = no_path ? snprintf(out, cap, "%.*s%s", (int)(scheme + host_len), url, PROM_PATH)
                    : snprintf(out, cap, "%s", url);
    return n > 0 && (size_t)n < cap;
}
