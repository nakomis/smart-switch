// Petro rev B's hardware. See board.h; the pins are petro_pins.h (a copy of pcb/out/petro/pins.h).
#include "board.h"

#include "driver/gpio.h"
#include "driver/uart.h"
#include "esp_adc/adc_cali.h"
#include "esp_adc/adc_cali_scheme.h"
#include "esp_adc/adc_oneshot.h"
#include "esp_attr.h"
#include "esp_check.h"
#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "led_strip.h"
#include "petro_pins.h"

static const char *TAG = "board";

#define BL_UART UART_NUM_1
#define NTC_CHANNEL ADC_CHANNEL_0  // GPIO0 is ADC1_CH0 on the C6
#define NTC_SAMPLES 16

static bool relay_on;
static led_strip_handle_t led;
static adc_oneshot_unit_handle_t adc;
static adc_cali_handle_t adc_cali;
// 32-bit counters, written only by their ISR and read whole by tasks: on the single-core C6 a
// 32-bit load is atomic, so no lock is needed.
static volatile uint32_t zx_edges, oc_edges;

static void IRAM_ATTR zx_isr(void *arg)
{
    (void)arg;
    zx_edges++;
}

static void IRAM_ATTR oc_isr(void *arg)
{
    (void)arg;
    oc_edges++;
}

static esp_err_t relay_init(void)
{
    // The gate has its own 100k pull-down, so the relay is off through reset and the bootloader.
    // Latch the output low before enabling the driver so it never glitches high, and add the
    // internal pull-down. (Not gpio_reset_pin: that enables the pull-up.)
    gpio_set_level(PETRO_PIN_RELAY, 0);
    gpio_config_t io = {
        .pin_bit_mask = 1ULL << PETRO_PIN_RELAY,
        .mode = GPIO_MODE_OUTPUT,
        .pull_up_en = GPIO_PULLUP_DISABLE,
        .pull_down_en = GPIO_PULLDOWN_ENABLE,
        .intr_type = GPIO_INTR_DISABLE,
    };
    esp_err_t err = gpio_config(&io);
    gpio_set_level(PETRO_PIN_RELAY, 0);
    relay_on = false;
    return err;
}

static esp_err_t inputs_init(void)
{
    // SW1 on GPIO9 (the boot strap, 10k pull-up on the board; held at reset it is download mode).
    gpio_config_t button = {
        .pin_bit_mask = 1ULL << PETRO_PIN_BUTTON,
        .mode = GPIO_MODE_INPUT,
        .pull_up_en = GPIO_PULLUP_ENABLE,
        .pull_down_en = GPIO_PULLDOWN_DISABLE,
        .intr_type = GPIO_INTR_DISABLE,
    };
    ESP_RETURN_ON_ERROR(gpio_config(&button), TAG, "button");

    // ZX and OC: the BL0939's push-pull outputs, every edge counted.
    gpio_config_t edges = {
        .pin_bit_mask = (1ULL << PETRO_PIN_ZX) | (1ULL << PETRO_PIN_OC),
        .mode = GPIO_MODE_INPUT,
        .pull_up_en = GPIO_PULLUP_DISABLE,
        .pull_down_en = GPIO_PULLDOWN_DISABLE,
        .intr_type = GPIO_INTR_ANYEDGE,
    };
    ESP_RETURN_ON_ERROR(gpio_config(&edges), TAG, "zx/oc");
    ESP_RETURN_ON_ERROR(gpio_install_isr_service(ESP_INTR_FLAG_IRAM), TAG, "isr service");
    ESP_RETURN_ON_ERROR(gpio_isr_handler_add(PETRO_PIN_ZX, zx_isr, NULL), TAG, "zx isr");
    ESP_RETURN_ON_ERROR(gpio_isr_handler_add(PETRO_PIN_OC, oc_isr, NULL), TAG, "oc isr");

    // J3: IN has a 100k pull-down on the board; OUT starts low.
    gpio_config_t in = {
        .pin_bit_mask = 1ULL << PETRO_PIN_IO_IN,
        .mode = GPIO_MODE_INPUT,
        .pull_up_en = GPIO_PULLUP_DISABLE,
        .pull_down_en = GPIO_PULLDOWN_DISABLE,
        .intr_type = GPIO_INTR_DISABLE,
    };
    ESP_RETURN_ON_ERROR(gpio_config(&in), TAG, "j3 in");
    gpio_set_level(PETRO_PIN_IO_OUT, 0);
    gpio_config_t out = {
        .pin_bit_mask = 1ULL << PETRO_PIN_IO_OUT,
        .mode = GPIO_MODE_OUTPUT,
        .pull_up_en = GPIO_PULLUP_DISABLE,
        .pull_down_en = GPIO_PULLDOWN_DISABLE,
        .intr_type = GPIO_INTR_DISABLE,
    };
    return gpio_config(&out);
}

static esp_err_t led_init(void)
{
    // SK6812-EC20, WS2812 protocol, GRB, one LED, through RMT. GPIO8 is a strap with a pull-up;
    // the LED ignores the steady high it sees through reset.
    led_strip_config_t strip = {
        .strip_gpio_num = PETRO_PIN_LED,
        .max_leds = 1,
        .led_model = LED_MODEL_WS2812,
        .color_component_format = LED_STRIP_COLOR_COMPONENT_FMT_GRB,
    };
    led_strip_rmt_config_t rmt = {
        .clk_src = RMT_CLK_SRC_DEFAULT,
        .resolution_hz = 10 * 1000 * 1000,
    };
    ESP_RETURN_ON_ERROR(led_strip_new_rmt_device(&strip, &rmt, &led), TAG, "led");
    return led_strip_clear(led);
}

