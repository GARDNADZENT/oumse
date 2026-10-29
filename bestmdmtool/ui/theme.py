"""Dark theme tokens and ttk style setup for the BestMDMTool interface."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

# -- palette ---------------------------------------------------------------
BG = "#0d1117"
BG_ALT = "#11161e"
PANEL = "#161b24"
PANEL_ALT = "#1b2230"
PANEL_HOVER = "#212a3a"
BORDER = "#263041"
BORDER_SOFT = "#1e2735"

TEXT = "#e6edf3"
TEXT_MUTED = "#93a1b3"
TEXT_DIM = "#6b7a8f"

ACCENT = "#3b82f6"
ACCENT_HOVER = "#2f6fd0"
ACCENT_DIM = "#1d3a63"

SUCCESS = "#22c55e"
SUCCESS_DIM = "#12351f"
WARNING = "#f59e0b"
WARNING_DIM = "#3a2a08"
DANGER = "#ef4444"
DANGER_DIM = "#3d1416"
INFO = "#38bdf8"

FONT_UI = ("Segoe UI", 10)
FONT_UI_SMALL = ("Segoe UI", 9)
FONT_UI_BOLD = ("Segoe UI Semibold", 10)
FONT_TITLE = ("Segoe UI Semibold", 17)
FONT_SUBTITLE = ("Segoe UI Semibold", 12)
FONT_MONO = ("Consolas", 9)
FONT_BADGE = ("Segoe UI", 8)

LOG_COLORS = {
    "INFO": TEXT,
    "OK": SUCCESS,
    "WARN": WARNING,
    "ERROR": DANGER,
    "STEP": INFO,
    "DEBUG": TEXT_DIM,
}


def configure_theme(root: tk.Misc) -> ttk.Style:
    """Apply the dark theme to ttk widgets and return the style object."""
    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass

    style.configure(".", background=BG, foreground=TEXT, font=FONT_UI, borderwidth=0)
    style.configure("TFrame", background=BG)
    style.configure("Panel.TFrame", background=PANEL)
    style.configure("TLabel", background=BG, foreground=TEXT, font=FONT_UI)
    style.configure("Muted.TLabel", background=BG, foreground=TEXT_MUTED, font=FONT_UI_SMALL)
    style.configure("Panel.TLabel", background=PANEL, foreground=TEXT)
    style.configure("PanelMuted.TLabel", background=PANEL, foreground=TEXT_MUTED, font=FONT_UI_SMALL)

    style.configure(
        "Treeview",
        background=PANEL_ALT,
        fieldbackground=PANEL_ALT,
        foreground=TEXT,
        bordercolor=BORDER,
        borderwidth=0,
        rowheight=25,
        font=FONT_UI_SMALL,
    )
    style.configure(
        "Treeview.Heading",
        background=PANEL,
        foreground=TEXT_MUTED,
        relief="flat",
        font=FONT_UI_SMALL,
        padding=(8, 6),
    )
    style.map(
        "Treeview",
        background=[("selected", ACCENT_DIM)],
        foreground=[("selected", TEXT)],
    )
    style.map("Treeview.Heading", background=[("active", PANEL_HOVER)])
    style.layout("Treeview", [("Treeview.treearea", {"sticky": "nswe"})])

    style.configure(
        "Svc.Horizontal.TProgressbar",
        troughcolor=PANEL_ALT,
        background=ACCENT,
        bordercolor=PANEL_ALT,
        lightcolor=ACCENT,
        darkcolor=ACCENT,
        thickness=8,
    )
    style.configure(
        "TCombobox",
        fieldbackground=PANEL_ALT,
        background=PANEL_ALT,
        foreground=TEXT,
        arrowcolor=TEXT_MUTED,
        bordercolor=BORDER,
    )
    style.map(
        "TCombobox",
        fieldbackground=[("readonly", PANEL_ALT)],
        foreground=[("readonly", TEXT)],
    )
    style.configure("TCheckbutton", background=BG, foreground=TEXT, font=FONT_UI_SMALL)
    style.map("TCheckbutton", background=[("active", BG)])
    style.configure("TRadiobutton", background=BG, foreground=TEXT, font=FONT_UI_SMALL)
    style.map("TRadiobutton", background=[("active", BG)])
    style.configure("Vertical.TScrollbar", background=PANEL_ALT, troughcolor=BG, arrowcolor=TEXT_DIM)
    style.configure("Horizontal.TScrollbar", background=PANEL_ALT, troughcolor=BG, arrowcolor=TEXT_DIM)
    return style
