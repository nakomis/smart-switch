// The sensor task: owns the I2C bus, reads the MLX90640 in chess mode at 2 Hz (both subpages per
// frame), the BMP280 once per frame, and keeps the latest result for the metrics and web tasks.
//
// The MLX90640's EEPROM is read and its calibration parameters extracted once at start. Each
// subpage then goes through Melexis' CalculateTo, which fills only that subpage's pixels (the
// chess pattern) of the 768-float frame, so the frame is only whole after both.
#include <math.h>
#include <string.h>

#include "MLX90640_API.h"
#include "MLX90640_I2C_Driver.h"
#include "esp_log.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/semphr.h"
#include "freertos/task.h"
#include "sdkconfig.h"
#include "zatt.h"

static const char *TAG = "sensors";

#define MLX_ADDR 0x33
#define REFRESH_2HZ 0x02
#define MODE_CHESS 1  // MLX90640_GetCurMode's value for chess, for BadPixelsCorrection

static paramsMLX90640 params;
static uint16_t ee[MLX90640_EEPROM_DUMP_NUM];
static uint16_t frame_data[MLX90640_PIXEL_NUM + MLX90640_AUX_NUM + 2];
static float to[ZATT_PIXELS];

static zatt_snapshot_t snap;
static SemaphoreHandle_t lock;

static bool mlx_init(void)
{
    MLX90640_I2CInit();
    int r = MLX90640_DumpEE(MLX_ADDR, ee);
    if (r != MLX90640_NO_ERROR)
    {
        ESP_LOGE(TAG, "MLX90640 EEPROM read failed (%d): wiring, address 0x33, power?", r);
        return false;
    }
    r = MLX90640_ExtractParameters(ee, &params);
    if (r != MLX90640_NO_ERROR)
    {
        ESP_LOGE(TAG, "MLX90640 parameters (%d): too many bad pixels, or a corrupt EEPROM read", r);
        return false;
    }
    // The vendor's recommended order: chess mode, rate, then the default 18-bit resolution.
    if (MLX90640_SetChessMode(MLX_ADDR) != 0 || MLX90640_SetRefreshRate(MLX_ADDR, REFRESH_2HZ) != 0)
    {
        ESP_LOGE(TAG, "MLX90640 mode or refresh rate not accepted");
        return false;
    }
    ESP_LOGI(TAG, "MLX90640 ready: chess mode, 2 Hz, emissivity %d%%", CONFIG_ZATT_EMISSIVITY_PERCENT);
    return true;
}

static void sensors_task(void *arg)
{
    (void)arg;
    bool mlx_ok = false;
    bool bmp_ok = bmp280_start() == ESP_OK;
    if (!bmp_ok)
        ESP_LOGW(TAG, "no BMP280 (air temperature and pressure will be missing)");
    uint32_t fails = 0;

    for (;;)
    {
        if (!mlx_ok)
        {
            mlx_ok = mlx_init();
            if (!mlx_ok)
            {
                vTaskDelay(pdMS_TO_TICKS(5000));
                continue;
            }
        }
        float ta = NAN;
        bool both = true;
        unsigned seen = 0;  // bit per subpage read
        for (int tries = 0; seen != 3 && tries < 6; tries++)
        {
            int sp = MLX90640_GetFrameData(MLX_ADDR, frame_data);
            if (sp < 0)
            {
                both = false;
                break;
            }
            if (sp > 1)
                continue;
            seen |= 1u << sp;
            ta = MLX90640_GetTa(frame_data, &params);
            float tr = ta - CONFIG_ZATT_REFLECTED_SHIFT_C;
            MLX90640_CalculateTo(frame_data, &params, CONFIG_ZATT_EMISSIVITY_PERCENT / 100.0f, tr, to);
        }
        if (both && seen != 3)
            both = false;  // never saw both subpages: don't publish a half frame
        if (both)
        {
            MLX90640_BadPixelsCorrection(params.brokenPixels, to, MODE_CHESS, &params);
            MLX90640_BadPixelsCorrection(params.outlierPixels, to, MODE_CHESS, &params);
        }
        if (!both)
        {
            if (++fails % 20 == 1)
                ESP_LOGW(TAG, "MLX90640 frame read failed (%u in a row)", (unsigned)fails);
            if (fails > 100)
                mlx_ok = false;  // re-run init: the sensor may have browned out and lost its settings
            vTaskDelay(pdMS_TO_TICKS(250));
            continue;
        }
        fails = 0;

        float air = NAN, pa = NAN;
        if (bmp_ok && bmp280_read(&air, &pa) != ESP_OK)
            air = pa = NAN;

        xSemaphoreTake(lock, portMAX_DELAY);
        memcpy(snap.to, to, sizeof(to));
        snap.ta = ta;
        snap.air = air;
        snap.pressure = pa;
        snap.frames++;
        snap.frame_us = esp_timer_get_time();
        xSemaphoreGive(lock);
    }
}

void sensors_start(void)
{
    lock = xSemaphoreCreateMutex();
    snap.ta = snap.air = snap.pressure = NAN;
    xTaskCreate(sensors_task, "sensors", 8192, NULL, 5, NULL);
}

void sensors_snapshot(zatt_snapshot_t *out)
{
    xSemaphoreTake(lock, portMAX_DELAY);
    *out = snap;
    xSemaphoreGive(lock);
}
