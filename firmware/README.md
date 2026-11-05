# Firmware

ESP-IDF 5.5 firmware for the ESP32-C6-WROOM-1, from the nakostat heatlink firmware's patterns:
portable C under `port/` with pytest host tests, and the IDF project under `esp32c6/`. The GPIOs
are in `pcb/out/petro/pins.h`, generated with the board. Work items: PETRO-3
(core), PETRO-4 (metering), PETRO-5 (protection).
