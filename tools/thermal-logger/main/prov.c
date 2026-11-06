// Reads Wi-Fi, metrics and HTTP-token settings from the "prov" NVS partition, namespace "zatt".
// Nothing secret is in the image: scripts/provision.sh writes the partition.
#include <string.h>

#include "esp_log.h"
#include "nvs.h"
#include "nvs_flash.h"
#include "zatt.h"

static const char *TAG = "prov";

static void get(nvs_handle_t h, const char *key, char *out, size_t cap)
{
    size_t n = cap;
    out[0] = 0;
    if (nvs_get_str(h, key, out, &n) != ESP_OK)
        out[0] = 0;
}

void prov_load(prov_t *p)
{
    memset(p, 0, sizeof(*p));
    esp_err_t err = nvs_flash_init_partition("prov");
    if (err == ESP_ERR_NVS_NO_FREE_PAGES || err == ESP_ERR_NVS_NEW_VERSION_FOUND)
    {
        // An unprovisioned (blank) partition: initialising it just formats it. Provision it next.
        nvs_flash_erase_partition("prov");
        err = nvs_flash_init_partition("prov");
    }
    nvs_handle_t h;
    if (err != ESP_OK || nvs_open_from_partition("prov", "zatt", NVS_READONLY, &h) != ESP_OK)
    {
        ESP_LOGE(TAG, "no prov settings: run scripts/provision.sh");
        return;
    }
    get(h, "wifi_ssid", p->wifi_ssid, sizeof(p->wifi_ssid));
    get(h, "wifi_pass", p->wifi_pass, sizeof(p->wifi_pass));
    get(h, "metrics_url", p->metrics_url, sizeof(p->metrics_url));
    get(h, "metrics_user", p->metrics_user, sizeof(p->metrics_user));
    get(h, "metrics_pass", p->metrics_pass, sizeof(p->metrics_pass));
    get(h, "http_token", p->http_token, sizeof(p->http_token));
    nvs_close(h);
    p->ok = p->wifi_ssid[0] != 0;
    ESP_LOGI(TAG, "wifi %s, metrics %s, POST token %s", p->wifi_ssid[0] ? "set" : "MISSING",
             p->metrics_url[0] ? "set" : "off", p->http_token[0] ? "set" : "MISSING (POST /spots disabled)");
}
