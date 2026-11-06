# Melexis' official MLX90640 API, vendored unmodified (Apache-2.0, see LICENSE) from
# github.com/melexis/mlx90640-library at f6be7ca. The I2C glue it calls is in main/mlx_i2c.c.
idf_component_register(SRCS "MLX90640_API.c"
                       INCLUDE_DIRS "include")
target_compile_options(${COMPONENT_LIB} PRIVATE -Wno-unused-variable -Wno-maybe-uninitialized)
