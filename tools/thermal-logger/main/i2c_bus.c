#include "esp_log.h"
#include "sdkconfig.h"
#include "zatt.h"

static const char *TAG = "i2c";
static i2c_master_bus_handle_t bus;

esp_err_t i2c_bus_start(void)
{
    i2c_master_bus_config_t cfg = {
        .i2c_port = I2C_NUM_0,
        .sda_io_num = CONFIG_ZATT_I2C_SDA_GPIO,
        .scl_io_num = CONFIG_ZATT_I2C_SCL_GPIO,
        .clk_source = I2C_CLK_SRC_DEFAULT,
        .glitch_ignore_cnt = 7,
        // Most breakouts carry their own pull-ups; the internal ones (~45k) only help a bare line.
        .flags.enable_internal_pullup = true,
    };
    esp_err_t err = i2c_new_master_bus(&cfg, &bus);
    if (err == ESP_OK)
        ESP_LOGI(TAG, "SDA GPIO%d SCL GPIO%d at %d Hz", CONFIG_ZATT_I2C_SDA_GPIO, CONFIG_ZATT_I2C_SCL_GPIO,
                 CONFIG_ZATT_I2C_FREQ_HZ);
    return err;
}

i2c_master_bus_handle_t i2c_bus(void)
{
    return bus;
}
