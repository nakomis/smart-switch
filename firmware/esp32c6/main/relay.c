// The relay, switched at zero crossings. See relay.h.
#include "relay.h"

#include "board.h"
#include "esp_log.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "sdkconfig.h"
#include "zx.h"

static const char *TAG = "relay";

#ifdef CONFIG_PETRO_ZX_SWITCHING
#define OPERATE_US CONFIG_PETRO_RELAY_OPERATE_US
#define RELEASE_US CONFIG_PETRO_RELAY_RELEASE_US
#endif

static esp_timer_handle_t timer;
static portMUX_TYPE mux = portMUX_INITIALIZER_UNLOCKED;
static bool target;  // under mux
static uint32_t timed, at_once;

// The esp_timer task (priority 22, above every task of ours): the latest target, whatever it is now.
static void on_timer(void *arg)
{
    (void)arg;
    portENTER_CRITICAL(&mux);
    bool on = target;
    portEXIT_CRITICAL(&mux);
    board_relay(on);
}

esp_err_t relay_init(void)
{
    const esp_timer_create_args_t args = {
        .callback = on_timer,
        .dispatch_method = ESP_TIMER_TASK,
        .name = "relay",
    };
    return esp_timer_create(&args, &timer);
}

bool relay_zx_sync(void)
{
#ifdef CONFIG_PETRO_ZX_SWITCHING
    zx_edges z;
    board_zx_snapshot(&z);
    return zx_period_us(&z, esp_timer_get_time()) != 0;
#else
    return false;
#endif
}

void relay_set(bool on, bool immediate)
{
    portENTER_CRITICAL(&mux);
    target = on;
    portEXIT_CRITICAL(&mux);
    if (timer != NULL)
        esp_timer_stop(timer);  // ESP_ERR_INVALID_STATE if none was pending: fine

    int64_t delay_us = -1;
#ifdef CONFIG_PETRO_ZX_SWITCHING
    if (!immediate && timer != NULL)
    {
        zx_edges z;
        board_zx_snapshot(&z);
        int64_t now = esp_timer_get_time();
        int64_t at = zx_switch_at(&z, now, on ? OPERATE_US : RELEASE_US);
        if (at >= 0)
            delay_us = at - now;
    }
#else
    (void)immediate;
#endif
    if (delay_us > 0 && esp_timer_start_once(timer, (uint64_t)delay_us) == ESP_OK)
    {
        timed++;
        return;
    }
    if (delay_us > 0)
        ESP_LOGW(TAG, "timer didn't start: switching at once");
    board_relay(on);
    at_once++;
}

void relay_counts(uint32_t *t, uint32_t *a)
{
    *t = timed;
    *a = at_once;
}
