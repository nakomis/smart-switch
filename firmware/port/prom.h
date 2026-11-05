// The VictoriaMetrics push: Prometheus text exposition format (one sample a line, no timestamps:
// VictoriaMetrics stamps them on arrival) and the push URL. Portable, so the host tests it.
//
// The metrics are exactly docs/testing/README.md's ("What the gates need from the firmware"):
//   petro_voltage_volts, petro_current_amps, petro_power_watts   (left out until the meter reads)
//   petro_energy_kwh_total                                         (kept across reboots)
//   petro_board_temperature_celsius                                (left out while the NTC can't read)
//   petro_relay_on                                                 0 or 1
//   petro_zx_hz                                                    zero-cross edges a second
//   petro_wifi_rssi_dbm                                            (left out when not associated)
//   petro_uptime_seconds
//   petro_resets_total{reason="..."}                               one line per reason seen
//   petro_trips_total{cause="overcurrent"|"overtemp"}              both, always
// vmauth adds host_name="petro-prod-bN" to every series.
#pragma once

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#define PROM_PATH "/api/v1/import/prometheus"

typedef struct
{
    bool have_meter;
    double volts, amps, watts;
    double energy_kwh;
    bool have_temp;
    double board_c;
    bool relay;
    bool have_zx;
    double zx_hz;
    bool have_rssi;
    int rssi;
    uint32_t uptime_s;
    // Reset counts by reason: names[i] has counts[i]; zero counts are left out.
    const char *const *reset_names;
    const uint32_t *reset_counts;
    size_t resets;
    uint32_t trips_overcurrent, trips_overtemp;
} prom_sample;

// Returns the length written (NUL-terminated), or -1 if it doesn't fit. Non-finite values are left
// out rather than sent as NaN.
int prom_format(char *out, size_t cap, const prom_sample *s);

// The push URL from prov's metrics_url: http:// or https://, and if it has no path (or just "/"),
// PROM_PATH is appended. False if it isn't an http(s) URL with a host, or doesn't fit.
bool prom_url(const char *metrics_url, char *out, size_t cap);
