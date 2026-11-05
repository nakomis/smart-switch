// The control and meter tasks. See app.h.
#include "app.h"

#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "bl0939.h"
#include "board.h"
#include "button.h"
#include "cJSON.h"
#include "energy.h"
#include "esp_app_desc.h"
#include "esp_log.h"
#include "esp_system.h"
#include "esp_task_wdt.h"
#include "esp_timer.h"
#include "fleet_cmd.h"
#include "freertos/FreeRTOS.h"
#include "freertos/queue.h"
#include "freertos/semphr.h"
#include "freertos/task.h"
#include "led.h"
#include "net.h"
#include "ntc.h"
#include "ota.h"
#include "report.h"
#include "status_json.h"
#include "store.h"
#include "stress.h"

static const char *TAG = "app";

// Fleet's largest message is an ota_update of at most ~1500 bytes (longer URLs come as url_chunks).
#define CMD_MAX_LEN 2048
#define QUEUE_LEN 8
#define CONTROL_STACK 8192  // cJSON and the command parsers run here
#define CONTROL_PRIORITY 8  // above MQTT (5), the OTA task (4), metrics (2) and stress (1)
#define METER_STACK 4096
#define METER_PRIORITY 6
#define METER_PERIOD_MS 1000
#define METER_STALE_READS 3  // failed reads in a row before V/A/W go unknown
#define RESTART_DELAY_MS 2000  // for the response to reach IoT Core first
#define STATUS_MAX 512

typedef struct
{
    char *json;  // malloc'd, NUL-terminated; the control task frees it
    size_t len;
} app_event;

static QueueHandle_t queue;
static SemaphoreHandle_t lock;  // ctl and the shared readings
static bool provisioned;

// Under lock.
static ctl_t ctl;
static struct
{
    bool have_meter;
    double volts, amps, watts;
    uint32_t meter_errors;
    bool have_temp;
    double board_c;
    bool have_zx;
    double zx_hz;
} readings;
static energy_t energy;

// Owned by the control task.
static button_t button;
static reporter_t reporter;
static bool applied_relay;
static ctl_mode stored_mode;
static bool have_stored_mode;
static bool healthy;

// The console's LED hold (any task writes, the control task reads).
static portMUX_TYPE led_lock = portMUX_INITIALIZER_UNLOCKED;
static int64_t led_hold_until_ms;

// While the console's `button` command watches SW1, presses don't change the mode.
static volatile bool button_watched;
static uint8_t led_hold_rgb[3];

static int64_t now_ms(void)
{
    return esp_timer_get_time() / 1000;
}

static void take(void)
{
    xSemaphoreTake(lock, portMAX_DELAY);
}

static void give(void)
{
    xSemaphoreGive(lock);
}

// Drives the relay to what ctl says now. Called with the lock held, by whichever task changed ctl,
// so a command or a trip acts at once rather than on the next loop.
static bool apply_locked(void)
{
    bool relay = ctl_relay(&ctl, now_ms());
    if (relay != applied_relay)
    {
        board_relay(relay);
        applied_relay = relay;
    }
    return relay;
}

// ---- the console and the trip hook (any task) ------------------------------------------------

ctl_result app_bench_relay(bool on)
{
    take();
    ctl_result r = ctl_bench_relay(&ctl, on);
    apply_locked();
    give();
    return r;
}

ctl_result app_bench_cycle(uint32_t n, uint32_t on_ms, uint32_t off_ms)
{
    take();
    ctl_result r = ctl_bench_cycle(&ctl, n, on_ms, off_ms, now_ms());
    apply_locked();
    give();
    return r;
}

bool app_cycle_stop(void)
{
    take();
    bool was = ctl_cycle_stop(&ctl);
    apply_locked();
    give();
    return was;
}

ctl_result app_set_mode(ctl_mode mode)
{
    take();
    ctl_result r = ctl_set_mode(&ctl, mode);
    apply_locked();
    give();
    return r;
}

void app_led_hold(uint8_t r, uint8_t g, uint8_t b)
{
    taskENTER_CRITICAL(&led_lock);
    led_hold_until_ms = now_ms() + APP_LED_HOLD_MS;
    led_hold_rgb[0] = r;
    led_hold_rgb[1] = g;
    led_hold_rgb[2] = b;
    taskEXIT_CRITICAL(&led_lock);
}

