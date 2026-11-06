// The NTC's divider to degrees. See ntc.h.
#include "ntc.h"

#include <math.h>

#define T25_KELVIN 298.15
#define KELVIN 273.15

ntc_params_t ntc_petro_params(void)
{
    ntc_params_t p = {NTC_R25_OHMS, NTC_B_KELVIN, NTC_R_TOP_OHMS, NTC_SUPPLY_MV};
    return p;
}

bool ntc_resistance(const ntc_params_t *p, double mv, double *ohms)
{
    if (!(mv > 0.0) || !(mv < p->supply_mv))
        return false;
    *ohms = p->r_top_ohms * mv / (p->supply_mv - mv);
    return true;
}

bool ntc_celsius(const ntc_params_t *p, double mv, double *celsius)
{
    double r;
    if (!(mv >= NTC_RAIL_MV && mv <= p->supply_mv - NTC_RAIL_MV) || !ntc_resistance(p, mv, &r))
        return false;
    double inv_t = 1.0 / T25_KELVIN + log(r / p->r25_ohms) / p->b_kelvin;
    double c = 1.0 / inv_t - KELVIN;
    if (!(c >= NTC_MIN_C && c <= NTC_MAX_C))
        return false;
    *celsius = c;
    return true;
}

double ntc_mv_at(const ntc_params_t *p, double celsius)
{
    double t = celsius + KELVIN;
    double r = p->r25_ohms * exp(p->b_kelvin * (1.0 / t - 1.0 / T25_KELVIN));
    return p->supply_mv * r / (r + p->r_top_ohms);
}
