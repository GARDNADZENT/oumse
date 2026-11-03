"""Fail-closed MediaTek service runner.

The previous DA connection path invoked vendor code that could bypass device
security and patch loaders automatically. That path is disabled pending review.
The runner emits a refusal before opening USB or sending any device command.

The command handlers remain for isolated tests and future audited stock-only
support; the public runner cannot create a device session at this time.
"""
from __future__ import annotations

import json
import os
import re
import sys
import traceback


def emit(line: str) -> None:
    sys.stdout.write(str(line) + "\n")
    sys.stdout.flush()


def log(message: str, level: str = "INFO") -> None:
    text = " ".join(str(message).split())
    emit("SVC_LOG:%s:%s" % (level, text[:400]))


def fail(op: str, reason, code: int | None = None) -> None:
    emit("SVC_FAIL:%s:%s" % (op, str(reason)[:300]))
    if code is not None:
        sys.exit(code)


class ProgressBus:
    """Object handed to mtkclient through ``config.guiprogress``."""

    def __init__(self, offset: int = 0) -> None:
        self.offset = offset
        self._last = 0

    def emit(self, pos) -> None:  # noqa: A003 - mtkclient calls .emit
        try:
            position = int(pos) + self.offset
        except Exception:
            return
        if position - self._last >= 0x10000 or position < self._last:
            self._last = position
            emit("SVC_PROGRESS:%d" % position)


def connect() -> tuple[object, object]:
    """Fail closed until an audited stock-only DA connection is available.

    The vendored DA handler can silently exploit security and patch the loader,
    even when the UI never asks for it. Do not invoke it or resume saved state.
    """
    fail("connect", "mtk_temporarily_disabled_security_review", 1)
    raise RuntimeError("MediaTek sessions are temporarily disabled for security review")


# ---------------------------------------------------------------------------
# Device helpers
# ---------------------------------------------------------------------------
STORAGE_NAMES = {0: "Auto", 1: "eMMC", 2: "NAND", 3: "UFS", 4: "SDcard"}


def chip_name(mtk) -> str:
    try:
        chipconfig = getattr(mtk.config, "chipconfig", None)
        name = getattr(chipconfig, "name", None)
        if name:
            return str(name)
    except Exception:
        pass
    return "MediaTek"


def storage_name(mtk) -> str:
    try:
        daconfig = getattr(getattr(mtk, "daloader", None), "daconfig", None)
        flashtype = int(getattr(daconfig, "flashtype", 0) or 0)
        return STORAGE_NAMES.get(flashtype, "type %d" % flashtype)
    except Exception:
        return "unknown"


def page_size(mtk) -> int:
    try:
        return int(mtk.config.pagesize)
    except Exception:
        return 512


def partition_table(mtk) -> list[dict]:
    """Return ``[{name, sectors, size, sector, pagesize}]`` from the live GPT."""
    entries: list[dict] = []
    pagesize = page_size(mtk)
    raw = []
    try:
        raw = mtk.daloader.get_partition_data(parttype="user") or []
    except Exception as exc:
        log("GPT read failed: %s" % exc, "WARN")
        raw = []
    for entry in raw:
        name = getattr(entry, "name", None)
        sectors = getattr(entry, "sectors", None)
        if not name or not sectors:
            continue
        sector = getattr(entry, "sector", None)
        try:
            sectors_i = int(sectors)
        except Exception:
            continue
        entries.append(
            {
                "name": str(name),
                "sectors": sectors_i,
                "size": sectors_i * pagesize,
                "sector": int(sector) if sector is not None else None,
                "pagesize": pagesize,
            }
        )
    return entries


def find_partition(mtk, name: str) -> dict | None:
    wanted = (name or "").strip().lower()
    if not wanted:
        return None
    for entry in partition_table(mtk):
        if entry["name"].lower() == wanted:
            return entry
    return None


def _pretty_size(size: int) -> str:
    value = float(size)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if value < 1024 or unit == "TB":
            return "%.2f %s" % (value, unit) if unit != "B" else "%d B" % int(value)
        value /= 1024
    return "%d B" % size


