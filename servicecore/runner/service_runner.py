"""service_runner.py - persistent MediaTek BROM/DA service runner.

This is the backend that powers the BestMDMTool GUI. It keeps ONE BROM/DA
connection open and accepts JSON commands on stdin, so read / write / erase /
flash operations can be chained on the same session without re-entering BROM
mode (the behaviour technicians expect from commercial service tools).

Protocol
--------
stdin  : one JSON object per line
stdout : ``SVC_*`` prefixed lines, human log lines are ignored by the client

Emissions
---------
SVC_STEP:<label>                operation step started
SVC_PROGRESS:<bytes>            progress tick (absolute bytes handled)
SVC_LOG:<level>:<message>       informational message for the console
SVC_INFO:<key>:<value>          device facts (hwcode, soc, storage, ...)
SVC_READY:<json>                session up: {"chip":..,"partitions":[..]}
SVC_OK:<op>[:<details>]         operation succeeded
SVC_FAIL:<op>:<reason>          operation failed
SVC_DATA:<chunk>                hex payload (peek)
SVC_BYE                       : session closed

Operations
----------
ping, info, gpt, partitions, gpt_export, read, write, erase, dump,
readflash, writeflash, eraseflash, peek, poke, seccfg, reboot, quit

Only use this tool on devices you own or are explicitly authorized to service.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
import threading
import traceback
from pathlib import Path

LOG = logging.getLogger("service_runner")


# ---------------------------------------------------------------------------
# Bootstrap: make the vendored mtkclient importable, reuse the field-tested
# Windows serial patches from the existing runner, then import mtkclient.
# ---------------------------------------------------------------------------
def _runtime_lib() -> Path:
    """Find the vendored mtkclient + DA files, frozen or from source."""
    for env_name in ("SVC_ROOT", "BESTMDMTOOL_ROOT", "OUMSE_ROOT"):
        raw = (os.environ.get(env_name) or "").strip()
        if raw:
            candidate = Path(raw).expanduser() / "runtime" / "lib"
            if candidate.is_dir():
                return candidate

    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).resolve().parent
        for base in (exe_dir, exe_dir.parent, exe_dir.parent.parent):
            candidate = base / "runtime" / "lib"
            if candidate.is_dir():
                return candidate
        return exe_dir

    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / "runtime" / "lib"
        if candidate.is_dir():
            return candidate
    return here.parent


LIB_DIR = _runtime_lib()
if str(LIB_DIR) not in sys.path:
    sys.path.insert(0, str(LIB_DIR))

COMPAT_PATCHES = False
try:  # pragma: no cover - depends on host USB stack
    import oumse_brom_session_runner as _compat  # noqa: F401  (applies pyserial patches)

    COMPAT_PATCHES = True
except Exception:  # pragma: no cover
    LOG.debug("compat runner not importable", exc_info=True)

try:
    from mtkclient.config.mtk_config import MtkConfig

    try:  # newer mtkclient layout
        from mtkclient.Library.argument_parser import ArgHandler
    except ImportError:  # vendored 2.1.4 keeps it in mtk_main
        from mtkclient.Library.mtk_main import ArgHandler

    from mtkclient.Library.DA.mtk_da_handler import DaHandler
    from mtkclient.Library.mtk_class import Mtk
except Exception as exc:  # pragma: no cover
    sys.stderr.write("mtkclient import failed: %s\n" % exc)
    sys.stderr.flush()
    raise


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


def _truthy(value: str | None) -> bool:
    return (value or "").strip().lower() in ("1", "true", "yes", "on")


# ---------------------------------------------------------------------------
# Connection
# ---------------------------------------------------------------------------
def _serial_support_available() -> bool:
    try:
        import serial  # noqa: F401

        return True
    except Exception:
        return False


def _resolve_loader(mode: str) -> str | None:
    override = (os.environ.get("SVC_MTK_LOADER") or os.environ.get("OUMSE_MTK_LOADER") or "").strip().strip('"')
    if override:
        if os.path.isfile(override):
            return override
        log("loader not found: %s" % override, "WARN")
    if mode != "preloader":
        return None
    for candidate in (
        LIB_DIR / "mtkclient" / "Loader" / "MTK_DA_V6.bin",
        LIB_DIR / "mtkclient" / "Loaders" / "MTK_DA_V6.bin",
        LIB_DIR / "Loaders" / "V6" / "MTK_DA_V6.bin",
        LIB_DIR / "Loader" / "MTK_DA_V6.bin",
    ):
        if candidate.is_file():
            return str(candidate)
    return None


def _resolve_auth() -> str | None:
    override = (os.environ.get("SVC_MTK_AUTH") or os.environ.get("OUMSE_MTK_AUTH") or "").strip().strip('"')
    if override:
        if os.path.isfile(override):
            return override
        log("auth file not found: %s" % override, "WARN")
    for name in ("auth_sv5.auth", "MTK_DA_V6.auth", "auth.auth", "Transsion.auth", "km6.auth"):
        candidate = LIB_DIR / "mtkclient" / "Loader" / name
        if candidate.is_file():
            return str(candidate)
    return None


def _transport_arg(mode: str) -> tuple[str | None, str]:
    requested = (os.environ.get("SVC_BROM_TRANSPORT") or os.environ.get("OUMSE_BROM_TRANSPORT") or "").strip().lower()
    if requested in ("auto", "libusb", "usb"):
        return None, "auto"
    if requested in ("serial", "detect", "vcom"):
        return "DETECT", "serial-detect"
    if requested.startswith("com"):
        return requested.upper(), requested.upper()
    if mode == "preloader" and _serial_support_available():
        return "DETECT", "serial-detect"
    return None, "auto"


def connect() -> tuple[object, object]:
    """Open the BROM/DA session and return ``(mtk, da_handler)``."""
    mode = (os.environ.get("SVC_BROM_MODE") or os.environ.get("OUMSE_BROM_MODE") or "brom").strip().lower()
    level = logging.DEBUG if _truthy(os.environ.get("SVC_LOG_DEBUG")) else logging.INFO
    if level == logging.DEBUG:
        try:
            logging.basicConfig(level=logging.DEBUG, stream=sys.stderr, format="%(name)s %(levelname)s %(message)s")
        except Exception:
            pass

    serial_arg, transport = _transport_arg(mode)
    log("mode=%s transport=%s" % (mode or "brom", transport))

    config = MtkConfig(loglevel=level, gui=None, guiprogress=ProgressBus())
    ArgHandler(argparse.Namespace(), config)

    loader = _resolve_loader(mode)
    auth = _resolve_auth()
    if loader:
        config.loader = loader
        log("loader=%s" % Path(loader).name)
    if auth:
        config.auth = auth
        log("auth=%s" % Path(auth).name)

    mtk = Mtk(config=config, loglevel=level, serialportname=serial_arg)
    config.set_peek(mtk.daloader.peek)
    mtk.config.preloader_filename = None
    mtk.config.guiprogress = ProgressBus()

    # Re-assert after construction: some mtkclient builds reload the DA config.
    if loader:
        try:
            mtk.config.loader = loader
            daconfig = getattr(getattr(mtk, "daloader", None), "daconfig", None)
            if daconfig is not None and hasattr(daconfig, "loader"):
                daconfig.loader = loader
        except Exception:
            pass
    if auth:
        try:
            mtk.config.auth = auth
        except Exception:
            pass

    da_handler = DaHandler(mtk, level)

    emit("SVC_STEP:connect")
    result: dict[str, object] = {"mtk": None, "err": None}

    def _do_connect() -> None:
        try:
            result["mtk"] = da_handler.connect(mtk, ".")
        except Exception as exc:  # pragma: no cover - hardware dependent
            result["err"] = str(exc)[:200]

    worker = threading.Thread(target=_do_connect, daemon=True)
    worker.start()
    worker.join(timeout=90.0)
    if worker.is_alive():
        fail("connect", "timeout:port_locked_90s", 1)
    if result["err"]:
        fail("connect", "usb:%s" % result["err"], 1)
    mtk = result["mtk"]
    if mtk is None:
        fail("connect", "no_device", 1)

    emit("SVC_STEP:da")
    try:
        mtk = da_handler.configure_da(mtk)
    except Exception as exc:  # pragma: no cover
        traceback.print_exc(file=sys.stderr)
        fail("configure", str(exc)[:200], 1)
    if mtk is None:
        fail("configure", "da_rejected", 1)

    mtk.config.guiprogress = ProgressBus()
    return mtk, da_handler


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
        "compat_patches": COMPAT_PATCHES,
    }
    emit("SVC_OK:info:%s" % json.dumps(info, ensure_ascii=False))


def op_gpt(mtk, da_handler, cmd) -> None:
    parts = partition_table(mtk)
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
    emit("SVC_OK:gpt_export:%s" % out)


def op_read(mtk, da_handler, cmd) -> None:
    part = (cmd.get("part") or "").strip()
    out = cmd.get("out")
    if not part or not out:
        return fail("read", "missing_args")
    entry = find_partition(mtk, part)
    if entry is None:
        return fail("read", "no_such_partition:%s" % part)
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
    if not result:
        return fail("read", "%s:empty" % part)
    size = os.path.getsize(out) if os.path.exists(out) else entry["size"]
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
    if not result:
        return fail("write", "%s:refused" % part)
    emit("SVC_OK:write:%s:%d" % (entry["name"], size))


def op_erase(mtk, da_handler, cmd) -> None:
    parts = cmd.get("parts") or []
    if isinstance(parts, str):
        parts = [parts]
    parts = [str(p).strip() for p in parts if str(p).strip()]
    if not parts:
        return fail("erase", "no_parts")
    known = {entry["name"].lower() for entry in partition_table(mtk)}
    unknown = [p for p in parts if p.lower() not in known]
    if unknown:
        return fail("erase", "unknown_partition:%s" % ",".join(unknown[:4]))
    emit("SVC_STEP:erase:%s" % ",".join(parts))
    try:
        da_handler.da_erase([p for p in parts], "user")
    except Exception as exc:
        return fail("erase", str(exc)[:160])
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
            if ok:
                done += 1
            else:
                failed.append(entry["name"])
        except Exception as exc:
            log("dump %s failed: %s" % (entry["name"], exc), "ERROR")
            failed.append(entry["name"])
    emit("SVC_OK:dump:%d/%d%s" % (done, len(entries), (":failed=" + ",".join(failed[:6])) if failed else ""))


def op_readflash(mtk, da_handler, cmd) -> None:
    try:
        offset = parse_int(cmd.get("offset", 0))
        length = parse_int(cmd.get("length", 0))
    except Exception:
        return fail("readflash", "bad_offset_length")
    out = cmd.get("out")
    if not out or length <= 0:
        return fail("readflash", "missing_args")
    _ensure_parent(out)
    emit("SVC_STEP:readflash:%d" % offset)
    mtk.config.guiprogress = ProgressBus()
    try:
        ok = mtk.daloader.readflash(addr=offset, length=length, filename=out, parttype="user", display=False)
    except Exception as exc:
        return fail("readflash", str(exc)[:160])
    if not ok:
        return fail("readflash", "read_failed")
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
    emit("SVC_STEP:writeflash:%d" % offset)
    mtk.config.guiprogress = ProgressBus()
    try:
        ok = mtk.daloader.writeflash(addr=offset, length=length, filename=src, parttype="user", display=False)
    except Exception as exc:
        return fail("writeflash", str(exc)[:160])
    if not ok:
        return fail("writeflash", "write_failed")
    emit("SVC_OK:writeflash:%d" % length)


def op_eraseflash(mtk, da_handler, cmd) -> None:
    try:
        offset = parse_int(cmd.get("offset", 0))
        length = parse_int(cmd.get("length", 0))
    except Exception:
        return fail("eraseflash", "bad_offset_length")
    if length <= 0:
        return fail("eraseflash", "bad_length")
    emit("SVC_STEP:eraseflash:%d" % offset)
    try:
        if hasattr(mtk.daloader, "formatflash"):
            ok = mtk.daloader.formatflash(addr=offset, length=length, partitionname="", parttype="user", display=False)
        else:
            ok = mtk.daloader.eraseflash(addr=offset, length=length, parttype="user")
    except Exception as exc:
        return fail("eraseflash", str(exc)[:160])
    if not ok:
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
    state = (cmd.get("state") or "").strip().lower()
    if state not in ("unlock", "lock"):
        return fail("seccfg", "state_must_be_unlock_or_lock")
    try:
        holder = getattr(mtk.daloader, "da", None)
        if holder is None or not hasattr(holder, "seccfg"):
            return fail("seccfg", "unsupported_by_this_da")
        ok, message = holder.seccfg(state)
    except Exception as exc:
        return fail("seccfg", str(exc)[:160])
    if not ok:
        return fail("seccfg", str(message)[:160])
    emit("SVC_OK:seccfg:%s" % state)


def op_reboot(mtk, da_handler, cmd) -> None:
    mode = cmd.get("mode", 0)
    try:
        bootmode = parse_int(mode)
    except Exception:
        bootmode = 0
    emit("SVC_STEP:reboot")
    try:
        mtk.daloader.shutdown(bootmode=bootmode)
    except Exception:
        pass
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
