"""Minimal MTK BootROM partition-reader interface.

USB discovery here is passive. Device sessions and partition reads remain
blocked until the MTK backend has passed an independent security review.
"""

from __future__ import annotations

import threading
import tkinter as tk
from tkinter import ttk
from typing import Any

from servicecore.chipsets import scan_report

from . import theme
from .widgets import ActionButton, Card


class PartitionReaderWindow(tk.Tk):
    """Single-screen, read-only MTK BootROM workspace."""

    def __init__(
        self,
        *,
        product_name: str,
        product_title: str,
        product_version: str,
        product_subtitle: str,
        authorized_use: str,
        build_ui: bool = True,
    ) -> None:
        super().__init__()
        self.product_name = product_name
        self.product_version = product_version
        self.product_subtitle = product_subtitle
        self.authorized_use = authorized_use
        self.title(product_title)
        self.configure(bg=theme.BG)
        self.geometry("980x700")
        self.minsize(820, 600)
        theme.configure_theme(self)

        self._scan_lock = threading.Lock()
        self._scan_in_progress = False
        self.last_scan: dict[str, Any] = {}

        if build_ui:
            self._build_ui()

    def _build_ui(self) -> None:
        """Build the only screen: passive BROM detection and read-only table."""
        shell = tk.Frame(self, bg=theme.BG)
        shell.pack(fill="both", expand=True, padx=18, pady=16)

        header = tk.Frame(shell, bg=theme.PANEL, highlightbackground=theme.BORDER, highlightthickness=1)
        header.pack(fill="x", pady=(0, 12))
        brand = tk.Frame(header, bg=theme.PANEL)
        brand.pack(side="left", fill="x", expand=True, padx=18, pady=14)
        title_row = tk.Frame(brand, bg=theme.PANEL)
        title_row.pack(anchor="w")
        tk.Label(title_row, text="●", bg=theme.PANEL, fg=theme.ACCENT, font=("Segoe UI", 15)).pack(
            side="left", padx=(0, 9)
        )
        tk.Label(
            title_row,
            text=self.product_name,
            bg=theme.PANEL,
            fg=theme.TEXT,
            font=theme.FONT_TITLE,
        ).pack(side="left")
        tk.Label(
            title_row,
            text=self.product_version,
            bg=theme.PANEL_ALT,
            fg=theme.TEXT_MUTED,
            font=theme.FONT_BADGE,
            padx=7,
            pady=3,
        ).pack(side="left", padx=(10, 0))
        tk.Label(
            brand,
            text=self.product_subtitle,
            bg=theme.PANEL,
            fg=theme.TEXT_DIM,
            font=theme.FONT_BADGE,
            anchor="w",
        ).pack(anchor="w", pady=(4, 0))
        tk.Label(
            header,
            text="LOCAL SESSION  ·  NO LOGIN",
            bg=theme.PANEL_ALT,
            fg=theme.TEXT_MUTED,
            font=theme.FONT_BADGE,
            padx=10,
            pady=6,
        ).pack(side="right", padx=16)

        intro = tk.Frame(shell, bg=theme.BG)
        intro.pack(fill="x", pady=(0, 12))
        tk.Label(
            intro,
            text="MTK BootROM Partition Reader",
            bg=theme.BG,
            fg=theme.TEXT,
            font=theme.FONT_SUBTITLE,
            anchor="w",
        ).pack(fill="x")
        tk.Label(
            intro,
            text=(
                "One task only: detect an MTK device in BootROM mode and, when the audited reader is available, "
                "read selected partitions."
            ),
            bg=theme.BG,
            fg=theme.TEXT_MUTED,
            font=theme.FONT_UI_SMALL,
            anchor="w",
            justify="left",
            wraplength=900,
        ).pack(fill="x", pady=(4, 0))

        warning = tk.Frame(
            shell,
            bg=theme.WARNING_DIM,
            highlightbackground=theme.WARNING,
            highlightthickness=1,
        )
        warning.pack(fill="x", pady=(0, 12))
        tk.Label(
            warning,
            text=(
                "MTK access is disabled pending independent security review. The previous backend could run "
                "unaudited security code and report a failed erase as successful. USB scanning is passive; "
                "this build sends no device commands."
            ),
            bg=theme.WARNING_DIM,
            fg=theme.WARNING,
            font=theme.FONT_UI_SMALL,
            justify="left",
            anchor="w",
            wraplength=900,
            padx=12,
            pady=10,
        ).pack(fill="x")

        device_card = Card(shell, "MTK BootROM detection", "Passive USB scan only")
        device_card.pack(fill="x", pady=(0, 12))
        device_row = tk.Frame(device_card.body, bg=theme.PANEL)
        device_row.pack(fill="x")
        self.device_status = tk.Label(
            device_row,
            text="No scan has been run.",
            bg=theme.PANEL,
            fg=theme.TEXT_MUTED,
            font=theme.FONT_UI,
            anchor="w",
            justify="left",
        )
        self.device_status.pack(side="left", fill="x", expand=True)
        self.scan_button = ActionButton(
            device_row,
            "Scan for MTK BootROM",
            self.scan_usb,
            variant="accent",
        )
        self.scan_button.pack(side="right", padx=(12, 0))

        partition_card = Card(shell, "Device partitions", "MTK BootROM only")
        partition_card.pack(fill="both", expand=True)
        table_wrapper = tk.Frame(partition_card.body, bg=theme.PANEL)
        table_wrapper.pack(fill="both", expand=True)
        self.partition_tree = ttk.Treeview(
            table_wrapper,
            columns=("name", "sector", "sectors", "size"),
            show="headings",
            selectmode="browse",
            height=11,
        )
        for key, label, width, anchor in (
            ("name", "Partition", 240, "w"),
            ("sector", "Start sector", 150, "e"),
            ("sectors", "Sectors", 150, "e"),
            ("size", "Size", 140, "e"),
        ):
            self.partition_tree.heading(key, text=label)
            self.partition_tree.column(key, width=width, anchor=anchor, stretch=key == "name")
        scroll = ttk.Scrollbar(table_wrapper, orient="vertical", command=self.partition_tree.yview)
        self.partition_tree.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.partition_tree.pack(side="left", fill="both", expand=True)

        actions = tk.Frame(partition_card.body, bg=theme.PANEL)
        actions.pack(fill="x", pady=(10, 0))
        self.partition_note = tk.Label(
            actions,
            text="No partition table loaded. Device reads are unavailable in this build.",
            bg=theme.PANEL,
            fg=theme.TEXT_MUTED,
            font=theme.FONT_UI_SMALL,
            anchor="w",
            justify="left",
        )
        self.partition_note.pack(side="left", fill="x", expand=True)
        self.read_button = ActionButton(
            actions,
            "Read selected partition",
            self._read_selected,
            variant="info",
        )
        self.read_button.pack(side="right", padx=(12, 0))
        self.read_button.configure(state="disabled")

        footer = tk.Frame(shell, bg=theme.PANEL, highlightbackground=theme.BORDER, highlightthickness=1)
        footer.pack(fill="x", pady=(12, 0))
        tk.Label(footer, text="●", bg=theme.PANEL, fg=theme.DANGER, font=("Segoe UI", 11)).pack(
            side="left", padx=(12, 6), pady=7
        )
        self.status_label = tk.Label(
            footer,
            text="Ready",
            bg=theme.PANEL,
            fg=theme.TEXT_MUTED,
            font=theme.FONT_UI_SMALL,
            anchor="w",
        )
        self.status_label.pack(side="left", pady=7)
        tk.Label(
            footer,
            text=self.authorized_use,
            bg=theme.PANEL,
            fg=theme.TEXT_DIM,
            font=theme.FONT_BADGE,
            anchor="e",
        ).pack(side="right", padx=12)

    def scan_usb(self) -> None:
        """Enumerate USB devices without opening a device session."""
        if not self._scan_lock.acquire(blocking=False):
            return
        self._scan_in_progress = True
        self.scan_button.configure(state="disabled")
        self.device_status.configure(text="Scanning USB devices (passive)...", fg=theme.INFO)
        self.status_label.configure(text="Scanning USB...")

        def _work() -> None:
            try:
                report = scan_report()
            except Exception as exc:
                report = {"error": "%s: %s" % (exc.__class__.__name__, exc), "relevant": []}
            try:
                self.after(0, lambda result=report: self._finish_scan(result))
            except tk.TclError:
                self._scan_in_progress = False
                self._scan_lock.release()

        threading.Thread(target=_work, name="bestmdmtool-usb-scan", daemon=True).start()

    def _finish_scan(self, report: dict[str, Any]) -> None:
        self.last_scan = dict(report or {})
        self._scan_in_progress = False
        if self._scan_lock.locked():
            self._scan_lock.release()
        self.scan_button.configure(state="normal")

        entries = [entry for entry in self.last_scan.get("relevant", []) if isinstance(entry, dict)]
        mtk_entries = [entry for entry in entries if str(entry.get("vendor") or "").upper() == "MTK"]
        brom_entries = [entry for entry in mtk_entries if str(entry.get("protocol") or "").upper() == "BROM"]

        if brom_entries:
            device = brom_entries[0]
            detail = format_device_summary(device)
            if device.get("service"):
                detail += " · driver %s" % device["service"]
            if device.get("port"):
                detail += " · %s" % device["port"]
            self.device_status.configure(text=detail, fg=theme.SUCCESS)
            self.status_label.configure(text="BROM device detected — no session opened", fg=theme.SUCCESS)
        elif mtk_entries:
            modes = ", ".join(sorted({str(entry.get("protocol") or "unknown") for entry in mtk_entries}))
            self.device_status.configure(
                text="MTK device detected, but not in BootROM mode (%s). No connection attempted." % modes,
                fg=theme.WARNING,
            )
            self.status_label.configure(text="BootROM mode required", fg=theme.WARNING)
        elif self.last_scan.get("error"):
            self.device_status.configure(text="USB scan failed: %s" % self.last_scan["error"], fg=theme.DANGER)
            self.status_label.configure(text="USB scan failed", fg=theme.DANGER)
        else:
            self.device_status.configure(text="No MTK BootROM device detected.", fg=theme.TEXT_MUTED)
            self.status_label.configure(text="Scan complete — no device commands sent", fg=theme.TEXT_MUTED)

        # This prototype deliberately never fills a device partition table:
        # passive USB enumeration is not a device read.
        self.partition_tree.delete(*self.partition_tree.get_children())
        self.partition_note.configure(text="No partition table loaded. Device reads are unavailable in this build.")
        self.read_button.configure(state="disabled")

    def _read_selected(self) -> None:
        """Fail closed: there is no active MTK session or read backend."""
        self.status_label.configure(
            text="Partition reading is disabled pending independent MTK security review.",
            fg=theme.WARNING,
        )


def format_device_summary(device: dict[str, Any]) -> str:
    """Format an MTK BROM scan result without claiming a session was opened."""
    usb_id = str(device.get("usb") or "USB ID unavailable")
    mode = str(device.get("protocol") or "unknown")
    return "MTK %s detected · %s · passive scan only" % (mode, usb_id)
