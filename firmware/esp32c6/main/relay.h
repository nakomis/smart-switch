// The relay, switched at the mains' zero crossings (port/zx.h): a close or an open is scheduled on
// an esp_timer so the contacts move at a crossing, allowing for the relay's operate and release
// times (Kconfig PETRO_RELAY_OPERATE_US, PETRO_RELAY_RELEASE_US). With no fresh ZX edges (no
// mains), or `immediate` (every trip, the shutdown, the health gate), it switches at once.
//
// A later call always wins: a pending switch is cancelled, and the timer's callback applies the
// latest target, so a stale callback can never re-close a relay that has since been opened. The
// OC interrupt (board.c) opens the relay itself and holds it open; nothing here can close it then.
#pragma once

#include <stdbool.h>
#include <stdint.h>

#include "esp_err.h"

esp_err_t relay_init(void);

// From any task.
void relay_set(bool on, bool immediate);

// Whether a switch now would be timed to a crossing (ZX edges seen in the last 100 ms).
bool relay_zx_sync(void);

// How the last switches went, for the console: timed to a crossing, and at once.
void relay_counts(uint32_t *timed, uint32_t *at_once);
