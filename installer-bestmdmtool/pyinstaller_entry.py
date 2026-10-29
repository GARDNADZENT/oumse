"""Entry point used by PyInstaller to build BestMDMTool.exe.

The frozen executable is installed next to the bundled runtime so the GUI can
launch the headless BROM runner without the user installing Python.

``BestMDMTool.exe --selftest [report.json]`` imports the whole interface (and
the runner client), checks the runtime paths, writes a JSON report, and exits.
The build workflow uses it to prove the frozen bundle is complete.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import traceback


def _show_error(message: str) -> None:
    try:
        import tkinter as tk
        from tkinter import messagebox

        root = tk.Tk()
        root.withdraw()
        messagebox.showerror("BestMDMTool", message)
        root.destroy()
    except Exception:  # pragma: no cover - last-resort reporting
        try:
            sys.stderr.write(message + "\n")
        except Exception:
            pass


def _ensure_import_path() -> None:
    """Allow running this file unfrozen from a source checkout."""
    if getattr(sys, "frozen", False):
        return
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))


def run_selftest(report_path: str) -> int:
    """Import every UI page and verify runtime paths; write a JSON report."""
    report: dict[str, object] = {"ok": False, "python": sys.version, "frozen": bool(getattr(sys, "frozen", False))}
    _ensure_import_path()
    try:
        import bestmdmtool.branding as branding
        from bestmdmtool.ui.pages import PAGES
        from servicecore.adb import find_adb, find_fastboot
        from servicecore.config import ROOT, python_executable, service_runner_path
        from servicecore.service_session import ServiceSession

        report.update(
            {
                "product": branding.PRODUCT_NAME,
                "version": branding.PRODUCT_VERSION,
                "root": str(ROOT),
                "runner": str(service_runner_path()),
                "runner_exists": service_runner_path().is_file(),
                "python": str(python_executable()),
                "python_exists": python_executable().exists(),
                "pages": sorted(PAGES),
                "session_client": ServiceSession.__name__,
                "adb": str(find_adb() or ""),
                "fastboot": str(find_fastboot() or ""),
                "runtime_lib": (ROOT / "runtime" / "lib").is_dir(),
            }
        )
        report["ok"] = bool(report["runner_exists"] and report["python_exists"] and report["runtime_lib"])
    except Exception:
        report["error"] = traceback.format_exc()

    try:
        with open(report_path, "w", encoding="utf-8") as handle:
            json.dump(report, handle, indent=2)
    except OSError:
        pass
    return 0 if report.get("ok") else 1


def main() -> int:
    if "--selftest" in sys.argv:
        index = sys.argv.index("--selftest")
        target = (
            sys.argv[index + 1]
            if len(sys.argv) > index + 1
            else os.path.join(tempfile.gettempdir(), "bestmdmtool-selftest.json")
        )
        return run_selftest(target)

    try:
        from bestmdmtool.gui import main as gui_main

        gui_main()
    except SystemExit:
        raise
    except Exception:
        _show_error(
            "BestMDMTool failed to start.\n\n"
            + traceback.format_exc()
            + "\nReinstall BestMDMTool or run START_BEST_MDM_TOOL.bat from a source checkout."
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
