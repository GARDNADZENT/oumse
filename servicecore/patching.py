from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

MAX_FILE_SIZE = 256 * 1024 * 1024
MAX_PATCH_ENTRIES = 10_000
MAX_FILL_BYTES = 64 * 1024 * 1024


class PatchError(ValueError):
    """Raised when a patch document or target file is invalid."""


@dataclass(frozen=True, slots=True)
class SinglePatch:
    offset: int
    value: int

    def to_dict(self) -> dict[str, int]:
        return {"offset": self.offset, "value": self.value}


@dataclass(frozen=True, slots=True)
class FillPatch:
    start: int
    end: int  # inclusive
    value: int

    @property
    def length(self) -> int:
        return self.end - self.start + 1

    def to_dict(self) -> dict[str, int]:
        return {"start": self.start, "end": self.end, "value": self.value}


@dataclass(frozen=True, slots=True)
class PatchPlan:
    single_offsets: tuple[SinglePatch, ...]
    fill_offsets: tuple[FillPatch, ...]

    @property
    def entry_count(self) -> int:
        return len(self.single_offsets) + len(self.fill_offsets)

    @property
    def write_count(self) -> int:
        return len(self.single_offsets) + sum(item.length for item in self.fill_offsets)

    def to_dict(self) -> dict[str, list[dict[str, int]]]:
        return {
            "single_offsets": [item.to_dict() for item in self.single_offsets],
            "fill_offsets": [item.to_dict() for item in self.fill_offsets],
        }


@dataclass(frozen=True, slots=True)
class PatchResult:
    input_path: str
    output_path: str
    backup_path: str | None
    input_sha256: str
    output_sha256: str
    writes: int
    changed_bytes: int
    file_size: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "input_path": self.input_path,
            "output_path": self.output_path,
            "backup_path": self.backup_path,
            "input_sha256": self.input_sha256,
            "output_sha256": self.output_sha256,
            "writes": self.writes,
            "changed_bytes": self.changed_bytes,
            "file_size": self.file_size,
        }


def _coerce_int(value: Any, label: str) -> int:
    if isinstance(value, bool):
        raise PatchError(f"{label} must be an integer, not a boolean.")
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        text = value.strip()
        try:
            return int(text, 0)
        except ValueError:
            try:
                return int(text, 10)
            except ValueError as exc:
                raise PatchError(f"{label} is not a valid integer: {value!r}.") from exc
    raise PatchError(f"{label} must be an integer, got {type(value).__name__}.")


def _coerce_value(value: Any, label: str) -> int:
    number = _coerce_int(value, label)
    if not 0 <= number <= 0xFF:
        raise PatchError(f"{label} must be between 0 and 255, got {number}.")
    return number


