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
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/semphr.h"
#include "freertos/task.h"
#include "led_strip.h"
#include "petro_pins.h"
#include "prot.h"

static const char *TAG = "board";

#define BL_UART UART_NUM_1
#define NTC_CHANNEL ADC_CHANNEL_0  // GPIO0 is ADC1_CH0 on the C6
#define NTC_SAMPLES 16

// The relay's output and the OC hold, under relay_mux (tasks and the OC interrupt).
static portMUX_TYPE relay_mux = portMUX_INITIALIZER_UNLOCKED;
static volatile bool relay_on;
static volatile bool oc_hold;  // the OC interrupt opened the relay: it stays open until released
static volatile bool oc_armed;
static volatile int oc_active_level;
static TaskHandle_t oc_task;
static bool bl_configured;
static uint32_t bl_fast_ctrl;
// The last three ZX edges, under zx_mux.
static portMUX_TYPE zx_mux = portMUX_INITIALIZER_UNLOCKED;
static zx_edges zx;
static esp_err_t part_err[BOARD_PARTS] = {
    ESP_ERR_INVALID_STATE, ESP_ERR_INVALID_STATE, ESP_ERR_INVALID_STATE, ESP_ERR_INVALID_STATE,
    ESP_ERR_INVALID_STATE,
};
static SemaphoreHandle_t bl_lock;
static led_strip_handle_t led;
static adc_oneshot_unit_handle_t adc;
static adc_cali_handle_t adc_cali;
// 32-bit counters, written only by their ISR and read whole by tasks: on the single-core C6 a
// 32-bit load is atomic, so no lock is needed.
static volatile uint32_t zx_count, oc_count;

static void IRAM_ATTR zx_isr(void *arg)
{
    (void)arg;
    zx_count++;
    int64_t t = esp_timer_get_time();
    portENTER_CRITICAL_ISR(&zx_mux);
    zx_edge(&zx, t);
    portEXIT_CRITICAL_ISR(&zx_mux);
}

