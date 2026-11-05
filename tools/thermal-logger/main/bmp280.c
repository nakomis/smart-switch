// BMP280 on the shared I2C bus: temperature x2, pressure x4, IIR 4, normal mode at 500 ms standby.
// Compensation is in components/zatt_core/bmp280_calc.c. A BME280 (id 0x60) works for these two.
#include "bmp280_calc.h"
#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "sdkconfig.h"
#include "zatt.h"

static const char *TAG = "bmp280";
static i2c_master_dev_handle_t dev;
static bmp280_calib_t calib;

static esp_err_t rd(uint8_t reg, uint8_t *out, size_t n)
{
    return i2c_master_transmit_receive(dev, &reg, 1, out, n, 100);
}

static esp_err_t wr(uint8_t reg, uint8_t v)
{
    uint8_t b[2] = {reg, v};
    return i2c_master_transmit(dev, b, 2, 100);
}

esp_err_t bmp280_start(void)
{
    for (uint8_t addr = 0x76; addr <= 0x77; addr++)
    {
        if (i2c_master_probe(i2c_bus(), addr, 50) != ESP_OK)
            continue;
        i2c_device_config_t cfg = {
            .dev_addr_length = I2C_ADDR_BIT_LEN_7,
            .device_address = addr,
            .scl_speed_hz = CONFIG_ZATT_I2C_FREQ_HZ,
        };
        if (i2c_master_bus_add_device(i2c_bus(), &cfg, &dev) != ESP_OK)
            return ESP_FAIL;
        uint8_t id = 0, raw[24];
        if (rd(0xD0, &id, 1) != ESP_OK || (id != 0x56 && id != 0x57 && id != 0x58 && id != 0x60))
        {
            ESP_LOGW(TAG, "0x%02x answers with id 0x%02x, not a BMP280", addr, id);
            i2c_master_bus_rm_device(dev);
            dev = NULL;
            continue;
        }
        if (rd(0x88, raw, 24) != ESP_OK)
            return ESP_FAIL;
        bmp280_calib_parse(raw, &calib);
        wr(0xE0, 0xB6);  // soft reset
        vTaskDelay(pdMS_TO_TICKS(5));
        wr(0xF5, 0x88);  // standby 500 ms, filter 4
        wr(0xF4, 0x4F);  // temperature x2, pressure x4, normal mode
        ESP_LOGI(TAG, "found at 0x%02x (id 0x%02x)", addr, id);
        return ESP_OK;
    }
    return ESP_ERR_NOT_FOUND;
}

esp_err_t bmp280_read(float *temp_c, float *pressure_pa)
{
    if (dev == NULL)
        return ESP_ERR_INVALID_STATE;
    uint8_t d[6];
    esp_err_t err = rd(0xF7, d, 6);
    if (err != ESP_OK)
        return err;
    int32_t adc_p = (int32_t)d[0] << 12 | d[1] << 4 | d[2] >> 4;
    int32_t adc_t = (int32_t)d[3] << 12 | d[4] << 4 | d[5] >> 4;
    if (adc_t == 0x80000 || adc_p == 0x80000)  // skipped / not yet measured
        return ESP_ERR_NOT_FINISHED;
    return bmp280_compensate(&calib, adc_t, adc_p, temp_c, pressure_pa) ? ESP_OK : ESP_ERR_INVALID_RESPONSE;
}
