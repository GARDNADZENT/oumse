"""Reusable widgets for the BestMDMTool interface."""

from __future__ import annotations

import time
import tkinter as tk
from collections.abc import Callable
from tkinter import ttk

from . import theme


class Card(tk.Frame):
    """Panel with a header strip and a body frame."""

    def __init__(self, master: tk.Misc, title: str = "", subtitle: str = "", *, padding: int = 14) -> None:
        super().__init__(master, bg=theme.PANEL, highlightbackground=theme.BORDER, highlightthickness=1)
        self.header = None
        if title:
            self.header = tk.Frame(self, bg=theme.PANEL)
            self.header.pack(fill="x", padx=padding, pady=(padding, 0))
            tk.Label(
                self.header,
                text=title,
                bg=theme.PANEL,
                fg=theme.TEXT,
                font=theme.FONT_SUBTITLE,
                anchor="w",
            ).pack(side="left")
            if subtitle:
                tk.Label(
                    self.header,
                    text=subtitle,
                    bg=theme.PANEL,
                    fg=theme.TEXT_MUTED,
                    font=theme.FONT_UI_SMALL,
                    anchor="e",
                ).pack(side="right")
        self.body = tk.Frame(self, bg=theme.PANEL)
        self.body.pack(fill="both", expand=True, padx=padding, pady=padding)


class ActionButton(tk.Button):
    """Flat button with an accent variant."""

    def __init__(
        self,
        master: tk.Misc,
        text: str,
        command: Callable[[], None] | None = None,
        *,
        variant: str = "default",
        width: int | None = None,
        height: int = 1,
        font=None,
        anchor: str = "center",
    ) -> None:
        colors = {
            "default": (theme.PANEL_ALT, theme.TEXT, theme.PANEL_HOVER, theme.BORDER),
            "accent": (theme.ACCENT, "#ffffff", theme.ACCENT_HOVER, theme.ACCENT),
            "success": (theme.SUCCESS, "#04170b", "#1ea44e", theme.SUCCESS),
            "danger": (theme.DANGER, "#ffffff", "#c93b3b", theme.DANGER),
            "warning": (theme.WARNING, "#1a1200", "#d18a08", theme.WARNING),
            "ghost": (theme.PANEL, theme.TEXT_MUTED, theme.PANEL_HOVER, theme.BORDER),
        }
        bg, fg, hover, border = colors.get(variant, colors["default"])
        super().__init__(
            master,
            text=text,
            command=command,
            bg=bg,
            fg=fg,
            activebackground=hover,
            activeforeground=fg,
            disabledforeground=theme.TEXT_DIM,
            relief="flat",
            bd=0,
            highlightthickness=1,
            highlightbackground=border,
            highlightcolor=border,
            font=font or theme.FONT_UI_SMALL,
            cursor="hand2",
            anchor=anchor,
            padx=12,
            pady=6,
        )
        if width:
            self.configure(width=width)
        if height != 1:
            self.configure(height=height)
        self._bg = bg
        self._hover = hover
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)

    def _on_enter(self, _event=None) -> None:
        if str(self["state"]) != "disabled":
            self.configure(bg=self._hover)

    def _on_leave(self, _event=None) -> None:
        if str(self["state"]) != "disabled":
            self.configure(bg=self._bg)


class Pill(tk.Label):
    """Small status badge."""

    STYLES = {
        "idle": (theme.PANEL_ALT, theme.TEXT_MUTED, theme.BORDER),
        "ok": (theme.SUCCESS_DIM, theme.SUCCESS, theme.SUCCESS),
        "busy": (theme.ACCENT_DIM, theme.INFO, theme.ACCENT),
        "warn": (theme.WARNING_DIM, theme.WARNING, theme.WARNING),
        "error": (theme.DANGER_DIM, theme.DANGER, theme.DANGER),
    }

    def __init__(self, master: tk.Misc, text: str = "", state: str = "idle") -> None:
        bg, fg, border = self.STYLES.get(state, self.STYLES["idle"])
        super().__init__(
            master,
            text=text,
            bg=bg,
            fg=fg,
            font=theme.FONT_BADGE,
            padx=8,
            pady=3,
            highlightbackground=border,
            highlightthickness=1,
        )

    def set(self, text: str, state: str = "idle") -> None:
        bg, fg, border = self.STYLES.get(state, self.STYLES["idle"])
        self.configure(text=text, bg=bg, fg=fg, highlightbackground=border)


class StatTile(tk.Frame):
    """Label + value tile used on the dashboard."""

    def __init__(self, master: tk.Misc, label: str, value: str = "—") -> None:
        super().__init__(master, bg=theme.PANEL_ALT, highlightbackground=theme.BORDER_SOFT, highlightthickness=1)
        self._label = tk.Label(
            self,
            text=label.upper(),
            bg=theme.PANEL_ALT,
            fg=theme.TEXT_DIM,
            font=theme.FONT_BADGE,
            anchor="w",
        )
        self._label.pack(fill="x", padx=12, pady=(10, 0))
        self._value = tk.Label(
            self,
            text=value,
            bg=theme.PANEL_ALT,
            fg=theme.TEXT,
            font=("Segoe UI Semibold", 13),
            anchor="w",
        )
        self._value.pack(fill="x", padx=12, pady=(1, 10))

    def set(self, value: str, color: str | None = None) -> None:
        self._value.configure(text=value or "—", fg=color or theme.TEXT)


