// The bench console (Gate 2) on the USB-Serial-JTAG: docs/testing/README.md, "What the gates need
// from the firmware". port/console_parse.c parses and validates each line; this file acts on it.
//
// USB only, and so never with mains connected: the board is at mains potential when plugged in.
#include "console.h"

#include <inttypes.h>
#include <stdio.h>
#include <string.h>

#include "board.h"
#include "bl0939.h"
#include "console_parse.h"
#include "driver/i2c_master.h"
#include "driver/usb_serial_jtag.h"
#include "esp_app_desc.h"
#include "esp_chip_info.h"
#include "esp_console.h"
#include "esp_event.h"
#include "esp_log.h"
#include "esp_mac.h"
#include "esp_netif.h"
#include "esp_system.h"
#include "esp_timer.h"
#include "esp_wifi.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "ntc.h"
#include "petro_pins.h"
#include "prov.h"

static const char *TAG = "console";

static const char *reset_reason(esp_reset_reason_t r)
{
    switch (r)
    {
    case ESP_RST_POWERON:
        return "poweron";
    case ESP_RST_EXT:
        return "external";
    case ESP_RST_SW:
        return "software";
    case ESP_RST_PANIC:
        return "panic";
    case ESP_RST_INT_WDT:
        return "int_wdt";
    case ESP_RST_TASK_WDT:
        return "task_wdt";
    case ESP_RST_WDT:
        return "wdt";
    case ESP_RST_DEEPSLEEP:
        return "deepsleep";
    case ESP_RST_BROWNOUT:
        return "brownout";
    case ESP_RST_SDIO:
        return "sdio";
    case ESP_RST_USB:
        return "usb";
    case ESP_RST_JTAG:
        return "jtag";
    case ESP_RST_EFUSE:
        return "efuse";
    case ESP_RST_PWR_GLITCH:
        return "power_glitch";
    case ESP_RST_CPU_LOCKUP:
        return "cpu_lockup";
    default:
        return "unknown";
    }
}

static void cmd_info(void)
{
    const esp_app_desc_t *app = esp_app_get_description();
    uint8_t mac[6];
    esp_read_mac(mac, ESP_MAC_WIFI_STA);
    esp_chip_info_t chip;
    esp_chip_info(&chip);
    printf("firmware   %s %s (IDF %s)\n", app->project_name, app->version, app->idf_ver);
    printf("mac        %02x:%02x:%02x:%02x:%02x:%02x\n", mac[0], mac[1], mac[2], mac[3], mac[4],
           mac[5]);
    printf("chip       ESP32-C6 rev v%d.%d, %d core(s)\n", chip.revision / 100, chip.revision % 100,
           chip.cores);
    printf("reset      %s\n", reset_reason(esp_reset_reason()));
    printf("uptime     %" PRId64 " s\n", esp_timer_get_time() / 1000000);
    // TODO(PETRO-3 slice 3): the mode (on, off, auto) from NVS, and the button cycling it.
    printf("mode       none yet (PETRO-3 slice 3): console control only\n");
    printf("relay      %s\n", board_relay_is_on() ? "on" : "off");
    // TODO(PETRO-5): the over-current and over-temperature trips and their thresholds.
    printf("trips      none in force (PETRO-5)\n");
    prov_state_t prov;
    prov_state(&prov);
    if (!prov.opened)
    {
        printf("prov       not provisioned (%s)\n", prov.error);
        return;
    }
    printf("prov       namespace '%s':", PROV_NAMESPACE);
    for (size_t i = 0; i < PROV_KEY_COUNT; i++)
        printf(" %s%s", prov.present[i] ? "+" : "-", PROV_KEYS[i]);
    printf("  (+ present, - missing; values never shown)\n");
}

// True once a key has arrived on the console (and swallows it). Non-blocking: the REPL's
// USB-Serial-JTAG driver is read directly, with no wait.
static bool key_pressed(void)
{
    uint8_t c;
    return usb_serial_jtag_is_driver_installed() && usb_serial_jtag_read_bytes(&c, 1, 0) > 0;
}

// Waits ms, checking for a key every 20 ms. True if one came (the wait then ends early).
static bool wait_or_key(uint32_t ms)
{
    while (ms > 0)
    {
        uint32_t step = ms < 20 ? ms : 20;
        vTaskDelay(pdMS_TO_TICKS(step));
        ms -= step;
        if (key_pressed())
            return true;
    }
    return false;
}

