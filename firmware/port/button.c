// SW1's debounce. See button.h.
#include "button.h"

#include <string.h>

void button_init(button_t *b)
{
    memset(b, 0, sizeof(*b));
}

bool button_update(button_t *b, bool pressed, int64_t now_ms)
{
    if (!b->started)
    {
        b->started = true;
        b->stable = b->last = pressed;
        b->since_ms = now_ms;
        return false;
    }
    if (pressed != b->last)
    {
        b->last = pressed;
        b->since_ms = now_ms;
        return false;
    }
    if (pressed == b->stable || now_ms - b->since_ms < BUTTON_DEBOUNCE_MS)
        return false;
    b->stable = pressed;
    return pressed;
}
