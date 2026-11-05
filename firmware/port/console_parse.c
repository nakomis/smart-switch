// The console's command lines. See console_parse.h.
#include "console_parse.h"

#include <stdarg.h>
#include <stdio.h>
#include <string.h>

const char *const CONSOLE_USAGE[] = {
    "info                              version, MAC, chip, reset reason, mode, trips, prov keys",
    "mode on | mode off | mode auto    set the mode (persisted: the power-on state)",
    "relay on | relay off              drive the relay (a bench override, until a press or mode change)",
    "relay cycle <n> <on_ms> <off_ms>  cycle it n times (n 1-10000, 50-60000 ms, 1 h at most; any key stops it)",
    "led <r> <g> <b> | led auto        set the LED (0-255 each; held 60 s) | back to the status",
    "button                            log presses and releases for 10 s",
    "bl                                read the BL0939 (raw and scaled)",
    "edges                             ZX and OC edges a second, over 2 s",
    "ntc                               the NTC's ADC reading and degrees C",
    "wifi scan                         SSIDs, channels and RSSI",
    "j3                                toggle OUT at 1 Hz for 5 s, read IN, scan I2C",
    "help                              this list",
};
const size_t CONSOLE_USAGE_LEN = sizeof(CONSOLE_USAGE) / sizeof(CONSOLE_USAGE[0]);

static bool fail(char *err, size_t err_len, const char *fmt, ...)
{
    if (err != NULL && err_len > 0)
    {
        va_list ap;
        va_start(ap, fmt);
        vsnprintf(err, err_len, fmt, ap);
        va_end(ap);
    }
    return false;
}

// A plain decimal in [lo, hi]: digits only, no sign, no spaces, at most 9 digits.
static bool number(const char *s, uint32_t lo, uint32_t hi, uint32_t *out)
{
    size_t len = strlen(s);
    if (len == 0 || len > 9)
        return false;
    uint32_t v = 0;
    for (size_t i = 0; i < len; i++)
    {
        if (s[i] < '0' || s[i] > '9')
            return false;
        v = v * 10 + (uint32_t)(s[i] - '0');
    }
    if (v < lo || v > hi)
        return false;
    *out = v;
    return true;
}

static bool want_args(const char *name, int argc, int want, char *err, size_t err_len)
{
    if (argc != want)
        return fail(err, err_len, "%s: expected %d argument%s, got %d", name, want - 1,
                    want - 1 == 1 ? "" : "s", argc - 1);
    return true;
}

