#include "mct_node.h"
#include "wifi_station.h"
#include "tcp_link.h"
#include "esp_random.h"

void app_main(void) {
    wifi_station_start();
    mct_node_t node;mct_node_init(&node,2,esp_random(),tcp_link_send,NULL);
    tcp_link_run(&node);
}
