"""Spreadtrum/Unisoc service runner.

Same line protocol as the MediaTek runner, so the GUI client
(:class:`servicecore.service_session.ServiceSession`) drives both engines with
one code path::

    SVC_LOG / SVC_INFO / SVC_PROGRESS / SVC_READY
    SVC_OK / SVC_FAIL / SVC_DATA / SVC_BYE

Operations::

    ping                                  info
    partitions                            read       {part, out}
    write      {part, src}                erase      {parts}
    readflash  {offset, size, out}        writeflash {offset, src}
    eraseflash {offset, size}
    pac_open   {path}                     pac_flash  {path, parts?}
    pac_extract {path, dir, parts?}       pac_build  {folder, out, version?}
    reboot                                quit

Environment::

    SPD_TRANSPORT   auto | usb | serial | simulator
    SPD_PORT        COM port name (when SPD_TRANSPORT=serial)
    SPD_BAUD        override the serial baud rate

``--selftest --simulate`` exercises the whole command set against the in-memory
device, which is how CI proves the SPD stack through the real frozen binary.
"""

from __future__ import annotations

import json
import os
import sys
import traceback
from pathlib import Path

if __package__ in (None, ""):  # pragma: no cover - direct script execution
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from servicecore.spd import constants as C  # noqa: E402
from servicecore.spd.device import SpdDevice, SpdError  # noqa: E402
from servicecore.spd.pac import PacError, PacFile, describe  # noqa: E402
from servicecore.spd.transport import TransportError  # noqa: E402


def emit(line: str) -> None:
    sys.stdout.write(str(line) + "\n")
    sys.stdout.flush()


def log(message: str, level: str = "INFO") -> None:
    text = " ".join(str(message).split())
    emit("SVC_LOG:%s:%s" % (level, text[:400]))


def fail(op: str, reason) -> None:
    emit("SVC_FAIL:%s:%s" % (op, str(reason)[:300]))


def progress(done: int) -> None:
    emit("SVC_PROGRESS:%d" % max(0, int(done)))


def _arg(cmd, *names, default=None):
    for name in names:
        if name in cmd and cmd[name] not in (None, ""):
            return cmd[name]
    return default


def _transport_kind() -> str:
    return (os.environ.get("SPD_TRANSPORT") or os.environ.get("OUMSE_SPD_TRANSPORT") or "auto").strip().lower()


def _port() -> str | None:
    value = (os.environ.get("SPD_PORT") or "").strip()
    return value or None


def connect() -> SpdDevice:
    kind = _transport_kind()
    log("Opening SPD transport: %s" % kind, "INFO")
    device = SpdDevice.connect(
        kind=kind,
        port=_port(),
        log=log,
        progress=progress,
    )
    return device


# ---------------------------------------------------------------------------
# Operations
# ---------------------------------------------------------------------------
def op_info(device: SpdDevice, cmd) -> None:
    emit("SVC_INFO:chip:%s" % (device.info.chip or device.info.chip_hex))
    emit("SVC_INFO:version:%s" % (device.info.version or "?"))
    emit("SVC_INFO:transport:%s" % device.info.transport)
    emit("SVC_OK:info:%s" % json.dumps(device.info.as_dict(), ensure_ascii=False))


def op_partitions(device: SpdDevice, cmd) -> None:
    try:
        entries = device.read_partitions()
    except SpdError as exc:
        pac = _arg(cmd, "pac")
        if not pac:
            raise
        log("%s - falling back to the PAC partition list" % exc, "WARN")
        entries = device.load_partitions_from_pac(pac)
    payload = json.dumps({"partitions": [entry.as_dict() for entry in entries]}, ensure_ascii=False)
    emit("SVC_OK:partitions:%s" % payload)


def op_read(device: SpdDevice, cmd) -> None:
    part = _arg(cmd, "part", "partition")
    out = _arg(cmd, "out", "path")
    if not part or not out:
        fail("read", "missing_args")
        return
    result = device.read_partition(str(part), str(out))
    emit("SVC_OK:read:%s:%d" % (result["partition"], result["size"]))


