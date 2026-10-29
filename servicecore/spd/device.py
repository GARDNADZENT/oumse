"""High-level Spreadtrum device session.

Wraps a :class:`~servicecore.spd.protocol.BslClient` with the things a
technician actually asks for: which chip is this, what partitions exist, read a
partition to a file, write an image, erase, flash a PAC package, reboot.

Partition information comes from the FDL when it supports the partition command
and otherwise from a PAC package the user supplies, so the page is explicitly
told which source it is looking at.
"""

from __future__ import annotations

import struct
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..chipsets import identify
from . import constants as C
from .pac import PacFile
from .protocol import BslClient, BslError
from .transport import Transport, TransportError, find_spd_usb, list_serial_ports


@dataclass(slots=True)
class SpdPartition:
    name: str
    offset: int
    size: int

    @property
    def end(self) -> int:
        return self.offset + self.size

    def as_dict(self) -> dict[str, Any]:
        return {"name": self.name, "offset": self.offset, "size": self.size, "address": self.offset}


@dataclass(slots=True)
class SpdInfo:
    chip_id: int = 0
    flash_id: int = 0
    version: str = ""
    transport: str = ""
    chip: str = ""
    family: str = ""
    flash_size: int = 0
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def chip_hex(self) -> str:
        return "0x%08X" % self.chip_id

    def as_dict(self) -> dict[str, Any]:
        return {
            "chip_id": self.chip_id,
            "chip": self.chip,
            "family": self.family,
            "flash_id": self.flash_id,
            "flash_size": self.flash_size,
            "version": self.version,
            "transport": self.transport,
            "extra": self.extra,
        }


