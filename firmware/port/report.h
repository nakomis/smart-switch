// When Petro publishes /status, and why (copied from the nakostat heatlink). Portable, so the host
// tests it.
//
// The control task calls report_due once a loop and, when it says so, publishes and tells
// report_sent how that went (a get_status request's publish goes to report_sent too).
//
//   - boot: the first status after power-up, as soon as MQTT is up. Retried until one is queued
//     and acknowledged (a boot status lost with the connection is sent again).
//   - change: mode, relay or trip changed. A change made while MQTT was down, or whose publish failed, or
//     that IoT Core never acknowledged before the connection dropped (MQTT only notices a dead link
//     at its keepalive, and the outbox drops what it couldn't send), is reported as "change" on the
//     first status after the reconnect. A boot status covers any change before it.
//   - heartbeat: 60 s after the last status, and once after every reconnect.
//   - A failed publish is retried after REPORT_RETRY_MS, not on every loop.
//
// "Acknowledged" is the network's word that the latest status has its PUBACK. QoS 1 PUBACKs come
// back in order, so the latest one acknowledged covers every status before it.
#pragma once

#include <stdbool.h>
#include <stdint.h>

typedef enum
{
    REPORT_BOOT,
    REPORT_HEARTBEAT,
    REPORT_CHANGE,
    REPORT_REQUEST,
} report_reason;

// "boot", "heartbeat", "change" or "request".
const char *report_reason_name(report_reason reason);

#define REPORT_HEARTBEAT_MS 60000
#define REPORT_RETRY_MS 5000

typedef struct
{
    bool boot_pending;       // no boot status has got through yet
    bool change_pending;     // a mode or relay change not yet reported
    bool reconnect_pending;  // connected again: a status is owed
    bool awaiting_ack;       // a boot or change status went out; no PUBACK for it (or later) yet
    report_reason awaiting;      // which of the two
    bool was_up;
    int64_t last_status_ms;  // the last status queued, of any reason
    int64_t retry_at_ms;     // after a failed publish, nothing before this
} reporter_t;

void report_init(reporter_t *r);

// One loop: `changed` = mode, relay or trip changed this loop; `mqtt` = connected; `acked` = the latest
// status queued has been acknowledged. True (and *reason set) when a status should go out now.
bool report_due(reporter_t *r, int64_t now_ms, bool mqtt, bool changed, bool acked, report_reason *reason);

// After any status publish: ok = it was queued for IoT Core.
void report_sent(reporter_t *r, int64_t now_ms, report_reason reason, bool ok);