def op_write(device: SpdDevice, cmd) -> None:
    part = _arg(cmd, "part", "partition")
    src = _arg(cmd, "src", "path")
    if not part or not src:
        fail("write", "missing_args")
        return
    result = device.write_partition(str(part), str(src))
    emit("SVC_OK:write:%s:%d" % (result["partition"], result["size"]))


def op_erase(device: SpdDevice, cmd) -> None:
    names = cmd.get("parts") or ([cmd["part"]] if cmd.get("part") else [])
    if not names:
        fail("erase", "missing_args")
        return
    erased = []
    for name in names:
        device.erase_partition(str(name))
        erased.append(str(name))
    emit("SVC_OK:erase:%s" % ",".join(erased))


def op_readflash(device: SpdDevice, cmd) -> None:
    out = _arg(cmd, "out", "path")
    if not out:
        fail("readflash", "missing_args")
        return
    offset = int(_arg(cmd, "offset", default=0) or 0)
    size = int(_arg(cmd, "size", default=0) or 0)
    data = device.client.read_flash(offset, size)
    Path(str(out)).parent.mkdir(parents=True, exist_ok=True)
    Path(str(out)).write_bytes(data)
    emit("SVC_OK:readflash:%d" % len(data))


def op_writeflash(device: SpdDevice, cmd) -> None:
    src = _arg(cmd, "src", "path")
    if not src:
        fail("writeflash", "missing_args")
        return
    offset = int(_arg(cmd, "offset", default=0) or 0)
    data = Path(str(src)).read_bytes()
    device.client.write_flash(offset, data)
    emit("SVC_OK:writeflash:%d" % len(data))


def op_eraseflash(device: SpdDevice, cmd) -> None:
    offset = int(_arg(cmd, "offset", default=0) or 0)
    size = int(_arg(cmd, "size", default=0) or 0)
    device.client.erase_flash(offset, size)
    emit("SVC_OK:eraseflash:%d" % size)


def op_pac_open(_device: SpdDevice, cmd) -> None:
    path = _arg(cmd, "path")
    if not path:
        fail("pac_open", "missing_args")
        return
    info = describe(str(path))
    emit("SVC_OK:pac_open:%s" % json.dumps(info, ensure_ascii=False))


def op_pac_flash(device: SpdDevice, cmd) -> None:
    path = _arg(cmd, "path")
    if not path:
        fail("pac_flash", "missing_args")
        return
    names = cmd.get("parts") or None
    result = device.flash_pac(str(path), only=names)
    emit("SVC_OK:pac_flash:%s" % json.dumps(result, ensure_ascii=False))


def op_pac_extract(_device: SpdDevice, cmd) -> None:
    path = _arg(cmd, "path")
    directory = _arg(cmd, "dir") or "."
    if not path:
        fail("pac_extract", "missing_args")
        return
    package = PacFile.open(str(path))
    written = package.extract(str(directory), only=cmd.get("parts"))
    emit("SVC_OK:pac_extract:%d" % len(written))


def op_pac_build(_device: SpdDevice, cmd) -> None:
    folder = _arg(cmd, "folder")
    out = _arg(cmd, "out")
    if not folder or not out:
        fail("pac_build", "missing_args")
        return
    package = PacFile.from_folder(
        str(folder),
        version=str(_arg(cmd, "version", default="BestMDMTool package")),
        flash_base=int(_arg(cmd, "flash_base", default=0) or 0),
    )
    saved = package.save(str(out))
    emit("SVC_OK:pac_build:%s:%d" % (saved.name, len(package.entries)))


def op_reboot(device: SpdDevice, cmd) -> None:
    device.reboot()
    emit("SVC_OK:reboot")
    emit("SVC_BYE")
    raise SystemExit(0)


HANDLERS = {
    "info": op_info,
    "partitions": op_partitions,
    "read": op_read,
    "write": op_write,
    "erase": op_erase,
    "readflash": op_readflash,
    "writeflash": op_writeflash,
    "eraseflash": op_eraseflash,
    "pac_open": op_pac_open,
    "pac_flash": op_pac_flash,
    "pac_extract": op_pac_extract,
    "pac_build": op_pac_build,
    "reboot": op_reboot,
}


