#include "bmp280_calc.h"

void bmp280_calib_parse(const uint8_t raw[24], bmp280_calib_t *c)
{
#define W(i) ((uint16_t)(raw[2 * (i)] | (raw[2 * (i) + 1] << 8)))
    c->T1 = W(0);
    c->T2 = (int16_t)W(1);
    c->T3 = (int16_t)W(2);
    c->P1 = W(3);
    c->P2 = (int16_t)W(4);
    c->P3 = (int16_t)W(5);
    c->P4 = (int16_t)W(6);
    c->P5 = (int16_t)W(7);
    c->P6 = (int16_t)W(8);
    c->P7 = (int16_t)W(9);
    c->P8 = (int16_t)W(10);
    c->P9 = (int16_t)W(11);
#undef W
}

int bmp280_compensate(const bmp280_calib_t *c, int32_t adc_t, int32_t adc_p, float *temp_c, float *pressure_pa)
{
    int32_t var1 = ((((adc_t >> 3) - ((int32_t)c->T1 << 1))) * ((int32_t)c->T2)) >> 11;
    int32_t var2 = (((((adc_t >> 4) - ((int32_t)c->T1)) * ((adc_t >> 4) - ((int32_t)c->T1))) >> 12) * ((int32_t)c->T3)) >> 14;
    int32_t t_fine = var1 + var2;
    *temp_c = (float)((t_fine * 5 + 128) >> 8) / 100.0f;

    int64_t v1 = (int64_t)t_fine - 128000;
    int64_t v2 = v1 * v1 * (int64_t)c->P6;
    v2 = v2 + ((v1 * (int64_t)c->P5) << 17);
    v2 = v2 + (((int64_t)c->P4) << 35);
    v1 = ((v1 * v1 * (int64_t)c->P3) >> 8) + ((v1 * (int64_t)c->P2) << 12);
    v1 = (((((int64_t)1) << 47) + v1)) * ((int64_t)c->P1) >> 33;
    if (v1 == 0)
        return 0;
    int64_t p = 1048576 - adc_p;
    p = (((p << 31) - v2) * 3125) / v1;
    v1 = (((int64_t)c->P9) * (p >> 13) * (p >> 13)) >> 25;
    v2 = (((int64_t)c->P8) * p) >> 19;
    p = ((p + v1 + v2) >> 8) + (((int64_t)c->P7) << 4);  // Q24.8 pascals
    *pressure_pa = (float)p / 256.0f;
    return *pressure_pa > 30000.0f && *pressure_pa < 110000.0f;
}
