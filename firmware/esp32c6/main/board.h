// Petro rev B's hardware: the relay, button, LED, NTC, the BL0939's UART and edge outputs, and J3.
// Thin glue over IDF drivers; the conversions are in port/.
#pragma once

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#include "bl0939.h"
#include "esp_err.h"

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

// J3.
void board_j3_out(bool level);
bool board_j3_in(void);
