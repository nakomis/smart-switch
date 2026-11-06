// Petro: the application starts here. Boot order: the relay latched off (board_init), NVS, OTA
// probation, the stored state (mode, energy, reset counters), the control and meter tasks (relay on
// only if the stored mode is on), the network (if provisioned), then the USB console.
#include <stdlib.h>

#include "app.h"
#include "board.h"
#include "console.h"
#include "esp_app_desc.h"
#include "esp_log.h"
#include "esp_ota_ops.h"
#include "metrics.h"
#include "net.h"
#include "nvs_flash.h"
#include "ota.h"
#include "prov.h"
#include "store.h"

static const char *TAG = "petro";

static prov_t prov;

// A new image from an update that can't get going goes back to the old one.
static void roll_back_if_new(void)
{
    esp_ota_img_states_t state;
    if (esp_ota_get_state_partition(esp_ota_get_running_partition(), &state) == ESP_OK &&
        state == ESP_OTA_IMG_PENDING_VERIFY)
        esp_ota_mark_app_invalid_rollback_and_reboot();
}

void app_main(void)
{
    // The relay first: board_init latches it low before touching anything else.
    esp_err_t err = board_init();
    if (err != ESP_OK)
        ESP_LOGE(TAG, "board init: %s (carrying on)", esp_err_to_name(err));
    const esp_app_desc_t *desc = esp_app_get_description();
    ESP_LOGI(TAG, "%s %s", desc->project_name, desc->version);

    // The default nvs partition: the mode, the energy total, the counters and OTA's bookkeeping.
    // A full or old-format partition is erased (a new image first goes back to the old one, which
    // can read it): the mode is then off, the safe power-on state, and the counters start again.
    err = nvs_flash_init();
    if (err == ESP_ERR_NVS_NO_FREE_PAGES || err == ESP_ERR_NVS_NEW_VERSION_FOUND)
    {
        roll_back_if_new();
        ESP_LOGE(TAG, "nvs unusable (%s): erasing it", esp_err_to_name(err));
        err = nvs_flash_erase();
        if (err == ESP_OK)
            err = nvs_flash_init();
    }
    if (err != ESP_OK)
    {
        ESP_LOGE(TAG, "nvs: %s", esp_err_to_name(err));
        roll_back_if_new();
        abort();  // a restart leaves the relay off
    }

    ota_boot();
    store_init();
    bool provisioned = prov_load(&prov);
    app_start(provisioned);

    if (provisioned)
    {
        if (net_start(&prov, app_on_command))
            metrics_start(&prov);
    }
    else
        ESP_LOGW(TAG, "not provisioned: console only (the button and relay still work)");

    ESP_ERROR_CHECK(console_start());
    ESP_LOGI(TAG, "console ready on USB: type help");
}
