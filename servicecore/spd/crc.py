"""Wire helpers for the Spreadtrum BSL protocol.

BSL frames are HDLC-ish: a ``0x7E`` flag, an escaped payload, a two byte CRC16
and another flag. Payload bytes ``0x7E`` and ``0x7D`` are escaped with ``0x7D``
by XOR-ing ``0x20``. The CRC is CRC16-XMODEM (poly ``0x1021``, init ``0``) sent
little-endian.

Everything here is pure byte maths, so it is fully covered by unit tests and is
the first thing to inspect if a device answers "checksum error".
"""

from __future__ import annotations

import re

FLAG = 0x7E
ESCAPE = 0x7D
ESCAPE_XOR = 0x20
#: Largest command/reply payload seen in one frame (a block plus its header).
MAX_PAYLOAD = 0x10010


def crc16_xmodem(data: bytes, crc: int = 0) -> int:
    """CRC16-XMODEM: poly 0x1021, init 0, no reflection, no final xor."""
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            if crc & 0x8000:
                crc = ((crc << 1) ^ 0x1021) & 0xFFFF
            else:
                crc = (crc << 1) & 0xFFFF
    return crc & 0xFFFF


def add_sum16(data: bytes) -> int:
    """16-bit one's complement style checksum used by the FDL protocol."""
    total = 0
    for index in range(0, len(data) - 1, 2):
        total += (data[index] << 8) | data[index + 1]
    if len(data) % 2:
        total += data[-1]
    while total >> 16:
        total = (total & 0xFFFF) + (total >> 16)
    return (~total) & 0xFFFF


_NEEDS_ESCAPE = re.compile(b"[\\x7d\\x7e]")
_ESCAPED_PAIR = re.compile(b"\\x7d(.)", re.DOTALL)


def escape(data: bytes) -> bytes:
    """Escape ``0x7D``/``0x7E`` the HDLC way (regex: big blocks must stay fast)."""
    return _NEEDS_ESCAPE.sub(lambda match: bytes([ESCAPE, match.group()[0] ^ ESCAPE_XOR]), data)


def unescape(data: bytes) -> bytes:
    """Reverse :func:`escape`; stray flags are dropped."""
    body = data.replace(bytes([FLAG]), b"")
    return _ESCAPED_PAIR.sub(lambda match: bytes([match.group(1)[0] ^ ESCAPE_XOR]), body)


def encode_frame(payload: bytes) -> bytes:
    """Build ``FLAG + escaped(payload + crc16) + FLAG``."""
    if len(payload) > MAX_PAYLOAD:
        raise ValueError("payload too large for one frame (%d bytes)" % len(payload))
    body = payload + crc16_xmodem(payload).to_bytes(2, "little")
    return bytes([FLAG]) + escape(body) + bytes([FLAG])


class FrameReader:
    """Collect bytes and yield complete, CRC-checked payloads."""

    def __init__(self) -> None:
        self._buffer = bytearray()
        self.checksum_errors = 0

    def reset(self) -> None:
        self._buffer.clear()

    def feed(self, data: bytes) -> list[bytes]:
        """Append raw bytes and return every payload completed by them."""
        payloads: list[bytes] = []
        buffer = self._buffer
        position = 0
        while position < len(data):
            flag = data.find(bytes([FLAG]), position)
            if flag < 0:
                buffer.extend(data[position:])
                if len(buffer) > MAX_PAYLOAD * 2 + 64:
                    buffer.clear()
                break
            buffer.extend(data[position:flag])
            if len(buffer) >= 3:
                body = unescape(bytes(buffer))
                payload, crc_bytes = body[:-2], body[-2:]
                if crc16_xmodem(payload).to_bytes(2, "little") == crc_bytes:
                    payloads.append(payload)
                else:
                    self.checksum_errors += 1
            buffer.clear()
            position = flag + 1
        return payloads
