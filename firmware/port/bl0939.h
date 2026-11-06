// The BL0939 energy-metering chip over its UART: the frames we send, the full packet it answers
// with, and the conversion from its registers to volts, amps and watts. Portable C, no IDF.
//
// The protocol and the datasheet's conversion formulas follow ESPHome's bl0939 component
// (esphome/components/bl0939), itself from Belling's Chinese-only datasheet
// (BL0939 V1.2). UART: 4800 baud, 8 data bits, no parity, 1 stop bit; multi-byte values are sent
// low byte first.
#pragma once

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#define BL0939_BAUD 4800
#define BL0939_READ_COMMAND 0x55
#define BL0939_WRITE_COMMAND 0xA5
#define BL0939_FULL_PACKET 0xAA
#define BL0939_PACKET_HEADER 0x55
#define BL0939_PACKET_LEN 35
#define BL0939_WRITE_LEN 6

// Registers we write.
#define BL0939_REG_IA_FAST_RMS_CTRL 0x10
#define BL0939_REG_MODE 0x18
#define BL0939_REG_SOFT_RESET 0x19
#define BL0939_REG_USR_WRPROT 0x1A
#define BL0939_REG_TPS_CTRL 0x1B
#define BL0939_REG_IB_FAST_RMS_CTRL 0x1E

// The datasheet's reference voltage.
#define BL0939_VREF 1.218

// The full-packet request: {0x55, 0xAA}. Returns the length written (2).
size_t bl0939_build_full_read(uint8_t out[2]);

// A register write: {0xA5, reg, low, mid, high, checksum}. Returns BL0939_WRITE_LEN.
size_t bl0939_build_write(uint8_t reg, uint32_t value24, uint8_t out[BL0939_WRITE_LEN]);

// The start-up sequence (soft reset, unlock writes, mode, temperature control) as consecutive
// write frames. Returns the number of frames written to out (at most max_frames).
size_t bl0939_init_frames(uint8_t out[][BL0939_WRITE_LEN], size_t max_frames);

// The raw registers of one full packet.
typedef struct
{
    uint32_t ia_fast_rms;
    uint32_t ia_rms;
    uint32_t ib_rms;
    uint32_t v_rms;
    uint32_t ib_fast_rms;
    int32_t a_watt;  // signed 24-bit, sign-extended
    int32_t b_watt;
    uint32_t cfa_cnt;
    uint32_t cfb_cnt;
    uint16_t tps1;   // internal temperature (low 10 bits)
    uint16_t tps2;   // external temperature (unused on Petro)
} bl0939_raw_t;

typedef enum
{
    BL0939_OK = 0,
    BL0939_ERR_LENGTH,    // not BL0939_PACKET_LEN bytes
    BL0939_ERR_HEADER,    // first byte not 0x55
    BL0939_ERR_CHECKSUM,  // checksum mismatch
} bl0939_status_t;

// The checksum the chip appends to a full packet: ~(0x55 + every byte before the checksum).
uint8_t bl0939_packet_checksum(const uint8_t *packet, size_t len_without_checksum);

// Verifies and unpacks a full packet. raw is filled only on BL0939_OK.
bl0939_status_t bl0939_parse_packet(const uint8_t *packet, size_t len, bl0939_raw_t *raw);

const char *bl0939_status_name(bl0939_status_t status);

// Conversion factors: register counts per volt, per amp, per watt and CF pulses per kWh.
typedef struct
{
    double volts;
    double amps;
    double watts;
    double pulses_per_kwh;
} bl0939_scale_t;

// The factors for a shunt (ohms) and a voltage divider (r_top over r_bottom, ohms), from the
// datasheet's direct-mode formulas: V_RMS = 79931 * Vp(mV) / Vref, I_RMS = 324004 * Vs(mV) / Vref,
// WATT = 4046 * Vs(mV) * Vp(mV) / Vref^2, one CF pulse = 1638.4 * 256 / WATT-per-watt joules.
bl0939_scale_t bl0939_scale(double shunt_ohms, double r_top_ohms, double r_bottom_ohms);

// Petro rev B: a 1 mOhm shunt in the neutral, 5 x 390 kOhm over 470 Ohm (about 4150:1).
#define PETRO_SHUNT_OHMS 0.001
#define PETRO_DIV_TOP_OHMS (5 * 390e3)
#define PETRO_DIV_BOTTOM_OHMS 470.0
bl0939_scale_t bl0939_petro_scale(void);

typedef struct
{
    double volts;
    double amps_a;   // channel A: metering
    double amps_b;   // channel B: the same shunt, feeding the fast over-current
    double watts_a;
    double watts_b;
    double kwh_a;    // from the CF count since the chip's last reset
    double celsius;  // the chip's own temperature
} bl0939_reading_t;

bl0939_reading_t bl0939_convert(const bl0939_raw_t *raw, const bl0939_scale_t *scale);

// The internal temperature from TPS1: Tx = (170 / 448) * (TB / 2 - 32) - 45, TB its low 10 bits.
double bl0939_temperature(uint16_t tps1);
