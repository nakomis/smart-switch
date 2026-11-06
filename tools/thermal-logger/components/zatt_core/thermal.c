#include "thermal.h"

#include <ctype.h>
#include <math.h>
#include <stdlib.h>

bool zatt_rect_valid(const zatt_rect_t *r)
{
    return r->x0 >= 0 && r->y0 >= 0 && r->x1 < ZATT_W && r->y1 < ZATT_H && r->x0 <= r->x1 && r->y0 <= r->y1;
}

bool zatt_rect_parse(const char *s, zatt_rect_t *r)
{
    const char *p = s;
    while (isspace((unsigned char)*p))
        p++;
    if (*p == 0)
    {
        *r = zatt_rect_disabled();
        return true;
    }
    long v[4];
    for (int i = 0; i < 4; i++)
    {
        char *end;
        v[i] = strtol(p, &end, 10);
        if (end == p || v[i] < 0 || v[i] > 127)
            return false;
        p = end;
        while (isspace((unsigned char)*p))
            p++;
        if (i < 3)
        {
            if (*p != ',')
                return false;
            p++;
        }
    }
    if (*p != 0)
        return false;
    zatt_rect_t t = {(int8_t)v[0], (int8_t)v[1], (int8_t)v[2], (int8_t)v[3]};
    if (!zatt_rect_valid(&t))
        return false;
    *r = t;
    return true;
}

bool zatt_frame_stats(const float *f, zatt_frame_stats_t *out)
{
    double sum = 0;
    int n = 0, hot = 0;
    float mn = 0, mx = 0;
    for (int i = 0; i < ZATT_PIXELS; i++)
    {
        if (!isfinite(f[i]))
            continue;
        if (n == 0 || f[i] < mn)
            mn = f[i];
        if (n == 0 || f[i] > mx)
        {
            mx = f[i];
            hot = i;
        }
        sum += f[i];
        n++;
    }
    if (n == 0)
        return false;
    out->min = mn;
    out->max = mx;
    out->mean = (float)(sum / n);
    out->hot_x = hot % ZATT_W;
    out->hot_y = hot / ZATT_W;
    out->n = n;
    return true;
}

bool zatt_rect_stats(const float *f, const zatt_rect_t *r, float *mean, float *max)
{
    if (!zatt_rect_valid(r))
        return false;
    double sum = 0;
    int n = 0;
    float mx = 0;
    for (int y = r->y0; y <= r->y1; y++)
        for (int x = r->x0; x <= r->x1; x++)
        {
            float v = f[y * ZATT_W + x];
            if (!isfinite(v))
                continue;
            if (n == 0 || v > mx)
                mx = v;
            sum += v;
            n++;
        }
    if (n == 0)
        return false;
    *mean = (float)(sum / n);
    *max = mx;
    return true;
}
