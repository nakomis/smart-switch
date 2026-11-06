// Network: Wi-Fi, SNTP and a held-open MQTT connection to AWS IoT Core (mutual TLS with Petro's
// own certificate). Fleet's commands arrive on petro/<thing>/commands; Petro answers on
// .../responses and reports on .../status. Everything here is best effort: Petro's own work
// (the button, the mode and the relay) never depends on it. Copied from the nakostat heatlink.
#pragma once

#include <stdbool.h>
#include <stddef.h>

#include "prov.h"

// Called on the MQTT task with one whole command (JSON, not NUL-terminated). Keep it quick.
typedef void (*net_command_cb)(const char *json, size_t len);

// Starts Wi-Fi, SNTP and MQTT in the background and returns at once. `prov` must stay valid for
// the life of the program. On any setup failure it logs and gives up (false).
bool net_start(const prov_t *prov, net_command_cb on_command);

// Publishes on petro/<thing>/responses at QoS 1. Copied into a queue for the network's tx task,
// so it never blocks: false (and dropped) if not connected, out of memory or the queue is full.
// Any task may call it.
bool net_respond(const char *json);

// Publishes on petro/<thing>/status at QoS 1, not retained. Same queueing as net_respond.
// Called only from the app task.
bool net_publish_status(const char *json);

// Whether IoT Core has acknowledged (PUBACK) the latest status queued by net_publish_status. QoS 1
// acknowledgements arrive in order, so this covers every earlier status too. True before the first.
bool net_status_acked(void);

// Whether net_start got as far as starting Wi-Fi (the console's wifi scan then only scans).
bool net_started(void);

// Whether Wi-Fi is associated and has an address.
bool net_wifi_up(void);

// Whether the MQTT connection to IoT Core is up.
bool net_mqtt_connected(void);

// Whether IoT Core has granted the subscription to .../commands on the current connection (a
// successful SUBACK): only then can Fleet reach Petro. Cleared on every disconnect.
bool net_subscribed(void);

// Signal strength of the access point in dBm, or 0 if not associated.
int net_rssi(void);