void app_led_release(void)
{
    taskENTER_CRITICAL(&led_lock);
    led_hold_until_ms = 0;
    taskEXIT_CRITICAL(&led_lock);
}

void app_button_watch(bool watching)
{
    button_watched = watching;
}

void app_trip(ctl_trip_cause cause)
{
    take();
    bool latched = ctl_trip(&ctl, cause);
    apply_locked();
    give();
    if (latched)
    {
        ESP_LOGW(TAG, "TRIP: %s, relay open", ctl_trip_name(cause));
        store_count_trip(cause);
    }
}

void app_get_state(app_state *out)
{
    memset(out, 0, sizeof(*out));
    take();
    out->mode = ctl.mode;
    out->relay = applied_relay;
    out->trip = ctl.trip;
    out->remote = ctl_accepts_remote(&ctl);
    out->bench = ctl.bench;
    out->cycle_active = ctl.cycle.active;
    out->cycle_done = ctl.cycle.done;
    out->cycle_n = ctl.cycle.n;
    out->trip_amps = ctl.trip_amps;
    out->trip_amps_temporary = ctl_trip_amps_temporary(&ctl);
    out->have_meter = readings.have_meter;
    out->volts = readings.volts;
    out->amps = readings.amps;
    out->watts = readings.watts;
    out->meter_errors = readings.meter_errors;
    out->energy_kwh = energy_kwh(&energy);
    out->have_temp = readings.have_temp;
    out->board_c = readings.board_c;
    out->have_zx = readings.have_zx;
    out->zx_hz = readings.zx_hz;
    give();
}

// ---- the meter task ------------------------------------------------------------------------------

static void save_energy(void)
{
    take();
    uint64_t mwh = energy_mwh(&energy);
    bool due = energy_save_due(&energy, now_ms());
    give();
    if (!due)
        return;
    if (store_set_energy_mwh(mwh) == ESP_OK)
    {
        take();
        energy_saved(&energy, mwh, now_ms());
        give();
    }
}

static void meter_task(void *arg)
{
    (void)arg;
    const bl0939_scale_t scale = bl0939_petro_scale();
    const ntc_params_t ntc = ntc_petro_params();
    int failures = 0;
    uint32_t zx_last = board_zx_edges();
    int64_t zx_last_ms = now_ms();
    TickType_t wake = xTaskGetTickCount();
    for (;;)
    {
        vTaskDelayUntil(&wake, pdMS_TO_TICKS(METER_PERIOD_MS));
        uint8_t packet[BL0939_PACKET_LEN];
        size_t len = 0;
        bl0939_raw_t raw;
        bool good = board_bl_read(packet, &len) == ESP_OK &&
                    bl0939_parse_packet(packet, len, &raw) == BL0939_OK;
        bl0939_reading_t r = {0};
        if (good)
            r = bl0939_convert(&raw, &scale);

        int adc_raw = 0, mv = -1;
        double celsius = NAN;
        bool have_temp = board_ntc_read(&adc_raw, &mv) == ESP_OK && ntc_celsius(&ntc, mv, &celsius);

        uint32_t zx = board_zx_edges();
        int64_t t = now_ms();
        double zx_hz = t > zx_last_ms ? (double)(zx - zx_last) * 1000.0 / (double)(t - zx_last_ms) : 0;
        zx_last = zx;
        zx_last_ms = t;

        take();
        if (good)
        {
            failures = 0;
            readings.have_meter = true;
            readings.volts = r.volts;
            readings.amps = r.amps_a;
            readings.watts = r.watts_a;
            if (!energy_update(&energy, raw.cfa_cnt, t))
                ESP_LOGW(TAG, "CF count jumped implausibly: rebaselined");
        }
        else
        {
            readings.meter_errors++;
            if (++failures >= METER_STALE_READS)
                readings.have_meter = false;
        }
        readings.have_temp = have_temp;
        readings.board_c = celsius;
        readings.have_zx = true;
        readings.zx_hz = zx_hz;
        give();

        // TODO(PETRO-5): the over-current trip (readings.amps against ctl.trip_amps, and the
        // BL0939's OC output through board_oc_edges) and the over-temperature trip (the NTC),
        // each calling app_trip(). Until then trips_enforced is false in the status.
        save_energy();
    }
}

