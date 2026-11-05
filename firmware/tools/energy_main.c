// petro-energy: the energy total (port/energy.c), one operation per line, keeping state:
//   {"op":"init","stored_mwh":n,"ppk":5641.0,"now":ms}
//   {"op":"cf","cnt":n,"now":ms}      -> also "accepted"
//   {"op":"saved","now":ms}           the caller stored energy_mwh
//   {"op":"due","now":ms}
// Each prints {"accepted":bool,"mwh":n,"kwh":x,"due":bool,"rejected":n}.
#include <inttypes.h>
#include <stdio.h>
#include <string.h>

#include "cJSON.h"
#include "energy.h"

static double num(const cJSON *in, const char *name, double dflt)
{
    const cJSON *item = cJSON_GetObjectItemCaseSensitive(in, name);
    return cJSON_IsNumber(item) ? item->valuedouble : dflt;
}

int main(void)
{
    static char line[512];
    energy_t e;
    energy_init(&e, 0, 5641.0, 0);
    while (fgets(line, sizeof(line), stdin) != NULL)
    {
        cJSON *in = cJSON_Parse(line);
        const cJSON *opi = cJSON_GetObjectItemCaseSensitive(in, "op");
        const char *op = cJSON_IsString(opi) ? opi->valuestring : "";
        int64_t now = (int64_t)num(in, "now", 0);
        bool accepted = true;
        if (strcmp(op, "init") == 0)
            energy_init(&e, (uint64_t)num(in, "stored_mwh", 0), num(in, "ppk", 5641.0), now);
        else if (strcmp(op, "cf") == 0)
            accepted = energy_update(&e, (uint32_t)num(in, "cnt", 0), now);
        else if (strcmp(op, "saved") == 0)
            energy_saved(&e, energy_mwh(&e), now);
        printf("{\"accepted\":%s,\"mwh\":%" PRIu64 ",\"kwh\":%.9f,\"due\":%s,\"rejected\":%u}\n",
               accepted ? "true" : "false", energy_mwh(&e), energy_kwh(&e),
               energy_save_due(&e, now) ? "true" : "false", e.rejected);
        fflush(stdout);
        cJSON_Delete(in);
    }
    return 0;
}
