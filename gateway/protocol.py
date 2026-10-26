"""Wire format shared with firmware/components/mct_protocol. No native packing."""
from dataclasses import dataclass, replace
from enum import IntEnum
import binascii
import struct

VERSION = 1
MESSAGE = struct.Struct("!BBBBQIIIIII")  # 36 bytes, big-endian
ATR_HEADER = struct.Struct("!HIH")
END, ESC, ESC_END, ESC_ESC = 0xC0, 0xDB, 0xDC, 0xDD


class Kind(IntEnum):
    COMMAND = 1
    DELIVERED = 2
    ACCEPTED = 3
    COMPLETED = 4
    REJECTED = 5
    HELLO = 6
    PING = 7


class Op(IntEnum):
    BIND = 1
    CONFIG = 2
    PRODUCE = 3
    INSPECT = 4


class Result(IntEnum):
    OK = 0
    PASS = 1
    FAIL = 2


@dataclass(frozen=True)
class Message:
    kind: int
    op: int
    station: int
    session: int
    command: int = 0
    part: int = 0
    arg0: int = 0
    arg1: int = 0
    arg2: int = 0
    boot: int = 0

    def pack(self) -> bytes:
        return MESSAGE.pack(VERSION, self.kind, self.op, self.station, self.session,
                            self.command, self.part, self.arg0, self.arg1, self.arg2, self.boot)

    @classmethod
    def unpack(cls, data: bytes):
        if len(data) != MESSAGE.size:
            raise ValueError("application message must be 36 bytes")
        version, *fields = MESSAGE.unpack(data)
        if version != VERSION:
            raise ValueError("unsupported message version")
        return cls(*fields)

    def reply(self, kind, result=None):
        return replace(self, kind=kind, **({"arg0": result} if result is not None else {}))


def atr_pack(payload: bytes, seq: int, test_id: int = 1) -> bytes:
    header = ATR_HEADER.pack(test_id, seq, len(payload))
    body = header + payload
    return body + struct.pack("!H", binascii.crc_hqx(body, 0xFFFF))


def atr_unpack(record: bytes) -> tuple[int, int, bytes]:
    if len(record) < 10:
        raise ValueError("short ATR")
    test_id, seq, size = ATR_HEADER.unpack(record[:8])
    if len(record) != 10 + size or size > 128:
        raise ValueError("invalid ATR length")
    if binascii.crc_hqx(record[:-2], 0xFFFF) != int.from_bytes(record[-2:], "big"):
        raise ValueError("CRC mismatch")
    return test_id, seq, record[8:-2]


def slip_encode(data: bytes) -> bytes:
    return bytes([END]) + data.replace(bytes([ESC]), bytes([ESC, ESC_ESC])).replace(
        bytes([END]), bytes([ESC, ESC_END])) + bytes([END])


class SlipDecoder:
    """Incremental decoding with noise, overflow, and invalid-escape recovery."""
    def __init__(self, maximum=138):
        self.maximum = maximum
        self.buffer = bytearray()
        self.started = False
        self.escaped = False
        self.invalid = False

    def feed(self, data: bytes) -> list[bytes]:
        records = []
        for value in data:
            if value == END:
                if self.started and self.buffer and not self.invalid and not self.escaped:
                    records.append(bytes(self.buffer))
                self.buffer.clear()
                self.started, self.escaped, self.invalid = True, False, False
            elif self.started and not self.invalid:
                if self.escaped:
                    if value not in (ESC_END, ESC_ESC):
                        self.invalid = True
                        continue
                    self.buffer.append(END if value == ESC_END else ESC)
                    self.escaped = False
                elif value == ESC:
                    self.escaped = True
                else:
                    self.buffer.append(value)
                if len(self.buffer) > self.maximum:
                    self.invalid = True
        return records
