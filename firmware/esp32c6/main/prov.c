// The provisioned settings. See prov.h.
#include "prov.h"

#include "esp_err.h"
#include "nvs.h"
#include "nvs_flash.h"

const char *const PROV_KEYS[] = {
    "wifi_ssid", "wifi_pass", "endpoint", "thing", "cert", "key",
    "metrics_url", "metrics_user", "metrics_pass",
};
const size_t PROV_KEY_COUNT = sizeof(PROV_KEYS) / sizeof(PROV_KEYS[0]);

_Static_assert(sizeof(PROV_KEYS) / sizeof(PROV_KEYS[0]) <= 16, "prov_state_t.present is too small");

static esp_err_t open_prov(nvs_handle_t *h)
{
    static bool initialised;
    if (!initialised)
    {
        esp_err_t err = nvs_flash_init_partition(PROV_PARTITION);
        if (err != ESP_OK)
            return err;
        initialised = true;
    }
    return nvs_open_from_partition(PROV_PARTITION, PROV_NAMESPACE, NVS_READONLY, h);
}

void prov_state(prov_state_t *state)
{
    *state = (prov_state_t){0};
    nvs_handle_t h;
    esp_err_t err = open_prov(&h);
    if (err != ESP_OK)
    {
        state->error = esp_err_to_name(err);
        return;
    }
    state->opened = true;
    for (size_t i = 0; i < PROV_KEY_COUNT; i++)
    {
        nvs_type_t type;
        state->present[i] = nvs_find_key(h, PROV_KEYS[i], &type) == ESP_OK;
    }
    nvs_close(h);
}

bool prov_get_str(const char *key, char *out, size_t out_len)
{
    nvs_handle_t h;
    if (open_prov(&h) != ESP_OK)
        return false;
    size_t len = out_len;
    esp_err_t err = nvs_get_str(h, key, out, &len);
    nvs_close(h);
    return err == ESP_OK;
}