class LogConsole(tk.Frame):
    """Colourised, auto-scrolling log with save/clear actions."""

    def __init__(self, master: tk.Misc, *, height: int = 10) -> None:
        super().__init__(master, bg=theme.BG_ALT)
        toolbar = tk.Frame(self, bg=theme.PANEL)
        toolbar.pack(fill="x")
        tk.Label(
            toolbar,
            text="ACTIVITY LOG",
            bg=theme.PANEL,
            fg=theme.TEXT_MUTED,
            font=theme.FONT_BADGE,
        ).pack(side="left", padx=10, pady=5)
        self._autoscroll = tk.BooleanVar(value=True)
        tk.Checkbutton(
            toolbar,
            text="auto-scroll",
            variable=self._autoscroll,
            bg=theme.PANEL,
            fg=theme.TEXT_MUTED,
            activebackground=theme.PANEL,
            activeforeground=theme.TEXT,
            selectcolor=theme.PANEL_ALT,
            font=theme.FONT_BADGE,
            bd=0,
            highlightthickness=0,
        ).pack(side="right", padx=6)
        ActionButton(toolbar, "Clear", self.clear, variant="ghost", font=theme.FONT_BADGE).pack(
            side="right", padx=(0, 6), pady=3
        )
        ActionButton(toolbar, "Save", self._save, variant="ghost", font=theme.FONT_BADGE).pack(
            side="right", padx=(0, 6), pady=3
        )

        wrapper = tk.Frame(self, bg=theme.BG_ALT)
        wrapper.pack(fill="both", expand=True)
        self.text = tk.Text(
            wrapper,
            height=height,
            bg=theme.BG_ALT,
            fg=theme.TEXT,
            insertbackground=theme.TEXT,
            font=theme.FONT_MONO,
            relief="flat",
            bd=0,
            wrap="none",
            padx=10,
            pady=6,
            state="disabled",
        )
        scroll = ttk.Scrollbar(wrapper, orient="vertical", command=self.text.yview)
        self.text.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.text.pack(side="left", fill="both", expand=True)
        for level, color in theme.LOG_COLORS.items():
            self.text.tag_configure(level, foreground=color)
        self.text.tag_configure("TIME", foreground=theme.TEXT_DIM)

    def write(self, message: str, level: str = "INFO") -> None:
        stamp = time.strftime("%H:%M:%S")
        self.text.configure(state="normal")
        self.text.insert("end", "[%s] " % stamp, "TIME")
        self.text.insert("end", "%s\n" % message.rstrip(), level if level in theme.LOG_COLORS else "INFO")
        if self._autoscroll.get():
            self.text.see("end")
        self.text.configure(state="disabled")

    def clear(self) -> None:
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.configure(state="disabled")

    def content(self) -> str:
        return self.text.get("1.0", "end-1c")

    def _save(self) -> None:
        from tkinter import filedialog

        path = filedialog.asksaveasfilename(
            title="Save log",
            defaultextension=".txt",
            filetypes=[("Text file", "*.txt"), ("All files", "*.*")],
        )
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(self.content())
            self.write("Log saved to %s" % path, "OK")
        except OSError as exc:
            self.write("Could not save log: %s" % exc, "ERROR")


class LabeledEntry(tk.Frame):
    """Label above a text entry."""

    def __init__(self, master: tk.Misc, label: str, *, width: int = 18, initial: str = "") -> None:
        super().__init__(master, bg=theme.PANEL)
        tk.Label(
            self,
            text=label,
            bg=theme.PANEL,
            fg=theme.TEXT_MUTED,
            font=theme.FONT_BADGE,
            anchor="w",
        ).pack(fill="x")
        self.var = tk.StringVar(value=initial)
        self.entry = tk.Entry(
            self,
            textvariable=self.var,
            width=width,
            bg=theme.PANEL_ALT,
            fg=theme.TEXT,
            insertbackground=theme.TEXT,
            relief="flat",
            bd=0,
            highlightthickness=1,
            highlightbackground=theme.BORDER,
            highlightcolor=theme.ACCENT,
            font=theme.FONT_UI_SMALL,
        )
        self.entry.pack(fill="x", ipady=4, pady=(3, 0))

    def get(self) -> str:
        return self.var.get().strip()

    def set(self, value: str) -> None:
        self.var.set(value)


class PathRow(tk.Frame):
    """Read-only path field with a browse button."""

    def __init__(
        self,
        master: tk.Misc,
        label: str,
        browse: Callable[[], str] | None = None,
    ) -> None:
        super().__init__(master, bg=theme.PANEL)
        tk.Label(
            self,
            text=label,
            bg=theme.PANEL,
            fg=theme.TEXT_MUTED,
            font=theme.FONT_BADGE,
            anchor="w",
        ).pack(fill="x")
        row = tk.Frame(self, bg=theme.PANEL)
        row.pack(fill="x", pady=(3, 0))
        self.var = tk.StringVar()
        tk.Entry(
            row,
            textvariable=self.var,
            bg=theme.PANEL_ALT,
            fg=theme.TEXT,
            readonlybackground=theme.PANEL_ALT,
            insertbackground=theme.TEXT,
            relief="flat",
            bd=0,
            highlightthickness=1,
            highlightbackground=theme.BORDER,
            font=theme.FONT_UI_SMALL,
            state="readonly",
        ).pack(side="left", fill="x", expand=True, ipady=4)
        if browse is not None:
            ActionButton(row, "Browse", browse, variant="ghost").pack(side="left", padx=(6, 0))

    def get(self) -> str:
        return self.var.get().strip()

    def set(self, value: str) -> None:
        self.var.set(value)
