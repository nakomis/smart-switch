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
#include "prot.h"
#include "relay.h"
#include "report.h"
#include "sdkconfig.h"
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
#define METER_PRIORITY 9    // the protection's readings: above the control task too
#define METER_PERIOD_MS 250  // the BL0939's RMS updates every 400 ms; a read takes about 77 ms
#define METER_STALE_READS 12  // failed reads in a row (3 s) before V/A/W go unknown
#define ZX_HZ_READS 4        // zx_hz over this many reads (1 s)
#define TRIP_STACK 3072
#define TRIP_PRIORITY 10    // the OC interrupt's follow-up: above everything of ours
#define RESTART_DELAY_MS 2000  // for the response to reach IoT Core first
#define STATUS_MAX 768
#define STORE_RETRY_MS 5000  // a failed NVS write of the mode or the trip latch is retried this often

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
static prot_t prot;
static ctl_trip_cause seen_trip;   // the latch as last counted and stored
static bool trip_store_pending;    // the latch's NVS write failed: retried by the control task
static int64_t trip_retry_at_ms;
static ctl_trip_cause trip_to_log; // a new trip or a clear, logged by the control task (not under lock)
static bool trip_log_pending;
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
static int64_t store_retry_at_ms;
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

// The protection's view into ctl: the sensors' health (relay-on refused without it) and whether a
// clear would be refused (the NTC's hysteresis, OC still active). Under the lock.
static void sync_locked(int64_t now)
{
    prot_oc(&prot, board_oc_active());
    ctl_set_sensors_ok(&ctl, prot_healthy(&prot, now));
    ctl_set_clear_blocked(&ctl, prot_clear_blocked(&prot, ctl.trip, now));
}

// Every locked section starts with ctl in step with the protection.
static void take(void)
{
    xSemaphoreTake(lock, portMAX_DELAY);
    sync_locked(now_ms());
}

static void give(void)
{
    xSemaphoreGive(lock);
}

// The latch in NVS, so a reboot doesn't clear it. Under the lock (it's rare, and the relay is
// already open); a failure is retried by the control task.
static void store_trip_locked(int64_t now)
{
    trip_store_pending = store_set_trip(ctl.trip) != ESP_OK;
    trip_retry_at_ms = now + STORE_RETRY_MS;
}

