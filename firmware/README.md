# Firmware

ESP-IDF 5.5 firmware for the ESP32-C6-WROOM-1, from the nakostat heatlink firmware's patterns:
portable C under `port/` with pytest host tests, and the IDF project under `esp32c6/`. Work items:
PETRO-3 (core), PETRO-4 (metering), PETRO-5 (protection).

PETRO-3 is the core: the bench console Gate 2 needs (slice 1), then the mode on SW1, the LED's
status patterns, Wi-Fi, Fleet over MQTT, OTA with rollback and the VictoriaMetrics push (slice 3).
PETRO-4 calibrates the metering; PETRO-5 adds the trips, whose hook is in place (`TODO(PETRO-5)`).

## Layout

| Path | What's there |
|---|---|
| `port/` | Portable C11, no IDF: `bl0939` (frames, packet checksum and layout, scaling for the 1 mΩ shunt and the 1.95 MΩ / 470 Ω divider, the chip's temperature), `ntc` (TH1, 10 k, B 3950, under 10 k from 3V3), `console_parse` (the console's command lines), `ctl` (the mode, the relay, the trip latch, relay cycle), `button` (SW1's debounce), `led` (the status patterns), `fleet_cmd` (Petro's Fleet commands), `ota_cmd` and `report` (Fleet's OTA protocol and when to publish the status, from the heatlink), `status_json`, `prom` (the metrics text and push URL), `energy` (the CF-count total) |
| `tools/` | Host drivers, one per module: `<name>_main.c` becomes `build/petro-<name>`, reading commands on stdin and answering in JSON |
| `tests/` | pytest over the drivers (`conftest.py` builds them once a session), and `coverage.sh` |
| `CMakeLists.txt` | The host build: every `port/*.c` into `petro_port`, every `tools/*_main.c` a driver |
| `esp32c6/` | The IDF project: `main/` (`board.c` the hardware, `app.c` the control and meter tasks, `net.c` Wi-Fi and MQTT, `ota.c` Fleet's OTA, `metrics.c` the VictoriaMetrics push, `stress.c` Gate 3's Wi-Fi stress, `store.c` what persists, `console.c` the commands, `prov.c` the `prov` reader, `petro_pins.h`), `AmazonRootCA1.pem`, `partitions.csv`, `sdkconfig.defaults`, `version.txt` |

`esp32c6/main/petro_pins.h` is a **copy** of `pcb/out/petro/pins.h` (the board generator's output),
so the firmware never builds from `pcb/out`. `tests/test_pins.py` fails if the two drift apart:
copy the header again after regenerating the board. Note the UART names are the BL0939's: `BL_TX`
(GPIO10) is its TX and our RX, `BL_RX` (GPIO11) its RX and our TX.

## Host tests

```bash
brew install cjson                # the command parsers' JSON (IDF has its own copy)
python -m pip install -r firmware/tests/requirements.txt
TEST_MAX_WORKERS=2 python -m pytest -q firmware/tests
firmware/tests/coverage.sh        # line coverage of port/ (gcov, or llvm-cov gcov on macOS)
```

`TEST_MAX_WORKERS` caps the build's parallel jobs (and `-n`, if you add pytest-xdist).

## Build and flash

```bash
. ~/esp/v5.5/esp-idf/export.sh
idf.py -C firmware/esp32c6 set-target esp32c6     # once
idf.py -C firmware/esp32c6 build
idf.py -C firmware/esp32c6 -p <port> flash monitor
```

or, with the image already built, from `firmware/esp32c6/build`:
`esptool --chip esp32c6 -p <port> --after watchdog_reset write_flash @flash_args`. **USB only, with
the mains unplugged**: the whole board is at mains potential when it's plugged in.

SW1 is on GPIO9, the boot strap: held while the board resets, it puts the C6 into download mode.
Release it before resetting unless that's what you want.

Bump `esp32c6/version.txt` with every firmware change. `sdkconfig`, `build/` and
`managed_components/` are not committed; `sdkconfig.defaults` and `dependencies.lock` are.

## Provisioning

Credentials live only in the `prov` NVS partition (0x12000, 24 KB), namespace `petro`, written by
the provisioning script (with Fleet, slice 3): `wifi_ssid`, `wifi_pass`, `endpoint`, `thing`,
`cert`, `key`, `metrics_url`, `metrics_user`, `metrics_pass`. The firmware only reads it, and
`info` lists which keys are present, never their values.

## The console

On the C6's USB-Serial-JTAG (J4), prompt `petro>`:

| Command | Does |
|---|---|
| `info` | Firmware version, MAC, chip revision, reset reason, uptime, the mode, the relay (and any bench override or cycle), the trip and the threshold in force, the trip counts, the meter's last reading and the energy total, the network, which `prov` keys are present |
| `mode on` / `mode off` / `mode auto` | Sets the mode, as the button does (stored: the power-on state). `mode off` also clears a trip |
| `relay on` / `relay off` | Drives the relay directly: a **bench override**, never stored, until the next press, mode change, remote relay command or trip. `relay on` is refused while a trip is latched |
| `relay cycle <n> <on_ms> <off_ms>` | Cycles it n times (1–10000, 50–60000 ms each, an hour at most in all), in any mode, leaving it off (a bench override). Any key, a press, a mode change or a trip stops it, relay off |
| `led <r> <g> <b>` / `led auto` | Holds the LED at a colour (0–255 each) for 60 s / gives it back to the status patterns |
| `button` | Logs SW1's presses and releases for 10 s (20 ms debounce). Presses don't change the mode meanwhile |
| `bl` | Three full-packet reads of the BL0939, 0.5 s apart: whether each frame's checksum was good, then V, IA, IB, PA, PB raw and scaled, the CF counts and the chip's temperature |
| `edges` | ZX and OC edges (rising and falling) in each of two seconds: about 100 a second on 50 Hz mains, 0 on USB |
| `ntc` | The NTC's averaged ADC code, calibrated mV, resistance and °C |
| `wifi scan` | SSIDs, channels and RSSI (scan only; UK channels 1–13) |
| `j3` | Toggles OUT at 1 Hz for 5 s, printing IN each half second, then scans I²C 0x08–0x77 |
| `help` | The list |

## Behaviour

**The mode** is off, on or auto (CLAUDE.md, Control). SW1 steps it **on → off → auto → on**
(Martin's decision): from off, two presses (off → auto → on) close the relay; from on, one press
opens it. A press counts once it has held 30 ms (5 ms polls).

- **on** and **off** are local overrides: the relay follows the mode, and Fleet's relay commands
  are refused (`"status":"error"`, "the mode is a local override").
- **auto** follows Fleet (and Alexa, later). Entering auto, by any route, starts with the relay
  open until a command closes it.
- The mode is stored in NVS (the default `nvs` partition, namespace `state`) at every change and is
  the **power-on state**: a unit left on closes its relay as soon as it boots (README rule 8). In
  auto the relay starts open. Nothing stored means off.
- **A trip** (PETRO-5) opens the relay and latches: every remote command that would close it is
  refused. A press clears it and leaves the relay off (the mode goes to off); so does `set_mode
  off`. A temporary trip threshold from Fleet lives in RAM only: every boot starts at 10.5 A.

**The relay** is latched low before anything else at boot, and every reset leaves it open (the
gate's 100 k pull-down; the GPIO resets to an input). Only the control task drives it from the
mode; it runs every 5 ms at priority 8, above MQTT (5), the OTA download (4), the metrics push (2)
and the Wi-Fi stress (1), and is watched by the 5 s task watchdog (a hang panics and restarts,
relay off). Every `esp_restart` opens the relay and saves the energy total first. Nothing on the
control task waits on the network: publishing only copies into a queue.

**Unprovisioned** (`prov` empty or incomplete): no network; the console, the button and the relay
still work, and the LED says so. Without the metrics keys, metrics are off and nothing else changes.

### The LED

In priority order (brightness 64 of 255):

| Shows | When |
|---|---|
| Red, blinking 4 Hz | A trip is latched (press the button to clear it) |
| Cyan, blinking 2 Hz | An OTA update is downloading or installing |
| White, steady | The first 1.5 s after boot |
| Magenta alternating with the mode's colour, 1 Hz | Not provisioned (console only) |
| The mode's colour, blinking 1 Hz | Joining Wi-Fi |
| The mode's colour, blinking 4 Hz | Wi-Fi up, connecting to IoT Core |
| The mode's colour, steady | Connected to Fleet |

The mode's colours: **off amber, on green, auto blue** (bright with the relay closed, dim while
auto holds it open). The console's `led` overrides all of this for 60 s.

## Fleet

As the heatlink and tinycrypt: MQTT over TLS to AWS IoT Core on 8883 (Amazon Root CA 1 in the
image; the Thing's certificate and key from `prov`), client ID the Thing name, a clean session that
subscribes to `petro/<thing>/commands` on every connect. Replies go to `petro/<thing>/responses`
and the status to `petro/<thing>/status`, both QoS 1. Fleet's message shapes are unchanged
(nakomis-fleet `docs/architecture/design.md`); Fleet adds its registry row on the first publish.

**Fleet's own commands:** `get_version` (answered `{"type":"version","version","project":"petro"}`,
also sent on every connect), `ping` (`pong`), and `ota_update` / `url_chunk` / `ota_cancel` (OTA,
below).

**Petro's commands**, each answered `{"type":"<command>_result","status":"ok"|"error","message"}`
(a malformed or unknown one `{"type":"error","message"}`):

| Command | Does |
|---|---|
| `{"command":"get_status"}` | Publishes a status now (`"reason":"request"`) |
| `{"command":"relay","on":true}` | The relay, in auto only |
| `{"command":"set_mode","mode":"off"}` | `on`, `off` or `auto`, stored; `off` also clears a trip |
| `{"command":"relay_cycle","n":500,"on_ms":3000,"off_ms":5000}` | Auto only. n 1–10000, 50–60000 ms each, **two hours at most in all** (Gate 4's 500 × 8 s is about 67 minutes; the console's cap stays at one hour). Leaves the relay open |
| `{"command":"relay_cycle_stop"}` | Stops a cycle, relay open |
| `{"command":"set_trip_threshold","amps":6.5}` | A **temporary** over-current threshold, 0.5–10.5 A (never above the default), RAM only, gone after a reboot; `"amps":null` restores 10.5 A. A status follows. Recorded and reported now; PETRO-5 enforces it |
| `{"command":"wifi_stress","on":true,"duration_s":3600}` | Gate 3's transmit stress: 1400-byte UDP datagrams to the gateway's discard port, back to back, for 60–7200 s (default 3600), RAM only. `"on":false` stops it |
| `{"command":"reboot"}` | Restarts after 2 s (relay open, energy saved) |

**The status** goes out on the first connect (`boot`), at once when the mode, the relay or the trip
changes (`change`, and again after a reconnect if it wasn't acknowledged), every 60 s (`heartbeat`)
and on request:

```json
{"mode":"auto","relay":true,"trip":null,"remote":true,"bench":false,"cycle":null,
 "volts":239.81,"amps":0.2611,"watts":61.24,"energy_kwh":1.234568,"board_c":24.1,"zx_hz":100.0,
 "trip_amps":10.5,"trip_amps_temporary":false,"trips_enforced":false,"stress_s":null,
 "rssi":-61,"uptime_s":3600,"reason":"heartbeat","version":"0.2.0"}
```

`remote` says whether a relay command would be accepted; `cycle` is `{"done","n"}` while one runs;
`stress_s` is the stress seconds left; readings are `null` until read.

### OTA

Fleet's protocol, the heatlink's implementation: `ota_update {url, version, sha256}`, or up to 10
`url_chunk`s with the sha256 on the last. The image downloads over HTTPS into the other OTA slot,
hashed as it comes, with `ota_progress` every 10 %. It is refused unless its SHA-256 is Fleet's, its
project is `petro` and its version is the one asked for and newer than the running one. Then
`ota_progress installing` and a restart into the new slot, where the image runs **on probation**:
it is kept (`esp_ota_mark_app_valid_cancel_rollback`) only once it has subscribed to Fleet's
commands. If that hasn't happened within 120 s, or it crashes first, the bootloader rolls back and
the old image reports `ota_error "rolled back"`; a kept one reports `ota_complete`. OTA never touches
`prov`. Images are unsigned, as the heatlink's.

## Metrics

Every 10 s, Prometheus text POSTed to `prov`'s `metrics_url` (with `/api/v1/import/prometheus`
appended when it has no path) with basic auth from `metrics_user` and `metrics_pass`. Skipped while
Wi-Fi is down or an update runs; a failed push is dropped and logged once per run of failures. It
has its own low-priority task and a 3 s timeout, so it never affects the relay.

| Metric | |
|---|---|
| `petro_voltage_volts`, `petro_current_amps`, `petro_power_watts` | V rms, A rms (channel A), W. Absent until the BL0939 reads, and after 3 failed reads in a row |
| `petro_energy_kwh_total` | From the CF count; stored in NVS at most every 10 minutes (every minute past 0.1 kWh) and at every restart, so a power cut loses at most 10 minutes' worth |
| `petro_board_temperature_celsius` | The NTC; absent if it can't read |
| `petro_relay_on` | 0 or 1 |
| `petro_zx_hz` | ZX edges a second (both edges: ≈ 100 on 50 Hz) |
| `petro_wifi_rssi_dbm`, `petro_uptime_seconds` | |
| `petro_resets_total{reason}` | Each reset reason seen, counted in NVS at boot: `poweron`, `brownout`, `panic`, `task_wdt`, `software`, … |
| `petro_trips_total{cause}` | `overcurrent` and `overtemp`, always both |

vmauth adds `host_name`. The counters start again only if the `nvs` partition is erased.
