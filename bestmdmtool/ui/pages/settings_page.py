"""Settings page: connection parameters and application preferences."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Any

from servicecore.adb import find_adb, find_fastboot
from servicecore.config import python_executable, service_runner_path

from ... import applog
from .. import theme
from ..widgets import ActionButton, Card, PathRow
from .base import BasePage


class SettingsPage(BasePage):
    key = "settings"
    heading = "Settings"
    description = "Connection parameters are applied the next time you connect."

    def build(self) -> None:
        row = tk.Frame(self.content, bg=theme.BG)
        row.pack(fill="x")
        row.grid_columnconfigure(0, weight=1)
        row.grid_columnconfigure(1, weight=1)

        conn = Card(row, "Connection")
        conn.grid(row=0, column=0, sticky="nsew", padx=(0, 8))

        self.engine_var = tk.StringVar(value=getattr(self.controller.settings, "engine", "mtk"))
        self.spd_transport_var = tk.StringVar(value=getattr(self.controller.settings, "spd_transport", "auto"))
        self.spd_port_var = tk.StringVar(value=getattr(self.controller.settings, "spd_port", ""))

        self._combo(conn.body, "Chip family", self.engine_var, ("mtk", "spd"))
        self._combo(conn.body, "SPD transport", self.spd_transport_var, ("auto", "usb", "serial", "simulator"))

        self.mode_var = tk.StringVar(value=self.controller.settings.mode)
        self.transport_var = tk.StringVar(value=self.controller.settings.transport)
        self.debug_var = tk.BooleanVar(value=self.controller.settings.debug_log)
        self.confirm_var = tk.BooleanVar(value=self.controller.settings.confirm_destructive)

        self._combo(conn.body, "Session mode", self.mode_var, ("brom", "preloader"))
        self._combo(conn.body, "Transport", self.transport_var, ("auto", "serial", "com3", "com4", "com5"))

        self.loader_row = PathRow(conn.body, "Custom DA loader (.bin)", self._browse_loader)
        self.loader_row.pack(fill="x", pady=(8, 8))
        self.loader_row.set(self.controller.settings.loader)

        self.auth_row = PathRow(conn.body, "Auth file (.auth)", self._browse_auth)
        self.auth_row.pack(fill="x", pady=(0, 8))
        self.auth_row.set(self.controller.settings.auth)

        tk.Checkbutton(
            conn.body,
            text="Verbose (debug) logging",
            variable=self.debug_var,
            bg=theme.PANEL,
            fg=theme.TEXT_MUTED,
            activebackground=theme.PANEL,
            activeforeground=theme.TEXT,
            selectcolor=theme.PANEL_ALT,
            font=theme.FONT_UI_SMALL,
            bd=0,
            highlightthickness=0,
        ).pack(anchor="w")

        behaviour = Card(row, "Behaviour")
        behaviour.grid(row=0, column=1, sticky="nsew")
        tk.Checkbutton(
            behaviour.body,
            text="Ask before destructive operations",
            variable=self.confirm_var,
            bg=theme.PANEL,
            fg=theme.TEXT_MUTED,
            activebackground=theme.PANEL,
            activeforeground=theme.TEXT,
            selectcolor=theme.PANEL_ALT,
            font=theme.FONT_UI_SMALL,
            bd=0,
            highlightthickness=0,
        ).pack(anchor="w", pady=(0, 12))

        ActionButton(behaviour.body, "Save settings", self._save, variant="accent").pack(fill="x", pady=(0, 6))
        ActionButton(behaviour.body, "Save and reconnect", self._save_and_reconnect).pack(fill="x", pady=(0, 6))
        ActionButton(
            behaviour.body, "Run backend self-test", self._run_selftest, variant="accent"
        ).pack(fill="x", pady=(0, 6))
        self.selftest_label = tk.Label(
            behaviour.body,
            text="Checks the runner, mtkclient, libusb and the DA loaders.",
            bg=theme.PANEL,
            fg=theme.TEXT_DIM,
            font=theme.FONT_UI_SMALL,
            anchor="w",
            justify="left",
            wraplength=260,
        )
        self.selftest_label.pack(fill="x", pady=(0, 10))
        ActionButton(behaviour.body, "Report tool paths", self.controller.report_tools, variant="ghost").pack(
            fill="x", pady=(0, 6)
        )
        ActionButton(behaviour.body, "Open log folder", self._open_logs, variant="ghost").pack(fill="x", pady=(0, 6))
        ActionButton(behaviour.body, "Export support bundle", self._export_bundle, variant="ghost").pack(
            fill="x", pady=(0, 6)
        )
        ActionButton(behaviour.body, "Reset to defaults", self._reset, variant="ghost").pack(fill="x")

        paths = Card(self.content, "Paths")
        paths.pack(fill="both", expand=True, pady=(10, 0))
        self.paths_text = tk.Text(
            paths.body,
            height=8,
            bg=theme.BG_ALT,
            fg=theme.TEXT,
            insertbackground=theme.TEXT,
            font=theme.FONT_MONO,
            relief="flat",
            bd=0,
            padx=10,
            pady=8,
            wrap="none",
        )
        self.paths_text.pack(fill="both", expand=True)
        self._refresh_paths()

    def _combo(self, master: tk.Misc, label: str, variable: tk.StringVar, values: tuple[str, ...]) -> None:
        wrapper = tk.Frame(master, bg=theme.PANEL)
        wrapper.pack(fill="x", pady=(0, 8))
        tk.Label(
            wrapper,
            text=label,
            bg=theme.PANEL,
            fg=theme.TEXT_MUTED,
            font=theme.FONT_BADGE,
            anchor="w",
        ).pack(fill="x")
        combo = ttk.Combobox(wrapper, textvariable=variable, values=list(values), state="normal")
        combo.pack(fill="x", pady=(3, 0), ipady=3)

    def _refresh_paths(self) -> None:
        adb = find_adb()
        fastboot = find_fastboot()
        from servicecore.config import frozen_runner_path

        frozen = frozen_runner_path()
        lines = [
            "Python      : %s" % python_executable(),
            "Runner      : %s" % (frozen if frozen is not None else service_runner_path()),
            "Runner mode : %s" % ("frozen executable" if frozen is not None else "source script"),
            "Chip family : %s" % (getattr(self.controller.settings, "engine", "mtk") or "mtk"),
            "ADB         : %s" % (adb or "not found"),
            "Fastboot    : %s" % (fastboot or "not found"),
            "Settings    : %s" % self.controller.settings.path(),
            "Activity log: %s" % applog.log_path(),
        ]
        self.paths_text.configure(state="normal")
        self.paths_text.delete("1.0", "end")
        self.paths_text.insert("1.0", "\n".join(lines))
        self.paths_text.configure(state="disabled")

    def _run_selftest(self) -> None:
        self.selftest_label.configure(text="Running backend self-test...", fg=theme.TEXT_MUTED)

        def _done(report: dict[str, Any]) -> None:
            if report.get("ok"):
                self.selftest_label.configure(text="Backend OK - ready to connect a device.", fg=theme.SUCCESS)
            else:
                from servicecore import selfcheck

                reason = selfcheck.describe_failure(report)
                self.selftest_label.configure(text="Failed: %s" % reason[:160], fg=theme.DANGER)

        self.controller.run_backend_selftest(_done)

    def _export_bundle(self) -> None:
        self.app.set_status("Collecting logs and a backend self-test...", "busy")

        def _done(path) -> None:
            self.app.set_status("Support bundle: %s" % path, "ok")

        self.controller.export_support_bundle(_done)

    def _open_logs(self) -> None:
        try:
            applog.open_log_folder()
            self.app.set_status("Opened the log folder.", "ok")
        except Exception as exc:
            self.app.set_status("Could not open the log folder: %s" % exc, "warn")

    def _browse_loader(self) -> str:
        path = self.app.ask_open("Select DA loader", [("Loader", "*.bin"), ("All files", "*.*")])
        if path:
            self.loader_row.set(path)
        return path

    def _browse_auth(self) -> str:
        path = self.app.ask_open("Select auth file", [("Auth", "*.auth"), ("All files", "*.*")])
        if path:
            self.auth_row.set(path)
        return path

    def _save(self) -> None:
        settings = self.controller.settings
        settings.engine = self.engine_var.get().strip() or "mtk"
        settings.spd_transport = self.spd_transport_var.get().strip() or "auto"
        settings.spd_port = self.spd_port_var.get().strip()
        settings.mode = self.mode_var.get().strip() or "brom"
        settings.transport = self.transport_var.get().strip() or "auto"
        settings.loader = self.loader_row.get()
        settings.auth = self.auth_row.get()
        settings.debug_log = bool(self.debug_var.get())
        settings.confirm_destructive = bool(self.confirm_var.get())
        settings.save()
        self.log("Settings saved.", "OK")
        self.app.set_status("Settings saved.", "ok")
        self._refresh_paths()

    def _save_and_reconnect(self) -> None:
        self._save()
        if self.controller.connected:
            self.controller.disconnect()
            self.app.after(1200, self.app.connect_device)
        else:
            self.app.connect_device()

    def _reset(self) -> None:
        from ...settings import Settings

        defaults = Settings()
        self.engine_var.set(defaults.engine)
        self.spd_transport_var.set(defaults.spd_transport)
        self.spd_port_var.set(defaults.spd_port)
        self.mode_var.set(defaults.mode)
        self.transport_var.set(defaults.transport)
        self.loader_row.set("")
        self.auth_row.set("")
        self.debug_var.set(defaults.debug_log)
        self.confirm_var.set(defaults.confirm_destructive)
        self.log("Settings reset to defaults (not yet saved).", "WARN")

    def on_device(self, device: dict[str, Any]) -> None:
        self._refresh_paths()
