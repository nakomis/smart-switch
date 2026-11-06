// The bench console on the USB-Serial-JTAG (Gate 2). See console.c.
#pragma once

#include "esp_err.h"

// Registers the commands and starts the REPL task.
esp_err_t console_start(void);
