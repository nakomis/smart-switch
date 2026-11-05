// Petro's own commands, as they arrive on petro/<thing>/commands (the shape follows the heatlink's
// hl_cmd). Portable, so the host tests it.
//
//   {"command":"get_status"}                       publish a status now (reason "request")
//   {"command":"relay","on":true}                  auto only (ctl.h): refused in on and off
//   {"command":"set_mode","mode":"on"|"off"|"auto"} persisted; "off" also clears a trip
//   {"command":"relay_cycle","n":500,"on_ms":3000,"off_ms":5000}
//                                                  auto only; the console's limits: n 1-10000,
//                                                  50-60000 ms each, an hour at most in all
//   {"command":"relay_cycle_stop"}
//   {"command":"set_trip_threshold","amps":6.5}    temporary, RAM only (gone after a reboot); 0.5 to
//                                                  10.5 A, never above the default. "amps":null
//                                                  puts the default back
//   {"command":"wifi_stress","on":true,"duration_s":3600}
//                                                  Gate 3's transmit stress; duration_s 60-7200,
//                                                  default 3600; "on":false stops it. RAM only
//   {"command":"reboot"}
//
// Fleet's own commands (get_version, ping, ota_update, url_chunk, ota_cancel) come back as
// FLEET_CMD_FLEET without their arguments being looked at: hand the same bytes to ota_cmd_parse.
// Anything malformed or unknown is FLEET_CMD_ERROR with a message, never a change. Nesting deeper
// than 8 levels is refused before cJSON parses it (cJSON recurses per level on a small task stack).
#pragma once

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#include "ctl.h"

#define FLEET_STRESS_DEFAULT_S 3600
#define FLEET_STRESS_MIN_S 60
#define FLEET_STRESS_MAX_S 7200

typedef enum
{
    FLEET_CMD_GET_STATUS,
    FLEET_CMD_RELAY,           // on
    FLEET_CMD_SET_MODE,        // mode
    FLEET_CMD_RELAY_CYCLE,     // n, on_ms, off_ms
    FLEET_CMD_RELAY_CYCLE_STOP,
    FLEET_CMD_SET_TRIP,        // amps (negative: the default)
    FLEET_CMD_WIFI_STRESS,     // on, duration_s
    FLEET_CMD_REBOOT,
    FLEET_CMD_FLEET,           // one of Fleet's: pass the bytes to ota_cmd_parse
    FLEET_CMD_ERROR,           // message
} fleet_cmd_kind;

typedef struct
{
    fleet_cmd_kind kind;
    bool on;
    ctl_mode mode;
    uint32_t n, on_ms, off_ms;
    double amps;
    uint32_t duration_s;
    char message[96];
} fleet_cmd;

void fleet_cmd_parse(const char *json, size_t len, fleet_cmd *out);

// The "type" of the reply to a command: "relay_result" and so on.
const char *fleet_cmd_result_type(fleet_cmd_kind kind);
