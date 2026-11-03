"""About page: product identity, credits, and safety boundaries."""

from __future__ import annotations

import tkinter as tk

from .. import theme
from ..widgets import Card
from .base import BasePage


class AboutPage(BasePage):
    key = "about"
    heading = "About"
    description = "Product information and the boundaries of what this tool does."

    def build(self) -> None:
        from ...branding import AUTHORIZED_USE, PRODUCT_NAME, PRODUCT_VERSION

        card = Card(self.content, "%s %s" % (PRODUCT_NAME, PRODUCT_VERSION))
        card.pack(fill="x")

        for title, body in (
            (
                "What this is",
                "A no-login service workspace with MediaTek detection and a first-party\n"
                "Spreadtrum/Unisoc BSL/FDL engine. MediaTek sessions are temporarily\n"
                "disabled pending security review; no MTK commands are sent.\n"
                "\n"
                "Spreadtrum/Unisoc: partition table, read/write/erase, PAC firmware\n"
                "flashing and packaging (ROM maker), and an AT/DIAG console.",
            ),
            (
                "What this is not",
                "It contains no MDM/FRP bypass, no credential extraction, and no\n"
                "licensing circumvention. There is no account, no heartbeat and no\n"
                "remote service — every operation runs locally.",
            ),
            ("Authorized use", AUTHORIZED_USE),
            (
                "Components",
                "First-party Spreadtrum/Unisoc BSL/FDL implementation, pyusb/pyserial,\n"
                "bundled libusb DLLs, and Android platform tools for ADB/Fastboot.\n"
                "The MediaTek DA backend is not included in this installer.",
            ),
        ):
            block = tk.Frame(card.body, bg=theme.PANEL)
            block.pack(fill="x", pady=(0, 12))
            tk.Label(
                block,
                text=title.upper(),
                bg=theme.PANEL,
                fg=theme.TEXT_DIM,
                font=theme.FONT_BADGE,
                anchor="w",
            ).pack(fill="x")
            tk.Label(
                block,
                text=body,
                bg=theme.PANEL,
                fg=theme.TEXT,
                font=theme.FONT_UI_SMALL,
                justify="left",
                anchor="w",
            ).pack(fill="x", pady=(2, 0))

        tk.Label(
            self.content,
            text="Keyboard: F5 refresh partition table  ·  log dock toggles from the status bar",
            bg=theme.BG,
            fg=theme.TEXT_DIM,
            font=theme.FONT_BADGE,
            anchor="w",
        ).pack(fill="x", pady=(10, 0))
