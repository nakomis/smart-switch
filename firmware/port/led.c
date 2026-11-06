// The status LED. See led.h.
#include "led.h"

// `on` for the first half of each period, `other` for the second.
static led_colour blink(int64_t now_ms, int64_t period_ms, led_colour on, led_colour other)
{
    return (now_ms % period_ms) < period_ms / 2 ? on : other;
}

static led_colour mode_colour(ctl_mode mode, bool relay)
{
    switch (mode)
    {
    case CTL_MODE_ON:
        return LED_GREEN;
    case CTL_MODE_AUTO:
        return relay ? LED_BLUE : LED_DIM_BLUE;
    case CTL_MODE_OFF:
        break;
    }
    return LED_AMBER;
}

led_colour led_show(const led_inputs *in)
{
    int64_t t = in->now_ms < 0 ? 0 : in->now_ms;
    if (in->tripped)
        return blink(t, 250, LED_RED, LED_DARK);
    if (in->ota)
        return blink(t, 500, LED_CYAN, LED_DARK);
    if (t < LED_BOOT_MS)
        return LED_WHITE;
    led_colour mode = mode_colour(in->mode, in->relay);
    if (!in->provisioned)
        return blink(t, 1000, LED_MAGENTA, mode);
    if (!in->wifi_up)
        return blink(t, 1000, mode, LED_DARK);
    if (!in->mqtt_up)
        return blink(t, 250, mode, LED_DARK);
    return mode;
}

void led_rgb(led_colour colour, uint8_t level, uint8_t *r, uint8_t *g, uint8_t *b)
{
    static const uint8_t rgb[][3] = {
        [LED_DARK] = {0, 0, 0},        [LED_RED] = {255, 0, 0},       [LED_CYAN] = {0, 200, 255},
        [LED_WHITE] = {200, 200, 200}, [LED_MAGENTA] = {255, 0, 200}, [LED_AMBER] = {255, 90, 0},
        [LED_GREEN] = {0, 255, 0},     [LED_BLUE] = {0, 0, 255},      [LED_DIM_BLUE] = {0, 0, 64},
    };
    unsigned i = (unsigned)colour < sizeof(rgb) / sizeof(rgb[0]) ? (unsigned)colour : LED_RED;
    *r = (uint8_t)(rgb[i][0] * level / 255);
    *g = (uint8_t)(rgb[i][1] * level / 255);
    *b = (uint8_t)(rgb[i][2] * level / 255);
}

const char *led_name(led_colour colour)
{
    static const char *const names[] = {
        [LED_DARK] = "dark",   [LED_RED] = "red",         [LED_CYAN] = "cyan",
        [LED_WHITE] = "white", [LED_MAGENTA] = "magenta", [LED_AMBER] = "amber",
        [LED_GREEN] = "green", [LED_BLUE] = "blue",       [LED_DIM_BLUE] = "dim blue",
    };
    return (unsigned)colour < sizeof(names) / sizeof(names[0]) ? names[colour] : "?";
}
