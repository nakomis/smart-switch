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

// Reads one string value into out (for later slices: Wi-Fi, Fleet, metrics). False if missing or
// too long. The caller must never log what comes back.
bool prov_get_str(const char *key, char *out, size_t out_len);
