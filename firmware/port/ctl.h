// Petro's control logic: the mode, the relay and the trip latch. Portable, so the host tests it;
// the control task (esp32c6/main/app.c) owns one ctl_t and drives the relay from ctl_relay().
//
// The mode is off, on or auto. The button steps it on -> off -> auto -> on (Martin's decision,
// CLAUDE.md: from off, two presses reach on; from on, one press opens the relay). Nothing stored
// means off.
//   - on and off are local overrides: the relay follows the mode, and remote relay commands are
//     refused (CTL_ERR_NOT_AUTO).
//   - auto follows remote commands (Fleet, later Alexa). Entering auto starts with the relay off,
//     until a remote command says otherwise.
// The mode persists (the caller stores ctl.mode in NVS whenever it changes) and is the power-on
// state; in auto the relay starts off. Remotely (Fleet) the mode can only be set to off: always the
// safe direction. On and auto are the button's (and the bench console's).
//
// A trip (PETRO-5, port/prot.h: over-current, sustained or instant, over-temperature, or a meter
// fault) opens the relay and latches, across reboots too (the caller stores the cause and hands it
// back to ctl_init). While latched the relay stays open whatever else happens. It is cleared only by
// a press of the button or Fleet's clear_trip (ctl_clear_trip), and clearing always leaves the
// relay off: the mode is kept, except that on becomes off (on would close the relay; off is the
// one mode Fleet may set anyway). In auto, auto's wish is reset to off. A clear is refused while
// the caller says it's blocked (ctl_set_clear_blocked: the NTC within the hysteresis of its limit,
// or the BL0939's over-current output still active).
//
// The sensors (ctl_set_sensors_ok, from prot_healthy): while the meter isn't healthy, every
// command that would close the relay (remote relay on and cycle, the bench's relay on and cycle) is
// refused with CTL_ERR_SENSORS. The button still steps the mode; the caller then holds the relay
// open and latches a meter fault (prot_check).
//
// Shutdown (ctl_shutdown, just before a restart) holds the relay open until the reset.
//
// Relay cycle (Gate 4's 500 cycles; Gate 2's bench test from the console) runs here too, timed by
// the caller's clock: on for on_ms, off for off_ms, n times, then off. Each phase lasts at least its
// time even if the caller's loop is late (a late loop never skips a switch). A press, a mode
// change, a trip or any relay command stops it, the relay off.
//
// The console's `relay on` / `relay off` drive the relay directly on the bench (USB, no mains):
// a bench override that holds until the next press, mode change, remote relay command or trip, and
// is never persisted.
#pragma once

#include <stdbool.h>
#include <stdint.h>

typedef enum
{
    CTL_MODE_OFF,
    CTL_MODE_ON,
    CTL_MODE_AUTO,
} ctl_mode;

typedef enum
{
    CTL_TRIP_NONE,
    CTL_TRIP_OVERCURRENT,
    CTL_TRIP_OVERTEMP,
    CTL_TRIP_OVERCURRENT_INSTANT,  // the BL0939's fast over-current output (OC, GPIO2)
    CTL_TRIP_METER_FAULT,          // relay-on wanted with the BL0939 (or the NTC) not healthy
} ctl_trip_cause;

// The causes, as stored and counted (index cause - 1). New causes go on the end: the stored values
// keep their meaning across an OTA.
#define CTL_TRIP_CAUSES 4

typedef enum
{
    CTL_OK,
    CTL_ERR_NOT_AUTO,  // a remote relay command while the mode is on or off
    CTL_ERR_TRIPPED,   // a trip is latched: press the button first
    CTL_ERR_INVALID,   // relay cycle's or the threshold's numbers are out of range
    CTL_ERR_LOCAL_ONLY,  // a remote set_mode on or auto: only the button sets those
    CTL_ERR_SENSORS,     // relay-on refused: the meter (BL0939 or NTC) isn't healthy
    CTL_ERR_CLEAR_BLOCKED,  // a trip can't be cleared yet (still hot, or OC still active)
} ctl_result;

// The over-current trip threshold (PETRO-5). The default (CLAUDE.md: ~10.5 A) is always what a boot
// starts with; a temporary threshold from Fleet (Gate 4's trip test) may only lower it, lives in
// RAM and is gone after a reboot.
#define CTL_TRIP_AMPS_DEFAULT 10.5
#define CTL_TRIP_AMPS_MIN 0.5
// The instant trip's threshold: the BL0939's fast RMS (half a cycle) on its OC output. The same
// rules: a temporary one may only lower it (so Gate 4 can trip it with the radiator), RAM only.
#define CTL_INSTANT_AMPS_DEFAULT 15.0
#define CTL_INSTANT_AMPS_MIN 1.0

