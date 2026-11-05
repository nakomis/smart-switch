// The BL0939's UART protocol and conversions. See bl0939.h.
#include "bl0939.h"

size_t bl0939_build_full_read(uint8_t out[2])
{
    out[0] = BL0939_READ_COMMAND;
    out[1] = BL0939_FULL_PACKET;
    return 2;
}

size_t bl0939_build_write(uint8_t reg, uint32_t value24, uint8_t out[BL0939_WRITE_LEN])
{
    out[0] = BL0939_WRITE_COMMAND;
    out[1] = reg;
    out[2] = (uint8_t)(value24 & 0xFF);
    out[3] = (uint8_t)((value24 >> 8) & 0xFF);
    out[4] = (uint8_t)((value24 >> 16) & 0xFF);
    unsigned sum = 0;
    for (int i = 0; i < 5; i++)
        sum += out[i];
    out[5] = (uint8_t)(~sum & 0xFF);
    return BL0939_WRITE_LEN;
}

size_t bl0939_init_frames(uint8_t out[][BL0939_WRITE_LEN], size_t max_frames, uint32_t fast_rms_ctrl)
{
    // ESPHome's start-up values, with Petro's own fast-RMS thresholds (the OC output, PETRO-5's
    // instant trip) on both channels: they read the same shunt.
    const struct
    {
        uint8_t reg;
        uint32_t value;
    } seq[] = {
        {BL0939_REG_SOFT_RESET, 0x5A5A5A},  // reset to defaults
        {BL0939_REG_USR_WRPROT, 0x000055},  // allow user register writes
        {BL0939_REG_MODE, 0x001000},        // 50 Hz, RMS update every 400 ms, as ESPHome
        {BL0939_REG_TPS_CTRL, 0x0047FF},    // alarms on, automatic temperature, 100 ms
        {BL0939_REG_IA_FAST_RMS_CTRL, fast_rms_ctrl},
        {BL0939_REG_IB_FAST_RMS_CTRL, fast_rms_ctrl},
    };
    size_t count = fast_rms_ctrl ? 6 : 4;
    size_t n = 0;
    for (; n < count && n < max_frames; n++)
        bl0939_build_write(seq[n].reg, seq[n].value, out[n]);
    return n;
}

size_t bl0939_build_read(uint8_t reg, uint8_t out[2])
{
    out[0] = BL0939_READ_COMMAND;
    out[1] = reg;
    return 2;
}

bl0939_status_t bl0939_parse_register(uint8_t reg, const uint8_t *reply, size_t len, uint32_t *value)
{
    if (len != BL0939_REG_REPLY_LEN)
        return BL0939_ERR_LENGTH;
    unsigned sum = BL0939_READ_COMMAND + reg + reply[0] + reply[1] + reply[2];
    if ((uint8_t)(~sum & 0xFF) != reply[3])
        return BL0939_ERR_CHECKSUM;
    *value = (uint32_t)reply[0] | ((uint32_t)reply[1] << 8) | ((uint32_t)reply[2] << 16);
    return BL0939_OK;
}

uint8_t bl0939_packet_checksum(const uint8_t *packet, size_t len_without_checksum)
{
    unsigned sum = BL0939_READ_COMMAND;
    for (size_t i = 0; i < len_without_checksum; i++)
        sum += packet[i];
    return (uint8_t)(~sum & 0xFF);
}

static uint32_t u24(const uint8_t *p)
{
    return (uint32_t)p[0] | ((uint32_t)p[1] << 8) | ((uint32_t)p[2] << 16);
}

static int32_t s24(const uint8_t *p)
{
    uint32_t v = u24(p);
    return (v & 0x800000u) ? (int32_t)(v | 0xFF000000u) : (int32_t)v;
}

static uint16_t u16(const uint8_t *p)
{
    return (uint16_t)(p[0] | (p[1] << 8));
}

bl0939_status_t bl0939_parse_packet(const uint8_t *packet, size_t len, bl0939_raw_t *raw)
{
    if (len != BL0939_PACKET_LEN)
        return BL0939_ERR_LENGTH;
    if (packet[0] != BL0939_PACKET_HEADER)
        return BL0939_ERR_HEADER;
    if (bl0939_packet_checksum(packet, BL0939_PACKET_LEN - 1) != packet[BL0939_PACKET_LEN - 1])
        return BL0939_ERR_CHECKSUM;
    // Header, nine 24-bit registers, TPS1, a reserved byte, TPS2, a reserved byte, the checksum.
    const uint8_t *p = packet + 1;
    raw->ia_fast_rms = u24(p + 0);
    raw->ia_rms = u24(p + 3);
    raw->ib_rms = u24(p + 6);
    raw->v_rms = u24(p + 9);
    raw->ib_fast_rms = u24(p + 12);
    raw->a_watt = s24(p + 15);
    raw->b_watt = s24(p + 18);
    raw->cfa_cnt = u24(p + 21);
    raw->cfb_cnt = u24(p + 24);
    raw->tps1 = u16(p + 27);
    raw->tps2 = u16(p + 30);
    return BL0939_OK;
}

const char *bl0939_status_name(bl0939_status_t status)
{
    switch (status)
    {
    case BL0939_OK:
        return "ok";
    case BL0939_ERR_LENGTH:
        return "length";
    case BL0939_ERR_HEADER:
        return "header";
    case BL0939_ERR_CHECKSUM:
        return "checksum";
    }
    return "unknown";
}

bl0939_scale_t bl0939_scale(double shunt_ohms, double r_top_ohms, double r_bottom_ohms)
{
    // Millivolts at the pins per volt (or amp) at the mains.
    double vp_mv_per_volt = 1000.0 * r_bottom_ohms / (r_top_ohms + r_bottom_ohms);
    double vs_mv_per_amp = 1000.0 * shunt_ohms;
    bl0939_scale_t s;
    s.volts = 79931.0 * vp_mv_per_volt / BL0939_VREF;
    s.amps = 324004.0 * vs_mv_per_amp / BL0939_VREF;
    s.watts = 4046.0 * vs_mv_per_amp * vp_mv_per_volt / (BL0939_VREF * BL0939_VREF);
    s.pulses_per_kwh = 3.6e6 * s.watts / (1638.4 * 256.0);
    return s;
}

bl0939_scale_t bl0939_petro_scale(void)
{
    return bl0939_scale(PETRO_SHUNT_OHMS, PETRO_DIV_TOP_OHMS, PETRO_DIV_BOTTOM_OHMS);
}

double bl0939_temperature(uint16_t tps1)
{
    double tb = (double)(tps1 & 0x3FF);
    return (170.0 / 448.0) * (tb / 2.0 - 32.0) - 45.0;
}

bl0939_reading_t bl0939_convert(const bl0939_raw_t *raw, const bl0939_scale_t *scale)
{
    bl0939_reading_t r;
    r.volts = raw->v_rms / scale->volts;
    r.amps_a = raw->ia_rms / scale->amps;
    r.amps_b = raw->ib_rms / scale->amps;
    r.watts_a = raw->a_watt / scale->watts;
    r.watts_b = raw->b_watt / scale->watts;
    r.kwh_a = raw->cfa_cnt / scale->pulses_per_kwh;
    r.celsius = bl0939_temperature(raw->tps1);
    return r;
}
