"""Spreadtrum BSL client.

Frames (see :mod:`servicecore.spd.crc`)::

    host -> device   7E  escaped( cmd | len_lo len_hi | payload | crc16_lo crc16_hi )  7E
    device -> host   7E  escaped( cmd|0x80 | status | len_lo len_hi | data | crc16 )  7E

``status`` is ``0x00`` for success and ``0x01`` for a refused command, in which
case ``data`` is a short ASCII reason.

Large transfers are chunked into :data:`~servicecore.spd.constants.BLOCK_SIZE`
frames and acknowledged per chunk, which is what makes progress reporting and
"stop after this block" cancellation possible.
"""

from __future__ import annotations

import struct
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from . import constants as C
from .crc import FrameReader, encode_frame
from .transport import Transport, TransportError

#: How many bytes to ask the transport for at a time.
RECEIVE_CHUNK = 8192


class BslError(RuntimeError):
    """Base class for BSL failures."""


class BslTimeout(BslError):
    """The device did not answer in time."""


class BslNack(BslError):
    """The device refused a command (``status != 0``)."""


@dataclass(slots=True)
class ChipInfo:
    chip_id: int
    flash_id: int
    raw: bytes

    @property
    def chip_hex(self) -> str:
        return "0x%08X" % self.chip_id

    def as_dict(self) -> dict[str, Any]:
        return {"chip_id": self.chip_id, "chip": self.chip_hex, "flash_id": self.flash_id}


