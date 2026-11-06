// This unit's own settings and credentials, read (never written) from the `prov` NVS partition
// that the provisioning script writes. Nothing here is in the firmware image, so every Petro runs
// the same image and a published update holds no secrets.
#pragma once

#include <stdbool.h>
#include <stddef.h>

#define PROV_PARTITION "prov"
#define PROV_NAMESPACE "petro"

// Every key the provisioning script writes.
extern const char *const PROV_KEYS[];
extern const size_t PROV_KEY_COUNT;

typedef struct
{
    bool opened;                // the partition and namespace exist
    const char *error;          // why not, when !opened
    bool present[16];           // per PROV_KEYS
} prov_state_t;

// Which keys are present. Never reads a value.
void prov_state(prov_state_t *state);

// Reads one string value into out. False if missing or too long. The caller must never log what
// comes back.
bool prov_get_str(const char *key, char *out, size_t out_len);

// Everything the network needs (the sizes are the provisioning script's limits, plus the NUL).
// The three metrics_* keys are all present or all absent: absent means no metrics (metrics_url[0]
// is then 0).
typedef struct
{
    char wifi_ssid[33];
    char wifi_pass[64];
    char endpoint[128];
    char thing[129];  // also the MQTT client id
    char *cert;       // PEM, malloc'd
    char *key;        // PEM, malloc'd
    char metrics_url[128];
    char metrics_user[33];
    char metrics_pass[65];
} prov_t;

// Loads it all. False (logging which key, never a value) if Wi-Fi, the endpoint, the Thing, the
// certificate or the key is missing: the unit is then unprovisioned and runs without the network.
bool prov_load(prov_t *prov);
