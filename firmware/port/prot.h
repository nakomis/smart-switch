// Petro's protection (PETRO-5): when to trip, whether the meter can be trusted, and when a trip
// may be cleared. Portable, so the host tests it; the meter task (esp32c6/main/app.c) feeds it
// every reading and acts on prot_check, and the control task checks it every loop too, so a meter
// task that stops is noticed.
//
// It is back-up protection. The plug's 13 A BS 1362 fuse is the real protection (F1 and F2 are
// bridged as built, docs/DESIGN.md 5.1); this trips for the unit's own rating:
//   - over-current, sustained: the RMS current (the larger of the BL0939's two channels, which read
//     the same shunt) above the threshold in force (ctl.trip_amps, 10.5 A unless Fleet lowered it)
//     for sustain_ms (2 s) without a break;
//   - over-current, instant: the BL0939's OC output (its fast RMS, over half a cycle, above
//     ctl.instant_amps, 15 A). Its interrupt opens the relay itself (board.c); here it is seen as a
//     level too, in case an edge was missed. OC with the relay open and the current reading under
//     PROT_ARM_MAX_AMPS can't be real: that's a meter fault (prot_oc_cause), never an inversion;
//   - over-temperature: the NTC (TH1, beside the relay) at or above overtemp_c for overtemp_ms;
//   - a meter fault: the relay wanted on while the meter isn't healthy (below), except in the
//     first stale_ms after boot, while the first readings arrive (the relay is held open then,
//     without a trip).
// Healthy: the BL0939 started and took its thresholds (read back), the instant trip is armed, a
// good frame and a good NTC reading (ntc.h's plausible window) each within stale_ms (3 s). A trip
// that can't see the current or the temperature is none.
//
// Arming the instant trip (prot_may_arm_oc): OC's active level isn't settled by the datasheet, so
// board.c takes the level it reads at arming as idle. That's only safe when there is certainly no
// current: the BL0939 configured, the relay open and a fresh frame reading under
// PROT_ARM_MAX_AMPS on both channels.
//
// Clearing (ctl_clear_trip) is blocked while the BL0939's OC output is active, while the latest
// frame still reads over the sustained threshold (the RMS takes most of a second to fall after
// the relay opens), while the NTC
// reads within clear_margin_c (5 C) of overtemp_c, and, for an over-temperature trip, while the
// NTC can't be read at all.
//
// The NTC limit. The NTC under-reads the hot spots (the terminals, K1's contacts, the shunt) by a
// ratio Gate 4 measures (docs/testing/gate-4-load-thermal.md, 2.7). Gate 4 5 sets it so the NTC
// trips before the hottest spot reaches 70 C in a 35 C room:
//     NTC limit = room + (70 - room) / ratio, room = 35 C        (prot_ntc_limit)
// 55 C is provisional (it assumes a ratio of 1.75) until Gate 4 has run.
#pragma once

#include <stdbool.h>
#include <stdint.h>

#include "ctl.h"

#define PROT_SUSTAIN_MS 2000
#define PROT_OVERTEMP_C 55.0
#define PROT_OVERTEMP_MS 2000
#define PROT_CLEAR_MARGIN_C 5.0
#define PROT_STALE_MS 3000
#define PROT_ARM_MAX_AMPS 0.1

typedef struct
{
    uint32_t sustain_ms;
    double overtemp_c;
    uint32_t overtemp_ms;
    double clear_margin_c;
    uint32_t stale_ms;
} prot_config;

// The defaults above.
prot_config prot_defaults(void);

typedef struct
{
    prot_config cfg;
    int64_t boot_ms;
    bool meter_init;  // the BL0939 started and took its thresholds
    bool have_frame;
    int64_t frame_ms;  // the last good frame
    bool amps_over;
    int64_t amps_over_ms;  // since when
    double amps;  // the larger channel; NaN if either was
    bool oc_armed;
    bool oc_relay_closed;  // the relay was closed when OC went active
    bool have_temp;
    int64_t temp_ms;  // the last good NTC reading
    double temp_c;
    bool temp_over;
    int64_t temp_over_ms;
    bool oc_active;
} prot_t;

void prot_init(prot_t *p, const prot_config *cfg, int64_t now_ms);

// Whether the BL0939 started and its thresholds read back as written.
void prot_meter_init(prot_t *p, bool ok);
// A good frame: both channels' currents (over if either is over the threshold, or NaN) and the
// sustained threshold in force.
void prot_frame(prot_t *p, double amps_a, double amps_b, double trip_amps, int64_t now_ms);
// An NTC reading; have false if it couldn't be read (the last good one then ages).
void prot_temp(prot_t *p, bool have, double celsius, int64_t now_ms);
// The OC output's level (true while active) and whether the relay was closed when it went active.
void prot_oc(prot_t *p, bool active, bool relay_closed);
// Whether the instant trip is armed (board.c).
void prot_oc_armed(prot_t *p, bool armed);
// Whether it may be armed now: see above.
bool prot_may_arm_oc(const prot_t *p, bool configured, bool relay_open, int64_t now_ms);
// What an active OC means: CTL_TRIP_OVERCURRENT_INSTANT, or CTL_TRIP_METER_FAULT if the relay was
// open and a fresh frame reads under PROT_ARM_MAX_AMPS (it can't be real).
ctl_trip_cause prot_oc_cause(const prot_t *p, int64_t now_ms);
// Whether a change of the latch from `before` to `after` is a clear (the OC hold is then released).
bool prot_oc_release_due(ctl_trip_cause before, ctl_trip_cause after);

bool prot_healthy(const prot_t *p, int64_t now_ms);
// The first stale_ms after boot, with the BL0939 started but the readings not yet in: unhealthy,
// but not a fault.
bool prot_starting(const prot_t *p, int64_t now_ms);

// What to trip now (CTL_TRIP_NONE for nothing). relay_wanted: ctl_relay's answer, before the
// caller's health gate. Over-current and over-temperature trip whether or not the relay is closed
// (current through an open relay means a welded contact, and is worth latching and reporting).
ctl_trip_cause prot_check(const prot_t *p, bool relay_wanted, int64_t now_ms);

// Whether a clear of `latched` must be refused now.
bool prot_clear_blocked(const prot_t *p, ctl_trip_cause latched, int64_t now_ms);

// The BL0939's fast-RMS control register (IA_FAST_RMS_CTRL 0x10, IB_FAST_RMS_CTRL 0x1E) for a
// threshold in amps: the threshold in its low 15 bits, compared with the fast RMS register's bits
// 23:8 (so counts / 256), and bit 15 clear for half-cycle refresh (ESPHome's 0x181C, "half cycle,
// threshold 6172"). counts_per_amp is bl0939_scale_t.amps: the fast RMS is assumed to share the
// RMS register's scale, which Gate 3 checks against the bl console's raw readings. Clamped to
// 1 .. 0x7FFF (about 31 A on Petro).
uint32_t prot_fast_rms_ctrl(double amps, double counts_per_amp);

// Gate 4 5's formula: the NTC limit for a hot-spot limit, at a room temperature, from the
// hot-spot-rise-over-NTC-rise ratio (>= 1).
double prot_ntc_limit(double room_c, double hot_limit_c, double ratio);
