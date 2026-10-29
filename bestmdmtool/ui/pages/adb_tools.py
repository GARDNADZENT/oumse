"""ADB and Fastboot workspace."""

from __future__ import annotations

import os
import tkinter as tk
from tkinter import ttk
from typing import Any

from .. import theme
from ..widgets import ActionButton, Card, LabeledEntry, Pill
from .base import BasePage


class AdbPage(BasePage):
    key = "adb"
    heading = "ADB & Fastboot"
    description = "Use the bundled platform tools for device-side servicing tasks."

    def build(self) -> None:
        top = tk.Frame(self.content, bg=theme.BG)
        top.pack(fill="x")
        top.grid_columnconfigure(0, weight=3)
        top.grid_columnconfigure(1, weight=2)

        device_card = Card(top, "Attached devices")
        device_card.grid(row=0, column=0, sticky="nsew", padx=(0, 8))

        bar = tk.Frame(device_card.body, bg=theme.PANEL)
        bar.pack(fill="x", pady=(0, 8))
        ActionButton(bar, "Rescan", self._rescan, variant="accent").pack(side="left")
        self.adb_pill = Pill(bar, "adb: unknown", "idle")
        self.adb_pill.pack(side="left", padx=10)
        self.fastboot_pill = Pill(bar, "fastboot: unknown", "idle")
        self.fastboot_pill.pack(side="left")

        self.serial_var = tk.StringVar()
        self.serial_combo = ttk.Combobox(device_card.body, textvariable=self.serial_var, values=[], state="readonly")
        self.serial_combo.pack(fill="x", pady=(0, 8))

        reboot_bar = tk.Frame(device_card.body, bg=theme.PANEL)
        reboot_bar.pack(fill="x")
        for label, target in (
            ("System", ""),
            ("Bootloader", "bootloader"),
            ("Recovery", "recovery"),
            ("Fastbootd", "fastboot"),
        ):
            ActionButton(reboot_bar, label, lambda t=target: self._reboot(t), variant="ghost").pack(
                side="left", padx=(0, 6)
            )

        tools_card = Card(top, "Device tools")
        tools_card.grid(row=0, column=1, sticky="nsew")
        ActionButton(tools_card.body, "Install APK", self._install_apk).pack(fill="x", pady=(0, 6))
        ActionButton(tools_card.body, "Push file", self._push).pack(fill="x", pady=(0, 6))
        ActionButton(tools_card.body, "Pull file", self._pull).pack(fill="x", pady=(0, 6))
        ActionButton(tools_card.body, "Install ADB helper APK", self._enable_adb, variant="ghost").pack(fill="x")

        shell_card = Card(self.content, "Shell command")
        shell_card.pack(fill="x", pady=(10, 0))
        shell_row = tk.Frame(shell_card.body, bg=theme.PANEL)
        shell_row.pack(fill="x")
        self.shell_entry = LabeledEntry(shell_row, "adb shell", width=60, initial="getprop ro.product.model")
        self.shell_entry.pack(side="left", fill="x", expand=True)
        ActionButton(shell_row, "Run", self._run_shell, variant="accent").pack(side="left", padx=(8, 0), pady=(14, 0))

        output_card = Card(self.content, "Output")
        output_card.pack(fill="both", expand=True, pady=(10, 0))
        self.output = tk.Text(
            output_card.body,
            height=9,
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
        self.output.pack(fill="both", expand=True)
        self.output.configure(state="disabled")

    # -- helpers -----------------------------------------------------------
    def on_show(self) -> None:
        self._rescan()

    def _show(self, text: str) -> None:
        self.output.configure(state="normal")
        self.output.delete("1.0", "end")
        self.output.insert("1.0", text or "(no output)")
        self.output.configure(state="disabled")

    def _tool(self):
        serial = self.serial_var.get().strip()
        if serial:
            self.controller.adb.serial = serial
            self.controller.fastboot.serial = serial
        return self.controller.adb

    def _rescan(self) -> None:
        def _work():
            return self.controller.adb.devices(), self.controller.fastboot.devices()

        def _done(result: Any) -> None:
            adb_devices, fastboot_devices = result if result else ([], [])
            serials = [serial for serial, _state in adb_devices]
            self.serial_combo.configure(values=serials)
            if serials and self.serial_var.get() not in serials:
                self.serial_var.set(serials[0])
            self.adb_pill.set(
                "adb: %d device(s)" % len(adb_devices) if adb_devices else "adb: no device",
                "ok" if adb_devices else "warn",
            )
            self.fastboot_pill.set(
                "fastboot: %d" % len(fastboot_devices) if fastboot_devices else "fastboot: no device",
                "ok" if fastboot_devices else "warn",
            )
            lines = ["ADB:"]
            lines += ["  %s  %s" % (serial, state) for serial, state in adb_devices] or ["  (none)"]
            lines += ["", "Fastboot:"]
            lines += ["  %s" % serial for serial in fastboot_devices] or ["  (none)"]
            self._show("\n".join(lines))

        self.controller.run_async("Scanning for devices", _work, _done)

    def _reboot(self, target: str) -> None:
        def _work():
            return self._tool().reboot(target)

        self.controller.run_async(
            "Rebooting device",
            _work,
            lambda result: self.log(
                "adb reboot %s" % (target or "system"), "OK" if getattr(result, "ok", False) else "ERROR"
            ),
        )

    def _run_shell(self) -> None:
        command = self.shell_entry.get()
        if not command:
            return
        args = command.split()

        def _work():
            return self._tool().shell(*args)

        self.controller.run_async(
            "Running shell command", _work, lambda result: self._show(getattr(result, "text", ""))
        )

    def _install_apk(self) -> None:
        path = self.app.ask_open("Select APK", [("Android package", "*.apk"), ("All files", "*.*")])
        if not path:
            return

        def _work():
            return self._tool().install(path)

        self.controller.run_async("Installing APK", _work, lambda result: self._show(getattr(result, "text", "")))

    def _enable_adb(self) -> None:
        apk = os.path.join("adb_assets", "OumseResConfig.apk")

        def _work():
            return self._tool().enable_adb(apk)

        self.controller.run_async(
            "Installing helper APK", _work, lambda result: self._show(getattr(result, "text", ""))
        )

    def _push(self) -> None:
        local = self.app.ask_open("Select local file", [("All files", "*.*")])
        if not local:
            return
        remote = "/sdcard/" + os.path.basename(local)

        def _work():
            return self._tool().push(local, remote)

        self.controller.run_async("Pushing file", _work, lambda result: self._show(getattr(result, "text", "")))

    def _pull(self) -> None:
        remote = self.shell_entry.get().strip() or "/sdcard/"
        target = self.app.ask_save("Save pulled file", filetypes=[("All files", "*.*")])
        if not target:
            return

        def _work():
            return self._tool().pull(remote, target)

        self.controller.run_async("Pulling file", _work, lambda result: self._show(getattr(result, "text", "")))
