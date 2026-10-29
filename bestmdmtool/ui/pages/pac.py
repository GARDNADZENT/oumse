"""SPD firmware page: inspect, verify, extract, flash and build PAC packages."""

from __future__ import annotations

import json
import os
import tkinter as tk
from tkinter import ttk
from typing import Any

from .. import theme
from ..widgets import ActionButton, Card, PathRow
from .base import BasePage


class PacPage(BasePage):
    key = "pac"
    heading = "SPD Firmware (PAC)"
    description = "Read a Spreadtrum .pac package, check every partition CRC, flash it, or build a new one."

    def build(self) -> None:
        row = tk.Frame(self.content, bg=theme.BG)
        row.pack(fill="x")
        row.grid_columnconfigure(0, weight=3)
        row.grid_columnconfigure(1, weight=2)

        package = Card(row, "Package")
        package.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        self.pac_row = PathRow(package.body, "PAC file", self._browse_pac)
        self.pac_row.pack(fill="x", pady=(0, 8))

        bar = tk.Frame(package.body, bg=theme.PANEL)
        bar.pack(fill="x", pady=(0, 8))
        ActionButton(bar, "Open and verify", self._open_pac, variant="accent").pack(side="left")
        ActionButton(bar, "Flash package", self._flash_pac, variant="danger").pack(side="left", padx=(8, 0))
        ActionButton(bar, "Extract all", self._extract).pack(side="left", padx=(8, 0))

        self.summary_label = tk.Label(
            package.body,
            text="No package loaded.",
            bg=theme.PANEL,
            fg=theme.TEXT_DIM,
            font=theme.FONT_BADGE,
            justify="left",
            anchor="w",
            wraplength=520,
        )
        self.summary_label.pack(fill="x")

        build = Card(row, "ROM maker")
        build.grid(row=0, column=1, sticky="nsew")
        self.folder_row = PathRow(build.body, "Folder with partition images", self._browse_folder)
        self.folder_row.pack(fill="x", pady=(0, 8))
        tk.Label(
            build.body,
            text="Packs every .bin/.img in the folder into a BP_R2 container,\nwith a CRC per partition.",
            bg=theme.PANEL,
            fg=theme.TEXT_DIM,
            font=theme.FONT_BADGE,
            justify="left",
            anchor="w",
        ).pack(fill="x", pady=(0, 8))
        ActionButton(build.body, "Build .pac", self._build_pac).pack(fill="x")

        table = Card(self.content, "Partitions in the package")
        table.pack(fill="both", expand=True, pady=(10, 0))
        wrapper = tk.Frame(table.body, bg=theme.PANEL)
        wrapper.pack(fill="both", expand=True)
        columns = ("name", "size", "flash", "crc")
        self.tree = ttk.Treeview(wrapper, columns=columns, show="headings", height=10)
        for column, title, width in (
            ("name", "Partition", 200),
            ("size", "Size", 110),
            ("flash", "Flash offset", 130),
            ("crc", "CRC", 90),
        ):
            self.tree.heading(column, text=title)
            self.tree.column(column, width=width, anchor="w")
        scroll = ttk.Scrollbar(wrapper, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

    # -- helpers -----------------------------------------------------------
    def _browse_pac(self) -> str:
        path = self.app.ask_open("Select PAC package", [("PAC firmware", "*.pac"), ("All files", "*.*")])
        if path:
            self.pac_row.set(path)
            self._open_pac()
        return path

    def _browse_folder(self) -> str:
        path = self.app.ask_directory("Select the folder with partition images")
        if path:
            self.folder_row.set(path)
        return path

    def _open_pac(self) -> None:
        path = self.pac_row.get()
        if not path:
            self.app.set_status("Choose a .pac file first.", "warn")
            return
        self.controller.run_command("Reading PAC package", {"op": "pac_open", "path": path}, self._show_package)

    def _show_package(self, result: Any) -> None:
        detail = self._payload(result)
        if not detail:
            return
        entries = detail.get("entries") or []
        self.tree.delete(*self.tree.get_children())
        for entry in entries:
            self.tree.insert(
                "",
                "end",
                values=(
                    entry.get("name", ""),
                    self.format_size(entry.get("size") or 0),
                    "0x%08X" % int(entry.get("address") or 0),
                    "0x%04X" % int(entry.get("checksum") or 0),
                ),
            )
        verified = detail.get("verified")
        problems = detail.get("problems") or []
        text = "%d partition(s), %s. %s" % (
            detail.get("partitions", 0),
            self.format_size(detail.get("total_size") or 0),
            "CRC check passed." if verified else "CRC problems: %s" % "; ".join(problems[:3]),
        )
        self.summary_label.configure(text=text, fg=theme.SUCCESS if verified else theme.DANGER)
        self.log("PAC %s: %s" % (os.path.basename(detail.get("path", "")), text), "OK" if verified else "ERROR")

    def _flash_pac(self) -> None:
        path = self.pac_row.get()
        if not path:
            self.app.set_status("Choose a .pac file first.", "warn")
            return
        if not self.app.confirm(
            "Flash PAC package",
            "Flash every partition of\n%s\n\nto the connected SPD device? This overwrites the device."
            % os.path.basename(path),
            danger=True,
        ):
            return

        def _done(result: Any) -> None:
            detail = self._payload(result)
            if detail:
                written = detail.get("written") or []
                skipped = detail.get("skipped") or []
                self.log("PAC flashed: %d partition(s)" % len(written), "OK")
                for entry in skipped:
                    self.log(
                        "Skipped %s: %s" % (entry.get("partition"), entry.get("reason")),
                        "WARN",
                    )

        self.controller.run_command(
            "Flashing PAC package", {"op": "pac_flash", "path": path, "verify": True}, _done
        )

    def _extract(self) -> None:
        path = self.pac_row.get()
        if not path:
            self.app.set_status("Choose a .pac file first.", "warn")
            return
        target = self.app.ask_directory("Where should the partitions be extracted?")
        if not target:
            return

        def _done(result: Any) -> None:
            if self._ok(result):
                self.log("Extracted package to %s" % target, "OK")

        self.controller.run_command(
            "Extracting PAC package", {"op": "pac_extract", "path": path, "dir": target}, _done
        )

    def _build_pac(self) -> None:
        folder = self.folder_row.get()
        if not folder:
            self.app.set_status("Choose a folder with partition images first.", "warn")
            return
        target = self.app.ask_save("Save new PAC", defaultextension=".pac", initialfile="repacked.pac")
        if not target:
            return

        def _done(result: Any) -> None:
            if self._ok(result):
                self.log("Built %s" % target, "OK")
                self.pac_row.set(target)
                self._open_pac()

        self.controller.run_command(
            "Building PAC package", {"op": "pac_build", "folder": folder, "out": target}, _done
        )

    @staticmethod
    def _ok(result: Any) -> bool:
        return bool(getattr(result, "ok", False))

    def _payload(self, result: Any) -> Any:
        if not self._ok(result):
            self.app.set_status("PAC command failed: %s" % (getattr(result, "detail", "") or "no answer"), "error")
            return {}
        try:
            return json.loads(getattr(result, "detail", "") or "{}")
        except (ValueError, TypeError):
            return {}

    def on_device(self, device: dict[str, Any]) -> None:
        if device and device.get("engine") != "spd":
            self.summary_label.configure(
                text="This page needs an SPD session. Connect a Spreadtrum device in the SPD Toolkit.",
                fg=theme.WARNING,
            )
