# Zatt, the Gate 4 thermal logger

A battery-powered ESP32 with an **MLX90640 55° (BAA)** thermal array and a **BMP280**, for Petro's
Gate 4 soak test ([`docs/testing/gate-4-load-thermal.md`](../../docs/testing/gate-4-load-thermal.md),
PETRO-7). It sits sealed in with a live mains board, touches nothing outside, and reports over Wi-Fi
to VictoriaMetrics. Named after Zatt, the youngling who solved the crystal cave by careful
observation (Martin's microcontrollers are Younglings). Device and vmauth user: `zatt-prod-zatt`.

ESP-IDF 5.5, target **ESP32-S3** (the S3-DevKitC-1). Changing target is
`idf.py set-target esp32c3` (or similar) and a check of the pins below in `menuconfig`.

## Wiring

| Zatt | MLX90640 | BMP280 |
|---|---|---|
| 3V3 | VIN (3.3 V) | VCC / VIN |
| GND | GND | GND |
| **GPIO8** | SDA | SDA |
| **GPIO9** | SCL | SCL |

- The pins are `CONFIG_ZATT_I2C_SDA_GPIO` / `_SCL_GPIO` (menuconfig: *Zatt thermal logger*). GPIO8 and
  9 are the S3-DevKitC-1's default I²C pair and are free on the board.
- Both parts share the bus: MLX90640 at **0x33**, BMP280 at **0x76** (SDO to GND) or 0x77 (SDO to
  VCC); the firmware tries both.
- **Pull-ups:** most breakouts (Adafruit, Pimoroni, SparkFun) carry 10k or 4k7 pull-ups, and two on
  one bus is fine. A bare chip needs 4k7 to 3V3 on each line. The firmware also enables the S3's
  internal ~45k pull-ups, which only help a bare line.
- **Clock:** 400 kHz by default (`CONFIG_ZATT_I2C_FREQ_HZ`), safe on jumper wires and ample for 2 Hz.
  The MLX90640 allows 1 MHz; try it with short wires and 4k7 pull-ups. If frames start failing
  (`MLX90640 frame read failed` in the log), go back to 400 kHz.
- **Power the MLX90640 at 3.3 V.** It draws about 23 mA, the whole logger about 100 to 150 mA with
  Wi-Fi.
- **Optional battery voltage:** enable `CONFIG_ZATT_BATTERY_ADC`, wire the battery through a divider
  (two equal resistors, 100k + 100k, to GPIO1, which is ADC1_CH0 on the S3) and leave the divider
  ratio at 200 %. Off by default; `zatt_battery_volts` is then not sent.

## Mounting

- Sensor **looking down at the board, about 130 mm above it**, on the lid of the Gate 4 hood: the
  55° field of view needs that to see all of a 120 × 80 mm board.
- **At least 10 mm from anything live**, and in the real case too (§3), where it only fits if that
  distance holds. Nothing conductive leaves the box: no USB cable while the mains board is powered.
  Charge or reflash with the hood open and the mains **unplugged**.
- Keep the lens clear. The BAA's 55° view is wide, so the walls of the hood are in frame at the
  edges; read the board, not the edges.
- Shiny metal reads far too low: mark each spot with Kapton tape or black marker (emissivity is set
  to 0.95 for those dots, `CONFIG_ZATT_EMISSIVITY_PERCENT`).
- Reflected temperature is taken as the sensor's own Ta minus 8 °C (Melexis' recommended shift,
  `CONFIG_ZATT_REFLECTED_SHIFT_C`). In a hood that warms up this is approximate; trust the Kapton
  spots over a bare-metal pixel.

## Battery

Any 3.7 V LiPo of about 1000 mAh or more through the DevKit's own regulator (or a small LiPo charger
board) gives a few hours: the test runs 60+ minutes plus the cool-down. A LiPo is comfortable at about
50 °C and shouldn't see more: keep the battery at the cool end of the hood, away from the board, and
below 60 °C always (charge it outside the hood, never on the live board). Check `zatt_battery_volts`
(if wired) in VictoriaMetrics. 3.3 V falling out of regulation, or a brown-out reset, shows as
`zatt_uptime_seconds` dropping.

## Build and flash

```bash
source ~/esp/esp-idf/export.sh        # ESP-IDF 5.5
idf.py -C tools/thermal-logger set-target esp32s3
idf.py -C tools/thermal-logger build
idf.py -C tools/thermal-logger -p /dev/cu.usbmodemXXXX flash monitor
```

(`~/esp/esp-idf` or `~/esp/v5.5/esp-idf`, whichever is 5.5.) The partition table needs a 4 MB flash
or more. Flash with `--after watchdog_reset` if you call esptool yourself.

