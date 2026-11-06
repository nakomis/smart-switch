// The provisioned settings. See prov.h.
#include "prov.h"

#include <stdlib.h>
#include <string.h>

#include "esp_err.h"
#include "esp_log.h"
#include "nvs.h"
#include "nvs_flash.h"

static const char *TAG = "prov";

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

static bool get_fixed(nvs_handle_t h, const char *key, char *out, size_t size, bool required)
{
    size_t len = size;
    esp_err_t err = nvs_get_str(h, key, out, &len);
    if (err != ESP_OK)
    {
        out[0] = 0;
        if (required)
            ESP_LOGE(TAG, "%s: %s", key, esp_err_to_name(err));
    }
    return err == ESP_OK;
}

static char *get_alloc(nvs_handle_t h, const char *key)
{
    size_t len = 0;
    esp_err_t err = nvs_get_str(h, key, NULL, &len);
    char *out = err == ESP_OK ? malloc(len) : NULL;
    if (out != NULL && nvs_get_str(h, key, out, &len) != ESP_OK)
    {
        free(out);
        out = NULL;
    }
    if (out == NULL)
        ESP_LOGE(TAG, "%s: %s", key, err == ESP_OK ? "out of memory" : esp_err_to_name(err));
    return out;
}

bool prov_load(prov_t *prov)
{
    memset(prov, 0, sizeof(*prov));
    nvs_handle_t h;
    esp_err_t err = open_prov(&h);
    if (err != ESP_OK)
    {
        ESP_LOGW(TAG, "not provisioned (%s)", esp_err_to_name(err));
        return false;
    }
    bool ok = get_fixed(h, "wifi_ssid", prov->wifi_ssid, sizeof(prov->wifi_ssid), true);
    ok = get_fixed(h, "wifi_pass", prov->wifi_pass, sizeof(prov->wifi_pass), true) && ok;
    ok = get_fixed(h, "endpoint", prov->endpoint, sizeof(prov->endpoint), true) && ok;
    ok = get_fixed(h, "thing", prov->thing, sizeof(prov->thing), true) && ok;
    prov->cert = get_alloc(h, "cert");
    prov->key = get_alloc(h, "key");
    // Optional: all three or none.
    bool metrics = get_fixed(h, "metrics_url", prov->metrics_url, sizeof(prov->metrics_url), false);
    metrics = get_fixed(h, "metrics_user", prov->metrics_user, sizeof(prov->metrics_user), false) && metrics;
    metrics = get_fixed(h, "metrics_pass", prov->metrics_pass, sizeof(prov->metrics_pass), false) && metrics;
    nvs_close(h);
    if (!metrics)
    {
        prov->metrics_url[0] = prov->metrics_user[0] = prov->metrics_pass[0] = 0;
        ESP_LOGI(TAG, "no metrics in prov: metrics off");
    }
    if (!ok || prov->cert == NULL || prov->key == NULL)
    {
        free(prov->cert);
        free(prov->key);
        memset(prov, 0, sizeof(*prov));
        ESP_LOGW(TAG, "incomplete provisioning: no network");
        return false;
    }
    ESP_LOGI(TAG, "provisioned as %s", prov->thing);
    return true;
}
