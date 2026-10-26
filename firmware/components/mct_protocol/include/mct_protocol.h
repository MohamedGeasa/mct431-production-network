#pragma once
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#define MCT_MESSAGE_SIZE 36
#define MCT_ATR_MAX 138
#define MCT_VERSION 1
enum mct_kind { MCT_COMMAND=1, MCT_DELIVERED, MCT_ACCEPTED, MCT_COMPLETED, MCT_REJECTED, MCT_HELLO, MCT_PING };
enum mct_op { MCT_BIND=1, MCT_CONFIG, MCT_PRODUCE, MCT_INSPECT };
enum mct_result { MCT_OK=0, MCT_PASS=1, MCT_FAIL=2 };
enum mct_error { MCT_BAD_BINDING=1, MCT_OLD_ID=2, MCT_BUSY=3, MCT_BAD_COMMAND=4 };

typedef struct {
    uint8_t kind, op, station;
    uint64_t session;
    uint32_t command, part, arg0, arg1, arg2, boot;
} mct_message_t;

typedef struct {
    uint8_t data[MCT_ATR_MAX];
    size_t length;
    bool started, escaped, invalid;
} mct_slip_t;

void mct_pack(const mct_message_t *message, uint8_t out[MCT_MESSAGE_SIZE]);
bool mct_unpack(const uint8_t *data, size_t length, mct_message_t *out);
bool mct_equal(const mct_message_t *a, const mct_message_t *b);
uint16_t mct_crc(const uint8_t *data, size_t length);
size_t mct_atr_pack(const uint8_t *payload, size_t length, uint32_t seq, uint8_t *out);
bool mct_atr_unpack(const uint8_t *data, size_t length, mct_message_t *out);
size_t mct_slip_encode(const uint8_t *data, size_t length, uint8_t *out);
bool mct_slip_feed(mct_slip_t *decoder, uint8_t value, mct_message_t *out);
