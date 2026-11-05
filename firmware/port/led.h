// The status LED (SK6812 under the light pipe): what it shows, from the device's state. Portable,
// so the host tests it.
//
// In priority order:
//   fault       red, fast blink (4 Hz)           a trip is latched (PETRO-5)
//   OTA         cyan, blink (2 Hz)               an update is downloading or installing
//   boot        white, steady                    the first LED_BOOT_MS after power-up
//   unprov.     magenta alternating with the     provisioning needed: prov is empty or
//               mode colour (1 Hz)               incomplete (console only, no network)
//   the mode    off amber, on green, auto blue (dim while auto holds the relay open), shown
//                 - blinking with dark (1 Hz)    while joining Wi-Fi
//                 - blinking with dark (4 Hz)    Wi-Fi up, connecting to IoT Core
//                 - steady                       connected to Fleet
#pragma once

#include <stdbool.h>
#include <stdint.h>

#include "ctl.h"

#define LED_BOOT_MS 1500
#define LED_LEVEL 64  // full brightness (of 255): plenty through the light pipe

typedef enum
{
    LED_DARK,
    LED_RED,
    LED_CYAN,
    LED_WHITE,
    LED_MAGENTA,
    LED_AMBER,
    LED_GREEN,
    LED_BLUE,
    LED_DIM_BLUE,
} led_colour;

typedef struct
{
    int64_t now_ms;  // since boot
    bool tripped;
    bool ota;
    bool provisioned;
    bool wifi_up;
    bool mqtt_up;
    ctl_mode mode;
    bool relay;
} led_inputs;

led_colour led_show(const led_inputs *in);

// RGB with `level` (0-255) as full scale.
void led_rgb(led_colour colour, uint8_t level, uint8_t *r, uint8_t *g, uint8_t *b);

const char *led_name(led_colour colour);
