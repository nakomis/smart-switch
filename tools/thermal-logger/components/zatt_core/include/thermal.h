// Frame statistics and spot rectangles for Zatt. Portable C, host-tested (tests/test_core.c).
#ifndef ZATT_THERMAL_H
#define ZATT_THERMAL_H

#include <stdbool.h>
#include <stdint.h>

#define ZATT_W 32
#define ZATT_H 24
#define ZATT_PIXELS (ZATT_W * ZATT_H)
#define ZATT_NSPOTS 7

// An inclusive pixel rectangle. x0 < 0 means the spot is disabled. Pixel (x, y) is f[y * 32 + x].
typedef struct
{
    int8_t x0, y0, x1, y1;
} zatt_rect_t;

typedef struct
{
    float min, max, mean;
    int hot_x, hot_y;  // the hottest pixel
    int n;             // finite pixels counted
} zatt_frame_stats_t;

static inline zatt_rect_t zatt_rect_disabled(void)
{
    zatt_rect_t r = {-1, -1, -1, -1};
    return r;
}

// True if the rectangle is enabled and lies within the frame with x0 <= x1, y0 <= y1.
bool zatt_rect_valid(const zatt_rect_t *r);

// "x0,y0,x1,y1" (spaces allowed) -> r. An empty or all-space string means disabled and succeeds.
// Returns false (r untouched) for anything malformed or out of range.
bool zatt_rect_parse(const char *s, zatt_rect_t *r);

// Over the finite pixels of a 768-float frame. False if there are none.
bool zatt_frame_stats(const float *f, zatt_frame_stats_t *out);

// Mean and max of the finite pixels in an enabled, valid rectangle. False otherwise.
bool zatt_rect_stats(const float *f, const zatt_rect_t *r, float *mean, float *max);

#endif
