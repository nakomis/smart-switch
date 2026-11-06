// The VictoriaMetrics push (Gates 3 and 4): every METRICS_INTERVAL_MS, port/prom.c's text POSTed
// to vmauth on Cal with basic auth from prov (metrics_url, metrics_user, metrics_pass). The URL
// gets /api/v1/import/prometheus when prov's has no path.
//
// Never in the way: a lowest-but-one priority task, a short timeout on every request, nothing
// while Wi-Fi is down or an update runs, and a failed POST is dropped (one log line per run of
// failures). The relay never waits on it.
#pragma once

#include "prov.h"

#define METRICS_INTERVAL_MS 10000

// Starts the push if prov has metrics (metrics_url set); otherwise logs and does nothing. `prov`
// must stay valid for the life of the program.
void metrics_start(const prov_t *prov);
