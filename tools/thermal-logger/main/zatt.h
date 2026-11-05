// Zatt, the Gate 4 thermal logger: the pieces main.c wires together.
#ifndef ZATT_MAIN_H
#define ZATT_MAIN_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#include "driver/i2c_master.h"
#include "esp_err.h"
#include "thermal.h"

// ---- prov: settings from the "prov" NVS partition, namespace "zatt" (scripts/provision.sh) ----
typedef struct
{
    char wifi_ssid[33];
    char wifi_pass[65];
    char metrics_url[128];  // base URL, e.g. http://172.29.0.33:8427
    char metrics_user[33];
    char metrics_pass[65];
    char http_token[65];
    bool ok;  // false if the partition or namespace is missing (nothing will connect)
} prov_t;

void prov_load(prov_t *p);

// ---- wifi ----
void wifi_start(const prov_t *p);
bool wifi_connected(void);
int wifi_rssi(void);  // dBm, or 0 when not connected

// ---- i2c: one bus for the MLX90640 (0x33) and the BMP280 (0x76 or 0x77) ----
esp_err_t i2c_bus_start(void);
i2c_master_bus_handle_t i2c_bus(void);

// ---- bmp280 ----
esp_err_t bmp280_start(void);  // probes 0x76 then 0x77
esp_err_t bmp280_read(float *temp_c, float *pressure_pa);

// ---- sensors: the task that owns the I2C bus and keeps the latest frame ----
typedef struct
{
    float to[ZATT_PIXELS];  // object temperatures, degC; pixel (x, y) at y * 32 + x
    float ta;               // the MLX90640's own die temperature, degC (NAN until the first frame)
    float air;              // BMP280 temperature, degC (NAN if absent)
    float pressure;         // BMP280 pressure, Pa (NAN if absent)
    uint32_t frames;        // complete frames (both subpages) since boot; 0 means no data yet
    int64_t frame_us;       // esp_timer time of the last frame
} zatt_snapshot_t;

void sensors_start(void);
void sensors_snapshot(zatt_snapshot_t *out);  // a consistent copy; out->frames == 0 before the first frame

// ---- spots: T1..T7 pixel rectangles, defaults from Kconfig, overridden from NVS ----
const char *spots_name(int i);  // "T1".."T7"
void spots_load(void);
zatt_rect_t spots_get(int i);
// Sets spot i (and saves all to NVS). A disabled rect clears it.
esp_err_t spots_set(int i, zatt_rect_t r);
int spots_index(const char *name);  // -1 if unknown

// ---- battery (optional, CONFIG_ZATT_BATTERY_ADC) ----
bool battery_volts(float *v);  // false if not configured or unreadable

// ---- metrics: the push every CONFIG_ZATT_PUSH_INTERVAL_S ----
void metrics_start(const prov_t *p);

// ---- web: GET /, GET /frame.json, POST /spots ----
void web_start(const prov_t *p);

#endif