static void cmd_relay_cycle(const console_cmd_t *c)
{
    printf("cycling %" PRIu32 " times, %" PRIu32 " ms on, %" PRIu32 " ms off (any key stops)\n",
           c->cycle.n, c->cycle.on_ms, c->cycle.off_ms);
    while (key_pressed())  // drop anything typed ahead
        ;
    uint32_t done = 0;
    bool stopped = false;
    while (done < c->cycle.n && !stopped)
    {
        board_relay(true);
        stopped = wait_or_key(c->cycle.on_ms);
        board_relay(false);
        if (!stopped)
            stopped = wait_or_key(c->cycle.off_ms);
        done++;
        if (done % 50 == 0 || done == c->cycle.n)
            printf("  %" PRIu32 "/%" PRIu32 "\n", done, c->cycle.n);
    }
    board_relay(false);
    if (stopped)
        printf("stopped by a key during cycle %" PRIu32 "/%" PRIu32 "\n", done, c->cycle.n);
    printf("relay off\n");
}

static void cmd_button(void)
{
    // A 5 ms poll and a 20 ms debounce: a level must hold for four polls to count.
    const int64_t end = esp_timer_get_time() + 10 * 1000000LL;
    const int64_t start = esp_timer_get_time();
    bool stable = board_button_pressed();
    bool last = stable;
    int same = 0, presses = 0;
    printf("watching SW1 for 10 s (now %s)\n", stable ? "pressed" : "released");
    while (esp_timer_get_time() < end)
    {
        vTaskDelay(pdMS_TO_TICKS(5));
        bool now = board_button_pressed();
        same = now == last ? same + 1 : 0;
        last = now;
        if (same >= 4 && now != stable)
        {
            stable = now;
            presses += stable ? 1 : 0;
            printf("  %6.3f s  %s\n", (esp_timer_get_time() - start) / 1e6,
                   stable ? "pressed" : "released");
        }
    }
    printf("%d press(es)\n", presses);
}

static void cmd_bl(void)
{
    const bl0939_scale_t scale = bl0939_petro_scale();
    printf("scale: %.1f /V, %.1f /A, %.3f /W, %.1f CF/kWh\n", scale.volts, scale.amps, scale.watts,
           scale.pulses_per_kwh);
    for (int i = 0; i < 3; i++)
    {
        if (i > 0)
            vTaskDelay(pdMS_TO_TICKS(500));
        uint8_t p[BL0939_PACKET_LEN];
        size_t len = 0;
        esp_err_t err = board_bl_read(p, &len);
        bl0939_raw_t raw;
        bl0939_status_t st = bl0939_parse_packet(p, len, &raw);
        printf("frame %d: %u bytes, %s\n", i + 1, (unsigned)len,
               err == ESP_OK && st == BL0939_OK ? "checksum good" : bl0939_status_name(st));
        if (st != BL0939_OK)
            continue;
        bl0939_reading_t r = bl0939_convert(&raw, &scale);
        printf("  V      raw %8" PRIu32 "  %8.2f V\n", raw.v_rms, r.volts);
        printf("  IA     raw %8" PRIu32 "  %8.4f A   (fast %" PRIu32 ")\n", raw.ia_rms, r.amps_a,
               raw.ia_fast_rms);
        printf("  IB     raw %8" PRIu32 "  %8.4f A   (fast %" PRIu32 ")\n", raw.ib_rms, r.amps_b,
               raw.ib_fast_rms);
        printf("  PA     raw %8" PRId32 "  %8.2f W\n", raw.a_watt, r.watts_a);
        printf("  PB     raw %8" PRId32 "  %8.2f W\n", raw.b_watt, r.watts_b);
        printf("  CF A   %8" PRIu32 "  %.6f kWh   CF B %" PRIu32 "\n", raw.cfa_cnt, r.kwh_a,
               raw.cfb_cnt);
        printf("  temp   raw %8u  %8.1f C\n", raw.tps1 & 0x3FF, r.celsius);
    }
}

