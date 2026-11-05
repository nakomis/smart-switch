// Petro's command parser. See fleet_cmd.h.
#include "fleet_cmd.h"

#include <math.h>
#include <stdio.h>
#include <string.h>

#include "cJSON.h"

#define MAX_DEPTH 8

static void fail(fleet_cmd *out, const char *message)
{
    out->kind = FLEET_CMD_ERROR;
    snprintf(out->message, sizeof(out->message), "%s", message);
}

// A whole number from 0 to max, or false.
static bool whole(const cJSON *root, const char *name, uint32_t max, uint32_t *out)
{
    const cJSON *item = cJSON_GetObjectItemCaseSensitive(root, name);
    if (!cJSON_IsNumber(item) || !isfinite(item->valuedouble))
        return false;
    double v = item->valuedouble;
    if (v < 0 || v > max || v != floor(v))
        return false;
    *out = (uint32_t)v;
    return true;
}

static bool boolean(const cJSON *root, const char *name, bool *out)
{
    const cJSON *item = cJSON_GetObjectItemCaseSensitive(root, name);
    if (!cJSON_IsBool(item))
        return false;
    *out = cJSON_IsTrue(item);
    return true;
}

static void relay(const cJSON *root, fleet_cmd *out)
{
    if (!boolean(root, "on", &out->on))
        return fail(out, "relay needs a boolean on");
    out->kind = FLEET_CMD_RELAY;
}

static void set_mode(const cJSON *root, fleet_cmd *out)
{
    const cJSON *mode = cJSON_GetObjectItemCaseSensitive(root, "mode");
    if (!cJSON_IsString(mode) || !ctl_mode_parse(mode->valuestring, &out->mode))
        return fail(out, "mode must be on, off or auto");
    out->kind = FLEET_CMD_SET_MODE;
}

static void relay_cycle(const cJSON *root, fleet_cmd *out)
{
    if (!whole(root, "n", UINT32_MAX, &out->n) || !whole(root, "on_ms", UINT32_MAX, &out->on_ms) ||
        !whole(root, "off_ms", UINT32_MAX, &out->off_ms))
        return fail(out, "relay_cycle needs whole numbers n, on_ms and off_ms");
    if (!ctl_cycle_valid(out->n, out->on_ms, out->off_ms, CTL_REMOTE_CYCLE_MAX_TOTAL_MS))
        return fail(out, "relay_cycle: n 1-10000, on_ms and off_ms 50-60000, at most 2 h in all");
    out->kind = FLEET_CMD_RELAY_CYCLE;
}

// An optional threshold: absent (false, *set false), null (-1, the default) or a number in range.
static bool threshold(const cJSON *root, const char *name, double min, double max, bool *set, double *out)
{
    const cJSON *item = cJSON_GetObjectItemCaseSensitive(root, name);
    *set = item != NULL;
    if (item == NULL)
        return true;
    if (cJSON_IsNull(item))
        *out = -1;
    else if (cJSON_IsNumber(item) && isfinite(item->valuedouble) && item->valuedouble >= min &&
             item->valuedouble <= max)
        *out = item->valuedouble;
    else
        return false;
    return true;
}

static void set_trip(const cJSON *root, fleet_cmd *out)
{
    if (!threshold(root, "amps", CTL_TRIP_AMPS_MIN, CTL_TRIP_AMPS_DEFAULT, &out->set_amps, &out->amps))
        return fail(out, "amps must be 0.5-10.5, or null for the default");
    if (!threshold(root, "instant_amps", CTL_INSTANT_AMPS_MIN, CTL_INSTANT_AMPS_DEFAULT, &out->set_instant,
                   &out->instant_amps))
        return fail(out, "instant_amps must be 1-15, or null for the default");
    if (!out->set_amps && !out->set_instant)
        return fail(out, "amps must be given (0.5-10.5), or instant_amps (1-15), or both");
    out->kind = FLEET_CMD_SET_TRIP;
}

static void wifi_stress(const cJSON *root, fleet_cmd *out)
{
    if (!boolean(root, "on", &out->on))
        return fail(out, "wifi_stress needs a boolean on");
    out->duration_s = FLEET_STRESS_DEFAULT_S;
    if (cJSON_GetObjectItemCaseSensitive(root, "duration_s") != NULL &&
        (!whole(root, "duration_s", FLEET_STRESS_MAX_S, &out->duration_s) || out->duration_s < FLEET_STRESS_MIN_S))
        return fail(out, "duration_s must be a whole number from 60 to 7200");
    out->kind = FLEET_CMD_WIFI_STRESS;
}

