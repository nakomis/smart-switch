// Prometheus text exposition lines, for VictoriaMetrics' /api/v1/import/prometheus. Portable C.
//
//   name 12.345\n
//   name{key="value"} 12.345\n
//
// No timestamps: VM stamps the lines on receipt, and vmauth forces the host_name label.
#ifndef ZATT_PROM_H
#define ZATT_PROM_H

#include <stdbool.h>
#include <stddef.h>

typedef struct
{
    char *buf;
    size_t cap;
    size_t len;
    bool overflow;
} prom_buf_t;

void prom_init(prom_buf_t *p, char *buf, size_t cap);

// One gauge line. label_key may be NULL for none. Non-finite values are skipped silently (a missing
// sample is better than a poisoned one); a bad metric or label name, or a full buffer, sets overflow.
void prom_gauge(prom_buf_t *p, const char *name, const char *label_key, const char *label_val, double v);

// Length of the text (NUL-terminated in buf), or -1 if anything didn't fit or was invalid.
int prom_finish(prom_buf_t *p);

#endif
