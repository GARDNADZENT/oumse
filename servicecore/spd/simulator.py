"""An in-memory Spreadtrum device.

This is the device side of the BSL protocol implemented against the same
specification as :mod:`servicecore.spd.protocol`. It exists so the whole data
path - framing, chunking, erase, partition table, error handling - can be
proven without a phone, both in unit tests and through the real frozen runner
(``BestMDMToolRunner.exe --engine spd --selftest --simulate``).

It is never used for real flashing: the runner only reaches it when the caller
explicitly asks for ``transport="simulator"``.
"""

from __future__ import annotations

import struct
from typing import Any

from . import constants as C
from .crc import FrameReader, encode_frame
from .transport import pair

DEFAULT_PARTITIONS = (
    ("splloader", 0x00000000, 0x00040000),
    ("uboot", 0x00040000, 0x00080000),
    ("boot", 0x000C0000, 0x00100000),
    ("system", 0x001C0000, 0x00400000),
    ("userdata", 0x005C0000, 0x00200000),
    ("miscdata", 0x007C0000, 0x00080000),
)


class SimulatedDevice:
    """A fake SPD device with a flat flash image and partition table."""

    def __init__(
        self,
        *,
        chip_id: int = 0x9832,
        flash_id: int = 0x00170000,
        flash_size: int = 0x04000000,
        partitions=DEFAULT_PARTITIONS,
        version: str = "SPL-SIM-1.0",
        write_protected: tuple[str, ...] = (),
    ) -> None:
        self.chip_id = chip_id
        self.flash_id = flash_id
        self.flash = bytearray(flash_size)
        self.partitions = [(str(name), int(offset), int(size)) for name, offset, size in partitions]
        self.version = version
        self.write_protected = tuple(write_protected)
        self.reader = FrameReader()
        self.host, self.device = pair()
        self.device.service = self.serve
        self.connected = False
        self.write_target: tuple[int, int] | None = None
        self.write_buffer = bytearray()
        self.read_offset = 0
        self.rebooted = False
        self.commands: list[int] = []

    # -- wiring ------------------------------------------------------------
    def serve(self) -> None:
        """Answer every complete frame waiting in the device inbox."""
        if not self.device.inbox:
            return
        data = bytes(self.device.inbox)
        self.device.inbox.clear()
        for payload in self.reader.feed(data):
            self._handle(payload)

    def _respond(self, command: int, status: int = C.ACK, data: bytes = b"") -> None:
        if len(data) > 0xFFFF:
            status = C.NACK
            data = b"reply too large"
        reply = bytes([command | C.RESPONSE_BIT, status]) + struct.pack("<H", len(data)) + data
        self.device.write(encode_frame(reply))

    def _nack(self, command: int, reason: str) -> None:
        self._respond(command, C.NACK, reason.encode("ascii", "replace")[:60])

    # -- helpers -----------------------------------------------------------
    def partition_entries(self) -> list[dict[str, Any]]:
        return [
            {"name": name, "offset": offset, "size": size, "address": offset}
            for name, offset, size in self.partitions
        ]

    def _find(self, name: str) -> tuple[str, int, int] | None:
        wanted = name.lower()
        for entry in self.partitions:
            if entry[0].lower() == wanted:
                return entry
        return None

    def _check_range(self, address: int, size: int) -> str | None:
        if address < 0 or size < 0:
            return "negative range"
        if address + size > len(self.flash):
            return "outside flash"
        for name, offset, length in self.partitions:
            if name in self.write_protected and address < offset + length and offset < address + size:
                return "partition %s is write protected" % name
        return None

    # -- command handling --------------------------------------------------
    def _handle(self, payload: bytes) -> None:
        if len(payload) < 3:
            return
        command = payload[0]
        length = struct.unpack("<H", payload[1:3])[0]
        data = payload[3 : 3 + length]
        self.commands.append(command)

        if command == C.CMD_CONNECT:
            self.connected = True
            self._respond(command, data=b"BSL")
        elif command == C.CMD_READ_CHIP_TYPE:
            self._respond(command, data=struct.pack("<II", self.chip_id, self.flash_id))
        elif command == C.CMD_READ_VERSION:
            self._respond(command, data=self.version.encode("ascii"))
        elif command == C.CMD_CHECK_BAUD:
            self._respond(command)
        elif command == C.CMD_READ_PARTITION:
            self._respond(command, data=self._partition_payload())
        elif command == C.CMD_READ_FLASH_INFO:
            self._respond(command, data=struct.pack("<II", len(self.flash), 0x1000))
        elif command in (C.CMD_READ_FLASH_START, C.CMD_READ_FLASH_MIDST):
            self._handle_read(command, data)
        elif command == C.CMD_READ_FLASH_END:
            self.read_offset = 0
            self._respond(command)
        elif command == C.CMD_WRITE_FLASH_START:
            self._handle_write_start(command, data)
        elif command == C.CMD_START_DATA:
            self._handle_data_start(command, data)
        elif command == C.CMD_MID_DATA:
            self._handle_data_mid(command, data)
        elif command == C.CMD_END_DATA:
            self._handle_data_end(command, data)
        elif command == C.CMD_ERASE_FLASH:
            self._handle_erase(command, data)
        elif command == C.CMD_EXEC_DATA:
            self._respond(command)
        elif command in (C.CMD_NORMAL_RESET, C.CMD_POWER_OFF):
            self.connected = False
            self.rebooted = True
            self._respond(command)
        else:
            self._nack(command, "unsupported command 0x%02X" % command)

    def _partition_payload(self) -> bytes:
        out = bytearray(struct.pack("<H", len(self.partitions)))
        for name, offset, size in self.partitions:
            raw = name.encode("ascii", "replace")[: C.PART_NAME_LEN]
            out.extend(raw.ljust(C.PART_NAME_LEN, b"\x00"))
            out.extend(struct.pack("<II", offset, size))
        return bytes(out)

    def _handle_read(self, command: int, data: bytes) -> None:
        if len(data) < 8:
            self._nack(command, "missing range")
            return
        address, size = struct.unpack("<II", data[:8])
        reason = self._check_range(address, size)
        if reason:
            self._nack(command, reason)
            return
        self.read_offset = address + size
        self._respond(command, data=bytes(self.flash[address : address + size]))

    def _handle_write_start(self, command: int, data: bytes) -> None:
        if len(data) < 8:
            self._nack(command, "missing range")
            return
        address, size = struct.unpack("<II", data[:8])
        reason = self._check_range(address, size)
        if reason:
            self._nack(command, reason)
            return
        self.write_target = (address, size)
        self.write_buffer = bytearray()
        self._respond(command)

    def _handle_data_start(self, command: int, data: bytes) -> None:
        if self.write_target is None:
            self._nack(command, "no write in progress")
            return
        self.write_buffer = bytearray(data)
        self._respond(command)

    def _handle_data_mid(self, command: int, data: bytes) -> None:
        if self.write_target is None:
            self._nack(command, "no write in progress")
            return
        self.write_buffer.extend(data)
        self._respond(command)

    def _handle_data_end(self, command: int, data: bytes) -> None:
        if self.write_target is None:
            self._nack(command, "no write in progress")
            return
        self.write_buffer.extend(data)
        address, size = self.write_target
        if len(self.write_buffer) != size:
            self.write_target = None
            self._nack(command, "size mismatch: %d != %d" % (len(self.write_buffer), size))
            return
        self.flash[address : address + size] = self.write_buffer
        self.write_target = None
        self.write_buffer = bytearray()
        self._respond(command)

    def _handle_erase(self, command: int, data: bytes) -> None:
        if len(data) < 8:
            self._nack(command, "missing range")
            return
        address, size = struct.unpack("<II", data[:8])
        reason = self._check_range(address, size)
        if reason:
            self._nack(command, reason)
            return
        self.flash[address : address + size] = b"\xFF" * size
        self._respond(command)
