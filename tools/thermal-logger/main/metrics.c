// Metrics to the house VictoriaMetrics, through vmauth on Cal: Prometheus text POSTed to
// <metrics_url>/api/v1/import/prometheus every CONFIG_ZATT_PUSH_INTERVAL_S, plain HTTP with basic
// auth (no TLS on the LAN, house rule). vmauth pins the host_name label to the user, so the
// credentials can only write as zatt-prod-zatt. A failed push is dropped, not retried; one log line
// per run of failures.
#include <math.h>
#include <stdio.h>
#include <string.h>

#include "esp_http_client.h"
#include "esp_log.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "mbedtls/base64.h"
#include "prom.h"
#include "sdkconfig.h"
#include "zatt.h"

static const char *TAG = "metrics";

#define TIMEOUT_MS 4000

static char url[160];
static char auth[8 + 4 * ((33 + 65 + 2) / 3) + 1];
static char body[3072];
static zatt_snapshot_t snap;

static bool post(int len, int *status)
{
    esp_http_client_config_t cfg = {
        .url = url,
        .method = HTTP_METHOD_POST,
        .timeout_ms = TIMEOUT_MS,
        .disable_auto_redirect = true,  // the credential goes to vmauth and nowhere else
    };
    esp_http_client_handle_t c = esp_http_client_init(&cfg);
    if (c == NULL)
        return false;
    esp_http_client_set_header(c, "Content-Type", "text/plain");
    if (auth[0])
        esp_http_client_set_header(c, "Authorization", auth);
    esp_http_client_set_post_field(c, body, len);
    esp_err_t err = esp_http_client_perform(c);
    *status = err == ESP_OK ? esp_http_client_get_status_code(c) : -1;
    esp_http_client_cleanup(c);
    return err == ESP_OK && *status / 100 == 2;
}

static int build(void)
{
    prom_buf_t p;
    prom_init(&p, body, sizeof(body));
    sensors_snapshot(&snap);
    zatt_frame_stats_t fs;
    if (snap.frames > 0 && zatt_frame_stats(snap.to, &fs))
    {
        prom_gauge(&p, "zatt_frame_max_celsius", NULL, NULL, fs.max);
        prom_gauge(&p, "zatt_frame_min_celsius", NULL, NULL, fs.min);
        prom_gauge(&p, "zatt_frame_mean_celsius", NULL, NULL, fs.mean);
        prom_gauge(&p, "zatt_hot_x", NULL, NULL, fs.hot_x);
        prom_gauge(&p, "zatt_hot_y", NULL, NULL, fs.hot_y);
        for (int i = 0; i < ZATT_NSPOTS; i++)
        {
            zatt_rect_t r = spots_get(i);
            float mean, max;
            if (zatt_rect_stats(snap.to, &r, &mean, &max))
            {
                prom_gauge(&p, "zatt_spot_celsius", "spot", spots_name(i), mean);
                prom_gauge(&p, "zatt_spot_max_celsius", "spot", spots_name(i), max);
            }
        }
        prom_gauge(&p, "zatt_ambient_celsius", NULL, NULL, snap.ta);
    }
    prom_gauge(&p, "zatt_air_celsius", NULL, NULL, snap.air);
    prom_gauge(&p, "zatt_pressure_pascals", NULL, NULL, snap.pressure);
    float v;
    if (battery_volts(&v))
        prom_gauge(&p, "zatt_battery_volts", NULL, NULL, v);
    prom_gauge(&p, "zatt_wifi_rssi_dbm", NULL, NULL, wifi_rssi());
    prom_gauge(&p, "zatt_uptime_seconds", NULL, NULL, (double)(esp_timer_get_time() / 1000000));
    return prom_finish(&p);
}

static void metrics_task(void *arg)
{
    (void)arg;
    bool failing = false;
    for (;;)
    {
        vTaskDelay(pdMS_TO_TICKS(CONFIG_ZATT_PUSH_INTERVAL_S * 1000));
        if (!wifi_connected())
            continue;
        int len = build(), status = 0;
        if (len < 0)
            ESP_LOGE(TAG, "metrics text didn't fit");
        else if (post(len, &status))
        {
            if (failing)
                ESP_LOGI(TAG, "pushing again");
            failing = false;
        }
        else if (!failing)
        {
            failing = true;
            ESP_LOGW(TAG, "POST %s failed (HTTP %d); dropping metrics until it works", url, status);
        }
    }
}

void metrics_start(const prov_t *p)
{
    if (p->metrics_url[0] == 0)
    {
        ESP_LOGI(TAG, "no metrics_url in prov: metrics off");
        return;
    }
    snprintf(url, sizeof(url), "%s/api/v1/import/prometheus", p->metrics_url);
    auth[0] = 0;
    if (p->metrics_user[0])
    {
        char creds[33 + 65 + 2];
        int n = snprintf(creds, sizeof(creds), "%s:%s", p->metrics_user, p->metrics_pass);
        size_t olen = 0;
        memcpy(auth, "Basic ", 6);
        if (mbedtls_base64_encode((unsigned char *)auth + 6, sizeof(auth) - 6, &olen, (unsigned char *)creds, n) != 0)
            auth[0] = 0;
        memset(creds, 0, sizeof(creds));
    }
    xTaskCreate(metrics_task, "metrics", 6144, NULL, tskIDLE_PRIORITY + 2, NULL);
    ESP_LOGI(TAG, "pushing every %d s to %s as %s", CONFIG_ZATT_PUSH_INTERVAL_S, url,
             p->metrics_user[0] ? p->metrics_user : "(no user)");
}