static void cmd_edges(void)
{
    printf("ZX and OC edges (rising and falling) a second:\n");
    for (int s = 1; s <= 2; s++)
    {
        uint32_t zx = board_zx_edges(), oc = board_oc_edges();
        vTaskDelay(pdMS_TO_TICKS(1000));
        printf("  second %d: ZX %" PRIu32 "  OC %" PRIu32 "\n", s, board_zx_edges() - zx,
               board_oc_edges() - oc);
    }
}

static void cmd_ntc(void)
{
    int raw = 0, mv = -1;
    esp_err_t err = board_ntc_read(&raw, &mv);
    if (err != ESP_OK)
    {
        printf("ntc: raw %d, no calibrated voltage (%s)\n", raw, esp_err_to_name(err));
        return;
    }
    ntc_params_t p = ntc_petro_params();
    double ohms, celsius;
    if (!ntc_resistance(&p, mv, &ohms) || !ntc_celsius(&p, mv, &celsius))
    {
        printf("ntc: raw %d, %d mV: out of range (open or shorted NTC?)\n", raw, mv);
        return;
    }
    printf("ntc: raw %d, %d mV, %.0f ohm, %.1f C (B %.0f, 3V3 taken as %.0f mV)\n", raw, mv, ohms,
           celsius, p.b_kelvin, p.supply_mv);
}

static esp_err_t wifi_start(void)
{
    // Each step once, so a retry after a failure only does what's still missing (creating the
    // default STA netif twice asserts).
    static bool netif_ready, loop_ready, sta_created, wifi_inited, wifi_set, started;
    esp_err_t err;
    if (!netif_ready)
    {
        if ((err = esp_netif_init()) != ESP_OK)
            return err;
        netif_ready = true;
    }
    if (!loop_ready)
    {
        err = esp_event_loop_create_default();
        if (err != ESP_OK && err != ESP_ERR_INVALID_STATE)  // INVALID_STATE: it already exists
            return err;
        loop_ready = true;
    }
    if (!sta_created)
    {
        if (esp_netif_create_default_wifi_sta() == NULL)
            return ESP_FAIL;
        sta_created = true;
    }
    if (!wifi_inited)
    {
        wifi_init_config_t cfg = WIFI_INIT_CONFIG_DEFAULT();
        if ((err = esp_wifi_init(&cfg)) != ESP_OK)
            return err;
        wifi_inited = true;
    }
    if (!wifi_set)
    {
        if ((err = esp_wifi_set_storage(WIFI_STORAGE_RAM)) != ESP_OK ||
            (err = esp_wifi_set_mode(WIFI_MODE_STA)) != ESP_OK ||
            (err = esp_wifi_set_country_code("GB", true)) != ESP_OK)  // channels 1-13
            return err;
        wifi_set = true;
    }
    if (!started)
    {
        if ((err = esp_wifi_start()) != ESP_OK)
            return err;
        started = true;
    }
    return ESP_OK;
}

static void cmd_wifi_scan(void)
{
    // Scan only: joining (with the prov partition's credentials) is PETRO-3 slice 3.
    esp_err_t err = wifi_start();
    if (err == ESP_OK)
        err = esp_wifi_scan_start(NULL, true);
    if (err != ESP_OK)
    {
        printf("wifi scan: %s\n", esp_err_to_name(err));
        return;
    }
    uint16_t n = 20;
    wifi_ap_record_t aps[20];
    uint16_t total = 0;
    esp_wifi_scan_get_ap_num(&total);
    esp_wifi_scan_get_ap_records(&n, aps);
    printf("%u AP(s)%s\n", total, total > n ? " (the strongest 20 shown)" : "");
    printf("  %-32s  ch  RSSI\n", "SSID");
    for (uint16_t i = 0; i < n; i++)
        printf("  %-32s  %2u  %4d dBm\n", aps[i].ssid[0] ? (const char *)aps[i].ssid : "(hidden)",
               aps[i].primary, aps[i].rssi);
}

