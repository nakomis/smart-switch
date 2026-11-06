// BMP280 compensation (datasheet BST-BMP280-DS001, section 3.11.3, 32-bit temperature and 64-bit
// pressure). Portable C, host-tested against the datasheet's worked example.
#ifndef ZATT_BMP280_CALC_H
#define ZATT_BMP280_CALC_H

#include <stdint.h>

typedef struct
{
    uint16_t T1;
    int16_t T2, T3;
    uint16_t P1;
    int16_t P2, P3, P4, P5, P6, P7, P8, P9;
} bmp280_calib_t;

// Fills c from the 24 bytes at register 0x88 (little-endian words, T1..P9).
void bmp280_calib_parse(const uint8_t raw[24], bmp280_calib_t *c);

// adc_t and adc_p are the raw 20-bit readings. Returns false if the pressure is out of range (or the
// calibration would divide by zero); the temperature is valid regardless.
int bmp280_compensate(const bmp280_calib_t *c, int32_t adc_t, int32_t adc_p, float *temp_c, float *pressure_pa);

#endif