static esp_err_t ntc_init(void)
{
    adc_oneshot_unit_init_cfg_t unit = {.unit_id = ADC_UNIT_1};
    ESP_RETURN_ON_ERROR(adc_oneshot_new_unit(&unit, &adc), TAG, "adc");
    adc_oneshot_chan_cfg_t chan = {.atten = ADC_ATTEN_DB_12, .bitwidth = ADC_BITWIDTH_DEFAULT};
    ESP_RETURN_ON_ERROR(adc_oneshot_config_channel(adc, NTC_CHANNEL, &chan), TAG, "adc channel");
    // Curve fitting from the eFuse calibration: the C6's only scheme.
    adc_cali_curve_fitting_config_t cali = {
        .unit_id = ADC_UNIT_1,
        .chan = NTC_CHANNEL,
        .atten = ADC_ATTEN_DB_12,
        .bitwidth = ADC_BITWIDTH_DEFAULT,
    };
    if (adc_cali_create_scheme_curve_fitting(&cali, &adc_cali) != ESP_OK)
    {
        ESP_LOGW(TAG, "no ADC calibration in eFuse: the NTC reads raw only");
        adc_cali = NULL;
    }
    return ESP_OK;
}

static esp_err_t bl_init(void)
{
    // UART1 at 4800 8N1: our TX (GPIO11, net BL_RX) to the BL0939's RX, its TX (GPIO10, net
    // BL_TX, 10k pull-up on the board) to our RX.
    uart_config_t cfg = {
        .baud_rate = BL0939_BAUD,
        .data_bits = UART_DATA_8_BITS,
        .parity = UART_PARITY_DISABLE,
        .stop_bits = UART_STOP_BITS_1,
        .flow_ctrl = UART_HW_FLOWCTRL_DISABLE,
        .source_clk = UART_SCLK_DEFAULT,
    };
    ESP_RETURN_ON_ERROR(uart_driver_install(BL_UART, 256, 0, 0, NULL, 0), TAG, "uart");
    ESP_RETURN_ON_ERROR(uart_param_config(BL_UART, &cfg), TAG, "uart config");
    ESP_RETURN_ON_ERROR(uart_set_pin(BL_UART, PETRO_PIN_BL_RX, PETRO_PIN_BL_TX, UART_PIN_NO_CHANGE,
                                     UART_PIN_NO_CHANGE),
                        TAG, "uart pins");

    uint8_t frames[8][BL0939_WRITE_LEN];
    size_t n = bl0939_init_frames(frames, 8);
    for (size_t i = 0; i < n; i++)
    {
        uart_write_bytes(BL_UART, frames[i], BL0939_WRITE_LEN);
        uart_wait_tx_done(BL_UART, pdMS_TO_TICKS(50));
        // The soft reset needs a moment before the chip listens again.
        vTaskDelay(pdMS_TO_TICKS(i == 0 ? 20 : 2));
    }
    uart_flush_input(BL_UART);
    return ESP_OK;
}

esp_err_t board_init(void)
{
    // The relay before anything else (and before anything can fail).
    esp_err_t relay = relay_init();
    ESP_RETURN_ON_ERROR(relay, TAG, "relay");
    ESP_RETURN_ON_ERROR(inputs_init(), TAG, "inputs");
    ESP_RETURN_ON_ERROR(led_init(), TAG, "led");
    ESP_RETURN_ON_ERROR(ntc_init(), TAG, "ntc");
    ESP_RETURN_ON_ERROR(bl_init(), TAG, "bl0939");
    return ESP_OK;
}

void board_relay(bool on)
{
    gpio_set_level(PETRO_PIN_RELAY, on ? 1 : 0);
    relay_on = on;
}

bool board_relay_is_on(void)
{
    return relay_on;
}

esp_err_t board_led(uint8_t r, uint8_t g, uint8_t b)
{
    ESP_RETURN_ON_ERROR(led_strip_set_pixel(led, 0, r, g, b), TAG, "led pixel");
    return led_strip_refresh(led);
}

bool board_button_pressed(void)
{
    return gpio_get_level(PETRO_PIN_BUTTON) == 0;
}

esp_err_t board_ntc_read(int *raw, int *mv)
{
    int sum = 0;
    for (int i = 0; i < NTC_SAMPLES; i++)
    {
        int v;
        ESP_RETURN_ON_ERROR(adc_oneshot_read(adc, NTC_CHANNEL, &v), TAG, "adc read");
        sum += v;
    }
    *raw = sum / NTC_SAMPLES;
    *mv = -1;
    if (adc_cali == NULL)
        return ESP_ERR_NOT_SUPPORTED;
    return adc_cali_raw_to_voltage(adc_cali, *raw, mv);
}

esp_err_t board_bl_read(uint8_t packet[BL0939_PACKET_LEN], size_t *len)
{
    uint8_t req[2];
    size_t n = bl0939_build_full_read(req);
    uart_flush_input(BL_UART);
    if (uart_write_bytes(BL_UART, req, n) != (int)n)
        return ESP_FAIL;
    // 2 bytes out and 35 back at 4800 baud is about 77 ms on the wire.
    int got = uart_read_bytes(BL_UART, packet, BL0939_PACKET_LEN, pdMS_TO_TICKS(250));
    *len = got > 0 ? (size_t)got : 0;
    return got == BL0939_PACKET_LEN ? ESP_OK : ESP_ERR_TIMEOUT;
}

uint32_t board_zx_edges(void)
{
    return zx_edges;
}

uint32_t board_oc_edges(void)
{
    return oc_edges;
}

void board_j3_out(bool level)
{
    gpio_set_level(PETRO_PIN_IO_OUT, level ? 1 : 0);
}

bool board_j3_in(void)
{
    return gpio_get_level(PETRO_PIN_IO_IN) != 0;
}
