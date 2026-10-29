"""DIAG page: AT console for Spreadtrum/Unisoc devices in normal (not download) mode."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Any

from servicecore.spd.diag import PRESETS, AtConsole, DiagError
from servicecore.spd.transport import list_serial_ports

from .. import theme
from ..widgets import ActionButton, Card
from .base import BasePage


class DiagPage(BasePage):
    key = "diag"
    heading = "SPD DIAG"
    description = (
        "AT / DIAG console over the device's serial port (useful once the phone boots normally). "
        "Read model, firmware, IMEI, SIM and network state on a bench device."
    )

    def build(self) -> None:
        controls = Card(self.content, "Port")
        controls.pack(fill="x")

        row = tk.Frame(controls.body, bg=theme.PANEL)
        row.pack(fill="x", pady=(0, 8))
        tk.Label(row, text="Serial port", bg=theme.PANEL, fg=theme.TEXT_MUTED, font=theme.FONT_BADGE).pack(side="left")
        self.port_var = tk.StringVar()
        self.port_combo = ttk.Combobox(row, textvariable=self.port_var, values=[], width=16)
        self.port_combo.pack(side="left", padx=(8, 12))
        ActionButton(row, "Refresh", self._refresh_ports, variant="ghost").pack(side="left")
        ActionButton(row, "Open port", self._open, variant="accent").pack(side="left", padx=(8, 0))
        ActionButton(row, "Close", self._close, variant="ghost").pack(side="left", padx=(8, 0))
        ActionButton(row, "Identify device", self._identify).pack(side="left", padx=(8, 0))
        self.state_label = tk.Label(row, text="port closed", bg=theme.PANEL, fg=theme.TEXT_DIM, font=theme.FONT_BADGE)
        self.state_label.pack(side="right")

        console = Card(self.content, "Console")
        console.pack(fill="both", expand=True, pady=(10, 0))

        entry_row = tk.Frame(console.body, bg=theme.PANEL)
        entry_row.pack(fill="x", pady=(0, 8))
        self.command_var = tk.StringVar(value="ATI")
        ttk.Entry(entry_row, textvariable=self.command_var).pack(side="left", fill="x", expand=True)
        ttk.Combobox(
            entry_row,
            values=[command for command, _label in PRESETS],
            state="readonly",
            width=16,
        ).pack(side="left", padx=(8, 0))
        ActionButton(entry_row, "Send", self._send, variant="accent").pack(side="left", padx=(8, 0))

        presets = tk.Frame(console.body, bg=theme.PANEL)
        presets.pack(fill="x", pady=(0, 8))
        for command, _description in PRESETS[:6]:
            ActionButton(
                presets,
                command,
                lambda cmd=command: self._quick(cmd),
                variant="ghost",
                font=theme.FONT_BADGE,
            ).pack(side="left", padx=(0, 6))
        tk.Label(
            presets,
            text="   ".join("%s=%s" % (c, d) for c, d in PRESETS[6:]),
            bg=theme.PANEL,
            fg=theme.TEXT_DIM,
            font=theme.FONT_BADGE,
        ).pack(side="left", padx=(8, 0))

        self.output = tk.Text(
            console.body,
            height=12,
            bg=theme.BG_ALT,
            fg=theme.TEXT,
            insertbackground=theme.TEXT,
            font=theme.FONT_MONO,
            relief="flat",
            bd=0,
            padx=10,
            pady=8,
            wrap="word",
        )
        self.output.pack(fill="both", expand=True)
        self.output.configure(state="disabled")
        self.console: AtConsole | None = None
        self._refresh_ports()

    # -- port handling -----------------------------------------------------
    def _refresh_ports(self) -> None:
        ports = list_serial_ports()
        self.port_combo.configure(values=ports)
        if ports and not self.port_var.get():
            self.port_var.set(ports[0])

    def _open(self) -> None:
        port = self.port_var.get().strip()
        if not port:
            self.app.set_status("Choose a serial port first.", "warn")
            return
        try:
            self.console = AtConsole.open(port, log=self.log)
        except DiagError as exc:
            self._write("ERROR: %s" % exc)
            self.app.set_status(str(exc), "error")
            return
        self.state_label.configure(text="%s open" % port, fg=theme.SUCCESS)
        self._write("Opened %s" % port)

    def _close(self) -> None:
        if self.console is not None:
            self.console.close()
            self.console = None
        self.state_label.configure(text="port closed", fg=theme.TEXT_DIM)
        self._write("Port closed")

    def _ensure_open(self) -> bool:
        if self.console is not None:
            return True
        self._open()
        return self.console is not None

    # -- commands ----------------------------------------------------------
    def _quick(self, command: str) -> None:
        self.command_var.set(command)
        self._send()

    def _send(self) -> None:
        command = self.command_var.get().strip()
        if not command or not self._ensure_open():
            return
        console = self.console

        def _work() -> Any:
            assert console is not None
            return console.send(command)

        def _done(result: Any) -> None:
            if result is None:
                return
            self._write("> %s" % result.command)
            self._write(result.text)
            self.app.set_status(
                "%s answered in %.2fs" % (result.command, result.duration), "ok" if result.ok else "warn"
            )

        self.controller.run_async("AT %s" % command, _work, _done)

    def _identify(self) -> None:
        if not self._ensure_open():
            return
        console = self.console

        def _work() -> Any:
            assert console is not None
            return console.identify()

        def _done(result: Any) -> None:
            values = result or {}
            if not values:
                self._write("(no identity data - is the phone booted normally?)")
                return
            for key, value in values.items():
                self._write("%-12s %s" % (key + ":", value))
            self.log("DIAG identity: %s" % ", ".join("%s=%s" % item for item in values.items()), "OK")

        self.controller.run_async("Reading device identity", _work, _done)

    # -- output ------------------------------------------------------------
    def _write(self, text: str) -> None:
        self.output.configure(state="normal")
        self.output.insert("end", "%s\n" % text)
        self.output.see("end")
        self.output.configure(state="disabled")

    def on_show(self) -> None:
        self._refresh_ports()

    def on_busy(self, busy: bool) -> None:
        return None
