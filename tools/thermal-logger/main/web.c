// A tiny LAN-only HTTP server, for choosing the spot rectangles.
//
//   GET  /            the heatmap page (web/index.html): hover for pixel coordinates, drag a rectangle
//   GET  /frame.json  the latest 32x24 frame, the sensors' readings and the current spots
//   POST /spots       {"T1":[x0,y0,x1,y1],"T3":null,...} saves those rectangles to NVS
//
// The two GETs are unauthenticated (they only show a temperature picture of the inside of a box on
// the LAN). POST needs "Authorization: Bearer <http_token>" with the token from prov; without a
// token in prov, POST is refused outright.
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "cJSON.h"
#include "esp_http_server.h"
#include "esp_log.h"
#include "esp_timer.h"
#include "sdkconfig.h"
#include "zatt.h"

static const char *TAG = "web";
extern const char index_html_start[] asm("_binary_index_html_start");
extern const char index_html_end[] asm("_binary_index_html_end");

static char token[65];

static esp_err_t get_index(httpd_req_t *req)
{
    httpd_resp_set_type(req, "text/html");
    return httpd_resp_send(req, index_html_start, index_html_end - index_html_start - 1);
}

static void put_num(char **p, char *end, float v, const char *fmt)
{
    if (*p >= end - 16)
        return;
    *p += isfinite(v) ? snprintf(*p, end - *p, fmt, v) : snprintf(*p, end - *p, "null");
}

static esp_err_t get_frame(httpd_req_t *req)
{
    size_t cap = 9000;
    char *out = malloc(cap + sizeof(zatt_snapshot_t));
    if (out == NULL)
        return httpd_resp_send_500(req);
    zatt_snapshot_t *s = (zatt_snapshot_t *)(out + cap);
    sensors_snapshot(s);
    char *p = out, *end = out + cap;
    p += snprintf(p, end - p, "{\"w\":%d,\"h\":%d,\"frames\":%u,\"up\":%lld,\"ta\":", ZATT_W, ZATT_H,
                  (unsigned)s->frames, (long long)(esp_timer_get_time() / 1000000));
    put_num(&p, end, s->ta, "%.2f");
    p += snprintf(p, end - p, ",\"air\":");
    put_num(&p, end, s->air, "%.2f");
    p += snprintf(p, end - p, ",\"pa\":");
    put_num(&p, end, s->pressure, "%.0f");
    p += snprintf(p, end - p, ",\"spots\":{");
    for (int i = 0; i < ZATT_NSPOTS; i++)
    {
        zatt_rect_t r = spots_get(i);
        if (r.x0 < 0)
            p += snprintf(p, end - p, "%s\"%s\":null", i ? "," : "", spots_name(i));
        else
            p += snprintf(p, end - p, "%s\"%s\":[%d,%d,%d,%d]", i ? "," : "", spots_name(i), r.x0, r.y0, r.x1, r.y1);
    }
    p += snprintf(p, end - p, "},\"data\":[");
    for (int i = 0; i < ZATT_PIXELS; i++)
    {
        if (i)
            *p++ = ',';
        put_num(&p, end, s->frames ? s->to[i] : NAN, "%.1f");
    }
    p += snprintf(p, end - p, "]}");
    httpd_resp_set_type(req, "application/json");
    httpd_resp_set_hdr(req, "Cache-Control", "no-store");
    esp_err_t err = httpd_resp_send(req, out, p - out);
    free(out);
    return err;
}

static bool token_ok(httpd_req_t *req)
{
    if (token[0] == 0)
        return false;
    char h[96];
    if (httpd_req_get_hdr_value_str(req, "Authorization", h, sizeof(h)) != ESP_OK || strncmp(h, "Bearer ", 7) != 0)
        return false;
    const char *given = h + 7;
    size_t n = strlen(token);
    unsigned diff = strlen(given) ^ n;  // constant-time over the token's length
    for (size_t i = 0; i < n; i++)
        diff |= (unsigned char)given[i] ^ (unsigned char)token[i];
    return diff == 0;
}

