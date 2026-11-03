"""USB discovery and connection diagnosis for BestMDMTool.

Three sources, tried in order, so the answer does not depend on one optional
library being present in the build:

* ``pyusb`` — richest view, but needs libusb.
* Windows PnP (PowerShell ``Get-CimInstance``) — always available on Windows and
  reports the bound driver, which is what decides whether BROM/BSL can be opened.
* ``pyserial`` — catches devices that enumerate as a COM port (PreLoader, VCOM).

``diagnose()`` turns whatever is found into one verdict plus the next steps to
try, so a failed connection names a cause instead of guessing.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field

MTK_VID = 0x0E8D
SPD_VID = 0x1782

#: UsbDk / WinUSB / libusbK are the drivers that can actually be opened.
OPENABLE_SERVICES = {"winusb", "libusbk", "libusb0", "usbdk", "libusb-1.0"}

#: PIDs that mean "this phone is waiting for a download", not "booting Android".
MTK_DOWNLOAD_PIDS = {0x0003: "PreLoader", 0x2000: "BROM", 0x2001: "BROM", 0x0006: "BROM"}
SPD_DOWNLOAD_PIDS = {0x4D00: "BSL", 0x5D00: "FDL", 0x4D01: "BSL", 0x5D01: "FDL"}

DEVICE_ID_RE = re.compile(r"VID_([0-9A-Fa-f]{4})&PID_([0-9A-Fa-f]{4})")
#: pyserial reports hardware ids as ``USB VID:PID=0E8D:0003 SER=...``.
HWID_RE = re.compile(r"VID:PID=([0-9A-Fa-f]{4}):([0-9A-Fa-f]{4})")
COMPORT_RE = re.compile(r"\(COM(\d+)\)", re.IGNORECASE)

PNP_SCRIPT = (
    "$ErrorActionPreference='SilentlyContinue';"
    "Get-CimInstance -ClassName Win32_PnPEntity |"
    " Where-Object { $_.DeviceID -like 'USB\\*' } |"
    " Select-Object Name,DeviceID,Service,Status,ConfigManagerErrorCode |"
    " ConvertTo-Json -Compress"
)


@dataclass(frozen=True)
class UsbDevice:
    """One USB device, from any source."""

    vid: int
    pid: int
    name: str = ""
    service: str = ""
    port: str = ""
    status: str = ""
    problem: str = ""
    source: str = ""

    @property
    def usb_id(self) -> str:
        return "%04X:%04X" % (self.vid, self.pid)

    @property
    def vendor(self) -> str:
        if self.vid == MTK_VID:
            return "MTK"
        if self.vid == SPD_VID:
            return "SPD"
        return ""

    @property
    def download_mode(self) -> str:
        """Name of the download mode this device is in, or an empty string."""

        if self.vid == MTK_VID:
            return MTK_DOWNLOAD_PIDS.get(self.pid, "")
        if self.vid == SPD_VID:
            return SPD_DOWNLOAD_PIDS.get(self.pid, "")
        return ""

    @property
    def openable(self) -> bool:
        return (self.service or "").strip().lower() in OPENABLE_SERVICES

    def as_dict(self) -> dict[str, object]:
        return {
            "vid": self.vid,
            "pid": self.pid,
            "usb": self.usb_id,
            "vendor": self.vendor or "unknown",
            "chip": self.name or self.usb_id,
            "protocol": self.download_mode or "unknown",
            "service": self.service,
            "port": self.port,
            "source": self.source,
        }


@dataclass
class UsbReport:
    """Everything one scan learned, plus a verdict and next steps."""

    platform: str = ""
    sources: dict[str, bool] = field(default_factory=dict)
    errors: dict[str, str] = field(default_factory=dict)
    devices: list[UsbDevice] = field(default_factory=list)
    ports: list[str] = field(default_factory=list)
    relevant: list[UsbDevice] = field(default_factory=list)
    adb_devices: list[str] = field(default_factory=list)
    verdict: str = "nothing"
    detail: str = ""
    steps: list[str] = field(default_factory=list)

    def summary(self) -> str:
        return self.detail or self.verdict


def _run_powershell(script: str, timeout: float = 20.0) -> str:
    """Run an inline PowerShell script and return its stdout."""

    exe = "powershell.exe"
    argv = [exe, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", script]
    creationflags = 0x08000000 if os.name == "nt" else 0  # CREATE_NO_WINDOW
    completed = subprocess.run(  # noqa: S603 - fixed argv, no shell
        argv,
        capture_output=True,
        timeout=timeout,
        creationflags=creationflags,
        check=False,
    )
    return completed.stdout.decode("utf-8", "replace")


def _loads(payload: str) -> list[dict]:
    """Parse PowerShell JSON that may be empty, a single object, or an array."""

    text = (payload or "").strip()
    if not text:
        return []
    if not text.startswith(("{", "[")):
        start = min((i for i in (text.find("{"), text.find("[")) if i >= 0), default=-1)
        if start < 0:
            return []
        text = text[start:]
    try:
        data = json.loads(text)
    except ValueError:
        return []
    if isinstance(data, dict):
        return [data]
    return [item for item in data if isinstance(item, dict)]


def pnp_devices() -> list[UsbDevice]:
    """List USB devices through the Windows device tree."""

    if os.name != "nt":
        return []
    try:
        payload = _run_powershell(PNP_SCRIPT)
    except Exception:
        return []
    found: list[UsbDevice] = []
    for entry in _loads(payload):
        device_id = str(entry.get("DeviceID") or "")
        match = DEVICE_ID_RE.search(device_id)
        if not match:
            continue
        name = str(entry.get("Name") or "")
        port_match = COMPORT_RE.search(name)
        problem = str(entry.get("ConfigManagerErrorCode") or "")
        found.append(
            UsbDevice(
                vid=int(match.group(1), 16),
                pid=int(match.group(2), 16),
                name=name,
                service=str(entry.get("Service") or ""),
                port=("COM" + port_match.group(1)) if port_match else "",
                status=str(entry.get("Status") or ""),
                problem="" if problem in ("", "0") else problem,
                source="pnp",
            )
        )
    return found


def pyusb_devices() -> list[UsbDevice]:
    """List USB devices through pyusb (needs libusb on Windows)."""

    try:
        import usb.core  # noqa: PLC0415 - optional dependency
    except Exception:
        return []
    try:
        raw = list(usb.core.find(find_all=True) or [])
    except Exception:
        return []
    found: list[UsbDevice] = []
    for device in raw:
        vid = int(getattr(device, "idVendor", 0) or 0)
        pid = int(getattr(device, "idProduct", 0) or 0)
        name = ""
        try:
            name = str(usb.util.get_string(device, device.iProduct) or "")
        except Exception:
            name = ""
        found.append(UsbDevice(vid=vid, pid=pid, name=name, source="pyusb"))
    return found


def serial_ports() -> list[dict[str, str]]:
    """Return serial ports with their description and hardware id."""

    try:
        from serial.tools import list_ports  # noqa: PLC0415 - optional dependency
    except Exception:
        return []
    ports: list[dict[str, str]] = []
    try:
        for port in list_ports.comports():
            ports.append(
                {
                    "device": str(port.device),
                    "description": str(getattr(port, "description", "") or ""),
                    "hwid": str(getattr(port, "hwid", "") or ""),
                }
            )
    except Exception:
        return []
    return ports


def serial_devices(ports: list[dict[str, str]]) -> list[UsbDevice]:
    """Turn COM ports into devices when their hardware id names a vendor."""

    found: list[UsbDevice] = []
    for port in ports:
        hwid = port.get("hwid", "")
        match = DEVICE_ID_RE.search(hwid) or HWID_RE.search(hwid)
        if not match:
            continue
        found.append(
            UsbDevice(
                vid=int(match.group(1), 16),
                pid=int(match.group(2), 16),
                name=port.get("description", ""),
                port=port.get("device", ""),
                source="serial",
            )
        )
    return found


def interface_status() -> dict[str, object]:
    """Which libraries this build can actually use."""

    status: dict[str, object] = {"platform": sys.platform, "windows": os.name == "nt"}
    try:
        import usb.core  # noqa: PLC0415 - optional dependency

        status["pyusb"] = True
        status["pyusb_error"] = ""
        # The only reliable backend check is a real enumeration: pyusb exposes
        # no stable "backend" attribute, so probing for one is a false alarm.
        try:
            found = list(usb.core.find(find_all=True) or [])
            status["libusb"] = "available"
            status["pyusb_devices"] = len(found)
        except Exception as exc:
            status["libusb"] = ""
            status["pyusb_devices"] = 0
            status["pyusb_error"] = "%s: %s" % (exc.__class__.__name__, exc)
    except Exception as exc:
        status["pyusb"] = False
        status["libusb"] = ""
        status["pyusb_devices"] = 0
        status["pyusb_error"] = "%s: %s" % (exc.__class__.__name__, exc)
    try:
        import serial  # noqa: F401  # noqa: PLC0415 - optional dependency

        status["pyserial"] = True
        status["pyserial_error"] = ""
    except Exception as exc:
        status["pyserial"] = False
        status["pyserial_error"] = "%s: %s" % (exc.__class__.__name__, exc)
    return status


def scan() -> UsbReport:
    """Collect USB devices from every available source."""

    report = UsbReport(platform=sys.platform)
    status = interface_status()
    report.sources = {
        "pyusb": bool(status.get("pyusb")),
        "pnp": os.name == "nt",
        "serial": bool(status.get("pyserial")),
    }
    for key in ("pyusb_error", "pyserial_error"):
        message = str(status.get(key) or "")
        if message:
            report.errors[key.replace("_error", "")] = message

    try:
        ports = serial_ports()
    except Exception:
        ports = []
    report.ports = [port["device"] for port in ports if port.get("device")]

    collected: list[UsbDevice] = []
    collected.extend(pnp_devices())
    collected.extend(pyusb_devices())
    collected.extend(serial_devices(ports))

    # One row per (vid, pid, port); PnP is the most descriptive source.
    seen: dict[tuple[int, int, str], UsbDevice] = {}
    order = {"pnp": 0, "pyusb": 1, "serial": 2}
    for device in sorted(collected, key=lambda item: order.get(item.source, 9)):
        key = (device.vid, device.pid, device.port)
        current = seen.get(key)
        if current is None:
            seen[key] = device
            continue
        if not current.name and device.name:
            seen[key] = device
    report.devices = list(seen.values())
    report.relevant = [device for device in report.devices if device.vendor]
    report.verdict, report.detail, report.steps = _verdict(report)
    return report


def _verdict(report: UsbReport) -> tuple[str, str, list[str]]:
    """Turn the collected devices into one sentence and the next steps."""

    if not report.sources.get("pyusb") and not report.sources.get("pnp") and not report.sources.get("serial"):
        return (
            "no_tools",
            "No USB library is available in this build, so USB cannot be checked at all.",
            ["Reinstall BestMDMTool; the bundled build must include pyusb and pyserial."],
        )

    download = [device for device in report.relevant if device.download_mode]
    if download:
        device = download[0]
        where = " on %s" % device.port if device.port else ""
        return (
            "download",
            "%s phone in %s mode detected at %s%s."
            % (
                "MediaTek" if device.vid == MTK_VID else "Spreadtrum",
                device.download_mode,
                device.usb_id,
                where,
            ),
            _driver_steps(device),
        )

    def _is_phone_interface(device: UsbDevice) -> bool:
        haystack = ("%s %s" % (device.name, device.service)).lower()
        return any(word in haystack for word in ("mtp", "android", "adb", "wpd"))

    booted = [device for device in report.devices if _is_phone_interface(device)]
    if booted:
        device = booted[0]
        return (
            "android",
            "The phone is connected and booted into Android (%s, %s, driver %s), so no download "
            "mode is open."
            % (device.name or device.usb_id, device.usb_id, device.service or "unknown"),
            [
                "MediaTek: power off, then hold Volume- (or Volume+ and Volume-) while plugging in.",
                "Spreadtrum: power off, then hold Volume- while plugging in.",
                "The screen must stay black; Windows re-detects the phone within a second or two.",
                "If Windows shows an unknown device with a yellow mark, install the vendor USB driver.",
            ],
        )

    known_vendor = report.relevant
    if known_vendor:
        device = known_vendor[0]
        return (
            "present_not_download",
            "A %s device is plugged in (%s, %s) but it is not in a download mode."
            % (
                "MediaTek" if device.vid == MTK_VID else "Spreadtrum",
                device.usb_id,
                device.name or "unnamed",
            ),
            _download_mode_steps(device),
        )

    android = [device for device in report.devices if "android" in device.name.lower() or "adb" in device.name.lower()]
    if android:
        return (
            "android",
            "The phone is in normal Android mode (%s), so BROM/BSL is not exposed yet."
            % (android[0].name or android[0].usb_id),
            [
                "Power the phone off completely.",
                "MediaTek: hold Volume- (or Volume+ and Volume-) while plugging the USB cable in.",
                "Spreadtrum: hold Volume- and plug in; the screen stays black when it works.",
                "Windows should chime and Device Manager should show a new port or a yellow warning icon.",
            ],
        )

    if report.sources.get("pyusb") and report.errors.get("pyusb"):
        if report.devices:
            return (
                "nothing",
                "Windows sees %d USB device%s, but none is a MediaTek or Spreadtrum phone. "
                "(pyusb also failed: %s)"
                % (len(report.devices), "" if len(report.devices) == 1 else "s", report.errors["pyusb"]),
                [
                    "Put the phone in download mode: power it off, then hold Volume- while plugging in.",
                    "Then run this check again from the Chipset Database page.",
                ],
            )
        return (
            "backend",
            "pyusb is installed but the libusb backend could not enumerate: %s" % report.errors["pyusb"],
            [
                "Reinstall BestMDMTool so libusb-1.0.dll ships next to the executable.",
                "Then run this check again.",
            ],
        )

    return (
        "nothing",
        "No USB device of any kind is visible to this process.",
        [
            "Replug the cable and try another port (avoid hubs).",
            "Check that Device Manager refreshes when you plug the phone in.",
            "Windows-only drivers: the phone must appear in Device Manager before any tool can see it.",
        ],
    )


def _driver_steps(device: UsbDevice) -> list[str]:
    steps: list[str] = []
    if device.service:
        steps.append("Windows driver bound to it: %s." % device.service)
    if device.problem:
        steps.append(
            "Device Manager reports a problem code %s: install the driver before connecting."
            % device.problem
        )
    if device.vid == MTK_VID and not device.openable:
        steps.append(
            "MediaTek BROM needs UsbDk (or WinUSB/libusbK bound to the port). Install the UsbDk "
            "driver, reconnect the phone, then press Connect."
        )
    if device.vid == SPD_VID and device.port and not device.openable:
        # Spreadtrum phones answer on a COM port, so the driver is fine as-is.
        steps.append(
            "This phone is on %s. In Settings set SPD transport to 'serial' and SPD port to %s, "
            "then press Connect." % (device.port, device.port)
        )
    elif device.service and not device.openable:
        steps.append(
            "The bound driver (%s) cannot be opened by the USB transport. Bind WinUSB or libusbK "
            "to it (Device Manager -> Update driver -> Browse -> Let me pick -> WinUSB), then "
            "reconnect." % device.service
        )
    steps.append("Press Connect in the title bar.")
    return steps


def _download_mode_steps(device: UsbDevice) -> list[str]:
    steps = [
        "Unplug the phone, power it off completely, then hold the download keys while plugging in.",
    ]
    if device.vid == MTK_VID:
        steps.append("MediaTek BROM: Volume- (some phones need Volume+ and Volume-, or a "
                     "test point) — Device Manager should briefly show 'MediaTek PreLoader'.")
    else:
        steps.append("Spreadtrum BSL: Volume- while plugging in; Windows should show a new COM port.")
    if device.service:
        steps.append("Currently bound driver: %s." % device.service)
    return steps