// ---- status and responses (control task) --------------------------------------------------------

static bool publish_status(report_reason reason)
{
    app_state s;
    app_get_state(&s);
    int rssi = net_rssi();
    uint32_t stress = stress_left_s();
    status_view v = {
        .mode = s.mode,
        .relay = s.relay,
        .trip = s.trip,
        .remote = s.remote,
        .bench = s.bench,
        .cycle_active = s.cycle_active,
        .cycle_done = s.cycle_done,
        .cycle_n = s.cycle_n,
        .have_meter = s.have_meter,
        .volts = s.volts,
        .amps = s.amps,
        .watts = s.watts,
        .energy_kwh = s.energy_kwh,
        .have_temp = s.have_temp,
        .board_c = s.board_c,
        .have_zx = s.have_zx,
        .zx_hz = s.zx_hz,
        .trip_amps = s.trip_amps,
        .trip_amps_temporary = s.trip_amps_temporary,
        .trips_enforced = false,  // PETRO-5
        .stress = stress > 0,
        .stress_left_s = stress,
        .have_rssi = rssi != 0,
        .rssi = rssi,
        .uptime_s = (uint32_t)(esp_timer_get_time() / 1000000),
        .reason = reason,
        .version = esp_app_get_description()->version,
    };
    char text[STATUS_MAX];
    if (status_json(text, sizeof(text), &v) < 0)
    {
        ESP_LOGE(TAG, "status doesn't fit %u bytes", (unsigned)sizeof(text));
        return false;
    }
    bool ok = net_publish_status(text);
    report_sent(&reporter, now_ms(), reason, ok);
    return ok;
}

// {"type":..., "status":"ok"|"error", "message":...} (Fleet's envelope, as the heatlink's).
static void respond(const char *type, const char *status, const char *message)
{
    cJSON *msg = cJSON_CreateObject();
    if (msg == NULL)
        return;
    cJSON_AddStringToObject(msg, "type", type);
    if (status != NULL)
        cJSON_AddStringToObject(msg, "status", status);
    cJSON_AddStringToObject(msg, "message", message);
    char *text = cJSON_PrintUnformatted(msg);
    if (text != NULL)
        net_respond(text);
    cJSON_free(text);
    cJSON_Delete(msg);
}

static void respond_result(fleet_cmd_kind kind, ctl_result r)
{
    respond(fleet_cmd_result_type(kind), r == CTL_OK ? "ok" : "error", ctl_result_message(r));
}

