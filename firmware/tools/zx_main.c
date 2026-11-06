// petro-zx: the zero-cross scheduler (port/zx.c), one question per line on stdin:
//   {"edges":[0,10000,20000],"now":25000,"actuate":8000}
// recorded with zx_edge in order (any number), answered with
//   {"period":20000,"at":32000,"n":3}           (at -1: switch at once)
#include <stdio.h>

#include "cJSON.h"
#include "zx.h"

int main(void)
{
    static char line[4096];
    while (fgets(line, sizeof(line), stdin) != NULL)
    {
        cJSON *in = cJSON_Parse(line);
        zx_edges z = {0};
        const cJSON *e;
        cJSON_ArrayForEach(e, cJSON_GetObjectItemCaseSensitive(in, "edges"))
        {
            zx_edge(&z, (int64_t)e->valuedouble);
        }
        const cJSON *now = cJSON_GetObjectItemCaseSensitive(in, "now");
        const cJSON *act = cJSON_GetObjectItemCaseSensitive(in, "actuate");
        int64_t t = cJSON_IsNumber(now) ? (int64_t)now->valuedouble : 0;
        int64_t a = cJSON_IsNumber(act) ? (int64_t)act->valuedouble : 0;
        printf("{\"period\":%lld,\"at\":%lld,\"n\":%u}\n", (long long)zx_period_us(&z, t),
               (long long)zx_switch_at(&z, t, a), z.n);
        fflush(stdout);
        cJSON_Delete(in);
    }
    return 0;
}
