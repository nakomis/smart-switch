// Host driver for port/ntc: one command a line on stdin, one JSON line out.
//
//   <mv>          -> {"ok":true,"ohms":..,"celsius":..}  (Petro's TH1 and divider)
//   at <celsius>  -> {"mv":..}
#include <stdio.h>
#include <string.h>

#include "ntc.h"

int main(void)
{
    char line[128];
    ntc_params_t p = ntc_petro_params();
    while (fgets(line, sizeof(line), stdin) != NULL)
    {
        double v;
        if (sscanf(line, "at %lf", &v) == 1)
        {
            printf("{\"mv\":%.6f}\n", ntc_mv_at(&p, v));
        }
        else if (sscanf(line, "%lf", &v) == 1)
        {
            double r = 0, c = 0;
            bool ok = ntc_resistance(&p, v, &r) && ntc_celsius(&p, v, &c);
            if (ok)
                printf("{\"ok\":true,\"ohms\":%.6f,\"celsius\":%.6f}\n", r, c);
            else
                printf("{\"ok\":false}\n");
        }
        else
        {
            printf("{\"error\":\"unknown\"}\n");
        }
    }
    return 0;
}
