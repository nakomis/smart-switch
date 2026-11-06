# Petro firmware for the ESP32-C6-WROOM-1-N8: the bench console (PETRO-3, slice 1) over the C6's
# USB-Serial-JTAG, for Gate 2.
#
#   . ~/esp/esp-idf/export.sh
#   idf.py -C firmware/esp32c6 set-target esp32c6
#   idf.py -C firmware/esp32c6 build
#
# The version is esp32c6/version.txt: IDF reads it into PROJECT_VER (and so esp_app_desc). Bump it
# with every firmware change.
cmake_minimum_required(VERSION 3.16)

set(IDF_TARGET esp32c6)
include($ENV{IDF_PATH}/tools/cmake/project.cmake)
project(petro)
