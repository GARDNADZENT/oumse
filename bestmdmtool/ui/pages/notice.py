"""Explanatory page shown where a bypass feature used to sit.

OumseGSM ships buttons for MDM patching, "direct bypass" and FRP clearing.
BestMDMTool keeps those entries in the tool list so the layout matches, but the
page behind them explains the omission and points at the real tool instead of
silently doing nothing.
"""

from __future__ import annotations

import tkinter as tk

from .. import theme
from ..i18n import t
from ..widgets import ActionButton, Card
from .base import BasePage


class NoticePage(BasePage):
    """Read-only page: why an action is missing, and what to use instead."""

    key = "notice"
    heading = ""
    description = ""

    def __init__(self, master: tk.Misc, app, *, body_key: str, alt: tuple[str, str] | None = None) -> None:
        self.body_key = body_key
        self.alt = alt
        super().__init__(master, app)

    def build(self) -> None:
        language = getattr(self.app, "language", "en")
        card = Card(self.content, t("notice.tag", language))
        card.pack(fill="both", expand=True)
        body = card.body

        tk.Label(
            body,
            text=t("notice.title", language),
            bg=theme.PANEL,
            fg=theme.ACCENT,
            font=theme.FONT_SUBTITLE,
            anchor="w",
            justify="left",
        ).pack(fill="x", pady=(4, 10))

        tk.Label(
            body,
            text=t(self.body_key, language),
            bg=theme.PANEL,
            fg=theme.TEXT,
            font=theme.FONT_UI,
            anchor="w",
            justify="left",
            wraplength=620,
        ).pack(fill="x", pady=(0, 14))

        tk.Frame(body, bg=theme.BORDER, height=1).pack(fill="x", pady=(0, 14))

        tk.Label(
            body,
            text=t("notice.policy", language),
            bg=theme.PANEL,
            fg=theme.TEXT_MUTED,
            font=theme.FONT_UI_SMALL,
            anchor="w",
            justify="left",
            wraplength=620,
        ).pack(fill="x", pady=(0, 16))

        if self.alt:
            label_key, section_key = self.alt
            ActionButton(
                body,
                t("notice.open_instead", language) % t(label_key, language),
                lambda: self.app.show_section(section_key),
                variant="accent",
            ).pack(anchor="w")

    def on_show(self) -> None:
        self.log("This action is not implemented: it would bypass a device lock or account.", "WARN")