// Drives the relay to what ctl and the protection say now, tripping first if the protection calls
// for it. Called with the lock held, by whichever task changed ctl or read the meter, so a command
// or a trip acts at once rather than on the next loop. Trips, the shutdown and the health gate
// switch at once; everything else at the next zero crossing (relay.h).
static bool apply_locked(void)
{
    int64_t now = now_ms();
    sync_locked(now);
    bool wanted = ctl_relay(&ctl, now);
    ctl_trip(&ctl, prot_check(&prot, wanted, now));  // CTL_TRIP_NONE does nothing
    wanted = ctl_relay(&ctl, now);
    bool relay = wanted && prot_healthy(&prot, now);  // held open while starting up
    if (relay != applied_relay)
    {
        relay_set(relay, !relay && (ctl.trip != CTL_TRIP_NONE || ctl.shutdown || wanted));
        applied_relay = relay;
    }
    if (ctl.trip == CTL_TRIP_NONE && board_oc_held())
        board_oc_release();  // cleared: the relay may close again
    if (ctl.trip != seen_trip)
    {
        if (ctl.trip != CTL_TRIP_NONE)
            store_count_trip(ctl.trip);
        seen_trip = ctl.trip;
        trip_to_log = ctl.trip;
        trip_log_pending = true;
        store_trip_locked(now);
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
    ctl_trip(&ctl, cause);
    apply_locked();  // opens the relay, counts and stores the latch
    give();
}

void app_get_state(app_state *out)
{
    memset(out, 0, sizeof(*out));
    take();
    int64_t now = now_ms();
    out->mode = ctl.mode;
    out->relay = board_relay_is_on();
    out->trip = ctl.trip;
    out->remote = ctl_accepts_remote(&ctl);
    out->bench = ctl.bench;
    out->cycle_active = ctl.cycle.active;
    out->cycle_done = ctl.cycle.done;
    out->cycle_n = ctl.cycle.n;
    out->trip_amps = ctl.trip_amps;
    out->trip_amps_temporary = ctl_trip_amps_temporary(&ctl);
    out->instant_amps = ctl.instant_amps;
    out->instant_amps_temporary = ctl_instant_amps_temporary(&ctl);
    out->overtemp_c = prot.cfg.overtemp_c;
    out->meter_ok = prot_healthy(&prot, now);
    out->meter_starting = prot_starting(&prot, now);
    out->bl_configured = prot.meter_init;
    out->oc_active = prot.oc_active;
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
    out->zx_sync = relay_zx_sync();
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

// The meter and the protection's readings, every 250 ms at a priority above the control task and
// the network. Each reading goes straight to prot and apply_locked, so a sustained over-current
// trips within one read of its 2 s; the watchdog resets Petro (relay off) if this task stops.
static void meter_task(void *arg)
{
    (void)arg;
    ESP_ERROR_CHECK(esp_task_wdt_add(NULL));
    const bl0939_scale_t scale = bl0939_petro_scale();
    const ntc_params_t ntc = ntc_petro_params();
    int failures = 0, reads = 0;
    uint32_t zx_last = board_zx_edges();
    int64_t zx_last_ms = now_ms();
    TickType_t wake = xTaskGetTickCount();
    for (;;)
    {
        vTaskDelayUntil(&wake, pdMS_TO_TICKS(METER_PERIOD_MS));
        esp_task_wdt_reset();
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

        int64_t t = now_ms();
        bool zx_due = ++reads % ZX_HZ_READS == 0;
        double zx_hz = 0;
        if (zx_due)
        {
            uint32_t zx = board_zx_edges();
            zx_hz = t > zx_last_ms ? (double)(zx - zx_last) * 1000.0 / (double)(t - zx_last_ms) : 0;
            zx_last = zx;
            zx_last_ms = t;
        }

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
            // Both channels read the same shunt: the larger counts.
            prot_frame(&prot, fmax(r.amps_a, r.amps_b), ctl.trip_amps, t);
        }
        else
        {
            readings.meter_errors++;
            if (++failures >= METER_STALE_READS)
                readings.have_meter = false;
        }
        readings.have_temp = have_temp;
        readings.board_c = celsius;
        prot_temp(&prot, have_temp, celsius, t);
        if (zx_due)
        {
            readings.have_zx = true;
            readings.zx_hz = zx_hz;
        }
        apply_locked();  // the trips (prot_check), and the relay held open while unhealthy
        give();

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
        .meter_ok = s.meter_ok,
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
        .instant_amps = s.instant_amps,
        .instant_amps_temporary = s.instant_amps_temporary,
        .overtemp_c = s.overtemp_c,
        .trips_enforced = true,
        .zx_sync = s.zx_sync,
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
        take();
        r = ctl_remote_mode(&ctl, cmd.mode);  // off only
        apply_locked();
        give();
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
        if (cmd.set_amps)
            r = ctl_set_trip_amps(&ctl, cmd.amps);
        if (r == CTL_OK && cmd.set_instant)
            r = ctl_set_instant_amps(&ctl, cmd.instant_amps);
        double amps = ctl.trip_amps, instant = ctl.instant_amps;
        bool temp_amps = ctl_trip_amps_temporary(&ctl), temp_instant = ctl_instant_amps_temporary(&ctl);
        give();
        // The instant threshold lives in the BL0939 (a UART write and read-back, outside the lock).
        esp_err_t err = ESP_OK;
        if (r == CTL_OK && cmd.set_instant)
        {
            err = board_bl_set_instant(instant);
            take();
            prot_meter_init(&prot, board_bl_configured());
            apply_locked();  // unconfigured: the meter is unhealthy and the relay opens
            give();
        }
        char message[128];
        if (err != ESP_OK)
            snprintf(message, sizeof(message), "the BL0939 didn't take %.2f A (%s): the relay stays off", instant,
                     esp_err_to_name(err));
        else
            snprintf(message, sizeof(message), "trip thresholds %.2f A over 2 s (%s), %.2f A instant (%s)", amps,
                     temp_amps ? "temporary, until a reboot" : "the default", instant,
                     temp_instant ? "temporary, until a reboot" : "the default");
        ESP_LOGI(TAG, "Fleet: %s", r == CTL_OK ? message : ctl_result_message(r));
        respond(fleet_cmd_result_type(cmd.kind), r == CTL_OK && err == ESP_OK ? "ok" : "error",
                r == CTL_OK ? message : ctl_result_message(r));
        publish_status(REPORT_REQUEST);  // the thresholds in force
        break;
    }
    case FLEET_CMD_CLEAR_TRIP:
    {
        take();
        bool was = ctl.trip != CTL_TRIP_NONE;
        r = ctl_clear_trip(&ctl);
        apply_locked();
        give();
        ESP_LOGI(TAG, "Fleet: clear trip: %s", ctl_result_message(r));
        respond(fleet_cmd_result_type(cmd.kind), r == CTL_OK ? "ok" : "error",
                r != CTL_OK ? ctl_result_message(r) : was ? "cleared, relay off" : "no trip latched");
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
    bool was_tripped = ctl.trip != CTL_TRIP_NONE;
    ctl_result pressed = CTL_OK;
    if (press)
        pressed = ctl_press(&ctl);
    bool relay = apply_locked();  // also the protection's checks, should the meter task stop
    ctl_mode mode = ctl.mode;
    bool tripped = ctl.trip != CTL_TRIP_NONE;
    bool cycling = ctl.cycle.active;
    if (trip_store_pending && now >= trip_retry_at_ms)
        store_trip_locked(now);
    bool log_trip = trip_log_pending;
    ctl_trip_cause logged = trip_to_log;
    trip_log_pending = false;
    give();

    if (press)
        ESP_LOGI(TAG, "button: %s", !was_tripped ? ctl_mode_name(mode)
                                    : pressed == CTL_OK ? "trip cleared, relay off"
                                                        : ctl_result_message(pressed));
    if (log_trip && logged != CTL_TRIP_NONE)
        ESP_LOGW(TAG, "TRIP: %s, relay open", ctl_trip_name(logged));
    else if (log_trip)
        ESP_LOGI(TAG, "trip cleared");

    // The power-on state, kept in NVS. A failed write (logged by store.c) is retried every
    // STORE_RETRY_MS until it succeeds. (The trip latch is stored by apply_locked.)
    if ((!have_stored_mode || mode != stored_mode) && now >= store_retry_at_ms)
    {
        if (store_set_mode(mode) == ESP_OK)
        {
            ESP_LOGI(TAG, "mode %s stored", ctl_mode_name(mode));
            stored_mode = mode;
            have_stored_mode = true;
            store_retry_at_ms = 0;
        }
        else
            store_retry_at_ms = now + STORE_RETRY_MS;
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
// The OC interrupt (board.c) has already opened the relay: latch, count and store the trip.
static void trip_task(void *arg)
{
    (void)arg;
    for (;;)
    {
        ulTaskNotifyTake(pdTRUE, portMAX_DELAY);
        app_trip(CTL_TRIP_OVERCURRENT_INSTANT);
    }
}

static void on_shutdown(void)
{
    relay_set(false, true);
    if (xSemaphoreTake(lock, pdMS_TO_TICKS(200)) == pdTRUE)
    {
        ctl_shutdown(&ctl);  // nothing re-closes it before the reset
        apply_locked();
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
    ctl_init(&ctl, have_stored_mode, mode, store_trip());
    seen_trip = ctl.trip;  // a stored latch is not a new trip
    prot_config cfg = prot_defaults();
    cfg.overtemp_c = CONFIG_PETRO_OVERTEMP_C;
    prot_init(&prot, &cfg, now_ms());
    prot_meter_init(&prot, board_bl_configured());
    if (!board_bl_configured())
        ESP_LOGE(TAG, "the BL0939 isn't configured: the relay stays off (meter fault)");
    if (relay_init() != ESP_OK)
        ESP_LOGE(TAG, "relay timer: switching without zero-cross timing");
    if (ctl.trip != CTL_TRIP_NONE)
        ESP_LOGW(TAG, "a %s trip is still latched: relay open until the button is pressed",
                 ctl_trip_name(ctl.trip));
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
    TaskHandle_t trip_handle = NULL;
    if (xTaskCreate(trip_task, "trip", TRIP_STACK, NULL, TRIP_PRIORITY, &trip_handle) != pdPASS ||
        xTaskCreate(control_task, "control", CONTROL_STACK, NULL, CONTROL_PRIORITY, NULL) != pdPASS ||
        xTaskCreate(meter_task, "meter", METER_STACK, NULL, METER_PRIORITY, NULL) != pdPASS)
    {
        ESP_LOGE(TAG, "no memory for the control, meter or trip task");
        abort();
    }
    // The instant trip, armed with the relay still open (board_oc_arm takes the idle level now).
    if (board_bl_configured())
        ESP_LOGI(TAG, "instant trip armed: OC active %s", board_oc_arm(trip_handle) ? "high" : "low");
}
