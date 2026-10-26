import binascii
from dataclasses import replace
import pytest
from gateway.config import BatchConfig
from gateway.protocol import Message, Kind, Op, SlipDecoder, slip_encode, atr_pack, atr_unpack


def test_crc_reference_and_cross_language_wire_vector():
    assert binascii.crc_hqx(b"123456789", 0xFFFF) == 0x29B1
    message = Message(Kind.COMMAND, Op.INSPECT, 2, 0x0102030405060708, 7, 8, 9, 10, 11, 0x12345678)
    assert message.pack().hex() == "0101040201020304050607080000000700000008000000090000000a0000000b12345678"
    assert Message.unpack(message.pack()) == message


def test_slip_fragmented_noise_escaped_bytes_and_multiple_frames():
    record = atr_pack(bytes([0xC0, 0xDB, 1, 0]), 123)
    wire = b"ROM boot noise" + slip_encode(record) + slip_encode(record)
    decoder = SlipDecoder()
    frames = []
    for value in wire:
        frames.extend(decoder.feed(bytes([value])))
    assert frames == [record, record]
    assert atr_unpack(frames[0]) == (1, 123, bytes([0xC0, 0xDB, 1, 0]))


def test_corruption_lengths_and_decoder_recovery():
    record = atr_pack(b"payload", 0)
    damaged = bytearray(record)
    damaged[8] ^= 1
    with pytest.raises(ValueError, match="CRC"):
        atr_unpack(damaged)
    with pytest.raises(ValueError, match="length"):
        atr_unpack(record[:-1])
    decoder = SlipDecoder()
    assert decoder.feed(b"\xc0\xdb\x01\xc0" + b"x" * 200 + b"\xc0") == []
    assert decoder.feed(slip_encode(record)) == [record]


@pytest.mark.parametrize("field,value", [("queue_capacity",0),("queue_capacity",1025),("production_ms",0),
    ("inspection_ms",60001),("reject_modulus",0),("reject_offset",-1),("target_parts",True)])
def test_invalid_runtime_parameters(field, value):
    with pytest.raises(ValueError):
        BatchConfig(**{field:value})
