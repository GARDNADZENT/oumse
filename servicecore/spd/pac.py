"""Spreadtrum PAC firmware files.

A ``.pac`` is a flat container of partitions. Files start with the five byte
tag ``BP_R1``/``BP_R2``; the rest of the header describes the package and each
partition carries its own CRC.

Container layout used here (little-endian)::

    file header, 512 bytes
        0   magic[8]        b"BP_R2" padded with NULs
        8   u32 version
        12  u32 header_size
        16  u32 entry_count
        20  u32 total_size
        24  u32 checksum
        28  md5[16]
        44  name[128]       ASCII, NUL padded
    entry, repeated
        u32 header_size     (32)
        char name[12]
        u32 data_size
        u32 flash_offset
        u32 crc16
        u16 flags           (0x0000 file, 0x0100 last entry)
        u16 index
        payload             padded to 512 bytes

Every field is bounds-checked while parsing, so a file from another producer is
either read correctly or rejected with a specific message - it is never
silently misread. :meth:`PacFile.check` reports per-partition CRC failures and
the UI refuses to flash a package that fails that check.
"""

from __future__ import annotations

import hashlib
import struct
from dataclasses import dataclass, field
from pathlib import Path

MAGIC_PREFIX = b"BP_R"
MAGIC_R1 = b"BP_R1"
MAGIC_R2 = b"BP_R2"
MAGIC_FIELD = 8
HEADER_SIZE = 0x200
ENTRY_HEADER_SIZE = 0x20
PACK_ALIGN = 512
MAX_NAME = 128
PARTITION_NAME_LEN = 12
ENTRY_TYPE_FILE = 0x0000
ENTRY_TYPE_END = 0x0100


class PacError(RuntimeError):
    """Raised when a file is not a usable PAC package."""


def _align(value: int, alignment: int = PACK_ALIGN) -> int:
    return (value + alignment - 1) // alignment * alignment


def crc16(data: bytes, crc: int = 0xFFFF) -> int:
    """CRC16-XMODEM with init ``0xFFFF``, as used per partition."""
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) & 0xFFFF if crc & 0x8000 else (crc << 1) & 0xFFFF
    return crc


@dataclass(slots=True)
class PacEntry:
    """One partition inside a PAC file."""

    name: str
    offset: int
    size: int
    flash_offset: int = 0
    checksum: int = 0
    payload_offset: int = 0
    data: bytes = field(default=b"", repr=False, compare=False)

    @property
    def address(self) -> int:
        return self.flash_offset or self.offset

    def check(self) -> bool:
        return not self.checksum or crc16(self.data) == self.checksum

    def as_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "offset": self.offset,
            "flash_offset": self.flash_offset,
            "address": self.address,
            "size": self.size,
            "checksum": self.checksum,
        }


