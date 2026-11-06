// The energy total (petro_energy_kwh_total), from the BL0939's CF pulse count, kept across reboots.
// Portable, so the host tests it.
//
// CFA_CNT is a 24-bit counter of CF pulses since the chip's last reset (the firmware soft-resets it
// at every boot). Each reading adds the pulses since the last one (modulo 2^24, so a wrap is
// counted); the first reading after boot only sets the baseline. A jump bigger than
// ENERGY_MAX_WATTS could make in the time since the last reading is not energy (a chip reset, a
// corrupted frame that passed its checksum): it is dropped and the count taken as the new baseline.
//
// The total is milliwatt-hours: the stored base (from NVS at boot) plus the pulses since boot. The
// caller writes it back to NVS when energy_save_due says so: no more than every
// ENERGY_SAVE_INTERVAL_MS (at most ~53k writes a year, which the 24 KB nvs partition's wear
// levelling spreads far beyond the flash's life), or sooner after ENERGY_SAVE_BIG_MWH. A power cut
// loses at most the energy since the last save.
#pragma once

#include <stdbool.h>
#include <stdint.h>

#define ENERGY_CF_MASK 0xFFFFFFu
#define ENERGY_MAX_WATTS 8000.0  // twice 16 A at 250 V
#define ENERGY_SAVE_INTERVAL_MS (10 * 60 * 1000)
#define ENERGY_SAVE_BIG_MWH 100000ull  // 0.1 kWh: saved after a minute rather than ten
#define ENERGY_SAVE_BIG_INTERVAL_MS (60 * 1000)

typedef struct
{
    double pulses_per_kwh;
    uint64_t base_mwh;   // stored at boot
    uint64_t pulses;     // counted since boot
    bool have_last;
    uint32_t last_cnt;
    int64_t last_ms;
    uint64_t saved_mwh;
    int64_t saved_ms;
    uint32_t rejected;   // implausible jumps dropped
} energy_t;

void energy_init(energy_t *e, uint64_t stored_mwh, double pulses_per_kwh, int64_t now_ms);

// One CFA_CNT reading at now_ms. False if it was an implausible jump (dropped, rebaselined).
bool energy_update(energy_t *e, uint32_t cf_cnt, int64_t now_ms);

uint64_t energy_mwh(const energy_t *e);
double energy_kwh(const energy_t *e);

bool energy_save_due(const energy_t *e, int64_t now_ms);
// After the caller has stored `mwh` (what energy_mwh returned).
void energy_saved(energy_t *e, uint64_t mwh, int64_t now_ms);
