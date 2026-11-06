// petro-button: SW1's debounce (port/button.c), one reading per line, keeping state:
//   {"now":ms,"pressed":bool}  ->  {"press":bool,"stable":bool}
#include <stdio.h>

#include "button.h"
#include "cJSON.h"

int main(void)
{
    static char line[256];
    button_t b;
    button_init(&b);
    while (fgets(line, sizeof(line), stdin) != NULL)
    {
        cJSON *in = cJSON_Parse(line);
        const cJSON *now = cJSON_GetObjectItemCaseSensitive(in, "now");
        bool pressed = cJSON_IsTrue(cJSON_GetObjectItemCaseSensitive(in, "pressed"));
        bool press = button_update(&b, pressed, cJSON_IsNumber(now) ? (int64_t)now->valuedouble : 0);
        printf("{\"press\":%s,\"stable\":%s}\n", press ? "true" : "false", b.stable ? "true" : "false");
        fflush(stdout);
        cJSON_Delete(in);
    }
    return 0;
}
