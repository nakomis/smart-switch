// Zatt, the thermal logger for Petro's Gate 4 soak test (PETRO-7). See ../README.md.
#include "esp_log.h"
#include "nvs_flash.h"
#include "zatt.h"

static const char *TAG = "zatt";

void app_main(void)
{
    esp_err_t err = nvs_flash_init();  // the default partition: spot rectangles
    if (err == ESP_ERR_NVS_NO_FREE_PAGES || err == ESP_ERR_NVS_NEW_VERSION_FOUND)
    {
        ESP_ERROR_CHECK(nvs_flash_erase());
        err = nvs_flash_init();
    }
    ESP_ERROR_CHECK(err);

    static prov_t prov;  // outlives app_main: the web and metrics tasks keep pointers into it
    prov_load(&prov);
    spots_load();

    if (i2c_bus_start() != ESP_OK)
        ESP_LOGE(TAG, "I2C bus failed to start");
    else
        sensors_start();

    if (!prov.ok)
        return;  // unprovisioned: the sensors still log to the console, but nothing needs the network
    wifi_start(&prov);
    web_start(&prov);
    metrics_start(&prov);
}