// Whether the bracket nesting outside strings ever goes deeper than MAX_DEPTH (from the heatlink's
// hl_cmd.c). Checked before cJSON sees the bytes, so a hostile "[[[[..." can't recurse through the
// stack.
static bool too_deep(const char *json, size_t len)
{
    int depth = 0;
    bool in_string = false;
    for (size_t i = 0; i < len; i++)
    {
        char c = json[i];
        if (in_string)
        {
            if (c == '\\')
                i++;
            else if (c == '"')
                in_string = false;
        }
        else if (c == '"')
            in_string = true;
        else if (c == '[' || c == '{')
        {
            if (++depth > MAX_DEPTH)
                return true;
        }
        else if ((c == ']' || c == '}') && depth > 0)
            depth--;
    }
    return false;
}

void fleet_cmd_parse(const char *json, size_t len, fleet_cmd *out)
{
    memset(out, 0, sizeof(*out));
    if (json != NULL && too_deep(json, len))
        return fail(out, "too deeply nested");
    const char *end = NULL;
    cJSON *root = (json != NULL && len > 0) ? cJSON_ParseWithLengthOpts(json, len, &end, false) : NULL;
    bool trailing = false;
    if (root != NULL)
        for (const char *p = end; p < json + len; p++)
            if (*p != '\0' && *p != ' ' && *p != '\t' && *p != '\r' && *p != '\n')
                trailing = true;
    const cJSON *name = root ? cJSON_GetObjectItemCaseSensitive(root, "command") : NULL;
    const char *command = cJSON_IsString(name) ? name->valuestring : NULL;

    if (root == NULL || !cJSON_IsObject(root))
        fail(out, "not a JSON object");
    else if (trailing)
        fail(out, "trailing bytes after the JSON");
    else if (command == NULL)
        fail(out, "missing command");
    else if (strcmp(command, "get_status") == 0)
        out->kind = FLEET_CMD_GET_STATUS;
    else if (strcmp(command, "relay") == 0)
        relay(root, out);
    else if (strcmp(command, "set_mode") == 0)
        set_mode(root, out);
    else if (strcmp(command, "relay_cycle") == 0)
        relay_cycle(root, out);
    else if (strcmp(command, "relay_cycle_stop") == 0)
        out->kind = FLEET_CMD_RELAY_CYCLE_STOP;
    else if (strcmp(command, "set_trip_threshold") == 0)
        set_trip(root, out);
    else if (strcmp(command, "clear_trip") == 0)
        out->kind = FLEET_CMD_CLEAR_TRIP;
    else if (strcmp(command, "wifi_stress") == 0)
        wifi_stress(root, out);
    else if (strcmp(command, "reboot") == 0)
        out->kind = FLEET_CMD_REBOOT;
    else if (strcmp(command, "get_version") == 0 || strcmp(command, "ping") == 0 ||
             strcmp(command, "ota_update") == 0 || strcmp(command, "url_chunk") == 0 ||
             strcmp(command, "ota_cancel") == 0)
        out->kind = FLEET_CMD_FLEET;
    else
        fail(out, "unknown command");
    cJSON_Delete(root);
}

const char *fleet_cmd_result_type(fleet_cmd_kind kind)
{
    switch (kind)
    {
    case FLEET_CMD_GET_STATUS:
        return "get_status_result";
    case FLEET_CMD_RELAY:
        return "relay_result";
    case FLEET_CMD_SET_MODE:
        return "set_mode_result";
    case FLEET_CMD_RELAY_CYCLE:
        return "relay_cycle_result";
    case FLEET_CMD_RELAY_CYCLE_STOP:
        return "relay_cycle_stop_result";
    case FLEET_CMD_SET_TRIP:
        return "set_trip_threshold_result";
    case FLEET_CMD_CLEAR_TRIP:
        return "clear_trip_result";
    case FLEET_CMD_WIFI_STRESS:
        return "wifi_stress_result";
    case FLEET_CMD_REBOOT:
        return "reboot_result";
    case FLEET_CMD_FLEET:
    case FLEET_CMD_ERROR:
        break;
    }
    return "error";
}
