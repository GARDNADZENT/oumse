"""Run the bundled backend self-test and summarise the result.

The device layer can fail long before a phone is attached: a missing runner, an
import error inside the bundle, or a libusb DLL that did not get installed. This
module asks the runner to check itself (``BestMDMToolRunner.exe --selftest``) so
the UI can show the real cause instead of a generic "connection failed".
"""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

from .config import selfcheck_command

#: Report keys that must be true for the device layer to be usable.
REQUIRED_KEYS = ("ok", "mtkclient", "libusb_backend")


def _summarise(report: dict[str, Any]) -> list[str]:
    """Turn a self-test report into short, human-readable lines."""
    lines: list[str] = []
    version = str(report.get("python") or "?").split()[0]
    kind = "frozen" if report.get("frozen") else "source"
    lines.append("Python %s (%s)" % (version, kind))
    lines.append("mtkclient: %s" % ("yes" if report.get("mtkclient") else "NO"))
    backend = "yes" if report.get("libusb_backend") else "NO"
    dll = report.get("libusb_dll")
    lines.append("libusb backend: %s%s" % (backend, " (%s)" % dll if dll else ""))
    lines.append(
        "DA loaders: v5 %s, v6 %s"
        % ("yes" if report.get("da_v5") else "NO", "yes" if report.get("da_v6") else "NO")
    )
    lines.append("USB devices visible: %s" % report.get("usb_devices", "?"))
    lib = report.get("runtime_lib")
    if lib:
        lines.append("runtime/lib: %s" % lib)
    operations = report.get("operations") or []
    if operations:
        lines.append("operations: %d" % len(operations))
    error = report.get("error")
    if error:
        tail = [line for line in str(error).strip().splitlines() if line.strip()][-3:]
        lines.extend("  %s" % line.strip() for line in tail)
    return lines


def run(report_path: str | Path | None = None, *, timeout: float = 180.0) -> dict[str, Any]:
    """Execute the backend self-test and return its parsed report.

    The returned dict always contains ``ok``, ``lines`` (human-readable summary)
    and, when the check could not run at all, ``error``.
    """
    command = selfcheck_command()
    if command is None:
        return {
            "ok": False,
            "error": "no device runner is installed",
            "lines": ["No device runner found. Reinstall BestMDMTool."],
        }
    argv, cwd = command

    handle_path = Path(report_path) if report_path else Path(tempfile.gettempdir()) / "bestmdmtool-selftest.json"
    if report_path is None:
        # Never trust a stale report from an earlier run.
        try:
            handle_path.unlink()
        except OSError:
            pass
    argv = [*argv, str(handle_path)]

    started = time.monotonic()
    try:
        completed = subprocess.run(
            argv,
            cwd=str(cwd),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
        exit_code = completed.returncode
        output = completed.stdout or ""
    except OSError as exc:
        return {
            "ok": False,
            "error": "cannot start the device runner: %s" % exc,
            "lines": ["Cannot start the device runner: %s" % exc],
            "command": " ".join(argv),
        }
    except subprocess.TimeoutExpired:
        return {
            "ok": False,
            "error": "the device runner self-test timed out after %.0fs" % timeout,
            "lines": ["Self-test timed out after %.0fs." % timeout],
            "command": " ".join(argv),
        }

    report: dict[str, Any] = {}
    try:
        report = json.loads(handle_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        report = {"ok": False, "error": "no usable self-test report (exit %s): %s" % (exit_code, exc)}

    report["exit_code"] = exit_code
    report["command"] = " ".join(argv)
    report["duration"] = round(time.monotonic() - started, 2)
    report.setdefault("ok", False)
    if not report["ok"] and not report.get("error"):
        tail = [line for line in output.strip().splitlines() if line.strip()][-3:]
        report["error"] = "\n".join(tail) or "self-test failed (exit %s)" % exit_code
    report["lines"] = _summarise(report)
    return report


def is_healthy(report: dict[str, Any]) -> bool:
    """True when every capability the device layer needs is present."""
    return all(bool(report.get(key)) for key in REQUIRED_KEYS)


def describe_failure(report: dict[str, Any]) -> str:
    """Return one actionable sentence explaining a failed self-test."""
    if not report.get("mtkclient"):
        return "the runner cannot import mtkclient (incomplete device backend)"
    if not report.get("libusb_backend"):
        return "the libusb backend did not load (missing libusb DLL)"
    if not report.get("da_v5"):
        return "the DA loader files are missing from runtime\\lib"
    if report.get("error"):
        first = str(report["error"]).strip().splitlines()[0]
        return first[:300]
    return "the device backend reported a problem"


def environment_hint() -> str:
    """Return a hint about where the runner is expected to live."""
    root = os.environ.get("BESTMDMTOOL_ROOT") or os.environ.get("SVC_ROOT") or ""
    if root:
        return "Application root: %s" % root
    return "Install the app with the installer so runtime\\runner\\BestMDMToolRunner.exe is present."
