// The USB console's commands (docs/testing/README.md, "What the gates need from the firmware"):
// parsing and validating a command line into a struct, so the rules are host-tested and the IDF
// side only acts on them. Portable C, no IDF.
#pragma once

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#include "ctl.h"

typedef enum
{
    CONSOLE_HELP,
    CONSOLE_INFO,
    CONSOLE_RELAY_ON,
    CONSOLE_RELAY_OFF,
    CONSOLE_RELAY_CYCLE,
    CONSOLE_LED,
    CONSOLE_BUTTON,
    CONSOLE_BL,
    CONSOLE_EDGES,
    CONSOLE_NTC,
    CONSOLE_WIFI_SCAN,
    CONSOLE_J3,
    CONSOLE_MODE,      // mode is set
    CONSOLE_LED_AUTO,  // the LED back to showing the state
} console_kind_t;

// relay cycle's limits: 50 ms is the shortest on or off time, comfortably above the relay's operate
// time plus bounce, so every cycle really switches; Gate 4 needs 500 cycles. The whole run
// (n x (on_ms + off_ms)) is capped at an hour, because the console is busy while it runs.
#define CONSOLE_CYCLE_MAX_N 10000
#define CONSOLE_CYCLE_MIN_MS 50
#define CONSOLE_CYCLE_MAX_MS 60000
#define CONSOLE_CYCLE_MAX_TOTAL_MS 3600000u

typedef struct
{
    console_kind_t kind;
    union
    {
        struct
        {
            uint32_t n, on_ms, off_ms;
        } cycle;
        struct
        {
            uint8_t r, g, b;
        } led;
        ctl_mode mode;
    };
} console_cmd_t;

// Parses argv (argv[0] the command). On failure returns false with a one-line reason in err.
bool console_parse_argv(int argc, const char *const *argv, console_cmd_t *out, char *err,
                        size_t err_len);

// Splits line in place on spaces and tabs. Returns argc, or -1 for more than max_args words.
int console_tokenise(char *line, char **argv, int max_args);

// The command's name, as typed ("relay cycle", "wifi scan").
const char *console_kind_name(console_kind_t kind);

// One line per command, for `help`.
extern const char *const CONSOLE_USAGE[];
extern const size_t CONSOLE_USAGE_LEN;
