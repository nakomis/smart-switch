# Firmware

ESP-IDF 5.5 firmware for the ESP32-C6-WROOM-1, from the nakostat heatlink firmware's patterns:
portable C under `port/` with pytest host tests, and the IDF project under `esp32c6/`. Work items:
PETRO-3 (core), PETRO-4 (metering), PETRO-5 (protection).

**This slice (PETRO-3, slice 1)** is the bench console Gate 2 needs (`docs/testing/README.md`,
"What the gates need from the firmware"): the BL0939 and NTC drivers, the `prov` reader, and the
USB console. The relay is off at boot and only the console drives it. Still to come (slice 3):
the mode state machine on SW1, the LED's status patterns, Wi-Fi join, Fleet over MQTT, OTA and the
VictoriaMetrics push; PETRO-5 adds the trips. They're marked `TODO(PETRO-3 slice 3)` / `TODO(PETRO-5)`.

## Layout

| Path | What's there |
|---|---|
| `port/` | Portable C11, no IDF: `bl0939` (frames, packet checksum and layout, scaling for the 1 mΩ shunt and the 1.95 MΩ / 470 Ω divider, the chip's temperature), `ntc` (TH1, 10 k, B 3950, under 10 k from 3V3), `console_parse` (the console's command lines) |
| `tools/` | Host drivers, one per module: `<name>_main.c` becomes `build/petro-<name>`, reading commands on stdin and answering in JSON |
| `tests/` | pytest over the drivers (`conftest.py` builds them once a session), and `coverage.sh` |
| `CMakeLists.txt` | The host build: every `port/*.c` into `petro_port`, every `tools/*_main.c` a driver |
| `esp32c6/` | The IDF project: `main/` (`board.c` the hardware, `console.c` the commands, `prov.c` the `prov` reader, `petro_pins.h`), `partitions.csv`, `sdkconfig.defaults`, `version.txt` |

`esp32c6/main/petro_pins.h` is a **copy** of `pcb/out/petro/pins.h` (the board generator's output),
so the firmware never builds from `pcb/out`. `tests/test_pins.py` fails if the two drift apart:
copy the header again after regenerating the board. Note the UART names are the BL0939's: `BL_TX`
(GPIO10) is its TX and our RX, `BL_RX` (GPIO11) its RX and our TX.

## Host tests

```bash
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
| `info` | Firmware version, MAC, chip revision, reset reason, uptime, the mode (none yet), the relay, the trips (none yet), which `prov` keys are present |
| `relay on` / `relay off` | Drives the relay |
| `relay cycle <n> <on_ms> <off_ms>` | Cycles it n times (1–10000, 50–60000 ms each), leaving it off |
| `led <r> <g> <b>` | Sets the LED (0–255 each) |
| `button` | Logs SW1's presses and releases for 10 s (20 ms debounce) |
| `bl` | Three full-packet reads of the BL0939, 0.5 s apart: whether each frame's checksum was good, then V, IA, IB, PA, PB raw and scaled, the CF counts and the chip's temperature |
| `edges` | ZX and OC edges (rising and falling) in each of two seconds: about 100 a second on 50 Hz mains, 0 on USB |
| `ntc` | The NTC's averaged ADC code, calibrated mV, resistance and °C |
| `wifi scan` | SSIDs, channels and RSSI (scan only; UK channels 1–13) |
| `j3` | Toggles OUT at 1 Hz for 5 s, printing IN each half second, then scans I²C 0x08–0x77 |
| `help` | The list |
