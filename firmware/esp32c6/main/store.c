// What Petro keeps across reboots. See store.h.
#include "store.h"

#include <string.h>

#include "esp_log.h"
#include "esp_system.h"
#include "nvs.h"

static const char *TAG = "store";

#define NAMESPACE "state"
#define KEY_MODE "mode"
#define KEY_ENERGY "energy_mwh"
#define KEY_RESETS "resets"
#define KEY_TRIPS "trips"
#define KEY_LATCHED "trip_latched"

static const char *const reset_names[STORE_RESET_REASONS] = {
    [ESP_RST_UNKNOWN] = "unknown",     [ESP_RST_POWERON] = "poweron",
    [ESP_RST_EXT] = "external",        [ESP_RST_SW] = "software",
    [ESP_RST_PANIC] = "panic",         [ESP_RST_INT_WDT] = "int_wdt",
    [ESP_RST_TASK_WDT] = "task_wdt",   [ESP_RST_WDT] = "wdt",
    [ESP_RST_DEEPSLEEP] = "deepsleep", [ESP_RST_BROWNOUT] = "brownout",
    [ESP_RST_SDIO] = "sdio",           [ESP_RST_USB] = "usb",
    [ESP_RST_JTAG] = "jtag",           [ESP_RST_EFUSE] = "efuse",
    [ESP_RST_PWR_GLITCH] = "power_glitch", [ESP_RST_CPU_LOCKUP] = "cpu_lockup",
};

static nvs_handle_t nvs;
static bool nvs_ok;
static uint32_t resets[STORE_RESET_REASONS];
static uint32_t trips[CTL_TRIP_CAUSES];
static unsigned this_reset;

static esp_err_t commit(esp_err_t err)
{
    if (err == ESP_OK)
        err = nvs_commit(nvs);
    if (err != ESP_OK)
        ESP_LOGW(TAG, "write failed: %s", esp_err_to_name(err));
    return err;
}

// A blob of up to size bytes; a shorter one (from an older image: 0.2.x stored two trip causes,
// 0.3.0 four) is kept and the rest zeroed.
static void load_blob(const char *key, void *out, size_t size)
{
    size_t len = 0;
    memset(out, 0, size);
    if (nvs_get_blob(nvs, key, NULL, &len) != ESP_OK || len > size || nvs_get_blob(nvs, key, out, &len) != ESP_OK)
        memset(out, 0, size);
}

void store_init(void)
{
    esp_err_t err = nvs_open(NAMESPACE, NVS_READWRITE, &nvs);
    nvs_ok = err == ESP_OK;
    unsigned reason = (unsigned)esp_reset_reason();
    this_reset = reason < STORE_RESET_REASONS ? reason : ESP_RST_UNKNOWN;
    if (!nvs_ok)
    {
        ESP_LOGE(TAG, "nvs namespace %s: %s (nothing persists this boot)", NAMESPACE, esp_err_to_name(err));
        resets[this_reset] = 1;
        return;
    }
    load_blob(KEY_RESETS, resets, sizeof(resets));
    load_blob(KEY_TRIPS, trips, sizeof(trips));
    resets[this_reset]++;
    commit(nvs_set_blob(nvs, KEY_RESETS, resets, sizeof(resets)));
    ESP_LOGI(TAG, "reset reason %s (%lu so far)", reset_names[this_reset], (unsigned long)resets[this_reset]);
}

bool store_mode(int *mode)
{
    uint8_t m;
    if (!nvs_ok || nvs_get_u8(nvs, KEY_MODE, &m) != ESP_OK)
        return false;
    *mode = m;
    return true;
}

esp_err_t store_set_mode(ctl_mode mode)
{
    if (!nvs_ok)
        return ESP_ERR_INVALID_STATE;
    return commit(nvs_set_u8(nvs, KEY_MODE, (uint8_t)mode));
}

uint64_t store_energy_mwh(void)
{
    uint64_t v = 0;
    if (nvs_ok)
        nvs_get_u64(nvs, KEY_ENERGY, &v);
    return v;
}

esp_err_t store_set_energy_mwh(uint64_t mwh)
{
    if (!nvs_ok)
        return ESP_ERR_INVALID_STATE;
    return commit(nvs_set_u64(nvs, KEY_ENERGY, mwh));
}

const uint32_t *store_reset_counts(void)
{
    return resets;
}

const char *const *store_reset_names(void)
{
    return reset_names;
}

uint32_t store_trips(ctl_trip_cause cause)
{
    return cause == CTL_TRIP_NONE ? 0 : trips[cause - 1];
}

esp_err_t store_count_trip(ctl_trip_cause cause)
{
    if (cause == CTL_TRIP_NONE)
        return ESP_ERR_INVALID_ARG;
    trips[cause - 1]++;
    if (!nvs_ok)
        return ESP_ERR_INVALID_STATE;
    return commit(nvs_set_blob(nvs, KEY_TRIPS, trips, sizeof(trips)));
}

int store_trip(void)
{
    uint8_t v = CTL_TRIP_NONE;
    if (nvs_ok)
        nvs_get_u8(nvs, KEY_LATCHED, &v);
    return v;
}

esp_err_t store_set_trip(ctl_trip_cause cause)
{
    if (!nvs_ok)
        return ESP_ERR_INVALID_STATE;
    return commit(nvs_set_u8(nvs, KEY_LATCHED, (uint8_t)cause));
}

const char *store_reset_reason(void)
{
    return reset_names[this_reset];
}
