// Host driver for port/console_parse: one command line on stdin, one JSON line out.
//
//   {"ok":true,"kind":"relay cycle","n":20,"on_ms":200,"off_ms":200}
//   {"ok":false,"error":"..."}
#include <stdio.h>
#include <string.h>

#include "console_parse.h"

#define MAX_ARGS 8

static void json_string(const char *s)
{
    putchar('"');
    for (; *s; s++)
    {
        if (*s == '"' || *s == '\\')
            putchar('\\');
        if ((unsigned char)*s < 0x20)
            printf("\\u%04x", (unsigned char)*s);
        else
            putchar(*s);
    }
    putchar('"');
}

int main(int argc_main, char **argv_main)
{
    if (argc_main > 1 && strcmp(argv_main[1], "usage") == 0)
    {
        for (size_t i = 0; i < CONSOLE_USAGE_LEN; i++)
            puts(CONSOLE_USAGE[i]);
        return 0;
    }
    char line[256];
    while (fgets(line, sizeof(line), stdin) != NULL)
    {
        char *argv[MAX_ARGS];
        int argc = console_tokenise(line, argv, MAX_ARGS);
        console_cmd_t cmd;
        char err[128] = "";
        if (argc < 0)
        {
            printf("{\"ok\":false,\"error\":\"too many words\"}\n");
            continue;
        }
        if (!console_parse_argv(argc, (const char *const *)argv, &cmd, err, sizeof(err)))
        {
            printf("{\"ok\":false,\"error\":");
            json_string(err);
            printf("}\n");
            continue;
        }
        printf("{\"ok\":true,\"kind\":\"%s\"", console_kind_name(cmd.kind));
        if (cmd.kind == CONSOLE_RELAY_CYCLE)
            printf(",\"n\":%u,\"on_ms\":%u,\"off_ms\":%u", cmd.cycle.n, cmd.cycle.on_ms,
                   cmd.cycle.off_ms);
        if (cmd.kind == CONSOLE_MODE)
            printf(",\"mode\":\"%s\"", ctl_mode_name(cmd.mode));
        if (cmd.kind == CONSOLE_LED)
            printf(",\"r\":%u,\"g\":%u,\"b\":%u", cmd.led.r, cmd.led.g, cmd.led.b);
        printf("}\n");
    }
    return 0;
}
