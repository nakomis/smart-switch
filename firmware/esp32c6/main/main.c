// Petro: PETRO-3 slice 1, the bench console for Gate 2. The relay is off at boot and only the
// console drives it.
//
// TODO(PETRO-3 slice 3): the mode state machine (on -> off -> auto on SW1, persisted in NVS as the
// power-on state), the LED's status patterns, Wi-Fi join from prov, Fleet over MQTT
// (petro/<thing>/{commands,responses,status}), OTA with rollback, and the VictoriaMetrics push.
#include "board.h"
#include "console.h"
#include "esp_log.h"
#include "nvs_flash.h"

static const char *TAG = "petro";

void app_main(void)
{
    // The relay first: board_init latches it low before touching anything else.
    esp_err_t err = board_init();
    if (err != ESP_OK)
        ESP_LOGE(TAG, "board init: %s (the console still starts)", esp_err_to_name(err));

    // The default nvs partition, for Wi-Fi's calibration data. (prov is opened separately,
    // read-only.)
    err = nvs_flash_init();
    if (err == ESP_ERR_NVS_NO_FREE_PAGES || err == ESP_ERR_NVS_NEW_VERSION_FOUND)
    {
        ESP_ERROR_CHECK(nvs_flash_erase());
        err = nvs_flash_init();
    }
    ESP_ERROR_CHECK(err);

    ESP_ERROR_CHECK(console_start());
    ESP_LOGI(TAG, "console ready on USB: type help");
}
