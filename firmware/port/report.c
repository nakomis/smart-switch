// When to publish /status. See report.h.
#include "report.h"

#include <string.h>

const char *report_reason_name(report_reason reason)
{
    switch (reason)
    {
    case REPORT_BOOT:
        return "boot";
    case REPORT_HEARTBEAT:
        return "heartbeat";
    case REPORT_CHANGE:
        return "change";
    case REPORT_REQUEST:
        return "request";
    }
    return "?";
}

void report_init(reporter_t *r)
{
    memset(r, 0, sizeof(*r));
    r->boot_pending = true;
}

bool report_due(reporter_t *r, int64_t now_ms, bool mqtt, bool changed, bool acked, report_reason *reason)
{
    if (changed)
        r->change_pending = true;
    if (r->awaiting_ack && acked)
        r->awaiting_ack = false;
    if (!mqtt)
    {
        if (r->awaiting_ack)
        {
            // Lost with the connection, as far as anyone can tell: say it again.
            if (r->awaiting == REPORT_BOOT)
                r->boot_pending = true;
            else
                r->change_pending = true;
            r->awaiting_ack = false;
        }
        r->was_up = false;
        return false;
    }
    if (!r->was_up)
    {
        r->was_up = true;
        r->reconnect_pending = true;
        r->retry_at_ms = now_ms;  // a new connection: no need to wait out an old failure
    }
    if (now_ms < r->retry_at_ms)
        return false;
    if (r->boot_pending)
        *reason = REPORT_BOOT;
    else if (r->change_pending)
        *reason = REPORT_CHANGE;
    else if (r->reconnect_pending || now_ms - r->last_status_ms >= REPORT_HEARTBEAT_MS)
        *reason = REPORT_HEARTBEAT;
    else
        return false;
    return true;
}

void report_sent(reporter_t *r, int64_t now_ms, report_reason reason, bool ok)
{
    if (!ok)
    {
        r->retry_at_ms = now_ms + REPORT_RETRY_MS;
        return;
    }
    r->last_status_ms = now_ms;
    r->reconnect_pending = false;
    if (reason == REPORT_BOOT || reason == REPORT_CHANGE)
    {
        // Any status carries the current mode and relay, so a boot status reports a change too.
        if (reason == REPORT_BOOT)
            r->boot_pending = false;
        r->change_pending = false;
        r->awaiting_ack = true;
        r->awaiting = reason;
    }
}
