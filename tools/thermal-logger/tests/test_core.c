// Host tests for components/zatt_core. Built and run by tests/test_core.py (or by hand:
//   cc -I../components/zatt_core/include test_core.c ../components/zatt_core/*.c -lm -o test_core).
#include <math.h>
#include <stdio.h>
#include <string.h>

#include "bmp280_calc.h"
#include "prom.h"
#include "thermal.h"

static int failures;
#define CHECK(c)                                                  \
    do                                                            \
    {                                                             \
        if (!(c))                                                 \
        {                                                         \
            printf("FAIL line %d: %s\n", __LINE__, #c);           \
            failures++;                                           \
        }                                                         \
    } while (0)

static void test_rect(void)
{
    zatt_rect_t r;
    CHECK(zatt_rect_parse("", &r) && r.x0 < 0 && !zatt_rect_valid(&r));
    CHECK(zatt_rect_parse(" 3, 4 ,5,6 ", &r) && r.x0 == 3 && r.y0 == 4 && r.x1 == 5 && r.y1 == 6);
    CHECK(zatt_rect_valid(&r));
    CHECK(!zatt_rect_parse("3,4,5", &r));
    CHECK(!zatt_rect_parse("3,4,5,6,7", &r));
    CHECK(!zatt_rect_parse("5,4,3,6", &r));   // x1 < x0
    CHECK(!zatt_rect_parse("0,0,32,5", &r));  // x out of range
    CHECK(!zatt_rect_parse("0,0,5,24", &r));  // y out of range
    CHECK(!zatt_rect_parse("a,b,c,d", &r));
    CHECK(zatt_rect_parse("0,0,31,23", &r) && zatt_rect_valid(&r));
}

static void test_frame(void)
{
    float f[ZATT_PIXELS];
    for (int i = 0; i < ZATT_PIXELS; i++)
        f[i] = 20.0f;
    f[5 * ZATT_W + 7] = 60.0f;
    f[0] = 10.0f;
    f[1] = NAN;
    zatt_frame_stats_t s;
    CHECK(zatt_frame_stats(f, &s));
    CHECK(s.max == 60.0f && s.hot_x == 7 && s.hot_y == 5);
    CHECK(s.min == 10.0f && s.n == ZATT_PIXELS - 1);
    CHECK(fabsf(s.mean - (20.0f * (ZATT_PIXELS - 3) + 60.0f + 10.0f) / (ZATT_PIXELS - 1)) < 1e-3f);

    float m, x;
    zatt_rect_t r = {6, 4, 8, 6};
    CHECK(zatt_rect_stats(f, &r, &m, &x) && x == 60.0f && fabsf(m - (20.0f * 8 + 60.0f) / 9) < 1e-4f);
    zatt_rect_t one = {7, 5, 7, 5};
    CHECK(zatt_rect_stats(f, &one, &m, &x) && m == 60.0f);
    zatt_rect_t off = zatt_rect_disabled();
    CHECK(!zatt_rect_stats(f, &off, &m, &x));
    zatt_rect_t nan_only = {1, 0, 1, 0};
    CHECK(!zatt_rect_stats(f, &nan_only, &m, &x));

    for (int i = 0; i < ZATT_PIXELS; i++)
        f[i] = NAN;
    CHECK(!zatt_frame_stats(f, &s));
}

static void test_prom(void)
{
    char buf[128];
    prom_buf_t p;
    prom_init(&p, buf, sizeof(buf));
    prom_gauge(&p, "zatt_frame_max_celsius", NULL, NULL, 41.5);
    prom_gauge(&p, "zatt_spot_celsius", "spot", "T1", 30.25);
    prom_gauge(&p, "zatt_nan", NULL, NULL, NAN);  // skipped
    CHECK(prom_finish(&p) == (int)strlen(buf));
    CHECK(strcmp(buf, "zatt_frame_max_celsius 41.500\nzatt_spot_celsius{spot=\"T1\"} 30.250\n") == 0);

    prom_init(&p, buf, sizeof(buf));
    prom_gauge(&p, "m", "k", "a\"b\\c\nd", 1);
    CHECK(strcmp(buf, "m{k=\"a\\\"b\\\\c\\nd\"} 1.000\n") == 0);

    prom_init(&p, buf, sizeof(buf));
    prom_gauge(&p, "1bad", NULL, NULL, 1);
    CHECK(prom_finish(&p) == -1);
    prom_init(&p, buf, 16);
    prom_gauge(&p, "zatt_frame_max_celsius", NULL, NULL, 1);
    CHECK(prom_finish(&p) == -1);
}

static void test_bmp280(void)
{
    // The datasheet's worked example: 25.08 degC and 100653.27 Pa.
    bmp280_calib_t c = {27504, 26435, -1000, 36477, -10685, 3024, 2855, 140, -7, 15500, -14600, 6000};
    float t, p;
    CHECK(bmp280_compensate(&c, 519888, 415148, &t, &p));
    CHECK(fabsf(t - 25.08f) < 0.01f);
    CHECK(fabsf(p - 100653.27f) < 1.0f);

    uint8_t raw[24] = {0x70, 0x6B, 0x43, 0x67, 0x18, 0xFC};  // T1 = 27504, T2 = 26435, T3 = -1000
    bmp280_calib_t d;
    bmp280_calib_parse(raw, &d);
    CHECK(d.T1 == 27504 && d.T2 == 26435 && d.T3 == -1000);
}

int main(void)
{
    test_rect();
    test_frame();
    test_prom();
    test_bmp280();
    puts(failures ? "FAILED" : "ok");
    return failures != 0;
}