def _ensure_parent(path: str) -> None:
    parent = os.path.dirname(os.path.abspath(path))
    if parent:
        os.makedirs(parent, exist_ok=True)


HEX_BYTES = re.compile(r"^(?:0x)?[0-9a-fA-F]+$")


def parse_int(value) -> int:
    if isinstance(value, int):
        return value
    text = str(value).strip().lower().replace("_", "")
    if text.startswith("0x"):
        return int(text, 16)
    return int(text, 10)


def flash_capacity(mtk) -> int:
    """Return the detected storage capacity in bytes, or zero if unknown."""
    daconfig = getattr(getattr(mtk, "daloader", None), "daconfig", None)
    storage = getattr(daconfig, "storage", None)
    try:
        return max(0, int(getattr(storage, "flashsize", 0) or 0))
    except (TypeError, ValueError):
        return 0


def validate_flash_range(mtk, offset: int, length: int) -> str | None:
    """Reject unchecked or out-of-range raw flash intervals."""
    if offset < 0 or length <= 0:
        return "invalid_range"
    capacity = flash_capacity(mtk)
    if capacity <= 0:
        return "storage_capacity_unknown"
    if offset + length > capacity:
        return "range_exceeds_storage"
    return None


# ---------------------------------------------------------------------------
# Operation handlers
# ---------------------------------------------------------------------------
def op_info(mtk, da_handler, cmd) -> None:
    info = {
        "chip": chip_name(mtk),
        "hwcode": "0x%X" % int(getattr(mtk.config, "hwcode", 0) or 0),
        "storage": storage_name(mtk),
        "pagesize": page_size(mtk),
        "parts": len(partition_table(mtk)),
    }
    emit("SVC_OK:info:%s" % json.dumps(info, ensure_ascii=False))


def op_gpt(mtk, da_handler, cmd) -> None:
    parts = partition_table(mtk)
    if not parts:
        return fail("gpt", "partition_table_unavailable")
    emit("SVC_OK:gpt:%s" % json.dumps({"partitions": parts}, ensure_ascii=False))


def op_gpt_export(mtk, da_handler, cmd) -> None:
    out = cmd.get("out")
    if not out:
        return fail("gpt_export", "missing_out")
    _ensure_parent(out)
    try:
        mtk.daloader.da_gpt(out, display=False)
    except Exception:
        # Fall back to dumping the raw GPT area.
        data, _guid = mtk.daloader.get_gpt(parttype="user")
        if not data:
            return fail("gpt_export", "no_gpt_data")
        with open(out, "wb") as handle:
            handle.write(data)
    if not os.path.isfile(out) or os.path.getsize(out) == 0:
        return fail("gpt_export", "empty_output")
    emit("SVC_OK:gpt_export:%s" % out)


def op_read(mtk, da_handler, cmd) -> None:
    part = (cmd.get("part") or "").strip()
    out = cmd.get("out")
    if not part or not out:
        return fail("read", "missing_args")
    entry = find_partition(mtk, part)
    if entry is None:
        return fail("read", "no_such_partition:%s" % part)
    if entry["sector"] is None or entry["size"] <= 0:
        return fail("read", "invalid_partition_range:%s" % entry["name"])
    _ensure_parent(out)
    emit("SVC_STEP:read:%s" % entry["name"])
    bus = ProgressBus()
    mtk.config.guiprogress = bus
    try:
        result = mtk.daloader.readflash(
            addr=entry["sector"] * entry["pagesize"],
            length=entry["size"],
            filename=out,
            parttype="user",
            display=False,
        )
    except Exception as exc:
        return fail("read", "%s:%s" % (part, str(exc)[:160]))
    if result is not True:
        return fail("read", "%s:read_failed" % part)
    size = os.path.getsize(out) if os.path.isfile(out) else 0
    if size != entry["size"]:
        return fail("read", "%s:short_read:%d_of_%d" % (part, size, entry["size"]))
    emit("SVC_OK:read:%s:%d" % (entry["name"], size))


