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
// A trip (PETRO-5: over-current or over-temperature) opens the relay and latches, across reboots
// too (the caller stores the cause and hands it back to ctl_init). While latched the relay stays
// open whatever else happens, and only a button press clears it, leaving the relay off (the mode
// goes to off). Nothing remote can clear it.
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
} ctl_trip_cause;

#define CTL_TRIP_CAUSES 2  // overcurrent and overtemp: index cause - 1

typedef enum
{
    CTL_OK,
    CTL_ERR_NOT_AUTO,  // a remote relay command while the mode is on or off
    CTL_ERR_TRIPPED,   // a trip is latched: press the button first
    CTL_ERR_INVALID,   // relay cycle's or the threshold's numbers are out of range
    CTL_ERR_LOCAL_ONLY,  // a remote set_mode on or auto: only the button sets those
} ctl_result;

// The over-current trip threshold (PETRO-5). The default (CLAUDE.md: ~10.5 A) is always what a boot
// starts with; a temporary threshold from Fleet (Gate 4's trip test) may only lower it, lives in
// RAM and is gone after a reboot.
#define CTL_TRIP_AMPS_DEFAULT 10.5
#define CTL_TRIP_AMPS_MIN 0.5

typedef struct
{
    ctl_mode mode;
    bool want;               // auto: the last remote relay command
    ctl_trip_cause trip;     // latched (and stored) until a press
    bool shutdown;           // restarting: the relay stays open
    bool bench, bench_on;    // the console's direct drive
    double trip_amps;        // in force (RAM only)
    struct
    {
        bool active, from_console, on_phase;
        uint32_t n, on_ms, off_ms, done;
        int64_t phase_start_ms;
    } cycle;
} ctl_t;

// Power-on: the stored mode (CTL_MODE_OFF if none was stored or it was unreadable), relay off in
// auto, the stored trip (CTL_TRIP_NONE if none; anything unknown counts as an over-current trip,
// the safe reading), the default threshold.
void ctl_init(ctl_t *c, bool have_stored, int stored_mode, int stored_trip);

// One debounced press of SW1.
void ctl_press(ctl_t *c);

// Remote (Fleet) commands.
ctl_result ctl_remote_relay(ctl_t *c, bool on);
ctl_result ctl_remote_mode(ctl_t *c, ctl_mode mode);  // off only (CTL_ERR_LOCAL_ONLY)
ctl_result ctl_remote_cycle(ctl_t *c, uint32_t n, uint32_t on_ms, uint32_t off_ms, int64_t now_ms);
// A threshold in amps (CTL_TRIP_AMPS_MIN .. CTL_TRIP_AMPS_DEFAULT), or a negative number for the
// default again.
ctl_result ctl_set_trip_amps(ctl_t *c, double amps);
bool ctl_trip_amps_temporary(const ctl_t *c);

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

// The trip hook (PETRO-5): opens the relay and latches. True if this latched a new trip (count
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
// "overcurrent", "overtemp", or NULL for none.
const char *ctl_trip_name(ctl_trip_cause cause);
const char *ctl_result_message(ctl_result r);
