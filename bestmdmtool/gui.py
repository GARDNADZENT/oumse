"""Entry point for the BestMDMTool desktop application.

The window opens straight into the device workspace: no login screen, no
account, and no remote service.
"""

from __future__ import annotations

try:
    import tkinter  # noqa: F401  # imported for the availability check below
except ImportError as exc:  # pragma: no cover - depends on the host Python install
    raise ImportError(
        "BestMDMTool needs a Python interpreter with Tkinter. On Windows use the "
        "official CPython installer; on Debian/Ubuntu install python3-tk."
    ) from exc

from .branding import (
    AUTHORIZED_USE,
    PRODUCT_NAME,
    PRODUCT_SUBTITLE,
    PRODUCT_TITLE,
    PRODUCT_VERSION,
)
from .ui import MainWindow


class BestMDMToolApp(MainWindow):
    """Main window carrying the BestMDMTool branding."""

    def __init__(self) -> None:
        super().__init__(
            product_name=PRODUCT_NAME,
            product_title=PRODUCT_TITLE,
            product_version=PRODUCT_VERSION,
            product_subtitle=PRODUCT_SUBTITLE,
            authorized_use=AUTHORIZED_USE,
        )
        self.title(PRODUCT_TITLE)


def main() -> None:
    """Open the workspace window. No login, no server, no account."""

    from .applog import configure, write_crash

    configure()
    try:
        app = BestMDMToolApp()
        app.mainloop()
    except Exception:
        report = write_crash()
        try:
            from tkinter import messagebox

            messagebox.showerror(
                "%s stopped unexpectedly" % PRODUCT_NAME,
                "A crash report was written to:\n\n%s\n\n"
                "Send that file with a description of what you were doing." % report,
            )
        except Exception:
            pass
        raise


if __name__ == "__main__":
    main()
