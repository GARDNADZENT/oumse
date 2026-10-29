"""Main application window for BestMDMTool."""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from tkinter import filedialog, messagebox, ttk
from typing import Any

from servicecore.adb import find_adb, find_fastboot

from . import theme
from .controller import Controller
from .pages import PAGES
from .widgets import ActionButton, LogConsole, Pill

NAV_LABELS = {
    "dashboard": "Dashboard",
    "partitions": "Partition Manager",
    "flasher": "Firmware Flasher",
    "advanced": "Advanced Tools",
    "bootloader": "Bootloader",
    "adb": "ADB & Fastboot",
    "settings": "Settings",
    "about": "About",
}


class MainWindow(tk.Tk):
    """Sidebar + page container + shared activity log."""

    def __init__(
        self,
        *,
        product_name: str,
        product_title: str,
        product_version: str,
        product_subtitle: str,
        authorized_use: str,
    ) -> None:
        super().__init__()
        self.product_name = product_name
        self.product_version = product_version
        self.authorized_use = authorized_use

        self.title(product_title)
        self.configure(bg=theme.BG)
        self.geometry("1200x780")
        self.minsize(1040, 700)
        try:
            self.iconbitmap(default="")
        except Exception:
            pass

        theme.configure_theme(self)
        self._nav_buttons: dict[str, tk.Frame] = {}
        self._pages: dict[str, Any] = {}
        self._current = ""
        self._log_visible = True

        self.controller = Controller(
            log=self.log,
            on_device=self._on_device,
            on_disconnect=self._on_disconnect,
            on_progress=self._on_progress,
            on_busy=self._on_busy,
            schedule=self._ui_call,
        )
        self.controller.bind_scheduler(self.after, self.after_cancel)

        self._build_header(product_subtitle)
        self._build_body()
        self._build_footer()
        self._build_log_dock()

        self.show_page("dashboard")

        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.after(250, self._startup_diagnostics)
        self.bind("<F5>", lambda _event: self.controller.refresh_partitions(self._on_partitions_refreshed))

    # -- construction ------------------------------------------------------
    def _build_header(self, product_subtitle: str) -> None:
        header = tk.Frame(self, bg=theme.PANEL, height=64)
        header.pack(side="top", fill="x")
        header.pack_propagate(False)
        tk.Frame(header, bg=theme.ACCENT, width=4).pack(side="left", fill="y")

        brand = tk.Frame(header, bg=theme.PANEL)
        brand.pack(side="left", padx=(14, 0), pady=10)
        tk.Label(
            brand,
            text=self.product_name,
            bg=theme.PANEL,
            fg=theme.TEXT,
            font=theme.FONT_TITLE,
            anchor="w",
        ).pack(anchor="w")
        tk.Label(
            brand,
            text=product_subtitle,
            bg=theme.PANEL,
            fg=theme.TEXT_MUTED,
            font=theme.FONT_BADGE,
            anchor="w",
        ).pack(anchor="w")

        right = tk.Frame(header, bg=theme.PANEL)
        right.pack(side="right", padx=14)

        self.btn_connect = ActionButton(right, "Connect device", self.connect_device, variant="accent")
        self.btn_connect.pack(side="right", padx=(8, 0), pady=14)
        self.btn_disconnect = ActionButton(right, "Disconnect", self.disconnect_device, variant="ghost")
        self.btn_disconnect.pack(side="right", padx=(8, 0), pady=14)
        self.btn_disconnect.configure(state="disabled")

        self.pill_session = Pill(right, "No session", "idle")
        self.pill_session.pack(side="right", padx=(8, 0))
        self.pill_chip = Pill(right, "No device", "idle")
        self.pill_chip.pack(side="right", padx=(8, 0))

        tk.Frame(self, bg=theme.BORDER, height=1).pack(side="top", fill="x")

    def _build_body(self) -> None:
        body = tk.Frame(self, bg=theme.BG)
        body.pack(side="top", fill="both", expand=True)

        self.sidebar = tk.Frame(body, bg=theme.BG_ALT, width=210)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)

        for key, label in NAV_LABELS.items():
            if key == "about":
                continue
            self._nav_buttons[key] = self._make_nav_button(key, label)

        spacer = tk.Frame(self.sidebar, bg=theme.BG_ALT)
        spacer.pack(fill="both", expand=True)

        info = tk.Frame(self.sidebar, bg=theme.PANEL)
        info.pack(side="bottom", fill="x", padx=10, pady=10)
        tk.Label(
            info,
            text="ENVIRONMENT",
            bg=theme.PANEL,
            fg=theme.TEXT_DIM,
            font=theme.FONT_BADGE,
            anchor="w",
        ).pack(fill="x", padx=10, pady=(8, 2))
        self.env_label = tk.Label(
            info,
            text="checking tools...",
            bg=theme.PANEL,
            fg=theme.TEXT_MUTED,
            font=theme.FONT_BADGE,
            justify="left",
            anchor="w",
        )
        self.env_label.pack(fill="x", padx=10, pady=(0, 8))

        tk.Frame(body, bg=theme.BORDER, width=1).pack(side="left", fill="y")

        self.page_container = tk.Frame(body, bg=theme.BG)
        self.page_container.pack(side="left", fill="both", expand=True)

        for key, page_class in PAGES.items():
            page = page_class(self.page_container, self)
            page.place(relx=0, rely=0, relwidth=1, relheight=1)
            self._pages[key] = page

    def _make_nav_button(self, key: str, label: str) -> tk.Frame:
        row = tk.Frame(self.sidebar, bg=theme.BG_ALT, cursor="hand2")
        row.pack(fill="x")
        accent = tk.Frame(row, bg=theme.BG_ALT, width=3)
        accent.pack(side="left", fill="y")
        text = tk.Label(
            row,
            text=label,
            bg=theme.BG_ALT,
            fg=theme.TEXT_MUTED,
            font=theme.FONT_UI,
            anchor="w",
            padx=12,
            pady=11,
            cursor="hand2",
        )
        text.pack(side="left", fill="x", expand=True)
        row._accent = accent  # type: ignore[attr-defined]
        row._text = text  # type: ignore[attr-defined]

        def _enter(_event=None) -> None:
            if self._current != key:
                row.configure(bg=theme.PANEL)
                text.configure(bg=theme.PANEL, fg=theme.TEXT)

        def _leave(_event=None) -> None:
            if self._current != key:
                row.configure(bg=theme.BG_ALT)
                text.configure(bg=theme.BG_ALT, fg=theme.TEXT_MUTED)

        for widget in (row, text):
            widget.bind("<Enter>", _enter)
            widget.bind("<Leave>", _leave)
            widget.bind("<Button-1>", lambda _event, page_key=key: self.show_page(page_key))
        return row

    def _build_footer(self) -> None:
        tk.Frame(self, bg=theme.BORDER, height=1).pack(side="bottom", fill="x")
        footer = tk.Frame(self, bg=theme.PANEL)
        footer.pack(side="bottom", fill="x")

        self.status_label = tk.Label(
            footer,
            text="Ready. No device session.",
            bg=theme.PANEL,
            fg=theme.TEXT_MUTED,
            font=theme.FONT_UI_SMALL,
            anchor="w",
        )
        self.status_label.pack(side="left", padx=12, pady=6)

        self.log_toggle = ActionButton(
            footer,
            "Hide log",
            self.toggle_log,
            variant="ghost",
            font=theme.FONT_BADGE,
        )
        self.log_toggle.pack(side="right", padx=8, pady=4)

        self.progress = ttk.Progressbar(footer, style="Svc.Horizontal.TProgressbar", mode="determinate", length=240)
        self.progress.pack(side="right", padx=8)
        self.progress_label = tk.Label(
            footer,
            text="",
            bg=theme.PANEL,
            fg=theme.TEXT_DIM,
            font=theme.FONT_BADGE,
        )
        self.progress_label.pack(side="right", padx=(0, 4))

    def _build_log_dock(self) -> None:
        self.log_dock = tk.Frame(self, bg=theme.BG_ALT)
        self.log_dock.pack(side="bottom", fill="x")
        self.console = LogConsole(self.log_dock, height=9)
        self.console.pack(fill="both", expand=True, padx=8, pady=(6, 8))

    # -- page handling -----------------------------------------------------
    def show_page(self, key: str) -> None:
        if key not in self._pages:
            return
        self._current = key
        for nav_key, button in self._nav_buttons.items():
            active = nav_key == key
            bg = theme.PANEL_ALT if active else theme.BG_ALT
            fg = theme.TEXT if active else theme.TEXT_MUTED
            accent = theme.ACCENT if active else bg
            button.configure(bg=bg)
            button._accent.configure(bg=accent)  # type: ignore[attr-defined]
            button._text.configure(bg=bg, fg=fg)  # type: ignore[attr-defined]
        page = self._pages[key]
        page.tkraise()
        if hasattr(page, "on_show"):
            page.on_show()

    # -- shared services for pages ----------------------------------------
    def log(self, message: str, level: str = "INFO") -> None:
        self.console.write(message, level)

    def set_status(self, text: str, kind: str = "idle") -> None:
        colors = {
            "idle": theme.TEXT_MUTED,
            "ok": theme.SUCCESS,
            "busy": theme.INFO,
            "warn": theme.WARNING,
            "error": theme.DANGER,
        }
        self.status_label.configure(text=text, fg=colors.get(kind, theme.TEXT_MUTED))

    def set_progress(self, value: float, total: float = 0, suffix: str = "") -> None:
        if total > 0:
            self.progress.configure(mode="determinate", maximum=total, value=min(value, total))
            self.progress_label.configure(text="%.0f%% %s" % (100.0 * min(value, total) / total, suffix))
        else:
            self.progress.configure(mode="determinate", maximum=100, value=value % 100)
            self.progress_label.configure(text=suffix)

    def clear_progress(self) -> None:
        self.progress.configure(value=0)
        self.progress_label.configure(text="")

    def toggle_log(self) -> None:
        if self._log_visible:
            self.log_dock.pack_forget()
            self.log_toggle.configure(text="Show log")
            self._log_visible = False
        else:
            self.log_dock.pack(side="bottom", fill="x")
            self.log_toggle.configure(text="Hide log")
            self._log_visible = True

    def ask_open(self, title: str, filetypes=None) -> str:
        path = filedialog.askopenfilename(title=title, filetypes=filetypes or [("All files", "*.*")])
        return path or ""

    def ask_save(self, title: str, defaultextension: str = "", filetypes=None) -> str:
        path = filedialog.asksaveasfilename(
            title=title,
            defaultextension=defaultextension,
            filetypes=filetypes or [("All files", "*.*")],
        )
        return path or ""

    def ask_dir(self, title: str) -> str:
        path = filedialog.askdirectory(title=title)
        return path or ""

    def confirm(self, title: str, message: str, *, danger: bool = False) -> bool:
        if danger and not self.controller.settings.confirm_destructive:
            return True
        icon = messagebox.WARNING if danger else messagebox.QUESTION
        return bool(messagebox.askokcancel(title, message, icon=icon))

    # -- device lifecycle --------------------------------------------------
    def connect_device(self) -> None:
        settings = self.controller.settings
        self.controller.connect(
            mode=settings.mode,
            transport=settings.transport,
            loader=settings.loader,
            auth=settings.auth,
            debug=settings.debug_log,
        )

    def disconnect_device(self) -> None:
        self.controller.disconnect()

    def _on_busy(self, busy: bool, text: str) -> None:
        state = "disabled" if busy else "normal"
        self.btn_connect.configure(state=state)
        self.btn_disconnect.configure(state="normal" if self.controller.connected or busy else "disabled")
        if busy:
            self.pill_session.set(text or "Working...", "busy")
            self.set_status(text or "Working...", "busy")
        elif self.controller.connected:
            self.pill_session.set("Session open", "ok")
            self.set_status("Idle — session open", "ok")
        else:
            self.pill_session.set("No session", "idle")
            self.set_status("Ready. No device session.", "idle")
        for page in self._pages.values():
            if hasattr(page, "on_busy"):
                page.on_busy(busy)

    def _on_device(self, device: dict[str, Any]) -> None:
        chip = str(device.get("chip") or "")
        soc = str(device.get("soc") or chip or "MediaTek")
        parts = device.get("parts") or len(self.controller.partitions)
        self.pill_chip.set("%s · %s parts" % (soc, parts), "ok")
        self.pill_session.set("Session open", "ok")
        self.btn_disconnect.configure(state="normal")
        for page in self._pages.values():
            if hasattr(page, "on_device"):
                page.on_device(device)

    def _on_disconnect(self, reason: str) -> None:
        self.pill_chip.set("No device", "idle")
        self.pill_session.set(
            "No session" if reason != "connection failed" else "Failed",
            "error" if reason == "connection failed" else "idle",
        )
        self.btn_disconnect.configure(state="disabled")
        self.set_status("Ready. No device session.", "idle")
        self.clear_progress()
        for page in self._pages.values():
            if hasattr(page, "on_device"):
                page.on_device({})

    def _on_progress(self, value: int, total: int) -> None:
        if total:
            self.set_progress(value, total)
        else:
            megabytes = value / (1024 * 1024)
            self.progress.configure(value=0)
            self.progress_label.configure(text="%.1f MB" % megabytes)

    def _on_partitions_refreshed(self, partitions) -> None:
        if partitions:
            self.log("Partition table refreshed: %d entries." % len(partitions), "OK")
            self.pill_chip.set(
                "%s · %d parts" % (self.controller.device.get("chip", "MediaTek"), len(partitions)), "ok"
            )

    # -- misc --------------------------------------------------------------
    def _ui_call(self, callback: Callable[[], None]) -> None:
        try:
            self.after(0, callback)
        except tk.TclError:
            pass

    def _startup_diagnostics(self) -> None:
        adb = find_adb()
        fastboot = find_fastboot()
        self.env_label.configure(
            text="ADB: %s\nFastboot: %s\nMode: %s"
            % (
                "found" if adb else "missing",
                "found" if fastboot else "missing",
                self.controller.settings.mode.upper(),
            )
        )
        self.log("%s %s ready." % (self.product_name, self.product_version), "OK")
        self.log("No login required — opens directly to the device workspace.", "INFO")
        self.log(self.authorized_use, "WARN")

    def _on_close(self) -> None:
        try:
            settings = self.controller.settings
            settings.window_geometry = self.geometry()
            settings.log_expanded = self._log_visible
            settings.save()
        except Exception:
            pass
        try:
            if self.controller.connected:
                self.controller.disconnect()
        finally:
            self.after(150, self.destroy)
