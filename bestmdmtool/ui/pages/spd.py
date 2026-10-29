"""SPD Toolkit: Spreadtrum/Unisoc (BSL) partition workspace."""

from __future__ import annotations

import json
import os
import tkinter as tk
from tkinter import ttk
from typing import Any

from servicecore.spd.transport import list_serial_ports

from .. import theme
from ..widgets import ActionButton, Card, StatTile
from .base import BasePage

SPD_FAMILIES = ("auto", "usb", "serial", "simulator")


class SpdPage(BasePage):
    key = "spd"
    heading = "SPD Toolkit"
    description = "Spreadtrum/Unisoc devices over the BSL protocol: partitions, read, write, erase, reboot."

    def build(self) -> None:
        top = tk.Frame(self.content, bg=theme.BG)
        top.pack(fill="x")
        top.grid_columnconfigure(0, weight=3)
        top.grid_columnconfigure(1, weight=2)

        connect = Card(top, "Connection")
        connect.grid(row=0, column=0, sticky="nsew", padx=(0, 8))

        row = tk.Frame(connect.body, bg=theme.PANEL)
        row.pack(fill="x", pady=(0, 8))
        tk.Label(
            row, text="Transport", bg=theme.PANEL, fg=theme.TEXT_MUTED, font=theme.FONT_BADGE
        ).pack(side="left")
        self.transport_var = tk.StringVar(value=self.controller.settings.spd_transport or "auto")
        ttk.Combobox(row, textvariable=self.transport_var, values=list(SPD_FAMILIES), state="readonly", width=12).pack(
            side="left", padx=(8, 16)
        )
        tk.Label(row, text="Port", bg=theme.PANEL, fg=theme.TEXT_MUTED, font=theme.FONT_BADGE).pack(side="left")
        self.port_var = tk.StringVar(value=self.controller.settings.spd_port or "")
        self.port_combo = ttk.Combobox(row, textvariable=self.port_var, values=[], state="normal", width=14)
        self.port_combo.pack(side="left", padx=(8, 8))

        buttons = tk.Frame(connect.body, bg=theme.PANEL)
        buttons.pack(fill="x", pady=(0, 8))
        ActionButton(buttons, "Refresh ports", self._refresh_ports, variant="ghost").pack(side="left")
        ActionButton(buttons, "Connect SPD", self._connect, variant="accent").pack(
            side="left", padx=(8, 0)
        )
        ActionButton(buttons, "Reboot", self._reboot, variant="ghost").pack(side="left", padx=(8, 0))

        tk.Label(
            connect.body,
            text=(
                "Put the phone in download mode (Volume- while plugging in). FDL1/FDL2 loaders are\n"
                "handled by the runner; the partition table comes from the loader, or from a PAC\n"
                "package when the loader does not expose one."
            ),
            bg=theme.PANEL,
            fg=theme.TEXT_DIM,
            font=theme.FONT_BADGE,
            justify="left",
            anchor="w",
        ).pack(fill="x")

        self._refresh_ports()

        info = Card(top, "Device")
        info.grid(row=0, column=1, sticky="nsew")
        tiles = tk.Frame(info.body, bg=theme.PANEL)
        tiles.pack(fill="x")
        self.tiles: dict[str, StatTile] = {}
        for index, (key, label) in enumerate(
            (("chip", "Chipset"), ("version", "Loader"), ("flash", "Flash size"), ("transport", "Transport"))
        ):
            tile = StatTile(tiles, label)
            padx = (0, 0) if index % 2 == 0 else (6, 0)
            tile.grid(row=index // 2, column=index % 2, sticky="nsew", padx=padx, pady=(0, 6))
            tiles.grid_columnconfigure(index % 2, weight=1)
            self.tiles[key] = tile

        table = Card(self.content, "Partitions")
        table.pack(fill="both", expand=True, pady=(10, 0))
        bar = tk.Frame(table.body, bg=theme.PANEL)
        bar.pack(fill="x", pady=(0, 6))
        ActionButton(bar, "Reload table", self._load_partitions, variant="ghost").pack(side="left")
        ActionButton(bar, "Read selected", self._read_selected).pack(side="left", padx=(8, 0))
        ActionButton(bar, "Write selected", self._write_selected).pack(side="left", padx=(8, 0))
        ActionButton(bar, "Erase selected", self._erase_selected, variant="danger").pack(side="left", padx=(8, 0))
        self.source_label = tk.Label(
            bar, text="table source: -", bg=theme.PANEL, fg=theme.TEXT_DIM, font=theme.FONT_BADGE
        )
        self.source_label.pack(side="right")

        wrapper = tk.Frame(table.body, bg=theme.PANEL)
        wrapper.pack(fill="both", expand=True)
        columns = ("name", "offset", "size")
        self.tree = ttk.Treeview(wrapper, columns=columns, show="headings", height=8, selectmode="browse")
        for column, title, width in (("name", "Partition", 220), ("offset", "Offset", 140), ("size", "Size", 140)):
            self.tree.heading(column, text=title)
            self.tree.column(column, width=width, anchor="w")
        scroll = ttk.Scrollbar(wrapper, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

    # -- helpers -----------------------------------------------------------
    def _refresh_ports(self) -> None:
        ports = list_serial_ports()
        self.port_combo.configure(values=ports)
        if not ports:
            self.port_combo.set("")
        elif not self.port_var.get():
            self.port_var.set(ports[0])

    def _connect(self) -> None:
        settings = self.controller.settings
        settings.spd_transport = self.transport_var.get().strip() or "auto"
        settings.spd_port = self.port_var.get().strip()
        settings.engine = "spd"
        settings.save()
        self.app.connect_device()

    def _table(self) -> None:
        self.tree.delete(*self.tree.get_children())
        for entry in self.partitions():
            self.tree.insert(
                "",
                "end",
                values=(
                    entry.get("name", ""),
                    "0x%08X" % int(entry.get("offset") or 0),
                    self.format_size(entry.get("size") or 0),
                ),
            )
        source = self.controller.device.get("partition_source") or "-"
        self.source_label.configure(text="table source: %s" % source)

    def _load_partitions(self) -> None:
        def _done(result: Any) -> None:
            detail = self._payload(result)
            entries = detail.get("partitions") if isinstance(detail, dict) else None
            if entries is not None:
                self.controller.partitions = list(entries)
                self._table()

        self.controller.run_command("Reading SPD partition table", {"op": "partitions"}, _done)

    def _selected(self) -> str:
        selection = self.tree.selection()
        if not selection:
            self.app.set_status("Select a partition in the SPD table first.", "warn")
            return ""
        values = self.tree.item(selection[0], "values")
        return str(values[0]) if values else ""

    def _read_selected(self) -> None:
        name = self._selected()
        if not name:
            return
        target = self.app.ask_save(
            "Save %s" % name, initialfile="%s.bin" % name, defaultextension=".bin"
        )
        if not target:
            return

        def _done(result: Any) -> None:
            if self._ok(result):
                self.log("Read %s -> %s" % (name, target), "OK")

        self.controller.run_command("Reading %s" % name, {"op": "read", "part": name, "out": target}, _done)

    def _write_selected(self) -> None:
        name = self._selected()
        if not name:
            return
        source = self.app.ask_open("Select image for %s" % name, [("Images", "*.bin *.img"), ("All files", "*.*")])
        if not source:
            return
        if not self.app.confirm("Write partition", "Write %s to %s?" % (os.path.basename(source), name), danger=True):
            return

        def _done(result: Any) -> None:
            if self._ok(result):
                self.log("Wrote %s from %s" % (name, os.path.basename(source)), "OK")

        self.controller.run_command("Writing %s" % name, {"op": "write", "part": name, "src": source}, _done)

    def _erase_selected(self) -> None:
        name = self._selected()
        if not name:
            return
        if not self.app.confirm("Erase partition", "Erase %s? This cannot be undone." % name, danger=True):
            return

        def _done(result: Any) -> None:
            if self._ok(result):
                self.log("Erased %s" % name, "OK")

        self.controller.run_command("Erasing %s" % name, {"op": "erase", "parts": [name]}, _done)

    def _reboot(self) -> None:
        if not self.app.confirm("Reboot", "Reboot the SPD device now?"):
            return
        self.controller.run_command("Rebooting SPD device", {"op": "reboot"})

    @staticmethod
    def _ok(result: Any) -> bool:
        return bool(getattr(result, "ok", False))

    def _payload(self, result: Any) -> Any:
        if not self._ok(result):
            detail = getattr(result, "detail", "") or "no answer"
            self.app.set_status("SPD command failed: %s" % detail, "error")
            return {}
        detail = getattr(result, "detail", "") or "{}"
        try:
            return json.loads(detail)
        except (ValueError, TypeError):
            return {}

    # -- updates -----------------------------------------------------------
    def on_device(self, device: dict[str, Any]) -> None:
        if not device:
            for tile in self.tiles.values():
                tile.set("-")
            return
        chip = str(device.get("chip") or "-")
        self.tiles["chip"].set(chip)
        self.tiles["version"].set(str(device.get("version") or "-"))
        flash = device.get("flash_size")
        self.tiles["flash"].set(self.format_size(int(flash)) if flash else "-")
        self.tiles["transport"].set(str(device.get("transport") or "-"))
        if device.get("partitions_source"):
            self.source_label.configure(text="table source: %s" % device["partitions_source"])
        self._table()

    def on_show(self) -> None:
        self._refresh_ports()
        self._table()
