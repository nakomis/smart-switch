// Zero-cross switching: when to drive the relay's coil so that its contacts close (or open) at a
// zero crossing of the mains voltage, from the BL0939's ZX output (GPIO1, an edge at every
// crossing). For a resistive load the current crosses zero there too, so the contacts make and
// break with almost no current: less arcing, longer contacts. Portable, so the host tests it.
//
// The coil is driven actuate_us ahead of a predicted crossing: the relay's operate time to close,
// its release time to open (HF115F: about 8 ms and 4 ms; Kconfig PETRO_RELAY_OPERATE_US and
// PETRO_RELAY_RELEASE_US). The crossings are predicted a whole period on from each of the last two
// edges, so a ZX output whose high and low halves differ (a comparator's offset) still predicts
// both kinds of crossing correctly.
//
// No prediction (switch at once) when there have been fewer than three edges, the last is more
// than ZX_STALE_US old (no mains: on USB, or unplugged), or the edges don't look like 40-62.5 Hz
// mains. Trips never wait for a crossing: the caller switches them at once.
#pragma once

#include <stdbool.h>
#include <stdint.h>

#define ZX_STALE_US 100000
#define ZX_MIN_PERIOD_US 16000  // 62.5 Hz
#define ZX_MAX_PERIOD_US 25000  // 40 Hz
#define ZX_LEAD_US 500          // the least time from now to the coil's switch (the timer's start)

typedef struct
{
    int64_t t[3];  // the last three edges (us), oldest first
    uint32_t n;    // edges seen (stops at 3)
} zx_edges;

// Records an edge. Inline (and so in IRAM with its caller) for the ZX interrupt.
static inline __attribute__((always_inline)) void zx_edge(zx_edges *z, int64_t t_us)
{
    z->t[0] = z->t[1];
    z->t[1] = z->t[2];
    z->t[2] = t_us;
    if (z->n < 3)
        z->n++;
}

// The full mains period from the edges, or 0 if they don't give one (see above).
int64_t zx_period_us(const zx_edges *z, int64_t now_us);

// When to drive the coil (us, >= now_us + ZX_LEAD_US) so the contacts move at a crossing,
// actuate_us after it; or -1 to switch at once.
int64_t zx_switch_at(const zx_edges *z, int64_t now_us, int64_t actuate_us);