class SpdDevice:
    """One open Spreadtrum session."""

    def __init__(
        self,
        transport: Transport,
        *,
        log: Callable[[str, str], None] | None = None,
        progress: Callable[[int], None] | None = None,
    ) -> None:
        self.transport = transport
        self.client = BslClient(transport, log=log, progress=progress)
        self._log = log or (lambda message, level="INFO": None)
        self.info = SpdInfo(transport=getattr(transport, "description", ""))
        self.partitions: list[SpdPartition] = []
        self.partition_source = ""
        self.connected = False

    # -- opening -----------------------------------------------------------
    @classmethod
    def open_transport(cls, kind: str = "auto", port: str | None = None) -> Transport:
        """Open a transport by name: ``auto``, ``usb``, ``serial``, ``simulator``."""
        kind = (kind or "auto").strip().lower()
        if kind in ("simulator", "sim", "loopback"):
            from .simulator import SimulatedDevice

            return SimulatedDevice().host
        if kind == "serial":
            if not port:
                ports = list_serial_ports()
                if not ports:
                    raise TransportError("no serial ports found; plug the device in download mode")
                port = ports[0]
            from .transport import SerialTransport

            return SerialTransport(port)
        if kind == "usb":
            from .transport import UsbTransport

            return UsbTransport(vid=C.SPD_USB_VID)
        # auto: prefer a USB download port, then the first serial port
        devices = find_spd_usb()
        if devices:
            from .transport import UsbTransport

            return UsbTransport(vid=C.SPD_USB_VID, pid=int(devices[0]["pid"]))
        ports = list_serial_ports()
        if ports:
            from .transport import SerialTransport

            return SerialTransport(port or ports[0])
        raise TransportError(
            "no Spreadtrum device found: put the phone in download mode (Vol- + power, "
            "or the boot key combination) and check the USB driver"
        )

    @classmethod
    def connect(
        cls,
        transport: Transport | None = None,
        *,
        kind: str = "auto",
        port: str | None = None,
        log: Callable[[str, str], None] | None = None,
        progress: Callable[[int], None] | None = None,
    ) -> SpdDevice:
        opener = transport or cls.open_transport(kind, port)
        device = cls(opener, log=log, progress=progress)
        device.handshake()
        return device

    def handshake(self) -> SpdInfo:
        """Sync with BSL and read chip information."""
        self.client.connect()
        self.connected = True
        try:
            chip = self.client.read_chip_type()
            self.info.chip_id = chip.chip_id
            self.info.flash_id = chip.flash_id
        except BslError as exc:
            self._log("could not read the chip type: %s" % exc, "WARN")
        try:
            self.info.version = self.client.read_version()
        except BslError:
            self.info.version = ""
        try:
            data = self.client._exchange(C.CMD_READ_FLASH_INFO, timeout=2.0)  # noqa: SLF001 - protocol probe
            if len(data) >= 8:
                self.info.flash_size, _sector = struct.unpack("<II", data[:8])
        except BslError:
            self.info.flash_size = 0

        # A USB product id identifies the family precisely; a serial port does
        # not, so there we only report the numeric chip id read from the ROM.
        pid = getattr(self.transport, "pid", None)
        match = identify(C.SPD_USB_VID, int(pid)) if pid else None
        if match is not None:
            self.info.chip = match.name
            self.info.family = match.family
        self._log(
            "Connected: %s%s" % (
                self.info.chip or ("chip 0x%08X" % self.info.chip_id if self.info.chip_id else "SPD device"),
                " (%s)" % self.info.version if self.info.version else "",
            ),
            "OK",
        )
        return self.info

    # -- partitions --------------------------------------------------------
    def read_partitions(self) -> list[SpdPartition]:
        """Ask the FDL for the partition table."""
        try:
            data = self.client._exchange(C.CMD_READ_PARTITION, timeout=8.0)  # noqa: SLF001
        except BslError as exc:
            raise SpdError("the loader does not expose a partition table: %s" % exc) from exc
        if len(data) < 2:
            raise SpdError("empty partition table")
        count = struct.unpack("<H", data[:2])[0]
        entries: list[SpdPartition] = []
        cursor = 2
        for _ in range(count):
            if cursor + C.PART_NAME_LEN + 8 > len(data):
                break
            raw_name = data[cursor : cursor + C.PART_NAME_LEN].split(b"\x00", 1)[0]
            offset, size = struct.unpack("<II", data[cursor + C.PART_NAME_LEN : cursor + C.PART_NAME_LEN + 8])
            cursor += C.PART_NAME_LEN + 8
            name = raw_name.decode("ascii", "replace").strip() or "part%d" % len(entries)
            entries.append(SpdPartition(name=name, offset=offset, size=size))
        self.partitions = entries
        self.partition_source = "fdl"
        self._log("Partition table: %d entries from the loader" % len(entries), "OK")
        return entries

    def load_partitions_from_pac(self, path: str | Path) -> list[SpdPartition]:
        """Fall back to the partition list inside a PAC package."""
        package = PacFile.open(path)
        entries = [
            SpdPartition(name=entry.name, offset=entry.address, size=entry.size) for entry in package.entries
        ]
        self.partitions = entries
        self.partition_source = "pac:%s" % Path(path).name
        self._log("Partition table: %d entries from %s" % (len(entries), Path(path).name), "INFO")
        return entries

    def find(self, name: str) -> SpdPartition:
        wanted = (name or "").strip().lower()
        for entry in self.partitions:
            if entry.name.lower() == wanted:
                return entry
        for entry in self.partitions:
            if wanted and wanted in entry.name.lower():
                return entry
        raise SpdError("no partition named %s" % name)

    # -- data operations ---------------------------------------------------
    def read_partition(self, name: str, destination: str | Path) -> dict[str, Any]:
        entry = self.find(name)
        data = self.client.read_flash(entry.offset, entry.size)
        target = Path(destination)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        self._log("Read %s (%d bytes) -> %s" % (entry.name, len(data), target), "OK")
        return {"partition": entry.name, "size": len(data), "path": str(target)}

    def write_partition(self, name: str, source: str | Path) -> dict[str, Any]:
        entry = self.find(name)
        payload = Path(source).read_bytes()
        if len(payload) > entry.size:
            raise SpdError(
                "image is %d bytes but %s only holds %d" % (len(payload), entry.name, entry.size)
            )
        self.client.write_flash(entry.offset, payload)
        self._log("Wrote %s (%d bytes) from %s" % (entry.name, len(payload), Path(source).name), "OK")
        return {"partition": entry.name, "size": len(payload)}

    def erase_partition(self, name: str) -> dict[str, Any]:
        entry = self.find(name)
        self.client.erase_flash(entry.offset, entry.size)
        return {"partition": entry.name, "size": entry.size}

    def flash_pac(self, path: str | Path, *, only: list[str] | None = None, verify: bool = True) -> dict[str, Any]:
        """Write every partition of a PAC package to flash."""
        package = PacFile.open(path)
        if not package.entries:
            raise SpdError("the package has no partitions")
        if not package.check():
            raise SpdError("the package failed verification: %s" % "; ".join(package.problems[:3]))
        if not self.partitions:
            self.partitions = [
                SpdPartition(name=entry.name, offset=entry.address, size=entry.size) for entry in package.entries
            ]
            self.partition_source = "pac:%s" % Path(path).name

        wanted = {name.lower() for name in only} if only else None
        written: list[str] = []
        skipped: list[dict[str, str]] = []
        for entry in package.entries:
            if wanted is not None and entry.name.lower() not in wanted:
                continue
            try:
                target = self.find(entry.name)
            except SpdError:
                skipped.append({"partition": entry.name, "reason": "not in the device partition table"})
                continue
            if len(entry.data) > target.size:
                skipped.append({"partition": entry.name, "reason": "image larger than the partition"})
                continue
            self.client.write_flash(target.offset, entry.data)
            if verify:
                readback = self.client.read_flash(target.offset, len(entry.data))
                if readback != entry.data:
                    raise SpdError("%s did not verify after writing" % entry.name)
            written.append(entry.name)
            self._log("Flashed %s (%d bytes)" % (entry.name, len(entry.data)), "OK")
        return {"written": written, "skipped": skipped, "verified": verify}

    def reboot(self) -> dict[str, Any]:
        self.client.reboot()
        self.connected = False
        return {"ok": True}

    def close(self) -> None:
        try:
            self.client.close()
        finally:
            self.connected = False


class SpdError(RuntimeError):
    """Raised for SPD operations that cannot be completed."""


def _known_spd():
    from ..chipsets import SPD_CHIPS

    return SPD_CHIPS


def diagnostics() -> dict[str, Any]:
    """Report what the SPD stack can see on this machine."""
    return {
        "serial_ports": list_serial_ports(),
        "usb_devices": find_spd_usb(),
        "chip_count": len(_known_spd()),
    }
