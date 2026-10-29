"""Build a support bundle the user can attach to a bug report.

The bundle is a single zip with the activity log, the newest crash report, a
backend self-test result and the current device/partition snapshot. Nothing
leaves the machine on its own: the user chooses where to send it.
"""

from __future__ import annotations

import json
import platform
import sys
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any

from .branding import PRODUCT_NAME, PRODUCT_VERSION

BUNDLE_STEM = "BestMDMTool-support"


def default_target(directory: Path | None = None) -> Path:
    """Pick an obvious place for the bundle (Desktop, else home)."""
    if directory is not None:
        base = Path(directory)
    else:
        desktop = Path.home() / "Desktop"
        base = desktop if desktop.is_dir() else Path.home()
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    base.mkdir(parents=True, exist_ok=True)
    return base / ("%s-%s.zip" % (BUNDLE_STEM, stamp))


def _system_report(extra: dict[str, Any] | None = None) -> str:
    lines = [
        "%s %s" % (PRODUCT_NAME, PRODUCT_VERSION),
        "generated: %s" % datetime.now().isoformat(timespec="seconds"),
        "platform: %s" % platform.platform(),
        "machine: %s" % platform.machine(),
        "python: %s" % sys.version.replace("\n", " "),
        "frozen: %s" % bool(getattr(sys, "frozen", False)),
        "executable: %s" % sys.executable,
    ]
    for key, value in sorted((extra or {}).items()):
        lines.append("%s: %s" % (key, value))
    return "\n".join(lines) + "\n"


def _newest_crash(log_dir: Path) -> Path | None:
    crashes = sorted(log_dir.glob("crash-*.log"), key=lambda item: item.stat().st_mtime)
    return crashes[-1] if crashes else None


def build(
    *,
    device: dict[str, Any] | None = None,
    partitions: list[dict[str, Any]] | None = None,
    settings: dict[str, Any] | None = None,
    selftest: dict[str, Any] | None = None,
    target: Path | None = None,
) -> Path:
    """Write the bundle and return its path."""
    import bestmdmtool.applog as applog  # absolute: keeps this module independent of app/

    log_directory = applog.log_dir()
    destination = Path(target) if target else default_target()
    destination.parent.mkdir(parents=True, exist_ok=True)

    snapshot = {
        "product": PRODUCT_NAME,
        "version": PRODUCT_VERSION,
        "device": device or {},
        "partitions": len(partitions or []),
        "partition_names": [str(entry.get("name", "")) for entry in (partitions or [])],
        "settings": settings or {},
    }

    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        activity = log_directory / "activity.log"
        if activity.is_file():
            archive.write(activity, "activity.log")
        crash = _newest_crash(log_directory)
        if crash is not None:
            archive.write(crash, crash.name)
        archive.writestr(
            "system.txt",
            _system_report(
                {
                    "log directory": str(log_directory),
                    "runner device": (device or {}).get("chip", ""),
                }
            ),
        )
        archive.writestr("device.json", json.dumps(snapshot, indent=2, default=str))
        if selftest is not None:
            archive.writestr("selftest.json", json.dumps(selftest, indent=2, default=str))
    return destination
