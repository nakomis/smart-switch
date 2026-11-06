// The board's NTC (TH1): a 10 kOhm NTC to GND under a 10 kOhm resistor to 3V3, read on GPIO0
// (ADC1_CH0). About 1.65 V at 25 C, falling as the board warms. Portable C, no IDF.
#pragma once

#include <stdbool.h>

// TH1 is KUU's KNTC0603/10KF3950 (LCSC C2892547): 10 kOhm at 25 C, B = 3950 K (the part number's
// "3950"), 1 %.
#define NTC_R25_OHMS 10000.0
#define NTC_B_KELVIN 3950.0
#define NTC_R_TOP_OHMS 10000.0
#define NTC_SUPPLY_MV 3300.0

typedef struct
{
    double r25_ohms;
    double b_kelvin;
    double r_top_ohms;
    double supply_mv;
} ntc_params_t;

ntc_params_t ntc_petro_params(void);

// The NTC's resistance from the divider's voltage. False when mv is outside (0, supply): an open
// NTC reads the supply and a shorted one 0 V.
bool ntc_resistance(const ntc_params_t *p, double mv, double *ohms);

// Degrees Celsius from the divider's voltage, by the B equation. False as ntc_resistance.
bool ntc_celsius(const ntc_params_t *p, double mv, double *celsius);

// The divider's voltage at a temperature (the inverse, for tests and limits).
double ntc_mv_at(const ntc_params_t *p, double celsius);
