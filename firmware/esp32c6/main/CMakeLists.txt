# The portable code in ../../port (pure C, host-tested) joins the image here.
file(GLOB PORT_SOURCES ${COMPONENT_DIR}/../../port/*.c)

idf_component_register(
  SRCS main.c app.c board.c console.c metrics.c net.c ota.c prov.c relay.c store.c stress.c ${PORT_SOURCES}
  INCLUDE_DIRS "." ${COMPONENT_DIR}/../../port
  PRIV_REQUIRES console nvs_flash esp_wifi esp_netif esp_event esp_adc esp_driver_gpio
                esp_driver_uart esp_driver_i2c esp_driver_usb_serial_jtag esp_timer app_update esp_app_format
                mqtt json esp_http_client mbedtls lwip
  # Amazon Root CA 1 (public) for IoT Core and the OTA download. The unit's own certificate, key
  # and settings are not in the image: they're in the prov partition (prov.h).
  EMBED_TXTFILES ${COMPONENT_DIR}/../AmazonRootCA1.pem
)
