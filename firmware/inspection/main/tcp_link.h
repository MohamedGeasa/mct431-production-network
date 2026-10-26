#pragma once
#include "mct_node.h"
void tcp_link_run(mct_node_t *node);
void tcp_link_send(const mct_message_t *message,void *context);
