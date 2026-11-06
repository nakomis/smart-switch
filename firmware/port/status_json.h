// The /status JSON (petro/<thing>/status), built from a read-only view of the device. Portable, so
// the host tests it. Fleet keeps the latest as the device's lastStatus; version is what it shows
// alongside currentVersion.
//
// {"mode":"auto","relay":true,"trip":null,"remote":true,"bench":false,"cycle":null,
//  "meter_ok":true,"volts":239.81,"amps":0.2611,"watts":61.2,"energy_kwh":1.234567,"board_c":24.1,"zx_hz":100.0,
//  "trip_amps":10.5,"trip_amps_temporary":false,"instant_amps":15.0,"instant_amps_temporary":false,
//  "overtemp_c":55.0,"trips_enforced":true,"zx_sync":true,"stress_s":null,
//  "rssi":-61,"uptime_s":3600,"reason":"heartbeat","version":"0.3.0"}
//
// trip is null or the latched cause: "overcurrent" (sustained), "overcurrent_instant" (the
// BL0939's OC output), "overtemp" or "meter_fault"; remote is whether a relay command would be
// accepted (auto, untripped); cycle is null or {"done":3,"n":500}; stress_s is null or the seconds
// of Wi-Fi stress left. meter_ok is prot.h's health (the BL0939 started and took its thresholds,
// a good frame and NTC reading within 3 s): without it relay-on is refused. The thresholds in
// force: trip_amps (sustained, 2 s), instant_amps (the OC output), each with whether Fleet has
// lowered it until a reboot, and overtemp_c (the NTC's). zx_sync is whether the relay is switching
// at zero crossings (ZX edges seen in the last 100 ms). The readings are null until the meter (or
// the NTC) has read; rssi is null when not associated.
#pragma once

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#include "ctl.h"
#include "report.h"

typedef struct
{
    ctl_mode mode;
    bool relay;
    ctl_trip_cause trip;
    bool remote;
    bool bench;
    bool cycle_active;
    uint32_t cycle_done, cycle_n;
    bool meter_ok;
    bool have_meter;
    double volts, amps, watts;
    double energy_kwh;
    bool have_temp;
    double board_c;
    bool have_zx;
    double zx_hz;
    double trip_amps;
    bool trip_amps_temporary;
    double instant_amps;
    bool instant_amps_temporary;
    double overtemp_c;
    bool trips_enforced;
    bool zx_sync;
    bool stress;
    uint32_t stress_left_s;
    bool have_rssi;
    int rssi;
    uint32_t uptime_s;
    report_reason reason;
    const char *version;  // NULL prints null; quotes, backslashes and control characters are escaped
} status_view;

// Returns the length (the buffer is NUL-terminated), or -1 if it doesn't fit.
int status_json(char *out, size_t cap, const status_view *v);
