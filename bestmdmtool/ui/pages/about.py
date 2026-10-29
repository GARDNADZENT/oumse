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
                "A no-login service workspace for two chip families.\n"
                "\n"
                "MediaTek: the bundled mtkclient BROM/DA layer, for partition reads,\n"
                "writes, erases, backups, raw flash access, seccfg and ADB/Fastboot.\n"
                "\n"
                "Spreadtrum/Unisoc: a built-in BSL/FDL engine with a partition table,\n"
                "read/write/erase, PAC firmware flashing, PAC packaging (ROM maker)\n"
                "and an AT/DIAG console.",
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
                "mtkclient 2.1.4 (GPLv3) for the MediaTek DA/BROM protocol, a first-party\n"
                "Spreadtrum BSL/FDL implementation, the bundled Python runtime for the\n"
                "headless runners, Android platform tools for ADB/Fastboot.",
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
