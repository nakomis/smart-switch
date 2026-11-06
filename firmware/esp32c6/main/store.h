// What Petro keeps across reboots, in the default nvs partition, namespace "state" (never prov,
// which is the provisioning script's and read-only here): the mode (the power-on state), the energy
// total, and the reset and trip counters behind petro_resets_total and petro_trips_total.
// OTA's own bookkeeping is in namespace "ota" (ota.c).
#pragma once

#include <stdbool.h>
#include <stdint.h>

#include "ctl.h"
#include "esp_err.h"

#define STORE_RESET_REASONS 16  // esp_reset_reason_t, ESP_RST_UNKNOWN to ESP_RST_CPU_LOCKUP

// Opens the namespace, counts this boot's reset reason and loads the rest. After nvs_flash_init.
void store_init(void);

// The stored mode, or false if none (or unreadable).
bool store_mode(int *mode);
esp_err_t store_set_mode(ctl_mode mode);

uint64_t store_energy_mwh(void);
esp_err_t store_set_energy_mwh(uint64_t mwh);

// Counts since the unit was first provisioned (they survive OTA; an NVS erase resets them).
const uint32_t *store_reset_counts(void);
const char *const *store_reset_names(void);
uint32_t store_trips(ctl_trip_cause cause);

// The latched trip (CTL_TRIP_NONE if none), so a reboot doesn't clear it: only a press does.
int store_trip(void);
esp_err_t store_set_trip(ctl_trip_cause cause);
esp_err_t store_count_trip(ctl_trip_cause cause);

// This boot's reset reason, by name ("poweron", "brownout", ...).
const char *store_reset_reason(void);