// The instant trip (PETRO-5): the BL0939's fast RMS passed its threshold. The relay opens here,
// within microseconds of the edge (then the relay's release time), and is held open; the trip task
// latches, stores and reports it (no NVS or flash in here). gpio_get_level and gpio_set_level are
// in IRAM (CONFIG_GPIO_CTRL_FUNC_IN_IRAM).
static void IRAM_ATTR oc_isr(void *arg)
{
    (void)arg;
    oc_count++;
    if (!oc_armed || gpio_get_level(PETRO_PIN_OC) != oc_active_level)
        return;
    portENTER_CRITICAL_ISR(&relay_mux);
    oc_hold = true;
    gpio_set_level(PETRO_PIN_RELAY, 0);
    relay_on = false;
    portEXIT_CRITICAL_ISR(&relay_mux);
    BaseType_t woken = pdFALSE;
    if (oc_task != NULL)
        vTaskNotifyGiveFromISR(oc_task, &woken);
    portYIELD_FROM_ISR(woken);
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

// One register read: {0x55, reg}, 4 bytes back. Under bl_lock.
static esp_err_t bl_read_reg_locked(uint8_t reg, uint32_t *value)
{
    uint8_t req[2], reply[BL0939_REG_REPLY_LEN];
    size_t n = bl0939_build_read(reg, req);
    uart_flush_input(BL_UART);
    if (uart_write_bytes(BL_UART, req, n) != (int)n)
        return ESP_FAIL;
    // 2 bytes out and 4 back at 4800 baud: about 13 ms.
    int got = uart_read_bytes(BL_UART, reply, sizeof(reply), pdMS_TO_TICKS(100));
    if (got != (int)sizeof(reply))
        return ESP_ERR_TIMEOUT;
    return bl0939_parse_register(reg, reply, sizeof(reply), value) == BL0939_OK ? ESP_OK : ESP_ERR_INVALID_CRC;
}

static esp_err_t bl_write_locked(uint8_t reg, uint32_t value)
{
    uint8_t f[BL0939_WRITE_LEN];
    bl0939_build_write(reg, value, f);
    if (uart_write_bytes(BL_UART, f, BL0939_WRITE_LEN) != BL0939_WRITE_LEN)
        return ESP_FAIL;
    return uart_wait_tx_done(BL_UART, pdMS_TO_TICKS(50));
}

// Whether the chip holds what we wrote: the mode and both fast-RMS thresholds. Under bl_lock.
static esp_err_t bl_verify_locked(uint32_t fast_ctrl)
{
    static const uint8_t regs[] = {BL0939_REG_MODE, BL0939_REG_IA_FAST_RMS_CTRL, BL0939_REG_IB_FAST_RMS_CTRL};
    const uint32_t want[] = {0x001000, fast_ctrl, fast_ctrl};
    for (size_t i = 0; i < sizeof(regs); i++)
    {
        uint32_t v = 0;
        esp_err_t err = bl_read_reg_locked(regs[i], &v);
        if (err != ESP_OK)
        {
            ESP_LOGE(TAG, "bl0939: reading back register 0x%02x: %s", regs[i], esp_err_to_name(err));
            return err;
        }
        // The fast-RMS registers are 16 bits wide in the chip: compare what we set.
        if ((v & 0xFFFF) != (want[i] & 0xFFFF))
        {
            ESP_LOGE(TAG, "bl0939: register 0x%02x reads 0x%06lx, wrote 0x%06lx", regs[i], (unsigned long)v,
                     (unsigned long)want[i]);
            return ESP_ERR_INVALID_RESPONSE;
        }
    }
    return ESP_OK;
}

static esp_err_t bl_init(void)
{
    bl_lock = xSemaphoreCreateMutex();
    if (bl_lock == NULL)
        return ESP_ERR_NO_MEM;
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

    // The instant trip's threshold (PETRO-5) goes in with the rest.
    bl_fast_ctrl = prot_fast_rms_ctrl(CTL_INSTANT_AMPS_DEFAULT, bl0939_petro_scale().amps);
    uint8_t frames[8][BL0939_WRITE_LEN];
    size_t n = bl0939_init_frames(frames, 8, bl_fast_ctrl);
    for (size_t i = 0; i < n; i++)
    {
        uart_write_bytes(BL_UART, frames[i], BL0939_WRITE_LEN);
        uart_wait_tx_done(BL_UART, pdMS_TO_TICKS(50));
        // The soft reset needs a moment before the chip listens again.
        vTaskDelay(pdMS_TO_TICKS(i == 0 ? 20 : 2));
    }
    uart_flush_input(BL_UART);
    // The UART works without the chip answering; the trips need it to have taken the thresholds.
    xSemaphoreTake(bl_lock, portMAX_DELAY);
    bl_configured = bl_verify_locked(bl_fast_ctrl) == ESP_OK;
    xSemaphoreGive(bl_lock);
    if (bl_configured)
        ESP_LOGI(TAG, "bl0939: thresholds set (fast RMS control 0x%04lx, %.1f A)", (unsigned long)bl_fast_ctrl,
                 CTL_INSTANT_AMPS_DEFAULT);
    return ESP_OK;
}

esp_err_t board_init(void)
{
    // The relay before anything else (and before anything can fail); then each part on its own.
    static esp_err_t (*const init[BOARD_PARTS])(void) = {relay_init, inputs_init, led_init, ntc_init, bl_init};
    esp_err_t first = ESP_OK;
    for (int i = 0; i < BOARD_PARTS; i++)
    {
        part_err[i] = init[i]();
        if (part_err[i] != ESP_OK)
        {
            ESP_LOGE(TAG, "%s: %s", board_part_name((board_part)i), esp_err_to_name(part_err[i]));
            if (first == ESP_OK)
                first = part_err[i];
        }
    }
    return first;
}

bool board_part_ok(board_part part)
{
    return part < BOARD_PARTS && part_err[part] == ESP_OK;
}

const char *board_part_name(board_part part)
{
    static const char *const names[BOARD_PARTS] = {"relay", "inputs", "led", "ntc", "bl0939"};
    return part < BOARD_PARTS ? names[part] : "?";
}

void board_relay(bool on)
{
    // The check and the write together, so the OC interrupt can't fall between them.
    portENTER_CRITICAL(&relay_mux);
    if (oc_hold)
        on = false;
    gpio_set_level(PETRO_PIN_RELAY, on ? 1 : 0);
    relay_on = on;
    portEXIT_CRITICAL(&relay_mux);
}

bool board_relay_is_on(void)
{
    return relay_on;
}

esp_err_t board_led(uint8_t r, uint8_t g, uint8_t b)
{
    if (led == NULL)
        return ESP_ERR_INVALID_STATE;
    ESP_RETURN_ON_ERROR(led_strip_set_pixel(led, 0, r, g, b), TAG, "led pixel");
    return led_strip_refresh(led);
}

bool board_button_pressed(void)
{
    return gpio_get_level(PETRO_PIN_BUTTON) == 0;
}

esp_err_t board_ntc_read(int *raw, int *mv)
{
    *raw = 0;
    *mv = -1;
    if (adc == NULL)
        return ESP_ERR_INVALID_STATE;
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
    *len = 0;
    if (!board_part_ok(BOARD_BL0939))
        return ESP_ERR_INVALID_STATE;
    uint8_t req[2];
    size_t n = bl0939_build_full_read(req);
    xSemaphoreTake(bl_lock, portMAX_DELAY);
    uart_flush_input(BL_UART);
    if (uart_write_bytes(BL_UART, req, n) != (int)n)
    {
        xSemaphoreGive(bl_lock);
        return ESP_FAIL;
    }
    // 2 bytes out and 35 back at 4800 baud is about 77 ms on the wire.
    int got = uart_read_bytes(BL_UART, packet, BL0939_PACKET_LEN, pdMS_TO_TICKS(250));
    xSemaphoreGive(bl_lock);
    *len = got > 0 ? (size_t)got : 0;
    return got == BL0939_PACKET_LEN ? ESP_OK : ESP_ERR_TIMEOUT;
}

uint32_t board_zx_edges(void)
{
    return zx_count;
}

uint32_t board_oc_edges(void)
{
    return oc_count;
}

void board_zx_snapshot(zx_edges *out)
{
    portENTER_CRITICAL(&zx_mux);
    *out = zx;
    portEXIT_CRITICAL(&zx_mux);
}

int board_oc_arm(TaskHandle_t notify)
{
    // Sampled with the relay open (no current), so whatever the pin shows now is its idle level.
    oc_task = notify;
    oc_active_level = !gpio_get_level(PETRO_PIN_OC);
    oc_armed = true;
    // Edge-triggered: a pin already active at arming (not possible with the relay open, unless the
    // polarity guess is wrong) shows up through board_oc_active instead.
    return oc_active_level;
}

bool board_oc_active(void)
{
    return oc_armed && gpio_get_level(PETRO_PIN_OC) == oc_active_level;
}

bool board_oc_held(void)
{
    return oc_hold;
}

bool board_oc_release(void)
{
    bool released = false;
    portENTER_CRITICAL(&relay_mux);
    if (!(oc_armed && gpio_get_level(PETRO_PIN_OC) == oc_active_level))
    {
        oc_hold = false;
        released = true;
    }
    portEXIT_CRITICAL(&relay_mux);
    return released;
}

bool board_bl_configured(void)
{
    return board_part_ok(BOARD_BL0939) && bl_configured;
}

uint32_t board_bl_fast_ctrl(void)
{
    return bl_fast_ctrl;
}

esp_err_t board_bl_set_instant(double amps)
{
    if (!board_part_ok(BOARD_BL0939))
        return ESP_ERR_INVALID_STATE;
    uint32_t ctrl = prot_fast_rms_ctrl(amps, bl0939_petro_scale().amps);
    xSemaphoreTake(bl_lock, portMAX_DELAY);
    esp_err_t err = bl_write_locked(BL0939_REG_IA_FAST_RMS_CTRL, ctrl);
    if (err == ESP_OK)
        err = bl_write_locked(BL0939_REG_IB_FAST_RMS_CTRL, ctrl);
    if (err == ESP_OK)
        err = bl_verify_locked(ctrl);
    bl_configured = err == ESP_OK;
    if (bl_configured)
        bl_fast_ctrl = ctrl;
    xSemaphoreGive(bl_lock);
    return err;
}

void board_j3_out(bool level)
{
    gpio_set_level(PETRO_PIN_IO_OUT, level ? 1 : 0);
}

bool board_j3_in(void)
{
    return gpio_get_level(PETRO_PIN_IO_IN) != 0;
}