class BslClient:
    """Talk to a device in BSL (ROM) or FDL stage."""

    def __init__(
        self,
        transport: Transport,
        *,
        log: Callable[[str, str], None] | None = None,
        progress: Callable[[int], None] | None = None,
        timeout_scale: float = 1.0,
    ) -> None:
        self.transport = transport
        self._log = log or (lambda message, level="INFO": None)
        self._progress = progress or (lambda done: None)
        self._timeout_scale = max(0.1, float(timeout_scale))
        self._reader = FrameReader()
        self._pending: list[bytes] = []

    # -- low level ---------------------------------------------------------
    def close(self) -> None:
        try:
            self.transport.close()
        except Exception:
            pass

    def _receive(self, timeout: float) -> bytes | None:
        if self._pending:
            return self._pending.pop(0)
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            remaining = max(0.02, min(0.2, deadline - time.monotonic()))
            chunk = self.transport.read(RECEIVE_CHUNK, remaining)
            if not chunk:
                continue
            # A single read can span frame boundaries; keep every payload so a
            # large transfer is not silently truncated.
            self._pending.extend(self._reader.feed(chunk))
            if self._pending:
                return self._pending.pop(0)
        return None

    def _exchange(self, command: int, payload: bytes = b"", *, timeout: float | None = None) -> bytes:
        if len(payload) > 0xFFFF:
            raise BslError("payload too large: %d bytes" % len(payload))
        request = bytes([command]) + struct.pack("<H", len(payload)) + payload
        wait = (timeout if timeout is not None else C.COMMAND_TIMEOUT) * self._timeout_scale
        try:
            self.transport.write(encode_frame(request))
        except TransportError as exc:
            raise BslError(str(exc)) from exc

        response = self._receive(wait)
        if response is None:
            raise BslTimeout("no answer to command 0x%02X within %.1fs" % (command, wait))
        if len(response) < 4:
            raise BslError("short response to 0x%02X: %s" % (command, response.hex()))
        head, status = response[0], response[1]
        length = struct.unpack("<H", response[2:4])[0]
        data = response[4 : 4 + length]
        expected = command | C.RESPONSE_BIT
        if head != expected:
            raise BslError("unexpected answer 0x%02X to command 0x%02X" % (head, command))
        if status == C.NACK:
            raise BslNack(data.decode("ascii", "replace") or "command 0x%02X refused" % command)
        if status not in (C.ACK,):
            raise BslError("unknown status 0x%02X for command 0x%02X" % (status, command))
        return data

    # -- stage handshake ---------------------------------------------------
    def connect(self, retries: int = 3) -> bytes:
        """Sync with the ROM bootloader. Returns the device's connect reply."""
        last: Exception | None = None
        for attempt in range(1, max(1, retries) + 1):
            self._reader.reset()
            try:
                reply = self._exchange(C.CMD_CONNECT, timeout=C.CONNECT_TIMEOUT)
                self._log("BSL answered on attempt %d" % attempt, "OK")
                return reply
            except BslError as exc:
                last = exc
                self._log("BSL connect attempt %d failed: %s" % (attempt, exc), "WARN")
                time.sleep(0.25)
        raise BslError("could not sync with the BSL: %s" % last)

    def read_chip_type(self) -> ChipInfo:
        data = self._exchange(C.CMD_READ_CHIP_TYPE)
        if len(data) < 8:
            raise BslError("chip type reply too short: %s" % data.hex())
        chip_id, flash_id = struct.unpack("<II", data[:8])
        return ChipInfo(chip_id=chip_id, flash_id=flash_id, raw=data)

    def read_version(self) -> str:
        data = self._exchange(C.CMD_READ_VERSION)
        return data.rstrip(b"\x00").decode("ascii", "replace")

    def check_baud(self) -> bool:
        try:
            self._exchange(C.CMD_CHECK_BAUD, timeout=2.0)
            return True
        except BslError:
            return False

    # -- data path ---------------------------------------------------------
    def upload(self, data: bytes, *, block: int = C.ROM_BLOCK_SIZE) -> None:
        """Stream ``data`` to the device: START, then MID blocks, then END.

        A payload that fits in one block still needs both START and END, because
        the device only commits its buffer on END.
        """
        if not data:
            raise BslError("nothing to upload")
        total = len(data)
        chunks = [data[index : index + block] for index in range(0, total, block)]
        steps = max(1, len(chunks))
        for index, chunk in enumerate(chunks):
            command = C.CMD_START_DATA if index == 0 else (
                C.CMD_END_DATA if index == len(chunks) - 1 else C.CMD_MID_DATA
            )
            self._exchange(command, chunk, timeout=C.READ_TIMEOUT)
            self._progress(int(100.0 * (index + 1) / steps))
        if len(chunks) == 1:
            self._exchange(C.CMD_END_DATA, b"", timeout=C.READ_TIMEOUT)
        self._log("Uploaded %d bytes in %d block(s)" % (total, len(chunks)), "INFO")

    def exec_data(self, address: int) -> None:
        self._exchange(C.CMD_EXEC_DATA, struct.pack("<IH", address, C.TAG_EXEC), timeout=C.EXEC_TIMEOUT)

    def read_flash(self, address: int, size: int, *, block: int = C.BLOCK_SIZE) -> bytes:
        if size <= 0:
            raise BslError("read size must be positive")
        out = bytearray()
        done = 0
        while done < size:
            chunk = min(block, size - done)
            header = struct.pack("<II", address + done, chunk)
            if done == 0:
                data = self._exchange(C.CMD_READ_FLASH_START, header, timeout=C.READ_TIMEOUT)
            else:
                data = self._exchange(C.CMD_READ_FLASH_MIDST, header, timeout=C.READ_TIMEOUT)
            out.extend(data)
            done += chunk
            self._progress(int(100.0 * done / size))
        tail = self._exchange(C.CMD_READ_FLASH_END, struct.pack("<II", address + done, 0), timeout=C.READ_TIMEOUT)
        if tail:
            out.extend(tail)
        if len(out) < size:
            raise BslError("short read: got %d of %d bytes" % (len(out), size))
        return bytes(out[:size])

    def write_flash(self, address: int, data: bytes, *, block: int = C.BLOCK_SIZE) -> None:
        if not data:
            raise BslError("nothing to write")
        header = struct.pack("<II", address, len(data))
        self._exchange(C.CMD_WRITE_FLASH_START, header, timeout=C.READ_TIMEOUT)
        self.upload(data, block=block if block < C.ROM_BLOCK_SIZE * 2 else C.ROM_BLOCK_SIZE)
        self._log("Wrote %d bytes at 0x%08X" % (len(data), address), "OK")

    def erase_flash(self, address: int, size: int) -> None:
        if size <= 0:
            raise BslError("erase size must be positive")
        self._exchange(C.CMD_ERASE_FLASH, struct.pack("<II", address, size), timeout=C.ERASE_TIMEOUT)
        self._log("Erased 0x%X bytes at 0x%08X" % (size, address), "OK")

    def reboot(self) -> None:
        try:
            self._exchange(C.CMD_NORMAL_RESET, timeout=2.0)
        except BslError:
            # The device usually reboots before answering; not an error.
            pass

    def power_off(self) -> None:
        try:
            self._exchange(C.CMD_POWER_OFF, timeout=2.0)
        except BslError:
            pass