static void handle_command(const char *json, size_t len)
{
    static fleet_cmd cmd;
    fleet_cmd_parse(json, len, &cmd);
    ctl_result r = CTL_OK;
    switch (cmd.kind)
    {
    case FLEET_CMD_GET_STATUS:
        publish_status(REPORT_REQUEST);
        break;
    case FLEET_CMD_RELAY:
        take();
        r = ctl_remote_relay(&ctl, cmd.on);
        apply_locked();
        give();
        ESP_LOGI(TAG, "Fleet: relay %s: %s", cmd.on ? "on" : "off", ctl_result_message(r));
        respond_result(cmd.kind, r);
        break;
    case FLEET_CMD_SET_MODE:
        r = app_set_mode(cmd.mode);
        ESP_LOGI(TAG, "Fleet: mode %s: %s", ctl_mode_name(cmd.mode), ctl_result_message(r));
        respond_result(cmd.kind, r);
        break;
    case FLEET_CMD_RELAY_CYCLE:
        take();
        r = ctl_remote_cycle(&ctl, cmd.n, cmd.on_ms, cmd.off_ms, now_ms());
        apply_locked();
        give();
        ESP_LOGI(TAG, "Fleet: relay cycle %lu x %lu/%lu ms: %s", (unsigned long)cmd.n, (unsigned long)cmd.on_ms,
                 (unsigned long)cmd.off_ms, ctl_result_message(r));
        respond_result(cmd.kind, r);
        break;
    case FLEET_CMD_RELAY_CYCLE_STOP:
        respond(fleet_cmd_result_type(cmd.kind), "ok", app_cycle_stop() ? "stopped, relay off" : "no cycle running");
        break;
    case FLEET_CMD_SET_TRIP:
    {
        take();
        r = ctl_set_trip_amps(&ctl, cmd.amps);
        double amps = ctl.trip_amps;
        give();
        char message[64];
        snprintf(message, sizeof(message), "trip threshold %.2f A (%s)", amps,
                 cmd.amps < 0 ? "the default" : "temporary, until a reboot");
        ESP_LOGI(TAG, "Fleet: %s", message);
        respond(fleet_cmd_result_type(cmd.kind), r == CTL_OK ? "ok" : "error",
                r == CTL_OK ? message : ctl_result_message(r));
        publish_status(REPORT_REQUEST);  // the thresholds in force
        break;
    }
    case FLEET_CMD_WIFI_STRESS:
        if (cmd.on && !stress_start(cmd.duration_s))
            respond(fleet_cmd_result_type(cmd.kind), "error", "out of memory");
        else
        {
            if (!cmd.on)
                stress_stop();
            respond(fleet_cmd_result_type(cmd.kind), "ok", cmd.on ? "Wi-Fi stress on" : "Wi-Fi stress off");
        }
        break;
    case FLEET_CMD_REBOOT:
        respond(fleet_cmd_result_type(cmd.kind), "ok", "rebooting");
        vTaskDelay(pdMS_TO_TICKS(RESTART_DELAY_MS));
        esp_restart();
        break;
    case FLEET_CMD_FLEET:
        ota_handle_command(json, len);
        break;
    case FLEET_CMD_ERROR:
        ESP_LOGW(TAG, "command refused: %s", cmd.message);
        respond("error", NULL, cmd.message);
        break;
    }
}

void app_on_command(const char *json, size_t len)
{
    if (len > CMD_MAX_LEN)
    {
        ESP_LOGW(TAG, "command of %u bytes refused", (unsigned)len);
        net_respond("{\"type\":\"error\",\"message\":\"Command too long\"}");
        return;
    }
    app_event ev = {.json = malloc(len + 1), .len = len};
    if (ev.json == NULL)
    {
        net_respond("{\"type\":\"error\",\"message\":\"Out of memory\"}");
        return;
    }
    memcpy(ev.json, json, len);
    ev.json[len] = '\0';
    if (queue == NULL || xQueueSend(queue, &ev, 0) != pdTRUE)
    {
        free(ev.json);
        net_respond("{\"type\":\"error\",\"message\":\"Busy: try again\"}");
    }
}

// ---- the control task ---------------------------------------------------------------------------

static void show_led(int64_t now, ctl_mode mode, bool relay, bool tripped)
{
    static bool shown;
    static uint8_t last[3];
    uint8_t rgb[3];
    taskENTER_CRITICAL(&led_lock);
    bool held = led_hold_until_ms != 0 && now < led_hold_until_ms;
    if (held)
        memcpy(rgb, led_hold_rgb, sizeof(rgb));
    taskEXIT_CRITICAL(&led_lock);
    if (!held)
    {
        led_inputs in = {
            .now_ms = now,
            .tripped = tripped,
            .ota = ota_busy(),
            .provisioned = provisioned,
            .wifi_up = net_wifi_up(),
            .mqtt_up = net_subscribed(),
            .mode = mode,
            .relay = relay,
        };
        led_rgb(led_show(&in), LED_LEVEL, &rgb[0], &rgb[1], &rgb[2]);
    }
    // Only changes go out: the RMT write is cheap, but not every 5 ms for nothing.
    if (!shown || memcmp(rgb, last, sizeof(rgb)) != 0)
    {
        if (board_led(rgb[0], rgb[1], rgb[2]) == ESP_OK)
        {
            shown = true;
            memcpy(last, rgb, sizeof(rgb));
        }
    }
}

