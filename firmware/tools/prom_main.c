// petro-prom: the VictoriaMetrics push (port/prom.c).
//
//   petro-prom url <metrics_url>     prints the push URL, or "invalid"
//   petro-prom [cap]                 one sample per line on stdin (JSON; missing fields are absent
//                                    or zero; "resets": {"poweron": 2, ...}); prints the text
//                                    followed by a line "--" ("-1" alone if it didn't fit cap,
//                                    default 2048)
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "cJSON.h"
#include "prom.h"

static double num(const cJSON *in, const char *name, bool *have)
{
    const cJSON *item = cJSON_GetObjectItemCaseSensitive(in, name);
    if (have)
        *have = cJSON_IsNumber(item) || cJSON_IsString(item);
    if (cJSON_IsString(item) && strcmp(item->valuestring, "nan") == 0)
        return NAN;
    return cJSON_IsNumber(item) ? item->valuedouble : 0;
}

int main(int argc, char **argv)
{
    if (argc == 3 && strcmp(argv[1], "url") == 0)
    {
        char out[160];
        puts(prom_url(argv[2], out, sizeof(out)) ? out : "invalid");
        return 0;
    }
    size_t cap = argc == 2 ? (size_t)atoi(argv[1]) : 2048;
    static char line[4096];
    while (fgets(line, sizeof(line), stdin) != NULL)
    {
        cJSON *in = cJSON_Parse(line);
        prom_sample s = {0};
        s.volts = num(in, "volts", &s.have_meter);
        s.amps = num(in, "amps", NULL);
        s.watts = num(in, "watts", NULL);
        s.energy_kwh = num(in, "energy_kwh", NULL);
        s.board_c = num(in, "board_c", &s.have_temp);
        s.relay = cJSON_IsTrue(cJSON_GetObjectItemCaseSensitive(in, "relay"));
        s.zx_hz = num(in, "zx_hz", &s.have_zx);
        s.rssi = (int)num(in, "rssi", &s.have_rssi);
        s.uptime_s = (uint32_t)num(in, "uptime_s", NULL);
        s.trips_overcurrent = (uint32_t)num(in, "trips_overcurrent", NULL);
        s.trips_overcurrent_instant = (uint32_t)num(in, "trips_overcurrent_instant", NULL);
        s.trips_overtemp = (uint32_t)num(in, "trips_overtemp", NULL);
        s.trips_meter_fault = (uint32_t)num(in, "trips_meter_fault", NULL);
        const char *names[16];
        uint32_t counts[16];
        const cJSON *resets = cJSON_GetObjectItemCaseSensitive(in, "resets"), *r;
        size_t n = 0;
        cJSON_ArrayForEach(r, resets)
        {
            if (n < 16)
            {
                names[n] = r->string;
                counts[n++] = (uint32_t)r->valuedouble;
            }
        }
        s.reset_names = names;
        s.reset_counts = counts;
        s.resets = n;
        char *out = malloc(cap ? cap : 1);
        int len = prom_format(out, cap, &s);
        if (len < 0)
            puts("-1");
        else
            printf("%s--\n", out);
        fflush(stdout);
        free(out);
        cJSON_Delete(in);
    }
    return 0;
}
