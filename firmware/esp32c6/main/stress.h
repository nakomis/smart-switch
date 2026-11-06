// Gate 3's Wi-Fi transmit-stress mode: continuous traffic for the supply's hour under load, rather
// than one push every 10 s. While on, a lowest-priority task sends 1400-byte UDP datagrams to the
// discard port (9) of the Wi-Fi gateway, as fast as lwIP takes them (yielding every packet), so the
// radio transmits nearly all the time. Nothing answers and nothing is stored. RAM only: a reboot
// ends it, and it ends by itself after its duration. It pauses while Wi-Fi is down or an update runs.
#pragma once

#include <stdbool.h>
#include <stdint.h>

// Starts (or restarts) it for duration_s. False if the task couldn't be created.
bool stress_start(uint32_t duration_s);
void stress_stop(void);

// Seconds left, or 0 when off.
uint32_t stress_left_s(void);