The MLX90640 API is Melexis' own
([`melexis/mlx90640-library`](https://github.com/melexis/mlx90640-library), Apache-2.0, vendored
unmodified in `components/mlx90640/` at f6be7ca). The I²C glue is `main/mlx_i2c.c`. At start the
firmware reads the sensor's EEPROM and extracts the calibration parameters once, then runs chess mode
at 2 Hz, reading both subpages for each frame.

## Provisioning

Nothing secret is in the image. `scripts/provision.sh` builds the `prov` NVS partition (namespace
`zatt`; keys `wifi_ssid`, `wifi_pass`, `metrics_url`, `metrics_user`, `metrics_pass`, `http_token`)
and flashes it:

```bash
tools/thermal-logger/scripts/provision.sh /dev/cu.usbmodemXXXX
```

- The house Wi-Fi comes from SSM `/Nakomis/Wifi/*` (`WIFI_PROFILE`, default `nakom.is-sandbox`).
- The vmauth password comes from SSM `/vmauth/device-zatt-prod-zatt-password` (`METRICS_PROFILE`,
  default `nakom.is-admin`, eu-west-2). **That parameter, and the `zatt-prod-zatt` user in
  `vmauth_devices` (home-infra PR), must exist first**; without the password the script warns and
  provisions without metrics.
- The script makes the HTTP token once and keeps it in `certs/zatt-prod-zatt/http_token`
  (gitignored, mode 600). Nothing secret is printed.
- Plain text in flash, on a LAN-only device, like the house's other test devices.

## Mapping the spots (Gate 4 §2)

1. With Zatt on the LAN (the log prints `up at http://<ip>/`; or find `zatt` in the router), open
   `http://<ip>/` over a view of the board with the marks on.
2. The page draws the 32 × 24 frame as a heatmap (auto-scaled). **Hover** for pixel `x, y` and its
   temperature. Pixel (0, 0) is top left as the sensor reports it; warm one with a hand to check the
   orientation before relying on it.
3. Pick a spot (T1 to T7) in the menu, **drag** a rectangle over its Kapton dot, enter the token (from
   `certs/zatt-prod-zatt/http_token`; the browser remembers it) and **Save spot**. It is stored in
   NVS and survives a reboot. *Clear spot* disables it.
4. T1 to T7 are as in the Gate 4 table: T1 J1's live screw, T2 J2's, T3 F1's clip, T4 K1's case,
   T5 the shunt and its pour (about one pixel, so it reads low), T6 the L_F pour, T7 R1.
5. Alternatively set defaults in menuconfig (*Default spot rectangles*, `x0,y0,x1,y1` inclusive);
   whatever is saved from the page overrides them. They start empty (disabled).

### HTTP API

- `GET /` the page. `GET /frame.json`
  `{"w":32,"h":24,"frames":n,"up":s,"ta":..,"air":..,"pa":..,"spots":{"T1":[x0,y0,x1,y1]|null,...},"data":[768 floats, row-major]}`.
  Both are **unauthenticated and LAN-only**: anyone on the Wi-Fi can see a temperature picture of the
  inside of the box. Don't forward the port.
- `POST /spots` with `Authorization: Bearer <http_token>` and a body such as
  `{"T1":[10,4,11,5],"T3":null}` (only those spots change; `null` disables). It is refused (403)
  when no token is in prov, and 401 for a wrong one. The token travels in clear on the LAN.

## Metrics

Prometheus text POSTed every 10 s (`CONFIG_ZATT_PUSH_INTERVAL_S`) to
`http://172.29.0.33:8427/api/v1/import/prometheus` with basic auth (user `zatt-prod-zatt`). vmauth
forces the `host_name` label.

| Metric | Meaning |
|---|---|
| `zatt_frame_max_celsius`, `_min_`, `_mean_` | over all 768 pixels |
| `zatt_hot_x`, `zatt_hot_y` | the hottest pixel's coordinates |
| `zatt_spot_celsius{spot="T1"}` ... `T7` | mean of the spot's rectangle (only spots that are set) |
| `zatt_spot_max_celsius{spot="T1"}` ... | hottest pixel in the rectangle |
| `zatt_ambient_celsius` | the MLX90640's own die temperature (Ta) |
| `zatt_air_celsius`, `zatt_pressure_pascals` | BMP280 |
| `zatt_battery_volts` | only if `CONFIG_ZATT_BATTERY_ADC` |
| `zatt_wifi_rssi_dbm`, `zatt_uptime_seconds` | health |

A sensor that is absent just leaves its metrics out. A failed push is dropped, not retried.

## Tests

The portable parts (Prometheus text, frame and spot statistics, rectangle parsing, the BMP280
compensation against the datasheet's worked example) are in `components/zatt_core/` and
`tests/test_core.c`; run `python3 -m pytest tools/thermal-logger/tests` (needs a host `cc`).
The vendored MLX90640 library and the hardware glue are not host-tested.