def op_write(mtk, da_handler, cmd) -> None:
    part = (cmd.get("part") or "").strip()
    src = cmd.get("in")
    if not part or not src:
        return fail("write", "missing_args")
    if not os.path.isfile(src):
        return fail("write", "missing_file:%s" % src)
    entry = find_partition(mtk, part)
    if entry is None:
        return fail("write", "no_such_partition:%s" % part)
    size = os.path.getsize(src)
    if size == 0:
        return fail("write", "empty_file")
    if size > entry["size"]:
        return fail("write", "image_exceeds_partition:%s" % entry["name"])
    if entry["sector"] is None:
        return fail("write", "invalid_partition_range:%s" % entry["name"])
    emit("SVC_STEP:write:%s" % entry["name"])
    log("writing %s (%s) to %s" % (os.path.basename(src), _pretty_size(size), entry["name"]))
    mtk.config.guiprogress = ProgressBus()
    try:
        result = mtk.daloader.writeflash(
            addr=entry["sector"] * entry["pagesize"],
            length=size,
            filename=src,
            parttype="user",
            display=False,
        )
    except Exception as exc:
        return fail("write", "%s:%s" % (part, str(exc)[:160]))
    if result is not True:
        return fail("write", "%s:write_failed" % part)
    emit("SVC_OK:write:%s:%d" % (entry["name"], size))


def op_erase(mtk, da_handler, cmd) -> None:
    parts = cmd.get("parts") or []
    if isinstance(parts, str):
        parts = [parts]
    parts = [str(p).strip() for p in parts if str(p).strip()]
    if not parts:
        return fail("erase", "no_parts")
    try:
        entries = {entry["name"].lower(): entry for entry in partition_table(mtk)}
        if not entries:
            return fail("erase", "partition_table_unavailable")
        unknown = [p for p in parts if p.lower() not in entries]
        if unknown:
            return fail("erase", "unknown_partition:%s" % ",".join(unknown[:4]))
        capacity = flash_capacity(mtk)
        if capacity <= 0:
            return fail("erase", "storage_capacity_unknown")
        for name in parts:
            entry = entries[name.lower()]
            sector = entry.get("sector")
            if sector is None or sector < 0 or entry["size"] <= 0:
                return fail("erase", "invalid_partition_range:%s" % name)
            offset = sector * entry["pagesize"]
            if offset + entry["size"] > capacity:
                return fail("erase", "partition_out_of_range:%s" % name)
        emit("SVC_STEP:erase:%s" % ",".join(parts))
        for name in parts:
            entry = entries[name.lower()]
            result = mtk.daloader.formatflash(
                addr=entry["sector"] * entry["pagesize"], length=entry["size"],
                partitionname=entry["name"], parttype="user", display=False,
            )
            if result is not True:
                return fail("erase", "format_failed:%s:operation_may_be_partial" % name)
    except Exception as exc:
        return fail("erase", "operation_may_be_partial:%s" % str(exc)[:120])
    emit("SVC_OK:erase:%s" % ",".join(parts))


def op_dump(mtk, da_handler, cmd) -> None:
    out_dir = cmd.get("dir")
    if not out_dir:
        return fail("dump", "missing_dir")
    os.makedirs(out_dir, exist_ok=True)
    requested = cmd.get("parts") or []
    if isinstance(requested, str):
        requested = [requested]
    wanted = {str(p).lower() for p in requested}
    entries = partition_table(mtk)
    if not entries:
        return fail("dump", "partition_table_unavailable")
    if wanted:
        entries = [e for e in entries if e["name"].lower() in wanted]
        if not entries:
            return fail("dump", "no_matching_partitions")
    done = 0
    failed: list[str] = []
    for entry in entries:
        target = os.path.join(out_dir, "%s.bin" % entry["name"])
        emit("SVC_STEP:dump:%s" % entry["name"])
        try:
            ok = mtk.daloader.readflash(
                addr=entry["sector"] * entry["pagesize"],
                length=entry["size"],
                filename=target,
                parttype="user",
                display=False,
            )
            actual = os.path.getsize(target) if os.path.isfile(target) else 0
            if ok is True and actual == entry["size"]:
                done += 1
            else:
                failed.append("%s:%d_of_%d" % (entry["name"], actual, entry["size"]))
        except Exception as exc:
            log("dump %s failed: %s" % (entry["name"], exc), "ERROR")
            failed.append(entry["name"])
    if failed or done != len(entries):
        return fail("dump", "partial:%d_of_%d:failed=%s" % (done, len(entries), ",".join(failed[:6])))
    emit("SVC_OK:dump:%d/%d" % (done, len(entries)))


