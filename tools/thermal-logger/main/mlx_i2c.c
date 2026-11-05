// The I2C glue Melexis' MLX90640_API.c calls (MLX90640_I2C_Driver.h), on IDF's i2c_master driver.
// Addresses and data are 16-bit big-endian words, as the sensor sends them.
#include <stdlib.h>

#include "MLX90640_I2C_Driver.h"
#include "esp_log.h"
#include "sdkconfig.h"
#include "zatt.h"

static const char *TAG = "mlx_i2c";
#define MLX_ADDR 0x33
#define TIMEOUT_MS 200

static i2c_master_dev_handle_t dev;
static int freq = CONFIG_ZATT_I2C_FREQ_HZ;

void MLX90640_I2CInit(void)
{
    if (dev)
        return;
    i2c_device_config_t cfg = {
        .dev_addr_length = I2C_ADDR_BIT_LEN_7,
        .device_address = MLX_ADDR,
        .scl_speed_hz = freq,
    };
    ESP_ERROR_CHECK(i2c_master_bus_add_device(i2c_bus(), &cfg, &dev));
}

int MLX90640_I2CGeneralReset(void)
{
    // I2C general call, reset (0x06). Not used by the logger; here for completeness.
    return 0;
}

int MLX90640_I2CRead(uint8_t slaveAddr, uint16_t startAddress, uint16_t nMemAddressRead, uint16_t *data)
{
    (void)slaveAddr;  // one MLX90640 on the bus, at 0x33
    if (dev == NULL)
        return -1;
    uint8_t cmd[2] = {startAddress >> 8, startAddress & 0xFF};
    size_t n = (size_t)nMemAddressRead * 2;
    uint8_t *raw = malloc(n);
    if (raw == NULL)
        return -1;
    esp_err_t err = i2c_master_transmit_receive(dev, cmd, 2, raw, n, TIMEOUT_MS);
    if (err == ESP_OK)
        for (size_t i = 0; i < nMemAddressRead; i++)
            data[i] = (uint16_t)(raw[2 * i] << 8 | raw[2 * i + 1]);
    else
        ESP_LOGD(TAG, "read 0x%04x x%u: %s", startAddress, nMemAddressRead, esp_err_to_name(err));
    free(raw);
    return err == ESP_OK ? 0 : -1;
}

int MLX90640_I2CWrite(uint8_t slaveAddr, uint16_t writeAddress, uint16_t data)
{
    (void)slaveAddr;
    if (dev == NULL)
        return -1;
    uint8_t buf[4] = {writeAddress >> 8, writeAddress & 0xFF, data >> 8, data & 0xFF};
    esp_err_t err = i2c_master_transmit(dev, buf, sizeof(buf), TIMEOUT_MS);
    if (err != ESP_OK)
        ESP_LOGD(TAG, "write 0x%04x: %s", writeAddress, esp_err_to_name(err));
    return err == ESP_OK ? 0 : -1;
}

void MLX90640_I2CFreqSet(int f)
{
    // The API's callers pass kHz (as in Melexis' Arduino/RPi ports); the bus speed is fixed at
    // device-add time here (CONFIG_ZATT_I2C_FREQ_HZ), so this only records it.
    freq = f;
}
