"""Bootloader page: lock state, seccfg operations, fastboot unlock helpers."""

from __future__ import annotations

import tkinter as tk
from typing import Any

from .. import theme
from ..widgets import ActionButton, Card, Pill
from .base import BasePage


class BootloaderPage(BasePage):
    key = "bootloader"
    heading = "Bootloader"
    description = "Read the lock state and flip seccfg on devices you are authorized to service."

    def build(self) -> None:
        row = tk.Frame(self.content, bg=theme.BG)
        row.pack(fill="x")
        row.grid_columnconfigure(0, weight=1)
        row.grid_columnconfigure(1, weight=1)

        state_card = Card(row, "Lock state")
        state_card.grid(row=0, column=0, sticky="nsew", padx=(0, 8))

        self.lock_pill = Pill(state_card.body, "unknown", "idle")
        self.lock_pill.pack(anchor="w", pady=(0, 10))

        self.state_labels: dict[str, tk.Label] = {}
        for key, label in (
            ("flash_locked", "ro.boot.flash.locked"),
            ("secure", "ro.secure"),
            ("debuggable", "ro.debuggable"),
            ("verified", "ro.boot.verifiedbootstate"),
        ):
            line = tk.Frame(state_card.body, bg=theme.PANEL)
            line.pack(fill="x", pady=2)
            tk.Label(
                line,
                text=label,
                bg=theme.PANEL,
                fg=theme.TEXT_MUTED,
                font=theme.FONT_UI_SMALL,
                width=24,
                anchor="w",
            ).pack(side="left")
            value = tk.Label(line, text="—", bg=theme.PANEL, fg=theme.TEXT, font=theme.FONT_MONO, anchor="w")
            value.pack(side="left")
            self.state_labels[key] = value

        ActionButton(state_card.body, "Check ADB lock state", self._check_state).pack(fill="x", pady=(10, 0))

        action_card = Card(row, "Seccfg operations (BROM)")
        action_card.grid(row=0, column=1, sticky="nsew")
        tk.Label(
            action_card.body,
            text="These write the seccfg partition through the open DA session.\n"
            "Unlocking wipes userdata on most MTK devices.",
            bg=theme.PANEL,
            fg=theme.TEXT_MUTED,
            font=theme.FONT_UI_SMALL,
            justify="left",
            anchor="w",
        ).pack(fill="x", pady=(0, 10))
        ActionButton(action_card.body, "Unlock bootloader", lambda: self._seccfg("unlock"), variant="warning").pack(
            fill="x", pady=(0, 8)
        )
        ActionButton(action_card.body, "Re-lock bootloader", lambda: self._seccfg("lock"), variant="ghost").pack(
            fill="x"
        )

        fastboot_card = Card(self.content, "Fastboot helpers")
        fastboot_card.pack(fill="both", expand=True, pady=(10, 0))
        buttons = tk.Frame(fastboot_card.body, bg=theme.PANEL)
        buttons.pack(fill="x")
        ActionButton(buttons, "Reboot to bootloader", lambda: self._adb_reboot("bootloader")).pack(
            side="left", padx=(0, 6)
        )
        ActionButton(buttons, "fastboot devices", self._fastboot_devices, variant="ghost").pack(
            side="left", padx=(0, 6)
        )
        ActionButton(buttons, "getvar unlocked", self._fastboot_getvar, variant="ghost").pack(side="left", padx=(0, 6))
        ActionButton(buttons, "Reboot system", lambda: self._fastboot_reboot(), variant="ghost").pack(side="left")

        self.output = tk.Text(
            fastboot_card.body,
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
        self.output.pack(fill="both", expand=True, pady=(10, 0))
        self.output.configure(state="disabled")

    # -- helpers -----------------------------------------------------------
    def _write(self, text: str) -> None:
        self.output.configure(state="normal")
        self.output.delete("1.0", "end")
        self.output.insert("1.0", text or "(no output)")
        self.output.configure(state="disabled")

    def _adb_reboot(self, target: str) -> None:
        def _work():
            return self.controller.adb.reboot(target)

        def _done(result) -> None:
            self.log(
                "adb reboot %s: %s" % (target, getattr(result, "text", "")),
                "OK" if getattr(result, "ok", False) else "ERROR",
            )

        self.controller.run_async("Rebooting to %s" % target, _work, _done)

    def _fastboot_devices(self) -> None:
        def _work():
            return self.controller.fastboot.run("devices")

        self.controller.run_async(
            "Listing fastboot devices",
            _work,
            lambda result: self._write(getattr(result, "text", "")),
        )

    def _fastboot_getvar(self) -> None:
        def _work():
            return self.controller.fastboot.run("getvar", "unlocked")

        self.controller.run_async(
            "Reading fastboot variables",
            _work,
            lambda result: self._write(getattr(result, "text", "")),
        )

    def _fastboot_reboot(self) -> None:
        def _work():
            return self.controller.fastboot.reboot()

        self.controller.run_async("Fastboot reboot", _work, lambda _r: None)

    def _check_state(self) -> None:
        def _work():
            return self.controller.adb.props(
                ("ro.boot.flash.locked", "ro.secure", "ro.debuggable", "ro.boot.verifiedbootstate")
            )

        def _done(values: Any) -> None:
            values = values or {}
            for key, label in self.state_labels.items():
                prop = {
                    "flash_locked": "ro.boot.flash.locked",
                    "secure": "ro.secure",
                    "debuggable": "ro.debuggable",
                    "verified": "ro.boot.verifiedbootstate",
                }[key]
                label.configure(text=str(values.get(prop) or "—"))
            locked = str(values.get("ro.boot.flash.locked", "")).strip()
            if locked == "1":
                self.lock_pill.set("locked", "warn")
            elif locked == "0":
                self.lock_pill.set("unlocked", "ok")
            else:
                self.lock_pill.set("unknown", "idle")

        self.controller.run_async("Checking bootloader state", _work, _done)

    def _seccfg(self, state: str) -> None:
        session = self.require_session()
        if session is None:
            return
        if not self.app.confirm(
            "Seccfg %s" % state,
            "%s the bootloader?\n\nThis writes the seccfg partition and can wipe userdata." % state.capitalize(),
            danger=True,
        ):
            return
        self.log("Requesting seccfg %s" % state, "STEP")
        self.controller.run_async(
            "Seccfg %s" % state,
            lambda: session.seccfg(state),
            lambda result: self.log(
                "Seccfg %s %s"
                % (state, "complete" if getattr(result, "ok", False) else "failed: %s" % getattr(result, "detail", "")),
                "OK" if getattr(result, "ok", False) else "ERROR",
            ),
        )
