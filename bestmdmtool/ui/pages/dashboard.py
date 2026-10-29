"""Dashboard: device summary and quick actions."""

from __future__ import annotations

import tkinter as tk
from typing import Any

from .. import theme
from ..widgets import ActionButton, Card, StatTile
from .base import BasePage


class DashboardPage(BasePage):
    key = "dashboard"
    heading = "Device Workspace"
    description = "Live MediaTek session summary. Connect a device to fill in the details."

    def build(self) -> None:
        tiles = tk.Frame(self.content, bg=theme.BG)
        tiles.pack(fill="x")
        self.tiles: dict[str, StatTile] = {}
        specs = (
            ("chip", "Chipset"),
            ("hwcode", "Hardware code"),
            ("storage", "Storage"),
            ("partitions", "Partitions"),
            ("mode", "Session mode"),
            ("adb", "ADB state"),
        )
        for index, (key, label) in enumerate(specs):
            tile = StatTile(tiles, label)
            tile.grid(
                row=index // 3, column=index % 3, sticky="nsew", padx=(0 if index % 3 == 0 else 8, 0), pady=(0, 8)
            )
            tiles.grid_columnconfigure(index % 3, weight=1)
            self.tiles[key] = tile

        row = tk.Frame(self.content, bg=theme.BG)
        row.pack(fill="both", expand=True, pady=(6, 0))
        row.grid_columnconfigure(0, weight=3)
        row.grid_columnconfigure(1, weight=2)
        row.grid_rowconfigure(0, weight=1)

        details = Card(row, "Session details")
        details.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        self.detail_labels: dict[str, tk.Label] = {}
        for index, (key, label) in enumerate(
            (
                ("chip", "Chipset"),
                ("hwcode", "Hardware code"),
                ("storage", "Storage type"),
                ("pagesize", "Sector size"),
                ("parts", "GPT entries"),
                ("runner", "Runner"),
                ("adb", "ADB"),
                ("fastboot", "Fastboot"),
            )
        ):
            tk.Label(
                details.body,
                text=label,
                bg=theme.PANEL,
                fg=theme.TEXT_MUTED,
                font=theme.FONT_UI_SMALL,
                anchor="w",
            ).grid(row=index, column=0, sticky="w", pady=3)
            value = tk.Label(
                details.body,
                text="—",
                bg=theme.PANEL,
                fg=theme.TEXT,
                font=theme.FONT_UI_SMALL,
                anchor="w",
            )
            value.grid(row=index, column=1, sticky="w", padx=(18, 0), pady=3)
            self.detail_labels[key] = value
        details.body.grid_columnconfigure(1, weight=1)

        actions = Card(row, "Quick actions")
        actions.grid(row=0, column=1, sticky="nsew")

        ActionButton(actions.body, "Connect device", self.app.connect_device, variant="accent").pack(
            fill="x", pady=(0, 6)
        )
        ActionButton(actions.body, "Refresh partition table", self._refresh).pack(fill="x", pady=(0, 6))
        ActionButton(actions.body, "Open partition manager", lambda: self.app.show_page("partitions")).pack(
            fill="x", pady=(0, 6)
        )
        ActionButton(actions.body, "Reboot to system", self._reboot).pack(fill="x", pady=(0, 6))
        ActionButton(actions.body, "Run diagnostics", self._diagnostics, variant="ghost").pack(fill="x")

        tk.Label(
            actions.body,
            text="Read-only until you confirm an operation.\nDestructive actions always ask first.",
            bg=theme.PANEL,
            fg=theme.TEXT_DIM,
            font=theme.FONT_BADGE,
            justify="left",
            anchor="w",
        ).pack(fill="x", pady=(10, 0))

    # -- actions -----------------------------------------------------------
    def _refresh(self) -> None:
        if self.require_session():
            self.controller.refresh_partitions(self._after_refresh)

    def _after_refresh(self, partitions) -> None:
        self.tiles["partitions"].set(str(len(partitions or [])))

    def _reboot(self) -> None:
        session = self.require_session()
        if session is None:
            return
        if not self.app.confirm("Reboot", "Reboot the device to system now?", danger=True):
            return
        self.controller.run_async("Rebooting device", lambda: session.reboot(0))

    def _diagnostics(self) -> None:
        self.controller.report_tools()

    # -- updates -----------------------------------------------------------
    def on_device(self, device: dict[str, Any]) -> None:
        if not device:
            for tile in self.tiles.values():
                tile.set("—")
            for label in self.detail_labels.values():
                label.configure(text="—")
            return
        chip = str(device.get("chip") or "MediaTek")
        hwcode = str(device.get("hwcode") or "—")
        storage = str(device.get("storage") or "—")
        parts = str(device.get("parts") or len(self.partitions()) or "—")
        self.tiles["chip"].set(chip)
        self.tiles["hwcode"].set(hwcode)
        self.tiles["storage"].set(storage)
        self.tiles["partitions"].set(parts)
        self.tiles["mode"].set(self.controller.settings.mode.upper(), theme.INFO)
        adb_state = self.controller.adb.state()
        self.tiles["adb"].set(adb_state or "not detected", theme.SUCCESS if adb_state == "device" else theme.TEXT_MUTED)

        self.detail_labels["chip"].configure(text=chip)
        self.detail_labels["hwcode"].configure(text=hwcode)
        self.detail_labels["storage"].configure(text=storage)
        self.detail_labels["pagesize"].configure(text=str(device.get("pagesize") or "—"))
        self.detail_labels["parts"].configure(text=parts)
        self.detail_labels["runner"].configure(text="service_runner.py")
        self.detail_labels["adb"].configure(text=adb_state or "not detected")
        self.detail_labels["fastboot"].configure(text="available" if self.controller.fastboot.available else "missing")