static esp_err_t post_spots(httpd_req_t *req)
{
    if (!token_ok(req))
    {
        httpd_resp_set_status(req, token[0] ? "401 Unauthorized" : "403 Forbidden");
        return httpd_resp_sendstr(req, "token required\n");
    }
    char buf[512];
    if (req->content_len == 0 || req->content_len >= sizeof(buf))
    {
        httpd_resp_set_status(req, "400 Bad Request");
        return httpd_resp_sendstr(req, "bad body size\n");
    }
    int got = 0;
    while (got < (int)req->content_len)
    {
        int r = httpd_req_recv(req, buf + got, req->content_len - got);
        if (r <= 0)
            return ESP_FAIL;
        got += r;
    }
    buf[got] = 0;

    // Validate everything first, then apply, so a bad request changes nothing.
    cJSON *root = cJSON_Parse(buf);
    zatt_rect_t next[ZATT_NSPOTS];
    bool set[ZATT_NSPOTS] = {false};
    bool ok = cJSON_IsObject(root);
    for (cJSON *it = ok ? root->child : NULL; ok && it; it = it->next)
    {
        int idx = it->string ? spots_index(it->string) : -1;
        if (idx < 0)
        {
            ok = false;
            break;
        }
        if (cJSON_IsNull(it))
            next[idx] = zatt_rect_disabled();
        else if (cJSON_IsArray(it) && cJSON_GetArraySize(it) == 4)
        {
            int v[4];
            for (int k = 0; k < 4; k++)
            {
                cJSON *n = cJSON_GetArrayItem(it, k);
                if (!cJSON_IsNumber(n) || n->valueint < 0 || n->valueint > 127)
                    ok = false;
                else
                    v[k] = n->valueint;
            }
            if (ok)
            {
                next[idx] = (zatt_rect_t){v[0], v[1], v[2], v[3]};
                ok = zatt_rect_valid(&next[idx]);
            }
        }
        else
            ok = false;
        set[idx] = true;
    }
    cJSON_Delete(root);
    if (!ok)
    {
        httpd_resp_set_status(req, "400 Bad Request");
        return httpd_resp_sendstr(req, "expected {\"T1\":[x0,y0,x1,y1] or null, ...}, inside 32x24\n");
    }
    for (int i = 0; i < ZATT_NSPOTS; i++)
        if (set[i] && spots_set(i, next[i]) != ESP_OK)
        {
            httpd_resp_set_status(req, "500 Internal Server Error");
            return httpd_resp_sendstr(req, "NVS write failed\n");
        }
    ESP_LOGI(TAG, "spots saved");
    return httpd_resp_sendstr(req, "saved\n");
}

void web_start(const prov_t *p)
{
    strlcpy(token, p->http_token, sizeof(token));
    httpd_config_t cfg = HTTPD_DEFAULT_CONFIG();
    cfg.server_port = CONFIG_ZATT_HTTP_PORT;
    cfg.stack_size = 8192;
    cfg.max_open_sockets = 4;
    cfg.lru_purge_enable = true;
    httpd_handle_t srv;
    if (httpd_start(&srv, &cfg) != ESP_OK)
    {
        ESP_LOGE(TAG, "HTTP server failed to start");
        return;
    }
    httpd_uri_t uris[] = {
        {.uri = "/", .method = HTTP_GET, .handler = get_index},
        {.uri = "/frame.json", .method = HTTP_GET, .handler = get_frame},
        {.uri = "/spots", .method = HTTP_POST, .handler = post_spots},
    };
    for (size_t i = 0; i < sizeof(uris) / sizeof(uris[0]); i++)
        httpd_register_uri_handler(srv, &uris[i]);
    ESP_LOGI(TAG, "HTTP on port %d", CONFIG_ZATT_HTTP_PORT);
}
