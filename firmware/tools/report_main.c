// petro-report: drive the status reporter (port/report.c) one loop per line on stdin, keeping state:
//
//   {"now":ms,"mqtt":bool,"changed":bool,"acked":bool,"ok":bool}
//       report_due; when it says publish, report_sent with ok (default true).
//   {"request":true,"now":ms,"ok":bool}
//       a get_status publish: report_sent(request).
//
// Prints {"publish":"boot"|"heartbeat"|"change"|"request"|null} per line.
#include <stdio.h>

#include "cJSON.h"
#include "report.h"

static bool flag(const cJSON *in, const char *name, bool dflt)
{
    const cJSON *item = cJSON_GetObjectItemCaseSensitive(in, name);
    return cJSON_IsBool(item) ? cJSON_IsTrue(item) : dflt;
}

int main(void)
{
    static char line[4096];
    reporter_t r;
    report_init(&r);
    while (fgets(line, sizeof(line), stdin) != NULL)
    {
        cJSON *in = cJSON_Parse(line);
        const cJSON *now_item = cJSON_GetObjectItemCaseSensitive(in, "now");
        int64_t now = cJSON_IsNumber(now_item) ? (int64_t)now_item->valuedouble : 0;
        bool ok = flag(in, "ok", true);
        const char *published = NULL;
        report_reason reason;
        if (flag(in, "request", false))
        {
            report_sent(&r, now, REPORT_REQUEST, ok);
            published = report_reason_name(REPORT_REQUEST);
        }
        else if (report_due(&r, now, flag(in, "mqtt", true), flag(in, "changed", false),
                               flag(in, "acked", false), &reason))
        {
            report_sent(&r, now, reason, ok);
            published = report_reason_name(reason);
        }
        cJSON *out = cJSON_CreateObject();
        if (published)
            cJSON_AddStringToObject(out, "publish", published);
        else
            cJSON_AddNullToObject(out, "publish");
        char *text = cJSON_PrintUnformatted(out);
        puts(text);
        fflush(stdout);
        cJSON_free(text);
        cJSON_Delete(out);
        cJSON_Delete(in);
    }
    return 0;
}
