// petro-ctl: drive the control logic (port/ctl.c), one operation per line on stdin, keeping state.
//
//   {"op":"init","stored":true,"mode":2,"trip":1}   ctl_init (also the start: stored false)
//   {"op":"press"}                             a debounced press (result: ctl_press's)
//   {"op":"clear"}                             ctl_clear_trip (Fleet's clear_trip)
//   {"op":"sensors","ok":false}                ctl_set_sensors_ok
//   {"op":"blocked","on":true}                 ctl_set_clear_blocked
//   {"op":"instant","amps":12.0}               ctl_set_instant_amps
//   {"op":"relay","on":true}                   a remote relay command
//   {"op":"mode","mode":"auto"}                set_mode, the console's ("bogus" tries an invalid one)
//   {"op":"remote_mode","mode":"off"}          Fleet's set_mode
//   {"op":"shutdown"}                          ctl_shutdown
//   {"op":"cycle","n":3,"on_ms":100,"off_ms":100}         a remote relay cycle
//   {"op":"bench_cycle","n":3,"on_ms":100,"off_ms":100}   the console's
//   {"op":"bench","on":true}                   the console's relay on/off
//   {"op":"stop"}                              ctl_cycle_stop
//   {"op":"trip","cause":"overcurrent"}        ctl_trip (any ctl_trip_name, else none)
//   {"op":"amps","amps":5.0}                   ctl_set_trip_amps
//   {"op":"tick"}                              nothing but ctl_relay
// Every line may carry "now" (ms; it stays until changed). Each prints the state after it, with
// ctl_relay at now:
//   {"result":"ok","relay":false,"mode":"off","trip":null,"remote":false,"bench":false,
//    "cycle":null|{"done":0,"n":3},"trip_amps":10.5,"temporary":false,"instant_amps":15,
//    "instant_temporary":false}
#include <stdio.h>
#include <string.h>

#include "cJSON.h"
#include "ctl.h"

static double num(const cJSON *in, const char *name, double dflt)
{
    const cJSON *item = cJSON_GetObjectItemCaseSensitive(in, name);
    return cJSON_IsNumber(item) ? item->valuedouble : dflt;
}

static const char *str(const cJSON *in, const char *name)
{
    const cJSON *item = cJSON_GetObjectItemCaseSensitive(in, name);
    return cJSON_IsString(item) ? item->valuestring : "";
}

static bool flag(const cJSON *in, const char *name)
{
    return cJSON_IsTrue(cJSON_GetObjectItemCaseSensitive(in, name));
}

static const char *result_name(ctl_result r)
{
    switch (r)
    {
    case CTL_OK:
        return "ok";
    case CTL_ERR_NOT_AUTO:
        return "not_auto";
    case CTL_ERR_TRIPPED:
        return "tripped";
    case CTL_ERR_INVALID:
        return "invalid";
    case CTL_ERR_LOCAL_ONLY:
        return "local_only";
    case CTL_ERR_SENSORS:
        return "sensors";
    case CTL_ERR_CLEAR_BLOCKED:
        return "blocked";
    }
    return "?";
}

int main(void)
{
    static char line[4096];
    ctl_t c;
    ctl_init(&c, false, 0, 0);
    int64_t now = 0;
    while (fgets(line, sizeof(line), stdin) != NULL)
    {
        cJSON *in = cJSON_Parse(line);
        now = (int64_t)num(in, "now", (double)now);
        const char *op = str(in, "op");
        const char *result = "ok";
        bool is_new = false;
        uint32_t n = (uint32_t)num(in, "n", 0), on_ms = (uint32_t)num(in, "on_ms", 0),
                 off_ms = (uint32_t)num(in, "off_ms", 0);
        if (strcmp(op, "init") == 0)
            ctl_init(&c, flag(in, "stored"), (int)num(in, "mode", 0), (int)num(in, "trip", 0));
        else if (strcmp(op, "press") == 0)
            result = result_name(ctl_press(&c));
        else if (strcmp(op, "clear") == 0)
            result = result_name(ctl_clear_trip(&c));
        else if (strcmp(op, "sensors") == 0)
            ctl_set_sensors_ok(&c, flag(in, "ok"));
        else if (strcmp(op, "blocked") == 0)
            ctl_set_clear_blocked(&c, flag(in, "on"));
        else if (strcmp(op, "instant") == 0)
            result = result_name(ctl_set_instant_amps(&c, num(in, "amps", 0)));
        else if (strcmp(op, "relay") == 0)
            result = result_name(ctl_remote_relay(&c, flag(in, "on")));
        else if (strcmp(op, "mode") == 0)
        {
            ctl_mode m = (ctl_mode)99;
            ctl_mode_parse(str(in, "mode"), &m);
            result = result_name(ctl_set_mode(&c, m));
        }
        else if (strcmp(op, "remote_mode") == 0)
        {
            ctl_mode m = (ctl_mode)99;
            ctl_mode_parse(str(in, "mode"), &m);
            result = result_name(ctl_remote_mode(&c, m));
        }
        else if (strcmp(op, "shutdown") == 0)
            ctl_shutdown(&c);
        else if (strcmp(op, "cycle") == 0)
            result = result_name(ctl_remote_cycle(&c, n, on_ms, off_ms, now));
        else if (strcmp(op, "bench_cycle") == 0)
            result = result_name(ctl_bench_cycle(&c, n, on_ms, off_ms, now));
        else if (strcmp(op, "bench") == 0)
            result = result_name(ctl_bench_relay(&c, flag(in, "on")));
        else if (strcmp(op, "stop") == 0)
            result = ctl_cycle_stop(&c) ? "stopped" : "idle";
        else if (strcmp(op, "trip") == 0)
        {
            ctl_trip_cause cause = CTL_TRIP_NONE;
            ctl_trip_parse(str(in, "cause"), &cause);
            is_new = ctl_trip(&c, cause);
            result = is_new ? "new" : "not_new";
        }
        else if (strcmp(op, "amps") == 0)
            result = result_name(ctl_set_trip_amps(&c, num(in, "amps", 0)));
        cJSON_Delete(in);

        bool relay = ctl_relay(&c, now);
        printf("{\"result\":\"%s\",\"relay\":%s,\"mode\":\"%s\",\"trip\":", result, relay ? "true" : "false",
               ctl_mode_name(c.mode));
        const char *trip = ctl_trip_name(c.trip);
        if (trip)
            printf("\"%s\"", trip);
        else
            printf("null");
        printf(",\"remote\":%s,\"bench\":%s,\"cycle\":", ctl_accepts_remote(&c) ? "true" : "false",
               c.bench ? "true" : "false");
        if (c.cycle.active)
            printf("{\"done\":%u,\"n\":%u}", c.cycle.done, c.cycle.n);
        else
            printf("null");
        printf(",\"trip_amps\":%g,\"temporary\":%s,\"instant_amps\":%g,\"instant_temporary\":%s}\n", c.trip_amps,
               ctl_trip_amps_temporary(&c) ? "true" : "false", c.instant_amps,
               ctl_instant_amps_temporary(&c) ? "true" : "false");
        fflush(stdout);
    }
    return 0;
}
