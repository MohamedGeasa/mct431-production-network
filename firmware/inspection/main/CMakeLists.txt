idf_component_register(SRCS "main.c" "wifi_station.c" "tcp_link.c" INCLUDE_DIRS "."
    REQUIRES mct_node esp_wifi esp_event esp_netif nvs_flash esp_timer esp_system lwip)
