"""Dark theme tokens and ttk style setup for the BestMDMTool interface."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

# -- palette ---------------------------------------------------------------
# Near-black surfaces, one orange accent, four action colours. Matches the
# OumseGSM workspace look: dark cards on a black canvas, orange for the tool
# that is currently open.
BG = "#08080a"
BG_ALT = "#0d0d10"
PANEL = "#151518"
PANEL_ALT = "#1c1c21"
PANEL_HOVER = "#26262c"
BORDER = "#2b2b32"
BORDER_SOFT = "#212127"
SIDE = "#101013"

TEXT = "#ececee"
TEXT_MUTED = "#9a9aa4"
TEXT_DIM = "#6d6d78"

ACCENT = "#f26a21"
ACCENT_HOVER = "#d95a15"
ACCENT_DIM = "#3a2110"
ACCENT_TEXT = "#160b03"

SUCCESS = "#3ecf5f"
SUCCESS_DIM = "#10290f"
WARNING = "#f5a524"
WARNING_DIM = "#33240a"
DANGER = "#e5484d"
DANGER_DIM = "#33161a"
INFO = "#5b9bd5"

FONT_UI = ("Segoe UI", 10)
FONT_UI_SMALL = ("Segoe UI", 9)
FONT_UI_BOLD = ("Segoe UI Semibold", 10)
FONT_TITLE = ("Segoe UI Semibold", 18)
FONT_SUBTITLE = ("Segoe UI Semibold", 12)
FONT_MONO = ("Consolas", 9)
FONT_BADGE = ("Segoe UI", 8)
FONT_NAV = ("Segoe UI", 8)

LOG_COLORS = {
    "INFO": "#c8c8d0",
    "OK": SUCCESS,
    "WARN": WARNING,
    "ERROR": DANGER,
    "STEP": INFO,
    "DEBUG": TEXT_DIM,
}

CONSOLE_BG = "#050506"
CONSOLE_TEXT = "#5ee07a"


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
