// petro-fleetcmd: Petro's command parser (port/fleet_cmd.c), one command per line on stdin, one JSON
// result per line:
//   {"kind":"relay","type":"relay_result","on":true}
//   {"kind":"error","type":"error","message":"..."}
// With an argument, every ctl_result's message, one a line (for the reply texts).
#include <stdio.h>
#include <string.h>

#include "cJSON.h"
#include "fleet_cmd.h"

static const char *kind_name(fleet_cmd_kind k)
{
    switch (k)
    {
    case FLEET_CMD_GET_STATUS:
        return "get_status";
    case FLEET_CMD_RELAY:
        return "relay";
    case FLEET_CMD_SET_MODE:
        return "set_mode";
    case FLEET_CMD_RELAY_CYCLE:
        return "relay_cycle";
    case FLEET_CMD_RELAY_CYCLE_STOP:
        return "relay_cycle_stop";
    case FLEET_CMD_SET_TRIP:
        return "set_trip_threshold";
    case FLEET_CMD_WIFI_STRESS:
        return "wifi_stress";
    case FLEET_CMD_REBOOT:
        return "reboot";
    case FLEET_CMD_FLEET:
        return "fleet";
    case FLEET_CMD_ERROR:
        return "error";
    }
    return "?";
}

int main(int argc, char **argv)
{
    (void)argv;
    if (argc > 1)
    {
        for (int r = CTL_OK; r <= CTL_ERR_LOCAL_ONLY + 1; r++)
            puts(ctl_result_message((ctl_result)r));
        printf("%s %s\n", ctl_mode_name((ctl_mode)99), fleet_cmd_result_type((fleet_cmd_kind)99));
        return 0;
    }
    static char line[16 * 1024];
    while (fgets(line, sizeof(line), stdin) != NULL)
    {
        size_t len = strlen(line);
        if (len > 0 && line[len - 1] == '\n')
            line[--len] = '\0';
        // "\0" in the line stands for a NUL byte (trailing-NUL tests).
        for (char *p = strstr(line, "\\0"); p; p = strstr(p + 1, "\\0"))
        {
            *p = '\0';
            memmove(p + 1, p + 2, len - (size_t)(p + 2 - line) + 1);
            len--;
        }
        fleet_cmd cmd;
        fleet_cmd_parse(len ? line : NULL, len, &cmd);
        cJSON *out = cJSON_CreateObject();
        cJSON_AddStringToObject(out, "kind", kind_name(cmd.kind));
        cJSON_AddStringToObject(out, "type", fleet_cmd_result_type(cmd.kind));
        switch (cmd.kind)
        {
        case FLEET_CMD_RELAY:
            cJSON_AddBoolToObject(out, "on", cmd.on);
            break;
        case FLEET_CMD_SET_MODE:
            cJSON_AddStringToObject(out, "mode", ctl_mode_name(cmd.mode));
            break;
        case FLEET_CMD_RELAY_CYCLE:
            cJSON_AddNumberToObject(out, "n", cmd.n);
            cJSON_AddNumberToObject(out, "on_ms", cmd.on_ms);
            cJSON_AddNumberToObject(out, "off_ms", cmd.off_ms);
            break;
        case FLEET_CMD_SET_TRIP:
            if (cmd.amps < 0)
                cJSON_AddNullToObject(out, "amps");
            else
                cJSON_AddNumberToObject(out, "amps", cmd.amps);
            break;
        case FLEET_CMD_WIFI_STRESS:
            cJSON_AddBoolToObject(out, "on", cmd.on);
            cJSON_AddNumberToObject(out, "duration_s", cmd.duration_s);
            break;
        case FLEET_CMD_ERROR:
            cJSON_AddStringToObject(out, "message", cmd.message);
            break;
        default:
            break;
        }
        char *text = cJSON_PrintUnformatted(out);
        puts(text);
        fflush(stdout);
        cJSON_free(text);
        cJSON_Delete(out);
    }
    return 0;
}
