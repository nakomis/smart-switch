# Firmware

ESP-IDF 5.5 firmware for the ESP32-C6-WROOM-1, from the nakostat heatlink firmware's patterns:
portable C under `port/` with pytest host tests, and the IDF project under `esp32c6/`. Work items:
PETRO-3 (core), PETRO-4 (metering), PETRO-5 (protection).

PETRO-3 is the core: the bench console Gate 2 needs (slice 1), then the mode on SW1, the LED's
status patterns, Wi-Fi, Fleet over MQTT, OTA with rollback and the VictoriaMetrics push (slice 3).
PETRO-4 calibrates the metering; PETRO-5 adds the protection (the trips, the meter's health and
zero-cross switching: [Protection](#protection)).

## Layout

| Path | What's there |
|---|---|
| `port/` | Portable C11, no IDF: `bl0939` (frames, packet checksum and layout, scaling for the 1 mΩ shunt and the 1.95 MΩ / 470 Ω divider, the chip's temperature), `ntc` (TH1, 10 k, B 3950, under 10 k from 3V3), `console_parse` (the console's command lines), `ctl` (the mode, the relay, the trip latch, relay cycle), `prot` (when to trip, the meter's health, when a trip may be cleared), `zx` (zero-cross switching times), `button` (SW1's debounce), `led` (the status patterns), `fleet_cmd` (Petro's Fleet commands), `ota_cmd` and `report` (Fleet's OTA protocol and when to publish the status, from the heatlink), `status_json`, `prom` (the metrics text and push URL), `energy` (the CF-count total) |
| `tools/` | Host drivers, one per module: `<name>_main.c` becomes `build/petro-<name>`, reading commands on stdin and answering in JSON |
| `tests/` | pytest over the drivers (`conftest.py` builds them once a session), and `coverage.sh` |
| `scripts/` | `provision-device.sh` (a unit's certificate, `prov.bin` and its flashing) and `make_prov.py`, with `tests/` (see Provisioning) |
| `CMakeLists.txt` | The host build: every `port/*.c` into `petro_port`, every `tools/*_main.c` a driver |
| `esp32c6/` | The IDF project: `main/` (`board.c` the hardware, `app.c` the control, meter and trip tasks, `relay.c` zero-cross switching, `net.c` Wi-Fi and MQTT, `ota.c` Fleet's OTA, `metrics.c` the VictoriaMetrics push, `stress.c` Gate 3's Wi-Fi stress, `store.c` what persists, `console.c` the commands, `prov.c` the `prov` reader, `petro_pins.h`, `Kconfig.projbuild` the protection's settings), `AmazonRootCA1.pem`, `partitions.csv`, `sdkconfig.defaults`, `version.txt` |

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

### Publishing (CI, PETRO-9)

A PR that touches `firmware/` fails if `version.txt` is already in the sandbox bucket. Its merge
takes the deployment tracker's next version for project `petro` (patch, or `--bump-minor` /
`--bump-major` alone on a line of the PR description), or `version.txt` if that's ahead, builds the
image stamped with it, and `scripts/ci-publish.sh` puts it at
`s3://nakomis-firmware-sandbox/petro/<x.y.z>/firmware.bin`, where Fleet offers it. Once Martin
approves the `production` environment, the same bytes go to `nakomis-firmware-prod`. Each publish is
recorded in the tracker. A published version is never replaced.

## Provisioning

Credentials live only in the `prov` NVS partition (0x12000, 24 KB), namespace `petro`, written by
`scripts/provision-device.sh`. The firmware only reads it, and `info` lists which keys are present,
never their values.

Each unit is an IoT Thing, `petro-<env>-bN` (`infra/devices.json`: prod `b1` to `b5`, sandbox `b1`),
made by `infra/`'s `PetroDeviceStack`, with the attributes Fleet reads (project `petro`, deviceType
`smart-switch`, capabilities `ota`). Fleet needs nothing else: it lists the Thing, finds firmware
under its bucket's `petro/` prefix, and adds a registry row the first time the unit speaks on
`petro/<thing>/{responses,status}`. **USB only, mains unplugged.**

```bash
firmware/scripts/provision-device.sh petro-prod-b1 --port /dev/cu.usbmodem101   # make, build, flash
firmware/scripts/provision-device.sh petro-sandbox-b1                          # sandbox, no flash
firmware/scripts/provision-device.sh petro-prod-b1 --new                       # a new certificate
```

Each run, safe to repeat:

1. Makes sure the unit's certificate is active and attached to its Thing and to the
   `petro-device-<env>` policy (creating one the first time; `--new` retires the old ones first,
   for a key that may have leaked).
2. Reads the IoT endpoint, the house Wi-Fi (`/Nakomis/Wifi/*`, `WIFI_PROFILE`, default
   `nakom.is-sandbox`) and the unit's vmauth password (`/vmauth/device-<thing>-password`,
   `METRICS_PROFILE`, default `nakom.is-admin`; missing means no metrics, with a warning).
3. Builds `firmware/certs/<thing>/prov.bin` with `scripts/make_prov.py` (IDF's NVS partition
   generator; secrets pass through the environment, never argv, and the CSV is overwritten and
   removed).
4. With `--port`, flashes it at prov's offset (`esptool --chip esp32c6 --after watchdog_reset
   write_flash 0x12000 prov.bin`); without, prints that command.

`AWS_PROFILE` defaults to `nakom.is-sandbox` for sandbox Things and `nakom.is-admin` for prod.
`firmware/certs/` is gitignored. **INSECURE, TEST ONLY**: AWS makes the private key, which sits in
`firmware/certs/` and the unit's flash in plain text, as do the Wi-Fi and vmauth passwords.

| Key | Holds | Most bytes |
|---|---|---|
| `wifi_ssid`, `wifi_pass` | The house Wi-Fi | 32, 63 |
| `endpoint` | IoT Core's ATS data endpoint | 127 |
| `thing` | The Thing's name, also the MQTT client id and the vmauth user | 128 |
| `cert`, `key` | The device certificate and private key, PEM | 3999 each (NVS's 4000 with the NUL) |
| `metrics_url` | vmauth's **base** URL, `http://172.29.0.33:8427` (`METRICS_URL`, or `none`): the firmware appends the write path, as tinycrypt does (`/write`, InfluxDB line protocol) | 127 |
| `metrics_user`, `metrics_pass` | The vmauth user (the Thing's name) and its password | 32, 64 |

The three `metrics_*` keys are all there or all absent. `scripts/tests/test_make_prov.py` checks the
keys against `prov.c` and reads a built partition back with IDF's `nvs_tool`:

```bash
python -m pytest -q firmware/scripts/tests
```

## The console

On the C6's USB-Serial-JTAG (J4), prompt `petro>`:

| Command | Does |
|---|---|
| `info` | Firmware version, MAC, chip revision, reset reason, uptime, the mode, the relay (and any bench override or cycle), the trip latched, the thresholds in force, the trip counts by cause, the protection (the BL0939's thresholds verified, OC's state, whether ZX switching is in sync and how many switches were timed), the meter's last reading, its health and the energy total, the network, which `prov` keys are present |
| `mode on` / `mode off` / `mode auto` | Sets the mode, as the button does (stored: the power-on state). While a trip is latched only `mode off` is accepted, and the trip stays latched |
| `relay on` / `relay off` | Drives the relay directly: a **bench override**, never stored, until the next press, mode change, remote relay command or trip. `relay on` is refused while a trip is latched or the meter isn't healthy |
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
- **Fleet can only set the mode to off** (always the safe direction; the gates use it). `set_mode`
  on or auto from Fleet is refused ("only off can be set remotely"): on and auto are the button's.
  Relay on/off and relay cycle from Fleet are accepted only in auto with no trip latched.
- **A trip** ([Protection](#protection)) opens the relay and latches, and the latch is stored in
  NVS, so it **survives a reboot** (the relay stays open even if the mode is on). A press of the
  button or Fleet's `clear_trip` clears it, and **clearing always leaves the relay off**: the mode
  is kept, except that on becomes off (on would close the relay). In auto the relay stays open
  until a command closes it. Temporary thresholds from Fleet live in RAM only: every boot starts at
  the defaults.
- A failed NVS write of the mode or the trip latch is retried every 5 s.

**The relay** is latched low before anything else at boot, and every reset leaves it open (the
gate's 100 k pull-down; the GPIO resets to an input). The control task drives it from the mode; it
runs every 5 ms at priority 8, above MQTT (5), the OTA download (4), the metrics push (2) and the
Wi-Fi stress (1). The meter task (priority 9) and the trip task (10) can open it too, and the OC
interrupt opens it directly. The control and meter tasks are watched by the 5 s task watchdog (a
hang panics and restarts, relay off). Closes and opens are timed to the mains' zero crossings
([Protection](#protection)). Every `esp_restart` opens the relay, holds it open until the reset (nothing can re-close it in
between), and saves the energy total first. `board_init` starts each part (relay, inputs, LED, NTC,
BL0939) independently, so one failing doesn't stop the rest; `info` lists which started. Nothing on the
control task waits on the network: publishing only copies into a queue.

**Unprovisioned** (`prov` empty or incomplete): no network; the console, the button and the relay
still work, and the LED says so. Without the metrics keys, metrics are off and nothing else changes.

### The LED

In priority order (brightness 64 of 255):

| Shows | When |
|---|---|
| Red, blinking 4 Hz | A trip is latched, any cause (press the button, or Fleet's `clear_trip`, to clear it; the cause is in the status and `info`) |
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
| `{"command":"set_mode","mode":"off"}` | **`off` only**, stored. `on` and `auto` are refused (`"status":"error"`): they're set with the button. Doesn't clear a trip |
| `{"command":"relay_cycle","n":500,"on_ms":3000,"off_ms":5000}` | Auto only. n 1–10000, 50–60000 ms each, **two hours at most in all** (Gate 4's 500 × 8 s is about 67 minutes; the console's cap stays at one hour). Leaves the relay open |
| `{"command":"relay_cycle_stop"}` | Stops a cycle, relay open |
| `{"command":"set_trip_threshold","amps":6.5,"instant_amps":5}` | **Temporary** thresholds, RAM only, gone after a reboot, each optional (one at least): `amps` the sustained one, 0.5–10.5 A; `instant_amps` the BL0939's OC output, 1–15 A (written to the chip and read back; if it doesn't take, the meter is unhealthy and the relay stays off). Never above the defaults; `null` restores a default. A status follows |
| `{"command":"clear_trip"}` | Clears a latched trip, leaving the relay off (on becomes off). Refused while the NTC is within 5 °C of its limit, or the current still reads over a threshold |
| `{"command":"wifi_stress","on":true,"duration_s":3600}` | Gate 3's transmit stress: 1400-byte UDP datagrams to the gateway's discard port, back to back, for 60–7200 s (default 3600), RAM only. `"on":false` stops it |
| `{"command":"reboot"}` | Restarts after 2 s (relay open, energy saved) |

**The status** goes out on the first connect (`boot`), at once when the mode, the relay or the trip
changes (`change`, and again after a reconnect if it wasn't acknowledged), every 60 s (`heartbeat`)
and on request:

```json
{"mode":"auto","relay":true,"trip":null,"remote":true,"bench":false,"cycle":null,
 "meter_ok":true,"volts":239.81,"amps":0.2611,"watts":61.24,"energy_kwh":1.234568,"board_c":24.1,"zx_hz":100.0,
 "trip_amps":10.5,"trip_amps_temporary":false,"instant_amps":15.00,"instant_amps_temporary":false,
 "overtemp_c":55.0,"trips_enforced":true,"zx_sync":true,"stress_s":null,
 "rssi":-61,"uptime_s":3600,"reason":"heartbeat","version":"0.3.0"}
```

`trip` is the latched cause (`overcurrent`, `overcurrent_instant`, `overtemp`, `meter_fault`) or
`null`; `remote` says whether a relay command would be accepted; `cycle` is `{"done","n"}` while
one runs; `stress_s` is the stress seconds left; `meter_ok` is the protection's health (below:
without it relay-on is refused); `trip_amps`, `instant_amps` and `overtemp_c` are the thresholds in
force; `zx_sync` is whether the relay is switching at zero crossings; readings are `null` until
read.

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

The push is **plain HTTP** on purpose: vmauth on Cal is reached over the LAN by design (as
tinycrypt's), and each device's credential can only write metrics as that device. An `https://`
`metrics_url` works too (the IDF certificate bundle).

| Metric | |
|---|---|
| `petro_voltage_volts`, `petro_current_amps`, `petro_power_watts` | V rms, A rms (channel A), W. Absent until the BL0939 reads, and after 3 s of failed reads |
| `petro_energy_kwh_total` | From the CF count; stored in NVS at most every 10 minutes (every minute past 0.1 kWh) and at every restart, so a power cut loses at most 10 minutes' worth |
| `petro_board_temperature_celsius` | The NTC; absent if it can't read |
| `petro_relay_on` | 0 or 1 |
| `petro_zx_hz` | ZX edges a second (both edges: ≈ 100 on 50 Hz) |
| `petro_wifi_rssi_dbm`, `petro_uptime_seconds` | |
| `petro_resets_total{reason}` | Each reset reason seen, counted in NVS at boot: `poweron`, `brownout`, `panic`, `task_wdt`, `software`, … |
| `petro_trips_total{cause}` | `overcurrent`, `overcurrent_instant`, `overtemp` and `meter_fault`, always all four |

vmauth adds `host_name`. The counters start again only if the `nvs` partition is erased.

## Protection

PETRO-5, in `port/prot.c` (the decisions, host-tested) and `esp32c6/main/app.c`, `board.c` and
`relay.c`. It is **back-up protection**: the plug's 13 A BS 1362 fuse is the real protection (F1
and F2 are bridged as built, `docs/DESIGN.md` §5.1). Trips are always enforced (`trips_enforced`
in the status).

| Trip (`cause`) | When | Default |
|---|---|---|
| `overcurrent` | The RMS current (the larger of the BL0939's two channels, which read the same shunt) over the threshold for **2 s** without a break. Read every 250 ms (the chip's RMS updates every 400 ms), so it trips 2–2.25 s in | **10.5 A** (Fleet may lower it until a reboot) |
| `overcurrent_instant` | The BL0939's fast RMS, over half a cycle, over its threshold: its OC output (GPIO2). The interrupt opens the relay itself, within microseconds of the edge (then the relay's release time) | **15 A** (Fleet may lower it until a reboot) |
| `overtemp` | The NTC (TH1, beside the relay) at or above the limit for 2 s | **55 °C, provisional** (below) |
| `meter_fault` | The relay wanted closed while the meter isn't healthy | |

Every trip opens the relay **at once** (never waiting for a crossing) and latches: LED red, the
cause in the status and `info`, `petro_trips_total{cause}` up by one, the latch in NVS.

**The meter's health** (`meter_ok`): the BL0939 started and its write unlock, mode, temperature
control (the alarms on) and fast-RMS thresholds **read back** as written, the instant trip
**armed**, a good frame within 3 s and a plausible NTC reading within 3 s (−20 to 150 °C, not
within 50 mV of either rail: an open NTC reads very cold, a shorted one very hot). Without it,
every command that would close the relay (Fleet's relay on and relay cycle, the console's `relay
on` and `relay cycle`) is refused, and a relay that should be closed (the mode on, by the button or
at boot) is opened and latched as `meter_fault`. In the first 3 s after boot the relay is held open
without a trip while the first readings come in.

**Clearing** (the button, or Fleet's `clear_trip`) leaves the relay off (above), and is refused
while the NTC is within **5 °C** of its limit (or, for an over-temperature trip, can't be read), the
current still reads over the sustained threshold, or OC is still active.

**The NTC limit and Gate 4.** The NTC under-reads the hot spots (the terminals, K1's contacts, the
shunt) by the ratio Gate 4's mapping run measures (`docs/testing/gate-4-load-thermal.md` §2.7: each
spot's rise over the NTC's, the largest). §5 then sets the limit so that the NTC trips before the
hottest spot reaches 70 °C in a 35 °C room:

> NTC limit = room + (70 − room) ÷ ratio, with room = 35 °C

55 °C assumes a ratio of 1.75. Once Gate 4 has the ratio, set `CONFIG_PETRO_OVERTEMP_C` (`idf.py
-C firmware/esp32c6 menuconfig`, "Petro protection", 40–70 °C, or in `sdkconfig.defaults`), bump
the version and rebuild. A ratio of 2.5, for example, gives 49 °C.

**Zero-cross switching.** The relay's closes and opens are timed to the BL0939's ZX output (GPIO1,
an edge at each crossing) so its contacts move at a voltage zero, where a resistive load's current
is zero too: the coil is driven the relay's **operate time (8 ms)** ahead of a crossing to close,
its **release time (4 ms)** ahead to open (HF115F, assumed; Kconfig `PETRO_RELAY_OPERATE_US` and
`PETRO_RELAY_RELEASE_US`, measured at Gate 2). The crossings are predicted a whole period on from
each of the last two edges, so unequal halves don't matter. With no ZX edge for 100 ms (no mains:
on USB) or edges that aren't 40–62.5 Hz, it switches at once. `CONFIG_PETRO_ZX_SWITCHING=n` turns
it off.

**Tasks.** The meter task (priority 9, every 250 ms, on the watchdog) reads the BL0939 and the
NTC and checks the trips; the control task (8, every 5 ms) checks them too, so a stale meter is
noticed even if the meter task stops (and the watchdog then restarts Petro, relay off). The OC
interrupt opens the relay and holds it open (nothing can close it until the trip is cleared), then
wakes the trip task (10), which latches, counts and stores it: no NVS or flash work in the
interrupt, whose code is all in IRAM (`CONFIG_GPIO_CTRL_FUNC_IN_IRAM`). No network task holds the
lock the trips take, and every network task runs below all three.

**OC's polarity** isn't settled by the datasheet (Chinese only, no pin polarity found) or by
ESPHome, so the firmware infers it: it arms the instant trip only with the relay open and a fresh
frame reading under 0.1 A on both channels, takes OC's level then (steady over 2 ms) as idle and
the other as active. Arming happens before the meter and control tasks start, and again whenever
it's safe after a failure (a wandering pin, or Fleet's `instant_amps` not taking). Until armed the
meter is unhealthy, so the relay stays open. An OC edge with the relay open and under 0.1 A can't
be real, so it latches `meter_fault`, not `overcurrent_instant`. The OC hold is released only when
a latched trip is cleared. Gate 2's `edges` should show no OC edges at rest; `info` shows OC's
state.
