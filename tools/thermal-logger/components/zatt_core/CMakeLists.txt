# Pure C with no IDF dependencies, so tests/test_core.c builds it on the host.
idf_component_register(SRCS "thermal.c" "prom.c" "bmp280_calc.c"
                       INCLUDE_DIRS "include")
