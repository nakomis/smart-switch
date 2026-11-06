// petro-status: the /status JSON (port/status_json.c), one view per line on stdin (JSON, with the
// status_view field names; a missing reading is unknown), printed as status_json writes it, or -1
// if it doesn't fit the buffer (argv[1], default 1024).
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "cJSON.h"
#include "status_json.h"

static double num(const cJSON *in, const char *name, bool *have)
{
    const cJSON *item = cJSON_GetObjectItemCaseSensitive(in, name);
    if (have)
        *have = cJSON_IsNumber(item);
    return cJSON_IsNumber(item) ? item->valuedouble : 0;
}

static bool flag(const cJSON *in, const char *name)
{
    return cJSON_IsTrue(cJSON_GetObjectItemCaseSensitive(in, name));
}

static const char *str(const cJSON *in, const char *name)
{
    const cJSON *item = cJSON_GetObjectItemCaseSensitive(in, name);
    return cJSON_IsString(item) ? item->valuestring : NULL;
}

int main(int argc, char **argv)
{
    size_t cap = argc == 2 ? (size_t)atoi(argv[1]) : 1024;
    static char line[4096];
    while (fgets(line, sizeof(line), stdin) != NULL)
    {
        cJSON *in = cJSON_Parse(line);
        status_view v = {0};
        const char *mode = str(in, "mode"), *trip = str(in, "trip"), *reason = str(in, "reason");
        if (mode)
            ctl_mode_parse(mode, &v.mode);
        if (!ctl_trip_parse(trip, &v.trip))
            v.trip = CTL_TRIP_NONE;
        v.reason = !reason                          ? REPORT_HEARTBEAT
                   : strcmp(reason, "boot") == 0    ? REPORT_BOOT
                   : strcmp(reason, "change") == 0  ? REPORT_CHANGE
                   : strcmp(reason, "request") == 0 ? REPORT_REQUEST
                   : strcmp(reason, "bogus") == 0   ? (report_reason)99
                                                    : REPORT_HEARTBEAT;
        v.relay = flag(in, "relay");
        v.remote = flag(in, "remote");
        v.bench = flag(in, "bench");
        v.meter_ok = flag(in, "meter_ok");
        v.cycle_n = (uint32_t)num(in, "cycle_n", &v.cycle_active);
        v.cycle_done = (uint32_t)num(in, "cycle_done", NULL);
        v.volts = num(in, "volts", &v.have_meter);
        v.amps = num(in, "amps", NULL);
        v.watts = num(in, "watts", NULL);
        v.energy_kwh = num(in, "energy_kwh", NULL);
        v.board_c = num(in, "board_c", &v.have_temp);
        v.zx_hz = num(in, "zx_hz", &v.have_zx);
        v.trip_amps = num(in, "trip_amps", NULL);
        v.trip_amps_temporary = flag(in, "trip_amps_temporary");
        v.instant_amps = num(in, "instant_amps", NULL);
        v.instant_amps_temporary = flag(in, "instant_amps_temporary");
        v.overtemp_c = num(in, "overtemp_c", NULL);
        v.trips_enforced = flag(in, "trips_enforced");
        v.zx_sync = flag(in, "zx_sync");
        v.stress_left_s = (uint32_t)num(in, "stress_s", &v.stress);
        v.rssi = (int)num(in, "rssi", &v.have_rssi);
        v.uptime_s = (uint32_t)num(in, "uptime_s", NULL);
        v.version = str(in, "version");
        char *out = malloc(cap ? cap : 1);
        int len = status_json(out, cap, &v);
        if (len < 0)
            puts("-1");
        else
            puts(out);
        fflush(stdout);
        free(out);
        cJSON_Delete(in);
    }
    return 0;
}
