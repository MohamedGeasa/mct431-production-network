#pragma once
#include "mct_protocol.h"
#include <stdbool.h>
#include <stdint.h>
typedef void (*mct_send_fn)(const mct_message_t *, void *);
typedef struct {
    uint8_t station;
    uint32_t boot, duration_ms, modulus, offset;
    uint64_t session;
    bool configured, has_last, busy, has_result;
    int64_t deadline_ms, last_gateway_ms, next_hello_ms;
    mct_message_t last, result;
    mct_send_fn send;
    void *context;
} mct_node_t;

void mct_node_init(mct_node_t *node, uint8_t station, uint32_t boot, mct_send_fn send, void *context);
void mct_node_receive(mct_node_t *node, const mct_message_t *message, int64_t now_ms);
/* False means gateway watchdog expired: caller must reboot to invalidate boot ID. */
bool mct_node_tick(mct_node_t *node, int64_t now_ms);
