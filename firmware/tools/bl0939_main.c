// Host driver for port/bl0939: one command a line on stdin, one JSON line out.
//
//   read                      -> {"frame":"55aa"}
//   write <reg> <value>       -> {"frame":"a5..."}       (hex, value 24-bit)
//   init [ctrl]               -> {"frames":["a5...",...]}   (ctrl hex: the fast-RMS control)
//   readreg <reg>             -> {"frame":"55.."}
//   verify <ctrl>             -> {"checks":[[reg,value,mask],...]}
//   parsereg <reg> <hex>      -> {"status":"ok","value":..}
//   parse <hex>               -> {"status":"ok","raw":{...},"petro":{...}}
//   scale <shunt> <top> <bot> -> {"volts":..,"amps":..,"watts":..,"pulses_per_kwh":..}
//   temp <tps1>               -> {"celsius":..}
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "bl0939.h"

static void hex(const uint8_t *b, size_t n)
{
    for (size_t i = 0; i < n; i++)
        printf("%02x", b[i]);
}

static size_t unhex(const char *s, uint8_t *out, size_t max)
{
    size_t n = 0;
    while (s[0] && s[1] && n < max)
    {
        unsigned v;
        if (sscanf(s, "%2x", &v) != 1)
            break;
        out[n++] = (uint8_t)v;
        s += 2;
    }
    return n;
}

static void print_scale(const bl0939_scale_t *s)
{
    printf("{\"volts\":%.6f,\"amps\":%.6f,\"watts\":%.6f,\"pulses_per_kwh\":%.6f}", s->volts,
           s->amps, s->watts, s->pulses_per_kwh);
}

int main(void)
{
    char line[512];
    while (fgets(line, sizeof(line), stdin) != NULL)
    {
        char cmd[16] = "";
        char arg[400] = "";
        sscanf(line, "%15s %399s", cmd, arg);
        if (strcmp(cmd, "read") == 0)
        {
            uint8_t f[2];
            size_t n = bl0939_build_full_read(f);
            printf("{\"frame\":\"");
            hex(f, n);
            printf("\"}\n");
        }
        else if (strcmp(cmd, "write") == 0)
        {
            unsigned reg = 0, value = 0;
            sscanf(line, "%*s %x %x", &reg, &value);
            uint8_t f[BL0939_WRITE_LEN];
            size_t n = bl0939_build_write((uint8_t)reg, value, f);
            printf("{\"frame\":\"");
            hex(f, n);
            printf("\"}\n");
        }
        else if (strcmp(cmd, "init") == 0)
        {
            uint8_t f[8][BL0939_WRITE_LEN];
            unsigned ctrl = (unsigned)strtoul(arg, NULL, 16);
            size_t n = bl0939_init_frames(f, 8, ctrl);
            printf("{\"frames\":[");
            for (size_t i = 0; i < n; i++)
            {
                printf("%s\"", i ? "," : "");
                hex(f[i], BL0939_WRITE_LEN);
                printf("\"");
            }
            printf("]}\n");
        }
        else if (strcmp(cmd, "verify") == 0)
        {
            bl0939_check_t c[8];
            size_t n = bl0939_verify_list((uint32_t)strtoul(arg, NULL, 16), c, 8);
            printf("{\"checks\":[");
            for (size_t i = 0; i < n; i++)
                printf("%s[%u,%u,%u]", i ? "," : "", c[i].reg, c[i].value, c[i].mask);
            printf("]}\n");
        }
        else if (strcmp(cmd, "readreg") == 0)
        {
            uint8_t f[2];
            size_t n = bl0939_build_read((uint8_t)strtoul(arg, NULL, 16), f);
            printf("{\"frame\":\"");
            hex(f, n);
            printf("\"}\n");
        }
        else if (strcmp(cmd, "parsereg") == 0)
        {
            unsigned reg = 0;
            char data[64] = "";
            sscanf(line, "%*s %x %63s", &reg, data);
            uint8_t p[32];
            size_t n = unhex(data, p, sizeof(p));
            uint32_t value = 0;
            bl0939_status_t st = bl0939_parse_register((uint8_t)reg, p, n, &value);
            printf("{\"status\":\"%s\"", bl0939_status_name(st));
            if (st == BL0939_OK)
                printf(",\"value\":%u", value);
            printf("}\n");
        }
        else if (strcmp(cmd, "parse") == 0)
        {
            uint8_t p[200];
            size_t n = unhex(arg, p, sizeof(p));
            bl0939_raw_t raw;
            bl0939_status_t st = bl0939_parse_packet(p, n, &raw);
            printf("{\"status\":\"%s\"", bl0939_status_name(st));
            if (st == BL0939_OK)
            {
                bl0939_scale_t s = bl0939_petro_scale();
                bl0939_reading_t r = bl0939_convert(&raw, &s);
                printf(",\"raw\":{\"ia_fast_rms\":%u,\"ia_rms\":%u,\"ib_rms\":%u,\"v_rms\":%u,"
                       "\"ib_fast_rms\":%u,\"a_watt\":%d,\"b_watt\":%d,\"cfa_cnt\":%u,\"cfb_cnt\":%u,"
                       "\"tps1\":%u,\"tps2\":%u}",
                       raw.ia_fast_rms, raw.ia_rms, raw.ib_rms, raw.v_rms, raw.ib_fast_rms,
                       raw.a_watt, raw.b_watt, raw.cfa_cnt, raw.cfb_cnt, raw.tps1, raw.tps2);
                printf(",\"petro\":{\"volts\":%.6f,\"amps_a\":%.6f,\"amps_b\":%.6f,\"watts_a\":%.6f,"
                       "\"watts_b\":%.6f,\"kwh_a\":%.9f,\"celsius\":%.6f}",
                       r.volts, r.amps_a, r.amps_b, r.watts_a, r.watts_b, r.kwh_a, r.celsius);
            }
            printf("}\n");
        }
        else if (strcmp(cmd, "scale") == 0)
        {
            double sh = 0, top = 0, bot = 0;
            sscanf(line, "%*s %lf %lf %lf", &sh, &top, &bot);
            bl0939_scale_t s = bl0939_scale(sh, top, bot);
            print_scale(&s);
            printf("\n");
        }
        else if (strcmp(cmd, "petro") == 0)
        {
            bl0939_scale_t s = bl0939_petro_scale();
            print_scale(&s);
            printf("\n");
        }
        else if (strcmp(cmd, "temp") == 0)
        {
            unsigned t = (unsigned)strtoul(arg, NULL, 0);
            printf("{\"celsius\":%.6f}\n", bl0939_temperature((uint16_t)t));
        }
        else
        {
            printf("{\"error\":\"unknown\"}\n");
        }
    }
    return 0;
}