def _entry_dict(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise PatchError(f"{label} entries must be JSON objects.")
    return value


def parse_patch_document(document: Any) -> PatchPlan:
    """Parse and structurally validate the patch JSON used by the original runner."""
    if not isinstance(document, dict):
        raise PatchError("Patch document must be a JSON object.")

    single_raw = document.get("single_offsets", [])
    fill_raw = document.get("fill_offsets", [])
    if not isinstance(single_raw, list) or not isinstance(fill_raw, list):
        raise PatchError("'single_offsets' and 'fill_offsets' must be arrays.")
    if len(single_raw) + len(fill_raw) == 0:
        raise PatchError("Patch document contains no offsets.")
    if len(single_raw) + len(fill_raw) > MAX_PATCH_ENTRIES:
        raise PatchError(f"Too many patch entries; maximum is {MAX_PATCH_ENTRIES}.")

    singles: list[SinglePatch] = []
    for index, item in enumerate(single_raw):
        entry = _entry_dict(item, "single_offsets")
        if "offset" not in entry or "value" not in entry:
            raise PatchError(f"single_offsets[{index}] needs 'offset' and 'value'.")
        singles.append(
            SinglePatch(
                offset=_coerce_int(entry["offset"], f"single_offsets[{index}].offset"),
                value=_coerce_value(entry["value"], f"single_offsets[{index}].value"),
            )
        )

    fills: list[FillPatch] = []
    for index, item in enumerate(fill_raw):
        entry = _entry_dict(item, "fill_offsets")
        if not all(key in entry for key in ("start", "end", "value")):
            raise PatchError(f"fill_offsets[{index}] needs 'start', 'end', and 'value'.")
        start = _coerce_int(entry["start"], f"fill_offsets[{index}].start")
        end = _coerce_int(entry["end"], f"fill_offsets[{index}].end")
        if end < start:
            raise PatchError(f"fill_offsets[{index}].end must be >= start.")
        fills.append(
            FillPatch(
                start=start,
                end=end,
                value=_coerce_value(entry["value"], f"fill_offsets[{index}].value"),
            )
        )

    plan = PatchPlan(tuple(singles), tuple(fills))
    if plan.write_count > MAX_FILL_BYTES:
        raise PatchError(f"Patch would write too many bytes; maximum is {MAX_FILL_BYTES}.")
    return plan


def load_patch_document(path: str | Path) -> PatchPlan:
    file_path = Path(path)
    try:
        document = json.loads(file_path.read_text(encoding="utf-8-sig"))
    except OSError as exc:
        raise PatchError(f"Cannot read patch file: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise PatchError(f"Invalid JSON in patch file: {exc}") from exc
    return parse_patch_document(document)


def validate_plan(plan: PatchPlan, size: int) -> list[str]:
    """Validate a plan against a concrete input size. Returns error strings."""
    errors: list[str] = []
    if size <= 0:
        errors.append("Input file is empty.")
    if size > MAX_FILE_SIZE:
        errors.append(f"Input file exceeds the {MAX_FILE_SIZE} byte safety limit.")

    for index, item in enumerate(plan.single_offsets):
        if item.offset < 0 or item.offset >= size:
            errors.append(f"single_offsets[{index}].offset {item.offset} is out of bounds.")

    for index, item in enumerate(plan.fill_offsets):
        if item.start < 0 or item.end < item.start or item.end >= size:
            errors.append(
                f"fill_offsets[{index}] range {item.start}-{item.end} "
                f"is out of bounds for size {size}."
            )
        if item.length > MAX_FILL_BYTES:
            errors.append(f"fill_offsets[{index}] is larger than the safety limit.")

    if plan.write_count > MAX_FILL_BYTES:
        errors.append("Total patch writes exceed the safety limit.")
    return errors


def apply_plan(data: bytes, plan: PatchPlan) -> tuple[bytes, int, int]:
    """Apply a validated plan and return (patched_bytes, writes, changed_bytes)."""
    errors = validate_plan(plan, len(data))
    if errors:
        raise PatchError("; ".join(errors))

    buffer = bytearray(data)
    writes = 0
    for item in plan.single_offsets:
        buffer[item.offset] = item.value
        writes += 1
    for item in plan.fill_offsets:
        buffer[item.start : item.end + 1] = bytes([item.value]) * item.length
        writes += item.length

    patched = bytes(buffer)
    changed = sum(1 for before, after in zip(data, patched, strict=True) if before != after)
    return patched, writes, changed


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _backup_file(path: Path) -> Path:
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    backup = path.with_name(f"{path.name}.{timestamp}.bak")
    counter = 1
    while backup.exists():
        backup = path.with_name(f"{path.name}.{timestamp}.{counter}.bak")
        counter += 1
    shutil.copy2(path, backup)
    return backup


def _atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temp_name = tempfile.mkstemp(prefix=f"{path.name}.", suffix=".tmp", dir=path.parent)
    temp_path = Path(temp_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, path)
    finally:
        if temp_path.exists():
            try:
                temp_path.unlink()
            except OSError:
                pass


def patch_file(
    input_path: str | Path,
    output_path: str | Path,
    plan: PatchPlan,
    *,
    backup: bool = True,
) -> PatchResult:
    """Safely patch a local file, creating a backup and writing atomically."""
    source = Path(input_path)
    destination = Path(output_path)
    if not source.is_file():
        raise PatchError(f"Input file does not exist: {source}")

    size = source.stat().st_size
    if size > MAX_FILE_SIZE:
        raise PatchError(f"Input file exceeds the {MAX_FILE_SIZE} byte safety limit.")
    data = source.read_bytes()
    patched, writes, changed = apply_plan(data, plan)

    backup_path: Path | None = None
    if backup and destination.exists():
        backup_path = _backup_file(destination)
    _atomic_write(destination, patched)

    return PatchResult(
        input_path=str(source),
        output_path=str(destination),
        backup_path=str(backup_path) if backup_path else None,
        input_sha256=sha256_bytes(data),
        output_sha256=sha256_bytes(patched),
        writes=writes,
        changed_bytes=changed,
        file_size=size,
    )
