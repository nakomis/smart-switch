// petro-prot: drive the protection logic (port/prot.c), one operation per line on stdin, keeping
// state. Every line may carry "now" (ms; it stays until changed).
//
//   {"op":"init"}                              prot_init with the defaults (also the start)
//   {"op":"meter","ok":true}                   prot_meter_init
//   {"op":"frame","amps":11,"amps_b":11,"limit":10.5}  prot_frame (amps_b defaults to amps; "nan")
//   {"op":"temp","c":40}                       prot_temp ("c" absent: couldn't be read)
//   {"op":"oc","on":true,"closed":true}        prot_oc
//   {"op":"armed","on":true}                   prot_oc_armed
//   {"op":"may_arm","configured":true,"open":true}   {"may_arm":..}
//   {"op":"release","before":"overtemp","after":null}  {"due":..}
// The state line also carries "oc_cause" (prot_oc_cause's name).
//   {"op":"tick"}                              nothing
// Each prints, at now, with "wanted" (the relay wanted on, default false) and "latched" (a cause's
// name, default none) from the line:
//   {"trip":null|"overcurrent"|...,"healthy":false,"starting":true,"blocked":false}
//
//   {"op":"ctrl","amps":15,"cpa":266013}       {"value":..}   prot_fast_rms_ctrl
//   {"op":"limit","room":35,"hot":70,"ratio":1.75}  {"limit":..}  prot_ntc_limit
//   {"op":"defaults"}                          the defaults
#include <math.h>
#include <stdio.h>
#include <string.h>

#include "cJSON.h"
#include "prot.h"

static double num(const cJSON *in, const char *name, double dflt)
{
    const cJSON *item = cJSON_GetObjectItemCaseSensitive(in, name);
    return cJSON_IsNumber(item) ? item->valuedouble : dflt;
}

static const char *str(const cJSON *in, const char *name)
{
    const cJSON *item = cJSON_GetObjectItemCaseSensitive(in, name);
    return cJSON_IsString(item) ? item->valuestring : NULL;
}

static bool flag(const cJSON *in, const char *name)
{
    return cJSON_IsTrue(cJSON_GetObjectItemCaseSensitive(in, name));
}

int main(void)
{
    static char line[4096];
    prot_config cfg = prot_defaults();
    prot_t p;
    int64_t now = 0;
    prot_init(&p, &cfg, now);
    while (fgets(line, sizeof(line), stdin) != NULL)
    {
        cJSON *in = cJSON_Parse(line);
        now = (int64_t)num(in, "now", (double)now);
        const char *op = str(in, "op");
        op = op ? op : "";
        if (strcmp(op, "ctrl") == 0)
        {
            printf("{\"value\":%u}\n", prot_fast_rms_ctrl(num(in, "amps", 0), num(in, "cpa", 0)));
            fflush(stdout);
            cJSON_Delete(in);
            continue;
        }
        if (strcmp(op, "limit") == 0)
        {
            printf("{\"limit\":%.6f}\n", prot_ntc_limit(num(in, "room", 0), num(in, "hot", 0), num(in, "ratio", 1)));
            fflush(stdout);
            cJSON_Delete(in);
            continue;
        }
        if (strcmp(op, "defaults") == 0)
        {
            printf("{\"sustain_ms\":%u,\"overtemp_c\":%g,\"overtemp_ms\":%u,\"clear_margin_c\":%g,\"stale_ms\":%u}\n",
                   cfg.sustain_ms, cfg.overtemp_c, cfg.overtemp_ms, cfg.clear_margin_c, cfg.stale_ms);
            fflush(stdout);
            cJSON_Delete(in);
            continue;
        }
        if (strcmp(op, "init") == 0)
            prot_init(&p, &cfg, now);
        else if (strcmp(op, "meter") == 0)
            prot_meter_init(&p, flag(in, "ok"));
        else if (strcmp(op, "frame") == 0)
        {
            const cJSON *b = cJSON_GetObjectItemCaseSensitive(in, "amps_b");
            double a = num(in, "amps", 0);
            double bv = cJSON_IsString(b) ? NAN : num(in, "amps_b", a);
            prot_frame(&p, a, bv, num(in, "limit", CTL_TRIP_AMPS_DEFAULT), now);
        }
        else if (strcmp(op, "temp") == 0)
        {
            const cJSON *c = cJSON_GetObjectItemCaseSensitive(in, "c");
            prot_temp(&p, cJSON_IsNumber(c), cJSON_IsNumber(c) ? c->valuedouble : 0, now);
        }
        else if (strcmp(op, "oc") == 0)
            prot_oc(&p, flag(in, "on"), flag(in, "closed"));
        else if (strcmp(op, "armed") == 0)
            prot_oc_armed(&p, flag(in, "on"));
        else if (strcmp(op, "may_arm") == 0 || strcmp(op, "release") == 0)
        {
            if (op[0] == 'm')
                printf("{\"may_arm\":%s}\n",
                       prot_may_arm_oc(&p, flag(in, "configured"), flag(in, "open"), now) ? "true" : "false");
            else
            {
                ctl_trip_cause before = CTL_TRIP_NONE, after = CTL_TRIP_NONE;
                ctl_trip_parse(str(in, "before"), &before);
                ctl_trip_parse(str(in, "after"), &after);
                printf("{\"due\":%s}\n", prot_oc_release_due(before, after) ? "true" : "false");
            }
            fflush(stdout);
            cJSON_Delete(in);
            continue;
        }

        ctl_trip_cause latched = CTL_TRIP_NONE;
        ctl_trip_parse(str(in, "latched"), &latched);
        const char *trip = ctl_trip_name(prot_check(&p, flag(in, "wanted"), now));
        printf("{\"trip\":");
        if (trip)
            printf("\"%s\"", trip);
        else
            printf("null");
        printf(",\"healthy\":%s,\"starting\":%s,\"blocked\":%s,\"oc_cause\":\"%s\"}\n",
               prot_healthy(&p, now) ? "true" : "false", prot_starting(&p, now) ? "true" : "false",
               prot_clear_blocked(&p, latched, now) ? "true" : "false", ctl_trip_name(prot_oc_cause(&p, now)));
        fflush(stdout);
        cJSON_Delete(in);
    }
    return 0;
}
