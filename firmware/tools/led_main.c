// petro-led: what the status LED shows (port/led.c), one state per line:
//   {"now":ms,"tripped":bool,"ota":bool,"provisioned":bool,"wifi":bool,"mqtt":bool,
//    "mode":"on"|"off"|"auto","relay":bool,"level":0-255}
//   -> {"colour":"green","r":0,"g":64,"b":0}
// Missing flags are false, except provisioned, wifi and mqtt (true); level defaults to 255.
#include <stdio.h>

#include "cJSON.h"
#include "led.h"

static bool flag(const cJSON *in, const char *name, bool dflt)
{
    const cJSON *item = cJSON_GetObjectItemCaseSensitive(in, name);
    return cJSON_IsBool(item) ? cJSON_IsTrue(item) : dflt;
}

int main(int argc, char **argv)
{
    (void)argv;
    if (argc > 1)
    {
        // Every name, and an out-of-range colour.
        for (int c = LED_DARK; c <= LED_DIM_BLUE + 1; c++)
        {
            uint8_t r, g, b;
            led_rgb((led_colour)c, 255, &r, &g, &b);
            printf("%s %u %u %u\n", led_name((led_colour)c), r, g, b);
        }
        return 0;
    }
    static char line[512];
    while (fgets(line, sizeof(line), stdin) != NULL)
    {
        cJSON *in = cJSON_Parse(line);
        const cJSON *now = cJSON_GetObjectItemCaseSensitive(in, "now");
        const cJSON *mode = cJSON_GetObjectItemCaseSensitive(in, "mode");
        const cJSON *level = cJSON_GetObjectItemCaseSensitive(in, "level");
        led_inputs li = {
            .now_ms = cJSON_IsNumber(now) ? (int64_t)now->valuedouble : 0,
            .tripped = flag(in, "tripped", false),
            .ota = flag(in, "ota", false),
            .provisioned = flag(in, "provisioned", true),
            .wifi_up = flag(in, "wifi", true),
            .mqtt_up = flag(in, "mqtt", true),
            .mode = CTL_MODE_OFF,
            .relay = flag(in, "relay", false),
        };
        if (cJSON_IsString(mode))
            ctl_mode_parse(mode->valuestring, &li.mode);
        led_colour c = led_show(&li);
        uint8_t r, g, b;
        led_rgb(c, cJSON_IsNumber(level) ? (uint8_t)level->valuedouble : 255, &r, &g, &b);
        printf("{\"colour\":\"%s\",\"r\":%u,\"g\":%u,\"b\":%u}\n", led_name(c), r, g, b);
        fflush(stdout);
        cJSON_Delete(in);
    }
    return 0;
}
