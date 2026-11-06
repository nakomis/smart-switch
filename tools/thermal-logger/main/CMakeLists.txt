idf_component_register(SRCS "main.c" "prov.c" "wifi.c" "i2c_bus.c" "mlx_i2c.c" "bmp280.c" "sensors.c"
                            "spots.c" "metrics.c" "web.c" "battery.c"
                       INCLUDE_DIRS "."
                       REQUIRES mlx90640 zatt_core
                       PRIV_REQUIRES nvs_flash esp_wifi esp_netif esp_event esp_http_client esp_http_server
                                     esp_driver_i2c esp_adc esp_timer json mbedtls
                       EMBED_TXTFILES "../web/index.html")
