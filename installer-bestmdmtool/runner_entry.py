"""Console entry point for the frozen BestMDMTool device runner.

Built by PyInstaller as ``BestMDMToolRunner.exe``. It ships a complete CPython
with the first-party Spreadtrum/Unisoc protocol engine, pyusb and pyserial.
The MediaTek connection path is intentionally disabled pending a security
review; the MTK backend and its loaders are not bundled by this installer.

``BestMDMToolRunner.exe --selftest [report.json]`` verifies the SPD and USB
runtime without touching a device and writes a JSON report.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import traceback
from pathlib import Path


def _ensure_import_path() -> None:
    """Allow running this file unfrozen from a source checkout."""
    if getattr(sys, "frozen", False):
        return
    from pathlib import Path

    # Append, never prepend: use installed USB packages rather than optional
    # vendored code from another product in this repository.
    root = Path(__file__).resolve().parents[1]
    if root.is_dir() and str(root) not in sys.path:
        sys.path.append(str(root))


def _engine_from_argv() -> str:
    if "--engine" in sys.argv:
        index = sys.argv.index("--engine")
        if len(sys.argv) > index + 1:
            return sys.argv[index + 1].strip().lower()
    return "mtk"


def _libusb_candidates() -> list[str]:
    """Return places the bundled USB transports can find the libusb library."""
    from pathlib import Path

    names = ["libusb32-1.0.dll", "libusb-1.0.dll"] if os.name == "nt" else ["libusb-1.0.so"]
    roots: list[Path] = []
    if getattr(sys, "frozen", False):
        roots.append(Path(sys.executable).resolve().parent)
    here = Path(__file__).resolve().parent
    roots.extend([here, here.parent, here.parent / "runtime" / "runner"])
    for env_name in ("BESTMDMTOOL_ROOT", "OUMSE_ROOT", "SVC_ROOT"):
        raw = (os.environ.get(env_name) or "").strip()
        if raw:
            roots.append(Path(raw).expanduser())

    candidates: list[str] = []
    for root in roots:
        for name in names:
            candidates.append(str(root / name))
    candidates.extend(names)  # let the loader search PATH / the exe directory
    seen: list[str] = []
    for item in candidates:
        if item not in seen:
            seen.append(item)
    return seen


def run_selftest(report_path: str) -> int:
    _ensure_import_path()
    report: dict[str, object] = {
        "ok": False,
        "frozen": bool(getattr(sys, "frozen", False)),
        "python": sys.version,
    }
    try:
        import serial
        import usb.backend.libusb1
        import usb.core

        report["pyserial"] = getattr(serial, "VERSION", "?")
        report["pyusb"] = getattr(usb, "__version__", "?")
        report["pyserial_available"] = True
        report["pyusb_available"] = True

        backend = None
        searched = _libusb_candidates()
        for candidate in searched:
            try:
                backend = usb.backend.libusb1.get_backend(find_library=lambda _name, p=candidate: p)
            except Exception:
                backend = None
            if backend is not None:
                report["libusb_dll"] = candidate
                break
        report["libusb_backend"] = backend is not None
        report["libusb_search"] = searched[:8]
        devices = list(usb.core.find(find_all=True, backend=backend) or []) if backend else []
        report["usb_devices"] = len(devices)

        from servicecore.runner import spd_runner

        report["libusb_backend"] = backend is not None
        report["libusb_search"] = searched[:8]
        report["libusb_dll"] = report.get("libusb_dll") or ""
        report["usb_devices"] = len(devices)
        report["spd_engine"] = True
        report["operations"] = sorted(spd_runner.HANDLERS)
        if getattr(sys, "frozen", False):
            runner_dir = Path(sys.executable).resolve().parent
        else:
            runner_dir = Path(__file__).resolve().parent
        report["runner_dir"] = str(runner_dir)
        report["mtk_available"] = False
        report["mtk_notice"] = "MediaTek sessions are disabled pending security review."
        report["ok"] = bool(
            report["libusb_backend"]
            and report["pyserial_available"]
            and report["pyusb_available"]
            and report["spd_engine"]
        )
    except Exception:
        report["error"] = traceback.format_exc()

    try:
        with open(report_path, "w", encoding="utf-8") as handle:
            json.dump(report, handle, indent=2, default=str)
    except OSError:
        pass
    return 0 if report.get("ok") else 1


def selftest_mtk_disabled(report_path: str) -> int:
    """Prove that the MTK entry point refuses before opening a device."""
    _ensure_import_path()
    report: dict[str, object] = {"ok": False, "mtk_available": False}
    try:
        from servicecore.runner.service_runner import connect

        try:
            connect()
        except SystemExit as exc:
            report["refused"] = exc.code == 1
            report["reason"] = "mtk_temporarily_disabled_security_review"
            report["ok"] = exc.code == 1
        else:
            report["refused"] = False
            report["error"] = "MTK connect returned without the required refusal"
    except Exception as exc:
        report["error"] = "%s: %s" % (exc.__class__.__name__, exc)

    try:
        with open(report_path, "w", encoding="utf-8") as handle:
            json.dump(report, handle, indent=2)
    except OSError:
        pass
    return 0 if report.get("ok") else 1


def main() -> int:
    if "--selftest-mtk-disabled" in sys.argv:
        index = sys.argv.index("--selftest-mtk-disabled")
        target = (
            sys.argv[index + 1]
            if len(sys.argv) > index + 1
            else os.path.join(tempfile.gettempdir(), "bestmdmtool-mtk-disabled-selftest.json")
        )
        return selftest_mtk_disabled(target)

    if "--selftest" in sys.argv and _engine_from_argv() == "spd":
        _ensure_import_path()
        from servicecore.runner.spd_runner import selftest as spd_selftest

        index = sys.argv.index("--selftest")
        target = (
            sys.argv[index + 1]
            if len(sys.argv) > index + 1
            else os.path.join(tempfile.gettempdir(), "bestmdmtool-spd-selftest.json")
        )
        return spd_selftest(target)

    if "--selftest" in sys.argv:
        index = sys.argv.index("--selftest")
        target = (
            sys.argv[index + 1]
            if len(sys.argv) > index + 1
            else os.path.join(tempfile.gettempdir(), "bestmdmtool-runner-selftest.json")
        )
        return run_selftest(target)

    _ensure_import_path()
    engine = "mtk"
    if "--engine" in sys.argv:
        index = sys.argv.index("--engine")
        if len(sys.argv) > index + 1:
            engine = sys.argv[index + 1].strip().lower()
    if engine == "spd":
        from servicecore.runner.spd_runner import main as spd_main

        spd_main()
        return 0
    if engine != "mtk":
        sys.stderr.write("unknown engine: %s\n" % engine)
        return 2

    from servicecore.runner.service_runner import main as runner_main

    runner_main()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
