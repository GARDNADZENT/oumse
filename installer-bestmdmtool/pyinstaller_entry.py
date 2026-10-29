"""Entry point used by PyInstaller to build BestMDMTool.exe.

The frozen executable is installed next to the bundled runtime so the GUI can
launch the headless BROM runner without the user installing Python.
"""

from __future__ import annotations

import sys
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
        sys.stderr.write(message + "\n")


def main() -> int:
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
