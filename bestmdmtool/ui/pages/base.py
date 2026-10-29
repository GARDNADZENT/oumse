"""Shared page scaffolding."""

from __future__ import annotations

import tkinter as tk
from typing import TYPE_CHECKING, Any

from .. import theme

if TYPE_CHECKING:  # pragma: no cover
    from ..main_window import MainWindow


class BasePage(tk.Frame):
    """Title block plus a content frame; subclasses implement ``build``."""

    key = ""
    heading = ""
    description = ""

    def __init__(self, master: tk.Misc, app: MainWindow) -> None:
        super().__init__(master, bg=theme.BG)
        self.app = app
        self.controller = app.controller
        self._build_header()
        self.content = tk.Frame(self, bg=theme.BG)
        self.content.pack(fill="both", expand=True, padx=18, pady=(0, 14))
        self.build()

    def _build_header(self) -> None:
        header = tk.Frame(self, bg=theme.BG)
        header.pack(fill="x", padx=18, pady=(16, 12))
        tk.Label(
            header,
            text=self.heading,
            bg=theme.BG,
            fg=theme.TEXT,
            font=theme.FONT_TITLE,
            anchor="w",
        ).pack(anchor="w")
        if self.description:
            tk.Label(
                header,
                text=self.description,
                bg=theme.BG,
                fg=theme.TEXT_MUTED,
                font=theme.FONT_UI_SMALL,
                anchor="w",
                justify="left",
            ).pack(anchor="w", pady=(2, 0))

    # -- hooks -------------------------------------------------------------
    def build(self) -> None:  # pragma: no cover - overridden
        raise NotImplementedError

    def on_show(self) -> None:
        return None

    def on_device(self, device: dict[str, Any]) -> None:
        return None

    def on_busy(self, busy: bool) -> None:
        return None

    # -- helpers -----------------------------------------------------------
    def log(self, message: str, level: str = "INFO") -> None:
        self.app.log(message, level)

    def require_session(self):
        session = self.controller.require_session()
        if session is None:
            self.app.set_status("Connect a device first.", "warn")
        return session

    def partitions(self) -> list[dict[str, Any]]:
        return self.controller.partitions

    @staticmethod
    def format_size(size: int) -> str:
        value = float(size or 0)
        for unit in ("B", "KB", "MB", "GB", "TB"):
            if value < 1024 or unit == "TB":
                if unit == "B":
                    return "%d B" % int(value)
                return "%.2f %s" % (value, unit)
            value /= 1024
        return "%d B" % int(size)
