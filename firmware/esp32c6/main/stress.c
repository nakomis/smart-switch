// Wi-Fi transmit stress. See stress.h.
#include "stress.h"

#include <string.h>

#include "esp_log.h"
#include "esp_netif.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "lwip/sockets.h"
#include "net.h"
#include "ota.h"

static const char *TAG = "stress";

#define PAYLOAD 1400
#define DISCARD_PORT 9

static portMUX_TYPE lock = portMUX_INITIALIZER_UNLOCKED;
static int64_t until_us;  // 0: off
static TaskHandle_t task;

static bool active(void)
{
    taskENTER_CRITICAL(&lock);
    int64_t until = until_us;
    taskEXIT_CRITICAL(&lock);
    if (until == 0)
        return false;
    if (esp_timer_get_time() < until)
        return true;
    stress_stop();
    ESP_LOGI(TAG, "Wi-Fi stress finished");
    return false;
}

// The gateway's address, or false while there isn't one.
static bool gateway(struct sockaddr_in *to)
{
    esp_netif_t *sta = esp_netif_get_handle_from_ifkey("WIFI_STA_DEF");
    esp_netif_ip_info_t ip;
    if (sta == NULL || esp_netif_get_ip_info(sta, &ip) != ESP_OK || ip.gw.addr == 0)
        return false;
    memset(to, 0, sizeof(*to));
    to->sin_family = AF_INET;
    to->sin_port = htons(DISCARD_PORT);
    to->sin_addr.s_addr = ip.gw.addr;
    return true;
}

static void stress_task(void *arg)
{
    (void)arg;
    static uint8_t payload[PAYLOAD];
    memset(payload, 0x5a, sizeof(payload));
    int sock = -1;
    uint32_t sent = 0;
    for (;;)
    {
        if (!active())
        {
            if (sock >= 0)
            {
                close(sock);
                sock = -1;
                ESP_LOGI(TAG, "stopped after %lu datagrams", (unsigned long)sent);
            }
            ulTaskNotifyTake(pdTRUE, portMAX_DELAY);
            sent = 0;
            continue;
        }
        struct sockaddr_in to;
        if (!net_wifi_up() || ota_busy() || !gateway(&to))
        {
            vTaskDelay(pdMS_TO_TICKS(500));
            continue;
        }
        if (sock < 0 && (sock = socket(AF_INET, SOCK_DGRAM, IPPROTO_UDP)) < 0)
        {
            vTaskDelay(pdMS_TO_TICKS(1000));
            continue;
        }
        if (sendto(sock, payload, sizeof(payload), 0, (struct sockaddr *)&to, sizeof(to)) > 0)
            sent++;
        else
            vTaskDelay(pdMS_TO_TICKS(2));  // out of buffers: let the radio catch up
        vTaskDelay(1);  // every packet: the idle task (watched by the task watchdog) must run
    }
}

bool stress_start(uint32_t duration_s)
{
    if (task == NULL && xTaskCreate(stress_task, "stress", 3072, NULL, tskIDLE_PRIORITY + 1, &task) != pdPASS)
    {
        task = NULL;
        return false;
    }
    taskENTER_CRITICAL(&lock);
    until_us = esp_timer_get_time() + (int64_t)duration_s * 1000000;
    taskEXIT_CRITICAL(&lock);
    xTaskNotifyGive(task);
    ESP_LOGI(TAG, "Wi-Fi stress on for %lu s", (unsigned long)duration_s);
    return true;
}

void stress_stop(void)
{
    taskENTER_CRITICAL(&lock);
    until_us = 0;
    taskEXIT_CRITICAL(&lock);
}

uint32_t stress_left_s(void)
{
    taskENTER_CRITICAL(&lock);
    int64_t until = until_us;
    taskEXIT_CRITICAL(&lock);
    int64_t left = until - esp_timer_get_time();
    return until == 0 || left <= 0 ? 0 : (uint32_t)((left + 999999) / 1000000);
}
