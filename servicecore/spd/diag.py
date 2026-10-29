"""Spreadtrum DIAG / AT console.

After a device boots normally its DIAG port exposes a plain AT command channel
(the same one a serial terminal would use). This module is a small, testable
console around it: send a command, read until the device answers ``OK``,
``ERROR`` or the timeout expires.

The serial object is injected, so the console can be exercised in tests with a
fake port and needs no hardware and no pyserial dependency at import time.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

DEFAULT_TIMEOUT = 3.0

#: Commands a technician actually uses on a service bench.
PRESETS: tuple[tuple[str, str], ...] = (
    ("AT", "Ping the modem"),
    ("ATI", "Model / manufacturer"),
    ("AT+CGMR", "Firmware revision"),
    ("AT+CGSN", "IMEI"),
    ("AT+CGMM", "Model name"),
    ("AT+CGMI", "Manufacturer"),
    ("AT+CPIN?", "SIM state"),
    ("AT+CSQ", "Signal quality"),
    ("AT+CREG?", "Network registration"),
    ("AT+CBC", "Battery charge"),
    ("AT+CLCC", "Active calls"),
    ("AT+DEVCONINFO", "Unisoc device info"),
)


class DiagError(RuntimeError):
    """Raised when the console cannot talk to the port."""


@dataclass(slots=True)
class AtReply:
    command: str
    lines: list[str]
    ok: bool
    duration: float

    @property
    def text(self) -> str:
        return "\n".join(self.lines)


class AtConsole:
    """Send AT commands over a serial port and collect the answers."""

    def __init__(self, port, *, log=None) -> None:
        self.port = port
        self._log = log or (lambda message, level="INFO": None)
        self.commands: list[str] = []

    @classmethod
    def open(cls, port_name: str, *, baudrate: int = 115200, log=None) -> AtConsole:
        try:
            import serial  # noqa: PLC0415 - optional dependency
        except ImportError as exc:  # pragma: no cover - depends on the host
            raise DiagError("pyserial is not installed: %s" % exc) from exc
        try:
            port = serial.Serial(port_name, baudrate, timeout=0.2, write_timeout=2.0)
        except Exception as exc:
            raise DiagError("cannot open %s: %s" % (port_name, exc)) from exc
        return cls(port, log=log)

    def close(self) -> None:
        try:
            self.port.close()
        except Exception:
            pass

    def _read_available(self, timeout: float) -> str:
        deadline = time.monotonic() + timeout
        chunks: list[str] = []
        while time.monotonic() < deadline:
            try:
                data = self.port.read(256)
            except Exception as exc:
                raise DiagError("read failed: %s" % exc) from exc
            if data:
                text = data.decode("utf-8", "replace") if isinstance(data, (bytes, bytearray)) else str(data)
                chunks.append(text)
                if "OK" in "".join(chunks) or "ERROR" in "".join(chunks):
                    # Give the device a moment to finish the trailing CRLF.
                    time.sleep(0.02)
                    break
        return "".join(chunks)

    def send(self, command: str, *, timeout: float = DEFAULT_TIMEOUT) -> AtReply:
        cmd = (command or "").strip()
        if not cmd:
            raise DiagError("empty command")
        started = time.monotonic()
        try:
            self.port.write((cmd + "\r").encode("ascii", "replace"))
            flush = getattr(self.port, "flush", None)
            if flush is not None:
                flush()
        except Exception as exc:
            raise DiagError("write failed: %s" % exc) from exc
        raw = self._read_available(timeout)
        duration = time.monotonic() - started
        lines = [line.strip("\r") for line in raw.replace("\r\n", "\n").split("\n") if line.strip()]
        ok = any(line.strip() == "OK" for line in lines)
        if not lines:
            lines = ["(no answer within %.1fs)" % timeout]
        self.commands.append(cmd)
        self._log("%s -> %s" % (cmd, lines[-1] if lines else ""), "INFO")
        return AtReply(command=cmd, lines=lines, ok=ok, duration=duration)

    def identify(self) -> dict[str, str]:
        """Collect model, firmware, IMEI and SIM state in one go."""
        wanted = {
            "model": "AT+CGMM",
            "manufacturer": "AT+CGMI",
            "firmware": "AT+CGMR",
            "imei": "AT+CGSN",
            "sim": "AT+CPIN?",
        }
        out: dict[str, str] = {}
        for key, command in wanted.items():
            try:
                reply = self.send(command, timeout=1.5)
            except DiagError:
                continue
            values = [line for line in reply.lines if line not in ("OK", "ERROR") and not line.startswith(("+", "AT"))]
            if values:
                out[key] = values[0]
        return out