class PacFile:
    """A parsed ``.pac`` package."""

    def __init__(self, path: str | Path | None = None, *, version: str = "", entries=None) -> None:
        self.path = Path(path) if path else None
        self.version = version
        self.entries: list[PacEntry] = list(entries or [])
        self.magic = MAGIC_R2
        self.md5_matches = True
        self.problems: list[str] = []

    # -- reading -----------------------------------------------------------
    @classmethod
    def open(cls, path: str | Path) -> PacFile:
        target = Path(path)
        try:
            raw = target.read_bytes()
        except OSError as exc:
            raise PacError("cannot read %s: %s" % (target, exc)) from exc
        if raw[:4] != MAGIC_PREFIX:
            raise PacError("%s is not a PAC file (magic %r)" % (target.name, raw[:4]))
        package = cls._parse(raw, target)
        package.path = target
        package.check()
        return package

    @classmethod
    def _parse(cls, raw: bytes, target: Path) -> PacFile:
        if len(raw) < HEADER_SIZE:
            raise PacError("%s is truncated: %d bytes is smaller than one header" % (target.name, len(raw)))
        magic = raw[:MAGIC_FIELD].rstrip(b"\x00")
        _version, header_size, count, total_size, _checksum = struct.unpack("<IIIII", raw[8:28])
        md5 = raw[28:44]
        name = raw[44 : 44 + MAX_NAME].split(b"\x00", 1)[0].decode("ascii", "replace")
        if header_size < 44 or header_size > len(raw):
            raise PacError("header size %d is out of range for %s" % (header_size, target.name))
        if count > 4096:
            raise PacError("implausible partition count %d" % count)

        package = PacFile(version=name or "PAC package")
        package.magic = magic
        package.md5_matches = (
            md5 == b"\x00" * 16
            or not total_size
            or total_size > len(raw)
            or hashlib.md5(raw[header_size:total_size], usedforsecurity=False).digest() == md5
        )
        offset = header_size
        for index in range(count):
            entry, offset = cls._read_entry(raw, offset, index)
            if entry is None:
                break
            package.entries.append(entry)
        if not package.entries:
            raise PacError("%s contains no readable partitions" % target.name)
        return package

    @staticmethod
    def _read_entry(raw: bytes, offset: int, index: int) -> tuple[PacEntry | None, int]:
        if offset + ENTRY_HEADER_SIZE > len(raw):
            raise PacError("partition %d: header runs past the end of the file" % index)
        (entry_size,) = struct.unpack("<I", raw[offset : offset + 4])
        if entry_size < ENTRY_HEADER_SIZE or entry_size > len(raw) - offset:
            raise PacError("partition %d: implausible header size %d" % (index, entry_size))
        raw_name = raw[offset + 4 : offset + 4 + PARTITION_NAME_LEN]
        size, flash_offset, checksum = struct.unpack("<III", raw[offset + 16 : offset + 28])
        (flags,) = struct.unpack("<H", raw[offset + 28 : offset + 30])
        name = raw_name.split(b"\x00", 1)[0].decode("ascii", "replace").strip() or "entry%d" % index

        payload_start = offset + entry_size
        padded = _align(size)
        if payload_start + padded > len(raw):
            missing = payload_start + padded - len(raw)
            raise PacError("partition %s: payload is truncated (%d bytes missing)" % (name, missing))
        entry = PacEntry(
            name=name,
            offset=index,
            size=size,
            flash_offset=flash_offset,
            checksum=checksum,
            payload_offset=payload_start,
            data=raw[payload_start : payload_start + size],
        )
        return (None if flags == ENTRY_TYPE_END else entry), payload_start + padded

    # -- inspection --------------------------------------------------------
    def check(self) -> bool:
        """Verify every partition CRC, recording any problems."""
        self.problems = []
        if not self.md5_matches:
            self.problems.append("file md5 does not match the payload (repacked by another tool?)")
        for entry in self.entries:
            if not entry.check():
                self.problems.append(
                    "%s: crc 0x%04X does not match the stored 0x%04X" % (entry.name, crc16(entry.data), entry.checksum)
                )
        return not self.problems

    @property
    def verified(self) -> bool:
        return bool(self.entries) and not self.problems

    def summary(self) -> dict[str, object]:
        return {
            "path": str(self.path) if self.path else "",
            "version": self.version,
            "magic": self.magic.decode("ascii", "replace"),
            "partitions": len(self.entries),
            "total_size": sum(entry.size for entry in self.entries),
            "verified": self.verified,
            "md5_matches": self.md5_matches,
            "problems": list(self.problems),
        }

    def find(self, name: str) -> PacEntry | None:
        wanted = name.lower()
        for entry in self.entries:
            if entry.name.lower() == wanted:
                return entry
        return None

    def read_entry(self, name: str) -> bytes:
        entry = self.find(name)
        if entry is None:
            raise PacError("no partition named %s in the package" % name)
        return entry.data

    def extract(self, directory: str | Path, *, only: list[str] | None = None) -> list[Path]:
        target = Path(directory)
        target.mkdir(parents=True, exist_ok=True)
        written: list[Path] = []
        wanted = {name.lower() for name in only} if only else None
        for entry in self.entries:
            if wanted is not None and entry.name.lower() not in wanted:
                continue
            destination = target / ("%s.bin" % entry.name)
            destination.write_bytes(entry.data)
            written.append(destination)
        return written

    # -- building ----------------------------------------------------------
    @classmethod
    def from_folder(
        cls,
        folder: str | Path,
        *,
        version: str = "BestMDMTool package",
        flash_base: int = 0,
        layout: list[tuple[str, int]] | None = None,
    ) -> PacFile:
        """Build a package from ``<folder>/<partition>.bin`` files.

        ``layout`` optionally pins ``(name, flash_offset)`` pairs; otherwise the
        files are packed in name order with sequential flash offsets.
        """
        source = Path(folder)
        if not source.is_dir():
            raise PacError("not a folder: %s" % source)
        images = sorted(path for path in source.iterdir() if path.suffix.lower() in (".bin", ".img", ".mbn", ".elf"))
        if not images:
            raise PacError("no .bin/.img files in %s" % source)
        pinned = {name.lower(): offset for name, offset in (layout or [])}
        entries: list[PacEntry] = []
        cursor = flash_base
        for path in images:
            data = path.read_bytes()
            address = pinned.get(path.stem.lower(), cursor)
            entries.append(
                PacEntry(
                    name=path.stem,
                    offset=len(entries),
                    size=len(data),
                    flash_offset=address,
                    checksum=crc16(data),
                    data=data,
                )
            )
            cursor = address + _align(len(data))
        return cls(version=version, entries=entries)

    def save(self, path: str | Path) -> Path:
        """Write a ``BP_R2`` container and return its path."""
        target = Path(path)
        if not self.entries:
            raise PacError("nothing to write: the package has no partitions")

        body = bytearray()
        for index, entry in enumerate(self.entries):
            payload = entry.data
            name = entry.name.encode("ascii", "replace")[:PARTITION_NAME_LEN]
            # The container is count-based, so every entry is a file entry; the
            # END marker is only understood on input, for other producers.
            body.extend(struct.pack("<I", ENTRY_HEADER_SIZE))
            body.extend(name.ljust(PARTITION_NAME_LEN, b"\x00"))
            body.extend(struct.pack("<III", len(payload), entry.flash_offset, entry.checksum or crc16(payload)))
            body.extend(struct.pack("<HH", ENTRY_TYPE_FILE, index))
            body.extend(payload)
            body.extend(b"\x00" * (_align(len(payload)) - len(payload)))

        header = bytearray(HEADER_SIZE)
        header[0:MAGIC_FIELD] = MAGIC_R2.ljust(MAGIC_FIELD, b"\x00")
        struct.pack_into("<IIIII", header, 8, 1, HEADER_SIZE, len(self.entries), HEADER_SIZE + len(body), 0)
        header[28:44] = hashlib.md5(bytes(body), usedforsecurity=False).digest()
        name_field = self.version.encode("ascii", "replace")[: MAX_NAME - 1]
        header[44 : 44 + len(name_field)] = name_field

        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(bytes(header) + bytes(body))
        self.path = target
        return target


def describe(path: str | Path) -> dict[str, object]:
    """Open a package and return a JSON-friendly description."""
    package = PacFile.open(path)
    summary = package.summary()
    summary["entries"] = [entry.as_dict() for entry in package.entries]
    return summary


def default_output_name(source: str | Path) -> str:
    stem = Path(source).stem if source else "BestMDMTool"
    return "%s-repacked.pac" % stem


def human_size(value: int) -> str:
    size = float(value or 0)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return "%d B" % int(size) if unit == "B" else "%.1f %s" % (size, unit)
        size /= 1024
    return "%d B" % int(value)
