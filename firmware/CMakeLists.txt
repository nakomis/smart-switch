# Host build of Petro's portable code, for the tests (python -m pytest -q firmware/tests). The
# ESP32-C6 image is built from esp32c6/ with idf.py; it compiles the same port/ sources.
#
#   cmake -S firmware -B firmware/build
#   cmake --build firmware/build
#
# Every port/*.c joins petro_port, and every tools/<name>_main.c becomes the driver petro-<name>, so
# a new module is just its files. -DPETRO_COVERAGE=ON instruments port/ for gcov/lcov.
cmake_minimum_required(VERSION 3.20)
project(petro_host C)

set(CMAKE_C_STANDARD 11)
set(CMAKE_C_STANDARD_REQUIRED ON)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)
option(PETRO_COVERAGE "Build port/ with --coverage" OFF)

file(GLOB PETRO_PORT_SOURCES CONFIGURE_DEPENDS ${CMAKE_CURRENT_SOURCE_DIR}/port/*.c)
add_library(petro_port STATIC ${PETRO_PORT_SOURCES})
target_include_directories(petro_port PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/port)
target_link_libraries(petro_port PUBLIC m)
target_compile_options(petro_port PRIVATE -Wall -Wextra -Werror)
if(PETRO_COVERAGE)
  target_compile_options(petro_port PRIVATE --coverage -O0)
  target_link_options(petro_port PUBLIC --coverage)
endif()

file(GLOB PETRO_DRIVERS CONFIGURE_DEPENDS ${CMAKE_CURRENT_SOURCE_DIR}/tools/*_main.c)
foreach(driver ${PETRO_DRIVERS})
  get_filename_component(stem ${driver} NAME_WE)
  string(REGEX REPLACE "_main$" "" stem ${stem})
  add_executable(petro-${stem} ${driver})
  target_link_libraries(petro-${stem} PRIVATE petro_port)
  target_compile_options(petro-${stem} PRIVATE -Wall -Wextra -Werror)
endforeach()