typedef struct
{
    ctl_mode mode;
    bool want;               // auto: the last remote relay command
    ctl_trip_cause trip;     // latched (and stored) until a press
    bool shutdown;           // restarting: the relay stays open
    bool bench, bench_on;    // the console's direct drive
    double trip_amps;        // in force (RAM only)
    double instant_amps;     // in force (RAM only)
    bool sensors_ok;         // the caller's (prot_healthy); true from ctl_init until it says
    bool clear_blocked;      // the caller's: a clear would be refused now
    struct
    {
        bool active, from_console, on_phase;
        uint32_t n, on_ms, off_ms, done;
        int64_t phase_start_ms;
    } cycle;
} ctl_t;

// Power-on: the stored mode (CTL_MODE_OFF if none was stored or it was unreadable), relay off in
// auto, the stored trip (CTL_TRIP_NONE if none; anything unknown counts as an over-current trip,
// the safe reading), the default thresholds.
void ctl_init(ctl_t *c, bool have_stored, int stored_mode, int stored_trip);

// One debounced press of SW1: a mode step or, with a trip latched, ctl_clear_trip (its result;
// CTL_OK otherwise).
ctl_result ctl_press(ctl_t *c);

// Clears a latched trip (the button, or Fleet's clear_trip), leaving the relay off: see above.
// CTL_OK if cleared or nothing was latched; CTL_ERR_CLEAR_BLOCKED while blocked.
ctl_result ctl_clear_trip(ctl_t *c);

// The caller's view of the protection, refreshed every loop.
void ctl_set_sensors_ok(ctl_t *c, bool ok);
void ctl_set_clear_blocked(ctl_t *c, bool blocked);

// Remote (Fleet) commands.
ctl_result ctl_remote_relay(ctl_t *c, bool on);
ctl_result ctl_remote_mode(ctl_t *c, ctl_mode mode);  // off only (CTL_ERR_LOCAL_ONLY)
ctl_result ctl_remote_cycle(ctl_t *c, uint32_t n, uint32_t on_ms, uint32_t off_ms, int64_t now_ms);
// A threshold in amps (CTL_TRIP_AMPS_MIN .. CTL_TRIP_AMPS_DEFAULT), or a negative number for the
// default again.
ctl_result ctl_set_trip_amps(ctl_t *c, double amps);
bool ctl_trip_amps_temporary(const ctl_t *c);
// The instant threshold: CTL_INSTANT_AMPS_MIN .. CTL_INSTANT_AMPS_DEFAULT, or negative for the
// default. The caller writes it to the BL0939.
ctl_result ctl_set_instant_amps(ctl_t *c, double amps);
bool ctl_instant_amps_temporary(const ctl_t *c);

// The console (bench): any mode, though on and auto are refused while tripped (off is always
// accepted, and leaves the trip latched).
ctl_result ctl_set_mode(ctl_t *c, ctl_mode mode);
ctl_result ctl_bench_relay(ctl_t *c, bool on);
ctl_result ctl_bench_cycle(ctl_t *c, uint32_t n, uint32_t on_ms, uint32_t off_ms, int64_t now_ms);

// Stops a running cycle (the relay off). True if one was running.
bool ctl_cycle_stop(ctl_t *c);

// Whether relay cycle's numbers are within limits: n 1-10000, 50-60000 ms each (console_parse.h),
// and n x (on_ms + off_ms) at most max_total_ms in all: CONSOLE_CYCLE_MAX_TOTAL_MS (an hour) from
// the console, which is busy while it runs; CTL_REMOTE_CYCLE_MAX_TOTAL_MS (two hours) from Fleet,
// for Gate 4's 500 x 8 s (about 67 minutes).
#define CTL_REMOTE_CYCLE_MAX_TOTAL_MS 7200000u
bool ctl_cycle_valid(uint32_t n, uint32_t on_ms, uint32_t off_ms, uint32_t max_total_ms);

// The trip (prot.h decides when): opens the relay and latches. True if this latched a new trip (count
// it); false if one was already latched (the first cause is kept) or cause is CTL_TRIP_NONE.
bool ctl_trip(ctl_t *c, ctl_trip_cause cause);

// Restarting: the relay open from now on, whatever comes next.
void ctl_shutdown(ctl_t *c);

// Whether a remote relay command would be accepted now.
bool ctl_accepts_remote(const ctl_t *c);

// The relay output at now_ms; advances a running cycle (call it every loop).
bool ctl_relay(ctl_t *c, int64_t now_ms);

const char *ctl_mode_name(ctl_mode mode);
// "on", "off" or "auto". False for anything else.
bool ctl_mode_parse(const char *name, ctl_mode *out);
// "overcurrent", "overtemp", "overcurrent_instant", "meter_fault", or NULL for none.
const char *ctl_trip_name(ctl_trip_cause cause);
// The reverse; false for anything else (NULL included).
bool ctl_trip_parse(const char *name, ctl_trip_cause *out);
const char *ctl_result_message(ctl_result r);
