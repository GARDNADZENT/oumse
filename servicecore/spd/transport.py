"""Transports for the SPD BSL protocol.

Three implementations share the tiny :class:`Transport` interface:

* :class:`SerialTransport` - pyserial, for COM ports and DIAG/AT mode.
* :class:`UsbTransport` - pyusb bulk transfers, for BSL/FDL stages.
* :class:`LoopbackTransport` - an in-memory pipe used by the simulator and the
  unit tests. It needs no hardware and no third-party package.

The heavy imports happen inside the constructors, so importing this module
never fails on a machine without pyserial/pyusb installed.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Protocol


class TransportError(RuntimeError):
    """Raised when the port cannot be opened or has gone away."""


class Transport(Protocol):
    def write(self, data: bytes) -> None: ...

    def read(self, size: int, timeout: float) -> bytes: ...

    def close(self) -> None: ...

    @property
    def description(self) -> str: ...


class SerialTransport:
    """BSL/AT over a serial port (pyserial)."""

    def __init__(self, port: str, baudrate: int = 115200, timeout: float = 0.05) -> None:
        try:
            import serial  # noqa: PLC0415 - optional dependency
        except ImportError as exc:  # pragma: no cover - depends on the host
            raise TransportError("pyserial is not installed: %s" % exc) from exc
        try:
            self._port = serial.Serial(port, baudrate, timeout=timeout, write_timeout=5.0)
        except Exception as exc:
            raise TransportError("cannot open %s: %s" % (port, exc)) from exc
        self.port = port
        self.baudrate = baudrate

    @property
    def description(self) -> str:
        return "%s @ %d" % (self.port, self.baudrate)

    def write(self, data: bytes) -> None:
        try:
            self._port.write(data)
            self._port.flush()
        except Exception as exc:
            raise TransportError("write failed on %s: %s" % (self.port, exc)) from exc

    def read(self, size: int, timeout: float) -> bytes:
        deadline = time.monotonic() + timeout
        out = bytearray()
        self._port.timeout = min(0.05, timeout)
        while len(out) < size and time.monotonic() < deadline:
            try:
                chunk = self._port.read(size - len(out))
            except Exception as exc:
                raise TransportError("read failed on %s: %s" % (self.port, exc)) from exc
            if chunk:
                out.extend(chunk)
        return bytes(out)

    def close(self) -> None:
        try:
            self._port.close()
        except Exception:
            pass


class UsbTransport:
    """BSL/FDL over USB bulk endpoints (pyusb)."""

    def __init__(self, vid: int = 0x1782, pid: int | None = None, out_ep: int = 0x02, in_ep: int = 0x81) -> None:
        try:
            import usb.core  # noqa: PLC0415 - optional dependency
            import usb.util  # noqa: PLC0415 - optional dependency
        except ImportError as exc:  # pragma: no cover - depends on the host
            raise TransportError("pyusb is not installed: %s" % exc) from exc
        self._usb_util = usb.util
        try:
            self._device = usb.core.find(idVendor=vid, idProduct=pid) if pid else usb.core.find(idVendor=vid)
        except Exception as exc:
            raise TransportError("cannot search USB devices: %s" % exc) from exc
        if self._device is None:
            raise TransportError("no device with vendor id 0x%04X" % vid)
        self.vid = self._device.idVendor
        self.pid = self._device.idProduct
        self._out_ep = out_ep
        self._in_ep = in_ep
        try:
            self._device.set_configuration()
        except Exception:
            # Already configured / interface claimed by another driver: the bulk
            # transfers below will explain the real problem if it matters.
            pass
        self._claimed = False

    @property
    def description(self) -> str:
        return "USB %04X:%04X" % (self.vid, self.pid)

    def _claim(self) -> None:
        if self._claimed:
            return
        try:
            self._usb_util.claim_interface(self._device, 0)
        except Exception:
            pass
        self._claimed = True

    def write(self, data: bytes) -> None:
        self._claim()
        try:
            self._device.write(self._out_ep, data, timeout=5000)
        except Exception as exc:
            raise TransportError("USB write failed: %s" % exc) from exc

    def read(self, size: int, timeout: float) -> bytes:
        self._claim()
        deadline = time.monotonic() + timeout
        out = bytearray()
        while len(out) < size and time.monotonic() < deadline:
            try:
                chunk = self._device.read(self._in_ep, size - len(out), timeout=max(1, int(timeout * 1000)))
            except Exception:
                break
            if not chunk:
                break
            out.extend(bytes(chunk))
        return bytes(out)

    def close(self) -> None:
        try:
            self._usb_util.release_interface(self._device, 0)
        except Exception:
            pass
        try:
            self._usb_util.dispose_resources(self._device)
        except Exception:
            pass


class LoopbackTransport:
    """In-memory transport: bytes written here land in the peer's inbox.

    ``peer.service`` (optional) runs whenever data arrives, which is how the
    simulator answers without a thread. It needs no hardware and no third-party
    package, so the whole protocol is testable in CI.
    """

    def __init__(self) -> None:
        self.inbox = bytearray()
        self.peer: LoopbackTransport | None = None
        self.service: Callable[[], None] | None = None
        self.closed = False

    @property
    def description(self) -> str:
        return "loopback"

    def attach(self, peer: LoopbackTransport) -> None:
        self.peer = peer
        peer.peer = self

    def write(self, data: bytes) -> None:
        if self.closed:
            raise TransportError("transport closed")
        peer = self.peer
        if peer is None or peer.closed:
            return
        peer.inbox += data
        service = peer.service
        if service is not None:
            service()

    def read(self, size: int, timeout: float) -> bytes:
        deadline = time.monotonic() + timeout
        out = bytearray()
        while time.monotonic() < deadline:
            if self.inbox:
                # Return whatever has arrived: the caller loops for more. Waiting
                # to fill ``size`` would stall every short reply by a full timeout.
                take = min(size, len(self.inbox))
                out += self.inbox[:take]
                del self.inbox[:take]
                break
            if self.service is not None:
                self.service()
            time.sleep(0.001)
        return bytes(out)

    def close(self) -> None:
        self.closed = True


def pair() -> tuple[LoopbackTransport, LoopbackTransport]:
    """Return two linked loopback transports (host side, device side)."""
    host = LoopbackTransport()
    device = LoopbackTransport()
    host.attach(device)
    return host, device


def list_serial_ports() -> list[str]:
    """Return available serial port names, or an empty list when pyserial is absent."""
    try:
        from serial.tools import list_ports  # noqa: PLC0415 - optional dependency
    except Exception:
        return []
    try:
        return sorted(port.device for port in list_ports.comports())
    except Exception:
        return []


def find_spd_usb() -> list[dict[str, object]]:
    """Return connected USB devices that look like Spreadtrum hardware."""
    try:
        import usb.core  # noqa: PLC0415 - optional dependency
    except Exception:
        return []
    from .constants import SPD_USB_PIDS, SPD_USB_VID

    found: list[dict[str, object]] = []
    try:
        devices = list(usb.core.find(find_all=True) or [])
    except Exception:
        return []
    for device in devices:
        vid = getattr(device, "idVendor", 0)
        pid = getattr(device, "idProduct", 0)
        if vid == SPD_USB_VID:
            found.append(
                {
                    "vid": vid,
                    "pid": pid,
                    "label": SPD_USB_PIDS.get(pid, "SPD device"),
                    "bus": getattr(device, "bus", 0),
                    "address": getattr(device, "address", 0),
                }
            )
    return found
