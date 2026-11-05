// The application: the control task (SW1, the mode, the relay, the LED, Fleet's commands and the
// status) and the meter task (the BL0939, the NTC and ZX once a second, and the energy total).
//
// The control task owns the relay. It runs every 5 ms at a priority above the network's tasks and
// is watched by the task watchdog (5 s, then a panic and a restart, which leaves the relay off).
// Nothing on it waits on the network: publishing only copies into net.c's queue, and the OTA
// download, the metrics push and the Wi-Fi stress traffic each run in their own lower-priority task.
//
// The console and the MQTT task reach the control logic (port/ctl.c) only through these functions,
// under one mutex.
#pragma once

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#include "ctl.h"

// Starts both tasks. After store_init and ota_boot. `provisioned` says whether the network will
// start (the LED shows "provisioning needed" if not).
void app_start(bool provisioned);

// From the MQTT task: one whole command (JSON, not NUL-terminated). Copied into the control
// task's queue.
void app_on_command(const char *json, size_t len);

// The console (bench): ctl.h's bench override and relay cycle, the mode, and the LED held at a
// colour for APP_LED_HOLD_MS (or given back at once).
#define APP_LED_HOLD_MS 60000
ctl_result app_bench_relay(bool on);
ctl_result app_bench_cycle(uint32_t n, uint32_t on_ms, uint32_t off_ms);
bool app_cycle_stop(void);
ctl_result app_set_mode(ctl_mode mode);
void app_led_hold(uint8_t r, uint8_t g, uint8_t b);
void app_led_release(void);
// While true, presses of SW1 are only watched (the console's button test), not acted on.
void app_button_watch(bool watching);

// The trip hook (PETRO-5): latch a trip, open the relay at once, store it (it survives a reboot;
// only a press clears it) and count it.
void app_trip(ctl_trip_cause cause);

// A copy of the device's state, for the console's info, the status and the metrics.
typedef struct
{
    ctl_mode mode;
    bool relay;
    ctl_trip_cause trip;
    bool remote, bench;
    bool cycle_active;
    uint32_t cycle_done, cycle_n;
    double trip_amps;
    bool trip_amps_temporary;
    bool meter_ok;   // the BL0939 started and its latest reads are good
    bool have_meter;
    double volts, amps, watts;
    double energy_kwh;
    uint32_t meter_errors;  // BL0939 reads that failed (timeout or checksum) since boot
    bool have_temp;
    double board_c;
    bool have_zx;
    double zx_hz;
} app_state;

void app_get_state(app_state *out);
