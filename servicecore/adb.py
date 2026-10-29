"""Thin wrappers around the bundled ADB / Fastboot binaries.

No network access: everything here shells out to the local executables shipped
in ``adb_assets/`` and ``Bin/``.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ADB_DIRS = (ROOT / "adb_assets", ROOT / "Bin", ROOT / "runtime" / "bin")
FASTBOOT_DIRS = (ROOT / "Bin", ROOT / "adb_assets")


def _find(names: tuple[str, ...], directories: tuple[Path, ...]) -> Path | None:
    for directory in directories:
        for name in names:
            candidate = directory / name
            if candidate.is_file():
                return candidate
    for name in names:
        found = shutil.which(name)
        if found:
            return Path(found)
    return None


def find_adb() -> Path | None:
    return _find(("adb.exe", "adb"), ADB_DIRS)


def find_fastboot() -> Path | None:
    return _find(("fastboot.exe", "fastboot"), FASTBOOT_DIRS)


def _no_window() -> int:
    return getattr(subprocess, "CREATE_NO_WINDOW", 0)


@dataclass(slots=True)
class CommandOutput:
    ok: bool
    code: int
    text: str
    command: str = ""


class AdbTool:
    """Run ADB commands against the attached device."""

    def __init__(self, adb_path: Path | None = None, *, serial: str = "", timeout: float = 60.0) -> None:
        self.adb_path = adb_path or find_adb()
        self.serial = serial
        self.timeout = timeout

    @property
    def available(self) -> bool:
        return self.adb_path is not None

    def run(self, *args: str, timeout: float | None = None) -> CommandOutput:
        if self.adb_path is None:
            return CommandOutput(False, 127, "adb.exe was not found next to the application.")
        command = [str(self.adb_path)]
        if self.serial:
            command += ["-s", self.serial]
        command += [str(arg) for arg in args]
        try:
            proc = subprocess.run(
                command,
                capture_output=True,
                text=True,
                errors="replace",
                timeout=timeout or self.timeout,
                creationflags=_no_window(),
            )
        except subprocess.TimeoutExpired:
            return CommandOutput(False, -1, "Timed out: %s" % " ".join(command))
        except OSError as exc:
            return CommandOutput(False, -1, str(exc))
        text = (proc.stdout or "") + (proc.stderr or "")
        return CommandOutput(proc.returncode == 0, proc.returncode, text.strip(), " ".join(command))

    # -- queries -----------------------------------------------------------
    def devices(self) -> list[tuple[str, str]]:
        result = self.run("devices")
        devices: list[tuple[str, str]] = []
        for line in result.text.splitlines():
            line = line.strip()
            if not line or line.lower().startswith("list of devices"):
                continue
            parts = line.split()
            if len(parts) >= 2:
                devices.append((parts[0], parts[1]))
        return devices

    def state(self) -> str:
        for serial, state in self.devices():
            if not self.serial or serial == self.serial:
                return state
        return "offline"

    def model(self) -> str:
        result = self.run("shell", "getprop", "ro.product.model")
        return result.text.strip() if result.ok else ""

    def props(self, keys: tuple[str, ...]) -> dict[str, str]:
        values: dict[str, str] = {}
        for key in keys:
            result = self.run("shell", "getprop", key)
            values[key] = result.text.strip() if result.ok else ""
        return values

    # -- actions -----------------------------------------------------------
    def shell(self, *args: str, timeout: float | None = None) -> CommandOutput:
        return self.run("shell", *args, timeout=timeout)

    def push(self, local: str, remote: str) -> CommandOutput:
        return self.run("push", local, remote, timeout=600.0)

    def pull(self, remote: str, local: str) -> CommandOutput:
        return self.run("pull", remote, local, timeout=600.0)

    def install(self, apk: str, *, reinstall: bool = True) -> CommandOutput:
        args = ["install"]
        if reinstall:
            args.append("-r")
        return self.run(*args, apk, timeout=600.0)

    def reboot(self, target: str = "") -> CommandOutput:
        return self.run("reboot", *([target] if target else []))

    def enable_adb(self, apk: str | None = None) -> CommandOutput:
        """Install the bundled helper APK that enables ADB on engineering units."""
        candidate = apk or str(ROOT / "adb_assets" / "OumseResConfig.apk")
        if not os.path.isfile(candidate):
            return CommandOutput(False, 2, "Helper APK not found: %s" % candidate)
        return self.install(candidate)


class FastbootTool:
    """Run Fastboot commands against the attached device."""

    def __init__(self, fastboot_path: Path | None = None, *, serial: str = "", timeout: float = 120.0) -> None:
        self.fastboot_path = fastboot_path or find_fastboot()
        self.serial = serial
        self.timeout = timeout

    @property
    def available(self) -> bool:
        return self.fastboot_path is not None

    def run(self, *args: str, timeout: float | None = None) -> CommandOutput:
        if self.fastboot_path is None:
            return CommandOutput(False, 127, "fastboot.exe was not found next to the application.")
        command = [str(self.fastboot_path)]
        if self.serial:
            command += ["-s", self.serial]
        command += [str(arg) for arg in args]
        try:
            proc = subprocess.run(
                command,
                capture_output=True,
                text=True,
                errors="replace",
                timeout=timeout or self.timeout,
                creationflags=_no_window(),
            )
        except subprocess.TimeoutExpired:
            return CommandOutput(False, -1, "Timed out: %s" % " ".join(command))
        except OSError as exc:
            return CommandOutput(False, -1, str(exc))
        text = (proc.stdout or "") + (proc.stderr or "")
        return CommandOutput(proc.returncode == 0, proc.returncode, text.strip(), " ".join(command))

    def devices(self) -> list[str]:
        result = self.run("devices")
        out = []
        for line in result.text.splitlines():
            line = line.strip()
            if not line or line.startswith("<"):
                continue
            out.append(line.split()[0])
        return out

    def getvar(self, name: str) -> str:
        result = self.run("getvar", name)
        for line in result.text.splitlines():
            if line.lower().startswith(name.lower()):
                _, _, value = line.partition(":")
                return value.strip()
        return ""

    def flash(self, partition: str, image: str) -> CommandOutput:
        return self.run("flash", partition, image, timeout=1800.0)

    def erase(self, partition: str) -> CommandOutput:
        return self.run("erase", partition)

    def reboot(self, target: str = "") -> CommandOutput:
        return self.run("reboot", *([target] if target else []))
