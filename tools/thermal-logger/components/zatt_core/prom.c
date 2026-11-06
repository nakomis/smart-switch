#include "prom.h"

#include <ctype.h>
#include <math.h>
#include <stdio.h>
#include <string.h>

void prom_init(prom_buf_t *p, char *buf, size_t cap)
{
    p->buf = buf;
    p->cap = cap;
    p->len = 0;
    p->overflow = cap == 0;
    if (cap)
        buf[0] = 0;
}

static bool name_ok(const char *s, bool colon)
{
    if (s == NULL || !(isalpha((unsigned char)s[0]) || s[0] == '_' || (colon && s[0] == ':')))
        return false;
    for (const char *c = s + 1; *c; c++)
        if (!(isalnum((unsigned char)*c) || *c == '_' || (colon && *c == ':')))
            return false;
    return true;
}

static void put(prom_buf_t *p, char c)
{
    if (p->len + 1 >= p->cap)
    {
        p->overflow = true;
        return;
    }
    p->buf[p->len++] = c;
    p->buf[p->len] = 0;
}

static void puts_(prom_buf_t *p, const char *s)
{
    for (; *s; s++)
        put(p, *s);
}

void prom_gauge(prom_buf_t *p, const char *name, const char *label_key, const char *label_val, double v)
{
    if (!name_ok(name, true) || (label_key && (!name_ok(label_key, false) || label_val == NULL)))
    {
        p->overflow = true;
        return;
    }
    if (!isfinite(v))
        return;
    puts_(p, name);
    if (label_key)
    {
        put(p, '{');
        puts_(p, label_key);
        puts_(p, "=\"");
        for (const char *c = label_val; *c; c++)
        {
            if (*c == '\\' || *c == '"')
            {
                put(p, '\\');
                put(p, *c);
            }
            else if (*c == '\n')
                puts_(p, "\\n");
            else
                put(p, *c);
        }
        puts_(p, "\"}");
    }
    char num[32];
    snprintf(num, sizeof(num), " %.3f\n", v);
    puts_(p, num);
}

int prom_finish(prom_buf_t *p)
{
    return p->overflow ? -1 : (int)p->len;
}
