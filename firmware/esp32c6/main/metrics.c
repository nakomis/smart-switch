// The VictoriaMetrics push (as tinycrypt's metrics.c, in Prometheus text). See metrics.h.
#include "metrics.h"

#include <stdio.h>
#include <string.h>

#include "app.h"
#include "esp_crt_bundle.h"
#include "esp_http_client.h"
#include "esp_log.h"
#include "esp_timer.h"
#include "esp_wifi.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "mbedtls/base64.h"
#include "net.h"
#include "ota.h"
#include "prom.h"
#include "store.h"

static const char *TAG = "metrics";

#define TIMEOUT_MS 3000
#define BODY_MAX 1024

static char url[sizeof(((prov_t *)0)->metrics_url) + sizeof(PROM_PATH)];
static char auth[8 + 4 * ((sizeof(((prov_t *)0)->metrics_user) + sizeof(((prov_t *)0)->metrics_pass) + 2) / 3) + 1];

static bool post(const char *body, int len, int *status)
{
    esp_http_client_config_t cfg = {
        .url = url,
        .method = HTTP_METHOD_POST,
        .timeout_ms = TIMEOUT_MS,
        .disable_auto_redirect = true,  // the credential goes to vmauth and nowhere else
        .buffer_size = 512,
        .buffer_size_tx = 512,
        .crt_bundle_attach = strncmp(url, "https://", 8) == 0 ? esp_crt_bundle_attach : NULL,
    };
    esp_http_client_handle_t client = esp_http_client_init(&cfg);
    if (client == NULL)
        return false;
    esp_http_client_set_header(client, "Content-Type", "text/plain");
    if (auth[0])
        esp_http_client_set_header(client, "Authorization", auth);
    esp_http_client_set_post_field(client, body, len);
    esp_err_t err = esp_http_client_perform(client);
    *status = err == ESP_OK ? esp_http_client_get_status_code(client) : -1;
    esp_http_client_cleanup(client);
    return err == ESP_OK && *status / 100 == 2;
}

static int format(char *body, size_t cap)
{
    app_state s;
    app_get_state(&s);
    wifi_ap_record_t ap;
    bool have_rssi = esp_wifi_sta_get_ap_info(&ap) == ESP_OK;
    prom_sample p = {
        .have_meter = s.have_meter,
        .volts = s.volts,
        .amps = s.amps,
        .watts = s.watts,
        .energy_kwh = s.energy_kwh,
        .have_temp = s.have_temp,
        .board_c = s.board_c,
        .relay = s.relay,
        .have_zx = s.have_zx,
        .zx_hz = s.zx_hz,
        .have_rssi = have_rssi,
        .rssi = have_rssi ? ap.rssi : 0,
        .uptime_s = (uint32_t)(esp_timer_get_time() / 1000000),
        .reset_names = store_reset_names(),
        .reset_counts = store_reset_counts(),
        .resets = STORE_RESET_REASONS,
        .trips_overcurrent = store_trips(CTL_TRIP_OVERCURRENT),
        .trips_overcurrent_instant = store_trips(CTL_TRIP_OVERCURRENT_INSTANT),
        .trips_overtemp = store_trips(CTL_TRIP_OVERTEMP),
        .trips_meter_fault = store_trips(CTL_TRIP_METER_FAULT),
    };
    return prom_format(body, cap, &p);
}

static void metrics_task(void *arg)
{
    (void)arg;
    static char body[BODY_MAX];
    bool failing = false;
    TickType_t last = xTaskGetTickCount();
    for (;;)
    {
        vTaskDelayUntil(&last, pdMS_TO_TICKS(METRICS_INTERVAL_MS));
        if (!net_wifi_up() || ota_busy())
            continue;
        int len = format(body, sizeof(body));
        int status = 0;
        if (len < 0)
            ESP_LOGE(TAG, "metrics don't fit %u bytes", (unsigned)sizeof(body));
        else if (post(body, len, &status))
        {
            if (failing)
                ESP_LOGI(TAG, "pushing again");
            failing = false;
        }
        else if (!failing)
        {
            failing = true;  // once per run of failures: Cal reboots, and that's fine
            ESP_LOGW(TAG, "POST %s failed (HTTP %d); dropping metrics until it works", url, status);
        }
    }
}

void metrics_start(const prov_t *p)
{
    if (p == NULL || p->metrics_url[0] == 0)
    {
        ESP_LOGI(TAG, "no metrics in prov: metrics off");
        return;
    }
    if (!prom_url(p->metrics_url, url, sizeof(url)))
    {
        ESP_LOGE(TAG, "metrics_url isn't an http(s) URL: metrics off");
        return;
    }
    auth[0] = 0;
    if (p->metrics_user[0])
    {
        char creds[sizeof(p->metrics_user) + sizeof(p->metrics_pass) + 1];
        int n = snprintf(creds, sizeof(creds), "%s:%s", p->metrics_user, p->metrics_pass);
        size_t olen = 0;
        memcpy(auth, "Basic ", 6);
        if (n < 0 || mbedtls_base64_encode((unsigned char *)auth + 6, sizeof(auth) - 6, &olen,
                                           (const unsigned char *)creds, (size_t)n) != 0)
            auth[0] = 0;
        memset(creds, 0, sizeof(creds));
    }
    if (xTaskCreate(metrics_task, "metrics", 6144, NULL, tskIDLE_PRIORITY + 2, NULL) != pdPASS)
        ESP_LOGW(TAG, "no memory for the metrics task: metrics off");
    else
        ESP_LOGI(TAG, "metrics every %d s to %s as %s", METRICS_INTERVAL_MS / 1000, url,
                 p->metrics_user[0] ? p->metrics_user : "(no user)");
}