def op_readflash(mtk, da_handler, cmd) -> None:
    try:
        offset = parse_int(cmd.get("offset", 0))
        length = parse_int(cmd.get("length", 0))
    except Exception:
        return fail("readflash", "bad_offset_length")
    out = cmd.get("out")
    if not out:
        return fail("readflash", "missing_args")
    range_error = validate_flash_range(mtk, offset, length)
    if range_error:
        return fail("readflash", range_error)
    _ensure_parent(out)
    emit("SVC_STEP:readflash:%d" % offset)
    mtk.config.guiprogress = ProgressBus()
    try:
        ok = mtk.daloader.readflash(addr=offset, length=length, filename=out, parttype="user", display=False)
    except Exception as exc:
        return fail("readflash", str(exc)[:160])
    if ok is not True:
        return fail("readflash", "read_failed")
    actual = os.path.getsize(out) if os.path.isfile(out) else 0
    if actual != length:
        return fail("readflash", "short_read:%d_of_%d" % (actual, length))
    emit("SVC_OK:readflash:%d" % length)


def op_writeflash(mtk, da_handler, cmd) -> None:
    src = cmd.get("in")
    if not src or not os.path.isfile(src):
        return fail("writeflash", "missing_file")
    try:
        offset = parse_int(cmd.get("offset", 0))
    except Exception:
        return fail("writeflash", "bad_offset")
    length = os.path.getsize(src)
    if length <= 0:
        return fail("writeflash", "empty_file")
    padded_length = ((length + 511) // 512) * 512
    range_error = validate_flash_range(mtk, offset, padded_length)
    if range_error:
        return fail("writeflash", range_error)
    emit("SVC_STEP:writeflash:%d" % offset)
    mtk.config.guiprogress = ProgressBus()
    try:
        ok = mtk.daloader.writeflash(addr=offset, length=length, filename=src, parttype="user", display=False)
    except Exception as exc:
        return fail("writeflash", str(exc)[:160])
    if ok is not True:
        return fail("writeflash", "write_failed")
    emit("SVC_OK:writeflash:%d" % length)


def op_eraseflash(mtk, da_handler, cmd) -> None:
    try:
        offset = parse_int(cmd.get("offset", 0))
        length = parse_int(cmd.get("length", 0))
    except Exception:
        return fail("eraseflash", "bad_offset_length")
    range_error = validate_flash_range(mtk, offset, length)
    if range_error:
        return fail("eraseflash", range_error)
    if offset % 512 or length % 512:
        return fail("eraseflash", "unaligned_range")
    emit("SVC_STEP:eraseflash:%d" % offset)
    try:
        if hasattr(mtk.daloader, "formatflash"):
            ok = mtk.daloader.formatflash(addr=offset, length=length, partitionname="", parttype="user", display=False)
        else:
            ok = mtk.daloader.eraseflash(addr=offset, length=length, parttype="user")
    except Exception as exc:
        return fail("eraseflash", str(exc)[:160])
    if ok is not True:
        return fail("eraseflash", "erase_failed")
    emit("SVC_OK:eraseflash:%d" % length)


def op_peek(mtk, da_handler, cmd) -> None:
    try:
        addr = parse_int(cmd.get("addr", 0))
        length = parse_int(cmd.get("length", 0x100))
    except Exception:
        return fail("peek", "bad_args")
    length = max(1, min(length, 0x10000))
    try:
        if hasattr(da_handler, "da_peek"):
            data = da_handler.da_peek(addr, length, "", registers=False)
        else:
            data = mtk.daloader.peek(addr=addr, length=length)
    except Exception as exc:
        return fail("peek", str(exc)[:160])
    if not data:
        return fail("peek", "empty")
    if isinstance(data, tuple):
        data = data[0]
    emit("SVC_OK:peek:%d" % len(data))
    emit("SVC_DATA:%s" % bytes(data).hex())


def op_poke(mtk, da_handler, cmd) -> None:
    try:
        addr = parse_int(cmd.get("addr", 0))
    except Exception:
        return fail("poke", "bad_addr")
    data = str(cmd.get("data") or "").strip()
    if not data:
        return fail("poke", "missing_data")
    if not HEX_BYTES.match(data):
        return fail("poke", "data_must_be_hex")
    try:
        payload = bytes.fromhex(data[2:] if data.lower().startswith("0x") else data)
    except Exception:
        return fail("poke", "bad_hex")
    try:
        ok = da_handler.da_poke(addr, payload, "")
    except Exception as exc:
        return fail("poke", str(exc)[:160])
    if not ok:
        return fail("poke", "write_failed")
    emit("SVC_OK:poke:%d" % len(payload))


def op_seccfg(mtk, da_handler, cmd) -> None:
    return fail("seccfg", "unavailable_security_policy")


def op_reboot(mtk, da_handler, cmd) -> None:
    mode = cmd.get("mode", 0)
    try:
        bootmode = parse_int(mode)
    except Exception:
        bootmode = 0
    emit("SVC_STEP:reboot")
    try:
        result = mtk.daloader.shutdown(bootmode=bootmode)
    except Exception as exc:
        return fail("reboot", str(exc)[:160])
    if result is not True:
        return fail("reboot", "shutdown_failed")
    emit("SVC_OK:reboot")


HANDLERS = {
    "info": op_info,
    "gpt": op_gpt,
    "partitions": op_gpt,
    "gpt_export": op_gpt_export,
    "read": op_read,
    "write": op_write,
    "erase": op_erase,
    "dump": op_dump,
    "readflash": op_readflash,
    "writeflash": op_writeflash,
    "eraseflash": op_eraseflash,
    "peek": op_peek,
    "poke": op_poke,
    "seccfg": op_seccfg,
    "reboot": op_reboot,
}


def main() -> None:
    mtk, da_handler = connect()

    parts = partition_table(mtk)
    if not parts:
        fail("gpt", "empty_partition_table", 1)

    emit("SVC_INFO:chip:%s" % chip_name(mtk))
    emit("SVC_INFO:storage:%s" % storage_name(mtk))
    emit("SVC_INFO:parts:%d" % len(parts))
    try:
        emit("SVC_INFO:hwcode:0x%X" % int(getattr(mtk.config, "hwcode", 0) or 0))
    except Exception:
        pass
    emit("SVC_READY:%s" % json.dumps({"chip": chip_name(mtk), "partitions": parts}, ensure_ascii=False))

    for raw in sys.stdin:
        line = raw.strip()
        if not line:
            continue
        try:
            cmd = json.loads(line)
        except Exception as exc:
            emit("SVC_FAIL:json:%s" % str(exc)[:80])
            continue
        op = str(cmd.get("op") or "").strip().lower()
        if op == "quit":
            emit("SVC_BYE")
            break
        if op == "ping":
            emit("SVC_OK:ping")
            continue
        handler = HANDLERS.get(op)
        if handler is None:
            emit("SVC_FAIL:unknown_op:%s" % op)
            continue
        try:
            handler(mtk, da_handler, cmd)
        except SystemExit:
            raise
        except BaseException as exc:  # keep the session alive on op failures
            traceback.print_exc(file=sys.stderr)
            emit("SVC_FAIL:%s:%s" % (op, str(exc)[:200]))
        if op == "reboot":
            break

    sys.exit(0)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except BaseException as exc:
        traceback.print_exc(file=sys.stderr)
        try:
            emit("SVC_FAIL:fatal:%s" % str(exc)[:200])
        except Exception:
            pass
        sys.exit(1)