static void cmd_j3(void)
{
    printf("j3: OUT (GPIO%d) at 1 Hz for 5 s, IN (GPIO%d) read each half second\n",
           PETRO_PIN_IO_OUT, PETRO_PIN_IO_IN);
    for (int half = 0; half < 10; half++)
    {
        bool out = (half % 2) == 0;
        board_j3_out(out);
        vTaskDelay(pdMS_TO_TICKS(500));
        printf("  %4.1f s  OUT %d  IN %d\n", half * 0.5, out, board_j3_in());
    }
    board_j3_out(false);

    i2c_master_bus_config_t bus_cfg = {
        .i2c_port = -1,
        .sda_io_num = PETRO_PIN_I2C_SDA,
        .scl_io_num = PETRO_PIN_I2C_SCL,
        .clk_source = I2C_CLK_SRC_DEFAULT,
        .glitch_ignore_cnt = 7,
        .flags.enable_internal_pullup = false,  // 4k7 on the board
    };
    i2c_master_bus_handle_t bus;
    esp_err_t err = i2c_new_master_bus(&bus_cfg, &bus);
    if (err != ESP_OK)
    {
        printf("i2c: %s\n", esp_err_to_name(err));
        return;
    }
    printf("i2c scan 0x08-0x77 (SDA GPIO%d, SCL GPIO%d):", PETRO_PIN_I2C_SDA, PETRO_PIN_I2C_SCL);
    int found = 0;
    for (uint16_t addr = 0x08; addr <= 0x77; addr++)
    {
        if (i2c_master_probe(bus, addr, 20) == ESP_OK)
        {
            printf(" 0x%02x", addr);
            found++;
        }
    }
    printf(found ? "\n" : " nothing\n");
    i2c_del_master_bus(bus);
}

static int run(int argc, char **argv)
{
    console_cmd_t c;
    char err[96];
    if (!console_parse_argv(argc, (const char *const *)argv, &c, err, sizeof(err)))
    {
        printf("%s\n", err);
        return 1;
    }
    switch (c.kind)
    {
    case CONSOLE_HELP:
        for (size_t i = 0; i < CONSOLE_USAGE_LEN; i++)
            printf("%s\n", CONSOLE_USAGE[i]);
        break;
    case CONSOLE_INFO:
        cmd_info();
        break;
    case CONSOLE_RELAY_ON:
    case CONSOLE_RELAY_OFF:
        board_relay(c.kind == CONSOLE_RELAY_ON);
        printf("relay %s\n", board_relay_is_on() ? "on" : "off");
        break;
    case CONSOLE_RELAY_CYCLE:
        cmd_relay_cycle(&c);
        break;
    case CONSOLE_LED:
    {
        esp_err_t e = board_led(c.led.r, c.led.g, c.led.b);
        printf("led %u %u %u%s%s\n", c.led.r, c.led.g, c.led.b, e == ESP_OK ? "" : ": ",
               e == ESP_OK ? "" : esp_err_to_name(e));
        break;
    }
    case CONSOLE_BUTTON:
        cmd_button();
        break;
    case CONSOLE_BL:
        cmd_bl();
        break;
    case CONSOLE_EDGES:
        cmd_edges();
        break;
    case CONSOLE_NTC:
        cmd_ntc();
        break;
    case CONSOLE_WIFI_SCAN:
        cmd_wifi_scan();
        break;
    case CONSOLE_J3:
        cmd_j3();
        break;
    }
    return 0;
}

esp_err_t console_start(void)
{
    static const char *const names[] = {"help", "info", "relay", "led", "button", "bl",
                                        "edges", "ntc", "wifi", "j3"};
    esp_console_repl_t *repl = NULL;
    esp_console_repl_config_t repl_cfg = ESP_CONSOLE_REPL_CONFIG_DEFAULT();
    repl_cfg.prompt = "petro>";
    repl_cfg.task_stack_size = 8192;  // wifi scan's records and printf of doubles
    esp_console_dev_usb_serial_jtag_config_t dev = ESP_CONSOLE_DEV_USB_SERIAL_JTAG_CONFIG_DEFAULT();
    esp_err_t err = esp_console_new_repl_usb_serial_jtag(&dev, &repl_cfg, &repl);
    if (err != ESP_OK)
        return err;
    for (size_t i = 0; i < sizeof(names) / sizeof(names[0]); i++)
    {
        const esp_console_cmd_t cmd = {.command = names[i], .help = NULL, .func = run};
        err = esp_console_cmd_register(&cmd);
        if (err != ESP_OK)
        {
            ESP_LOGE(TAG, "register %s: %s", names[i], esp_err_to_name(err));
            return err;
        }
    }
    return esp_console_start_repl(repl);
}