def ready_payload(device: SpdDevice) -> dict:
    partitions = []
    try:
        partitions = [entry.as_dict() for entry in device.read_partitions()]
    except SpdError as exc:
        log("partition table unavailable: %s" % exc, "WARN")
    return {
        "engine": "spd",
        "chip": device.info.chip or (device.info.chip_hex if device.info.chip_id else "SPD device"),
        "version": device.info.version,
        "transport": device.info.transport,
        "flash_size": device.info.flash_size,
        "partition_source": device.partition_source,
        "partitions": partitions,
    }


def serve(device: SpdDevice) -> None:
    payload = ready_payload(device)
    emit("SVC_INFO:engine:spd")
    emit("SVC_INFO:chip:%s" % payload["chip"])
    if payload["version"]:
        emit("SVC_INFO:version:%s" % payload["version"])
    emit("SVC_INFO:parts:%d" % len(payload["partitions"]))
    emit("SVC_READY:%s" % json.dumps(payload, ensure_ascii=False))

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
            return
        if op == "ping":
            emit("SVC_OK:ping")
            continue
        handler = HANDLERS.get(op)
        if handler is None:
            emit("SVC_FAIL:unknown_op:%s" % op)
            continue
        try:
            handler(device, cmd)
        except SystemExit:
            raise
        except (SpdError, PacError, TransportError) as exc:
            fail(op, exc)
        except BaseException as exc:
            traceback.print_exc(file=sys.stderr)
            fail(op, exc)


# ---------------------------------------------------------------------------
# Self-test (used by CI through the frozen executable)
# ---------------------------------------------------------------------------
def selftest(report_path: str) -> int:
    from servicecore.spd.simulator import SimulatedDevice

    report: dict[str, object] = {"ok": False, "engine": "spd", "frozen": bool(getattr(sys, "frozen", False))}
    try:
        device = SimulatedDevice()
        session = SpdDevice(device.host)
        session.handshake()
        report["chip_id"] = session.info.chip_id
        partitions = session.read_partitions()
        report["partitions"] = len(partitions)

        payload = b"\xa5" * 0x3000
        target = partitions[2] if len(partitions) > 2 else partitions[0]
        session.client.write_flash(target.offset, payload)
        readback = session.client.read_flash(target.offset, len(payload))
        report["write_read_ok"] = readback == payload

        session.client.erase_flash(target.offset, len(payload))
        report["erase_ok"] = session.client.read_flash(target.offset, 16) == b"\xff" * 16

        import tempfile

        work = Path(tempfile.mkdtemp())
        for name, size in (("boot", 0x1200), ("system", 0x2400)):
            (work / ("%s.bin" % name)).write_bytes(bytes([len(name)]) * size)
        package = PacFile.from_folder(work, version="selftest")
        pac_path = package.save(work / "selftest.pac")
        reopened = PacFile.open(pac_path)
        report["pac_partitions"] = len(reopened.entries)
        report["pac_verified"] = reopened.verified
        report["pac_roundtrip"] = reopened.read_entry("boot") == (work / "boot.bin").read_bytes()

        summary = reopened.summary()
        session.load_partitions_from_pac(pac_path)
        report["pac_partition_source"] = session.partition_source
        report["pac_total"] = summary["total_size"]
        report["operations"] = sorted(HANDLERS)
        report["ok"] = bool(
            report["write_read_ok"] and report["erase_ok"] and report["pac_verified"] and report["pac_roundtrip"]
        )
    except Exception:
        report["error"] = traceback.format_exc()

    try:
        Path(report_path).write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    except OSError:
        pass
    return 0 if report.get("ok") else 1


def main() -> None:
    if "--selftest" in sys.argv:
        index = sys.argv.index("--selftest")
        target = (
            sys.argv[index + 1]
            if len(sys.argv) > index + 1
            else os.path.join(os.environ.get("TEMP", "/tmp"), "bestmdmtool-spd-selftest.json")
        )
        raise SystemExit(selftest(target))

    device = connect()
    try:
        serve(device)
    finally:
        device.close()


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except BaseException as exc:
        traceback.print_exc(file=sys.stderr)
        try:
            fail("fatal", exc)
        except Exception:
            pass
        raise SystemExit(1) from None


_ = C  # re-exported constants for callers that import this module
