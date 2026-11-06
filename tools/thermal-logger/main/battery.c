// Optional battery voltage on an ADC1 pin behind a resistor divider (CONFIG_ZATT_BATTERY_ADC).
#include "sdkconfig.h"
#include "zatt.h"

#ifndef CONFIG_ZATT_BATTERY_ADC

bool battery_volts(float *v)
{
    (void)v;
    return false;
}

#else

#include "esp_adc/adc_cali.h"
#include "esp_adc/adc_cali_scheme.h"
#include "esp_adc/adc_oneshot.h"
#include "esp_log.h"

static const char *TAG = "battery";
static adc_oneshot_unit_handle_t unit;
static adc_cali_handle_t cali;
static adc_channel_t chan;
static bool ready, tried;

static bool setup(void)
{
    adc_unit_t u;
    if (adc_oneshot_io_to_channel(CONFIG_ZATT_BATTERY_GPIO, &u, &chan) != ESP_OK || u != ADC_UNIT_1)
    {
        ESP_LOGE(TAG, "GPIO%d is not an ADC1 pin", CONFIG_ZATT_BATTERY_GPIO);
        return false;
    }
    adc_oneshot_unit_init_cfg_t ucfg = {.unit_id = ADC_UNIT_1};
    adc_oneshot_chan_cfg_t ccfg = {.atten = ADC_ATTEN_DB_12, .bitwidth = ADC_BITWIDTH_DEFAULT};
    if (adc_oneshot_new_unit(&ucfg, &unit) != ESP_OK || adc_oneshot_config_channel(unit, chan, &ccfg) != ESP_OK)
        return false;
#if ADC_CALI_SCHEME_CURVE_FITTING_SUPPORTED
    adc_cali_curve_fitting_config_t cc = {.unit_id = ADC_UNIT_1, .chan = chan, .atten = ADC_ATTEN_DB_12,
                                          .bitwidth = ADC_BITWIDTH_DEFAULT};
    return adc_cali_create_scheme_curve_fitting(&cc, &cali) == ESP_OK;
#elif ADC_CALI_SCHEME_LINE_FITTING_SUPPORTED
    adc_cali_line_fitting_config_t cc = {.unit_id = ADC_UNIT_1, .atten = ADC_ATTEN_DB_12,
                                         .bitwidth = ADC_BITWIDTH_DEFAULT};
    return adc_cali_create_scheme_line_fitting(&cc, &cali) == ESP_OK;
#else
    return false;
#endif
}

bool battery_volts(float *v)
{
    if (!tried)
    {
        tried = true;
        ready = setup();
    }
    if (!ready)
        return false;
    int sum = 0, n = 0;
    for (int i = 0; i < 16; i++)
    {
        int raw;
        if (adc_oneshot_read(unit, chan, &raw) == ESP_OK)
        {
            sum += raw;
            n++;
        }
    }
    int mv;
    if (n == 0 || adc_cali_raw_to_voltage(cali, sum / n, &mv) != ESP_OK)
        return false;
    *v = mv / 1000.0f * CONFIG_ZATT_BATTERY_DIVIDER_PERCENT / 100.0f;
    return true;
}

#endif
