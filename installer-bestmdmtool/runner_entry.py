"""Console entry point for the frozen MTK service runner.

Built by PyInstaller as ``BestMDMToolRunner.exe``. It ships a complete CPython
with all C extensions (the vendored ``runtime/bin`` interpreter has none), so
mtkclient, pyusb and pyserial work out of the box.

``BestMDMToolRunner.exe --selftest [report.json]`` verifies the bundled backend
without touching a device: it imports mtkclient, pyserial, pyusb, loads the
libusb backend, enumerates USB devices, and writes a JSON report.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import traceback


def _ensure_import_path() -> None:
    """Allow running this file unfrozen from a source checkout."""
    if getattr(sys, "frozen", False):
        return
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    for extra in (root, root / "runtime" / "lib", root / "runtime" / "bin" / "Lib" / "site-packages"):
        if extra.is_dir() and str(extra) not in sys.path:
            sys.path.insert(0, str(extra))


def _libusb_candidates() -> list[str]:
    """Return places mtkclient expects to find the libusb shared library."""
    from pathlib import Path

    names = ["libusb32-1.0.dll", "libusb-1.0.dll"] if os.name == "nt" else ["libusb-1.0.so"]
    roots: list[Path] = []
    if getattr(sys, "frozen", False):
        roots.append(Path(sys.executable).resolve().parent)
    here = Path(__file__).resolve().parent
    roots.extend([here, here.parent])
    for env_name in ("BESTMDMTOOL_ROOT", "OUMSE_ROOT", "SVC_ROOT"):
        raw = (os.environ.get(env_name) or "").strip()
        if raw:
            roots.append(Path(raw).expanduser())

    candidates: list[str] = []
    for root in roots:
        for name in names:
            candidates.append(str(root / name))
            candidates.append(str(root / "runtime" / "lib" / "mtkclient" / "Windows" / name))
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

        from mtkclient.config.mtk_config import MtkConfig  # noqa: F401
        from mtkclient.Library.DA.mtk_da_handler import DaHandler  # noqa: F401
        from mtkclient.Library.mtk_class import Mtk  # noqa: F401

        from servicecore.runner.service_runner import HANDLERS, LIB_DIR

        report["mtkclient"] = True
        report["runtime_lib"] = str(LIB_DIR)
        report["runtime_lib_exists"] = LIB_DIR.is_dir()
        report["operations"] = sorted(HANDLERS)
        report["da_v5"] = (LIB_DIR / "mtkclient" / "Loader" / "MTK_DA_V5.bin").is_file()
        report["da_v6"] = (LIB_DIR / "mtkclient" / "Loader" / "MTK_DA_V6.bin").is_file()
        report["ok"] = bool(report["libusb_backend"] and report["runtime_lib_exists"])
    except Exception:
        report["error"] = traceback.format_exc()

    try:
        with open(report_path, "w", encoding="utf-8") as handle:
            json.dump(report, handle, indent=2, default=str)
    except OSError:
        pass
    return 0 if report.get("ok") else 1


def main() -> int:
    if "--selftest" in sys.argv:
        index = sys.argv.index("--selftest")
        target = (
            sys.argv[index + 1]
            if len(sys.argv) > index + 1
            else os.path.join(tempfile.gettempdir(), "bestmdmtool-runner-selftest.json")
        )
        return run_selftest(target)

    _ensure_import_path()
    from servicecore.runner.service_runner import main as runner_main

    runner_main()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