bool console_parse_argv(int argc, const char *const *argv, console_cmd_t *out, char *err,
                        size_t err_len)
{
    if (argc < 1 || argv == NULL || argv[0] == NULL)
        return fail(err, err_len, "empty command");
    memset(out, 0, sizeof(*out));
    const char *cmd = argv[0];

    static const struct
    {
        const char *name;
        console_kind_t kind;
    } plain[] = {
        {"help", CONSOLE_HELP}, {"info", CONSOLE_INFO},   {"button", CONSOLE_BUTTON},
        {"bl", CONSOLE_BL},     {"edges", CONSOLE_EDGES}, {"ntc", CONSOLE_NTC},
        {"j3", CONSOLE_J3},
    };
    for (size_t i = 0; i < sizeof(plain) / sizeof(plain[0]); i++)
    {
        if (strcmp(cmd, plain[i].name) == 0)
        {
            if (!want_args(cmd, argc, 1, err, err_len))
                return false;
            out->kind = plain[i].kind;
            return true;
        }
    }

    if (strcmp(cmd, "wifi") == 0)
    {
        if (argc != 2 || strcmp(argv[1], "scan") != 0)
            return fail(err, err_len, "usage: wifi scan");
        out->kind = CONSOLE_WIFI_SCAN;
        return true;
    }

    if (strcmp(cmd, "relay") == 0)
    {
        if (argc < 2)
            return fail(err, err_len, "usage: relay on | relay off | relay cycle <n> <on_ms> <off_ms>");
        const char *sub = argv[1];
        if (strcmp(sub, "on") == 0 || strcmp(sub, "off") == 0)
        {
            if (argc != 2)
                return fail(err, err_len, "relay %s: no arguments", sub);
            out->kind = sub[1] == 'n' ? CONSOLE_RELAY_ON : CONSOLE_RELAY_OFF;
            return true;
        }
        if (strcmp(sub, "cycle") == 0)
        {
            if (argc != 5)
                return fail(err, err_len, "usage: relay cycle <n> <on_ms> <off_ms>");
            if (!number(argv[2], 1, CONSOLE_CYCLE_MAX_N, &out->cycle.n))
                return fail(err, err_len, "relay cycle: n must be 1-%d", CONSOLE_CYCLE_MAX_N);
            if (!number(argv[3], CONSOLE_CYCLE_MIN_MS, CONSOLE_CYCLE_MAX_MS, &out->cycle.on_ms))
                return fail(err, err_len, "relay cycle: on_ms must be %d-%d", CONSOLE_CYCLE_MIN_MS,
                            CONSOLE_CYCLE_MAX_MS);
            if (!number(argv[4], CONSOLE_CYCLE_MIN_MS, CONSOLE_CYCLE_MAX_MS, &out->cycle.off_ms))
                return fail(err, err_len, "relay cycle: off_ms must be %d-%d", CONSOLE_CYCLE_MIN_MS,
                            CONSOLE_CYCLE_MAX_MS);
            uint64_t total = (uint64_t)out->cycle.n * (out->cycle.on_ms + out->cycle.off_ms);
            if (total > CONSOLE_CYCLE_MAX_TOTAL_MS)
                return fail(err, err_len, "relay cycle: n x (on_ms + off_ms) must be at most 1 h");
            out->kind = CONSOLE_RELAY_CYCLE;
            return true;
        }
        return fail(err, err_len, "relay: unknown subcommand '%s'", sub);
    }

    if (strcmp(cmd, "mode") == 0)
    {
        if (argc != 2 || !ctl_mode_parse(argv[1], &out->mode))
            return fail(err, err_len, "usage: mode on | mode off | mode auto");
        out->kind = CONSOLE_MODE;
        return true;
    }

    if (strcmp(cmd, "led") == 0 && argc == 2 && strcmp(argv[1], "auto") == 0)
    {
        out->kind = CONSOLE_LED_AUTO;
        return true;
    }

    if (strcmp(cmd, "led") == 0)
    {
        if (!want_args(cmd, argc, 4, err, err_len))
            return false;
        uint32_t c[3];
        for (int i = 0; i < 3; i++)
            if (!number(argv[1 + i], 0, 255, &c[i]))
                return fail(err, err_len, "led: '%s' is not 0-255", argv[1 + i]);
        out->kind = CONSOLE_LED;
        out->led.r = (uint8_t)c[0];
        out->led.g = (uint8_t)c[1];
        out->led.b = (uint8_t)c[2];
        return true;
    }

    return fail(err, err_len, "unknown command '%s' (try help)", cmd);
}

int console_tokenise(char *line, char **argv, int max_args)
{
    int argc = 0;
    char *p = line;
    for (;;)
    {
        while (*p == ' ' || *p == '\t' || *p == '\r' || *p == '\n')
            p++;
        if (*p == '\0')
            return argc;
        if (argc == max_args)
            return -1;
        argv[argc++] = p;
        while (*p != '\0' && *p != ' ' && *p != '\t' && *p != '\r' && *p != '\n')
            p++;
        if (*p != '\0')
            *p++ = '\0';
    }
}

const char *console_kind_name(console_kind_t kind)
{
    switch (kind)
    {
    case CONSOLE_HELP:
        return "help";
    case CONSOLE_INFO:
        return "info";
    case CONSOLE_RELAY_ON:
        return "relay on";
    case CONSOLE_RELAY_OFF:
        return "relay off";
    case CONSOLE_RELAY_CYCLE:
        return "relay cycle";
    case CONSOLE_LED:
        return "led";
    case CONSOLE_BUTTON:
        return "button";
    case CONSOLE_BL:
        return "bl";
    case CONSOLE_EDGES:
        return "edges";
    case CONSOLE_NTC:
        return "ntc";
    case CONSOLE_WIFI_SCAN:
        return "wifi scan";
    case CONSOLE_J3:
        return "j3";
    case CONSOLE_MODE:
        return "mode";
    case CONSOLE_LED_AUTO:
        return "led auto";
    }
    return "unknown";
}
