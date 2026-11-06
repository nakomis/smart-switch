// Petro rev B's hardware: the relay, button, LED, NTC, the BL0939's UART and edge outputs, and J3.
// Thin glue over IDF drivers; the conversions are in port/.
#pragma once

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#include "bl0939.h"
#include "esp_err.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "zx.h"

// Drives the relay low first of all, then sets up each other part independently: one failing
// doesn't stop the rest. Returns the first failure (ESP_OK if none); board_part_ok says which.
esp_err_t board_init(void);

typedef enum
{
    BOARD_RELAY,
    BOARD_INPUTS,
    BOARD_LED,
    BOARD_NTC,
    BOARD_BL0939,
    BOARD_PARTS,
} board_part;

bool board_part_ok(board_part part);
const char *board_part_name(board_part part);

// The relay's output, at once. Refuses to close it (drives it open) while the OC interrupt holds
// it (board_oc_release). Zero-cross timing is relay.h's.
void board_relay(bool on);
bool board_relay_is_on(void);

esp_err_t board_led(uint8_t r, uint8_t g, uint8_t b);

// True while SW1 is held (GPIO9 reads low).
bool board_button_pressed(void);

// The NTC: the averaged raw ADC code and the calibrated millivolts. ESP_ERR_NOT_SUPPORTED for mv
// if the chip has no ADC calibration in eFuse (mv is then -1).
esp_err_t board_ntc_read(int *raw, int *mv);

// Asks the BL0939 for its full packet and waits for the 35 bytes. len is how many came. Holds a
// lock for the exchange, so the console's `bl` and the meter task never interleave on UART1.
// ESP_ERR_INVALID_STATE if the BL0939's UART didn't start.
esp_err_t board_bl_read(uint8_t packet[BL0939_PACKET_LEN], size_t *len);

// Running totals of edges (rising and falling) on ZX and OC since boot, counted in their ISRs.
uint32_t board_zx_edges(void);
uint32_t board_oc_edges(void);

// The last three ZX edges' times (esp_timer us), for zero-cross switching.
void board_zx_snapshot(zx_edges *out);

// The instant trip (PETRO-5). From arming, an edge on OC to its active level opens the relay in
// the interrupt and holds it open, then notifies `notify` (which latches the trip). The active
// level is the opposite of the level at arming: call it only when prot_may_arm_oc says there is no
// current (the relay open, under 0.1 A). Returns the active level, or -1 (unarmed) if the pin
// doesn't hold still. The BL0939's datasheet doesn't settle the polarity, so this needn't guess.
int board_oc_arm(TaskHandle_t notify);
bool board_oc_armed(void);
// Whether the relay was closed when OC went active (or now, if no hold is set): prot_oc_cause.
bool board_oc_relay_was_on(void);
// OC at its active level now.
bool board_oc_active(void);
// The interrupt has opened the relay and holds it.
bool board_oc_held(void);
// Lets the relay close again (after the trip is cleared): false, still held, if OC is still active.
bool board_oc_release(void);

// The BL0939 started and its mode and fast-RMS thresholds read back as written.
bool board_bl_configured(void);
// The fast-RMS control value in the chip (prot_fast_rms_ctrl).
uint32_t board_bl_fast_ctrl(void);
// Writes the instant threshold to both channels and reads it back. On failure the chip counts as
// unconfigured and the instant trip unarmed (the meter is then unhealthy, so the relay stays open,
// until app.c re-arms it).
esp_err_t board_bl_set_instant(double amps);

// J3.
void board_j3_out(bool level);
bool board_j3_in(void);
