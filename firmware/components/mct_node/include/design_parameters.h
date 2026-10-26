#pragma once
/* Firmware design limits and link defaults. Batch settings arrive over the wire.
 * Keep Python BatchConfig limits aligned with these validation limits. */
#define MCT_BAUD_RATE 115200
#define MCT_UART_BUFFER_SIZE 2048
#define MCT_HEARTBEAT_MS 1000
#define MCT_GATEWAY_WATCHDOG_MS 6000
#define MCT_LOOP_MS 10
#define MCT_MIN_DURATION_MS 1
#define MCT_MAX_DURATION_MS 60000
#define MCT_MAX_RULE_PARAMETER 1000000
#define MCT_TCP_PORT 9000
#define MCT_TCP_SEND_TIMEOUT_MS 500