// One loop: the button, the relay, the stored mode, the LED. Returns whether the mode, the relay
// or the trip changed (for the status).
static bool step(void)
{
    static ctl_mode last_mode;
    static bool last_relay, last_trip, first = true;
    int64_t now = now_ms();
    bool press = button_update(&button, board_button_pressed(), now) && !button_watched;

    take();
    if (press)
    {
        bool tripped = ctl.trip != CTL_TRIP_NONE;
        ctl_press(&ctl);
        ESP_LOGI(TAG, "button: %s", tripped ? "trip cleared, mode off" : ctl_mode_name(ctl.mode));
    }
    bool relay = apply_locked();
    ctl_mode mode = ctl.mode;
    bool tripped = ctl.trip != CTL_TRIP_NONE;
    bool cycling = ctl.cycle.active;
    give();

    if (!have_stored_mode || mode != stored_mode)
    {
        // The power-on state. A failed write is retried on the next change only (NVS is logged).
        if (store_set_mode(mode) == ESP_OK)
            ESP_LOGI(TAG, "mode %s stored", ctl_mode_name(mode));
        stored_mode = mode;
        have_stored_mode = true;
    }
    show_led(now, mode, relay, tripped);

    // A relay cycle's own switching isn't a change (500 cycles would be 1000 statuses); its end is.
    bool changed = !first && (mode != last_mode || (relay != last_relay && !cycling) || tripped != last_trip);
    if (changed)
        ESP_LOGI(TAG, "mode %s, relay %s%s", ctl_mode_name(mode), relay ? "on" : "off", tripped ? ", tripped" : "");
    first = false;
    last_mode = mode;
    last_relay = relay;
    last_trip = tripped;
    return changed;
}

static void control_task(void *arg)
{
    (void)arg;
    ESP_ERROR_CHECK(esp_task_wdt_add(NULL));
    for (;;)
    {
        esp_task_wdt_reset();
        app_event ev;
        if (xQueueReceive(queue, &ev, pdMS_TO_TICKS(BUTTON_POLL_MS)) == pdTRUE)
        {
            handle_command(ev.json, ev.len);
            free(ev.json);
        }
        bool changed = step();

        report_reason reason;
        if (provisioned &&
            report_due(&reporter, now_ms(), net_mqtt_connected(), changed, net_status_acked(), &reason))
            publish_status(reason);

        // The image is healthy once it can hear Fleet (subscribed, not just connected).
        if (!healthy && net_subscribed())
        {
            healthy = true;
            ota_mark_healthy();
        }
    }
}

// On every esp_restart (a reboot command, an OTA install): the relay off at once, and the energy
// since the last save kept. (A panic or a power cut skips this; the reset leaves the relay off.)
static void on_shutdown(void)
{
    board_relay(false);
    if (xSemaphoreTake(lock, pdMS_TO_TICKS(200)) == pdTRUE)
    {
        uint64_t mwh = energy_mwh(&energy);
        bool changed = mwh != energy.saved_mwh;
        xSemaphoreGive(lock);
        if (changed)
            store_set_energy_mwh(mwh);
    }
}

void app_start(bool is_provisioned)
{
    provisioned = is_provisioned;
    lock = xSemaphoreCreateMutex();
    queue = xQueueCreate(QUEUE_LEN, sizeof(app_event));
    if (lock == NULL || queue == NULL)
    {
        ESP_LOGE(TAG, "no memory for the control task");
        abort();
    }

    int mode = CTL_MODE_OFF;
    have_stored_mode = store_mode(&mode);
    ctl_init(&ctl, have_stored_mode, mode);
    stored_mode = ctl.mode;
    have_stored_mode = have_stored_mode && stored_mode == (ctl_mode)mode;
    energy_init(&energy, store_energy_mwh(), bl0939_petro_scale().pulses_per_kwh, now_ms());
    ESP_LOGI(TAG, "power-on mode %s%s, energy %.3f kWh", ctl_mode_name(ctl.mode),
             have_stored_mode ? "" : " (none stored)", energy_kwh(&energy));

    // Relay off (board_init) until this first decision: on only if the stored mode is on.
    button_init(&button);
    report_init(&reporter);
    applied_relay = false;
    take();
    apply_locked();
    give();

    esp_register_shutdown_handler(on_shutdown);
    if (xTaskCreate(control_task, "control", CONTROL_STACK, NULL, CONTROL_PRIORITY, NULL) != pdPASS ||
        xTaskCreate(meter_task, "meter", METER_STACK, NULL, METER_PRIORITY, NULL) != pdPASS)
    {
        ESP_LOGE(TAG, "no memory for the control or meter task");
        abort();
    }
}
