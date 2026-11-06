// The T1..T7 spot rectangles. Kconfig gives the defaults (empty: disabled); a save from the mapping
// page overrides them in the default NVS partition, namespace "spots", one "T1".."T7" string each
// ("x0,y0,x1,y1", or empty to go back to disabled).
#include <stdio.h>
#include <string.h>

#include "esp_log.h"
#include "nvs.h"
#include "sdkconfig.h"
#include "zatt.h"

static const char *TAG = "spots";
static const char *NAMES[ZATT_NSPOTS] = {"T1", "T2", "T3", "T4", "T5", "T6", "T7"};
static const char *DEFAULTS[ZATT_NSPOTS] = {
    CONFIG_ZATT_SPOT_T1_DEFAULT, CONFIG_ZATT_SPOT_T2_DEFAULT, CONFIG_ZATT_SPOT_T3_DEFAULT,
    CONFIG_ZATT_SPOT_T4_DEFAULT, CONFIG_ZATT_SPOT_T5_DEFAULT, CONFIG_ZATT_SPOT_T6_DEFAULT,
    CONFIG_ZATT_SPOT_T7_DEFAULT,
};
static zatt_rect_t rects[ZATT_NSPOTS];

const char *spots_name(int i)
{
    return NAMES[i];
}

int spots_index(const char *name)
{
    for (int i = 0; i < ZATT_NSPOTS; i++)
        if (strcmp(name, NAMES[i]) == 0)
            return i;
    return -1;
}

void spots_load(void)
{
    nvs_handle_t h;
    bool have = nvs_open("spots", NVS_READONLY, &h) == ESP_OK;
    for (int i = 0; i < ZATT_NSPOTS; i++)
    {
        char s[32];
        size_t n = sizeof(s);
        const char *src = DEFAULTS[i];
        if (have && nvs_get_str(h, NAMES[i], s, &n) == ESP_OK)
            src = s;
        if (!zatt_rect_parse(src, &rects[i]))
        {
            ESP_LOGW(TAG, "%s: bad rectangle \"%s\", disabled", NAMES[i], src);
            rects[i] = zatt_rect_disabled();
        }
    }
    if (have)
        nvs_close(h);
}

zatt_rect_t spots_get(int i)
{
    return rects[i];
}

esp_err_t spots_set(int i, zatt_rect_t r)
{
    if (i < 0 || i >= ZATT_NSPOTS || (r.x0 >= 0 && !zatt_rect_valid(&r)))
        return ESP_ERR_INVALID_ARG;
    nvs_handle_t h;
    esp_err_t err = nvs_open("spots", NVS_READWRITE, &h);
    if (err != ESP_OK)
        return err;
    char s[32] = "";
    if (r.x0 >= 0)
        snprintf(s, sizeof(s), "%d,%d,%d,%d", r.x0, r.y0, r.x1, r.y1);
    err = nvs_set_str(h, NAMES[i], s);
    if (err == ESP_OK)
        err = nvs_commit(h);
    nvs_close(h);
    if (err == ESP_OK)
        rects[i] = r;
    return err;
}
