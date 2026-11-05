// SW1's debounce. Portable, so the host tests it. The control task polls GPIO9 every
// BUTTON_POLL_MS and feeds each reading here; a level counts once it has held for
// BUTTON_DEBOUNCE_MS, and a press is the debounced change from released to pressed.
#pragma once

#include <stdbool.h>
#include <stdint.h>

#define BUTTON_POLL_MS 5
#define BUTTON_DEBOUNCE_MS 30

typedef struct
{
    bool started;
    bool stable;       // the debounced level (true = pressed)
    bool last;         // the last raw reading
    int64_t since_ms;  // when the raw reading last changed
} button_t;

void button_init(button_t *b);

// One reading. True once per press, when it has held for BUTTON_DEBOUNCE_MS. The first reading is
// taken as the starting level, so a button held through boot is no press.
bool button_update(button_t *b, bool pressed, int64_t now_ms);
