"""Chipset browser: MediaTek and Spreadtrum/Unisoc parts, plus USB detection."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Any

from servicecore.chipsets import ALL_CHIPS, families, protocols, summary

from .. import theme
from ..widgets import ActionButton, Card
from .base import BasePage


class ChipsetsPage(BasePage):
    key = "chipsets"
    heading = "Chipsets"
    description = (
        "MediaTek (BROM/DA) and Spreadtrum/Unisoc (BSL/FDL) parts this tool can service, "
        "with the USB ids each one reports in download mode."
    )

    def build(self) -> None:
        overview = Card(self.content, "Database")
        overview.pack(fill="x")
        stats = summary()
        tk.Label(
            overview.body,
            text="%d chipsets: %d MediaTek, %d Spreadtrum/Unisoc"
            % (stats["total"], stats["mtk"], stats["spd"]),
            bg=theme.PANEL,
            fg=theme.TEXT,
            font=theme.FONT_UI_SMALL,
            anchor="w",
        ).pack(fill="x", pady=(0, 4))
        for key, text in protocols().items():
            tk.Label(
                overview.body,
                text="%s - %s" % (key.upper(), text),
                bg=theme.PANEL,
                fg=theme.TEXT_DIM,
                font=theme.FONT_BADGE,
                anchor="w",
                justify="left",
            ).pack(fill="x")

        filters = tk.Frame(self.content, bg=theme.BG)
        filters.pack(fill="x", pady=(10, 0))
        tk.Label(filters, text="Vendor", bg=theme.BG, fg=theme.TEXT_MUTED, font=theme.FONT_BADGE).pack(side="left")
        self.vendor_var = tk.StringVar(value="All")
        vendor_box = ttk.Combobox(
            filters, textvariable=self.vendor_var, values=["All", "MTK", "SPD"], state="readonly", width=8
        )
        vendor_box.pack(side="left", padx=(8, 16))
        vendor_box.bind("<<ComboboxSelected>>", lambda _event: self._render())

        tk.Label(filters, text="Family", bg=theme.BG, fg=theme.TEXT_MUTED, font=theme.FONT_BADGE).pack(side="left")
        self.family_var = tk.StringVar(value="All")
        self.family_box = ttk.Combobox(
            filters, textvariable=self.family_var, values=["All"] + families(), state="readonly", width=18
        )
        self.family_box.pack(side="left", padx=(8, 16))
        self.family_box.bind("<<ComboboxSelected>>", lambda _event: self._render())

        tk.Label(filters, text="Search", bg=theme.BG, fg=theme.TEXT_MUTED, font=theme.FONT_BADGE).pack(side="left")
        self.search_var = tk.StringVar()
        entry = ttk.Entry(filters, textvariable=self.search_var, width=18)
        entry.pack(side="left", padx=(8, 16))
        entry.bind("<KeyRelease>", lambda _event: self._render())

        ActionButton(filters, "Detect on USB", self._detect, variant="accent").pack(side="right")

        table = Card(self.content, "")
        table.pack(fill="both", expand=True, pady=(10, 0))
        self.status_label = tk.Label(
            table.body, text="", bg=theme.PANEL, fg=theme.TEXT_DIM, font=theme.FONT_BADGE, anchor="w"
        )
        self.status_label.pack(fill="x", pady=(0, 6))

        wrapper = tk.Frame(table.body, bg=theme.PANEL)
        wrapper.pack(fill="both", expand=True)
        columns = ("name", "vendor", "family", "protocol", "usb", "year")
        self.tree = ttk.Treeview(wrapper, columns=columns, show="headings", height=10)
        for column, title, width in (
            ("name", "Chipset", 150),
            ("vendor", "Vendor", 70),
            ("family", "Family", 150),
            ("protocol", "Protocol", 80),
            ("usb", "USB ids", 190),
            ("year", "Year", 60),
        ):
            self.tree.heading(column, text=title)
            self.tree.column(column, width=width, anchor="w")
        scroll = ttk.Scrollbar(wrapper, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        self.tree.bind("<<TreeviewSelect>>", self._on_select)

        self.notes_label = tk.Label(
            table.body,
            text="Select a chipset to see what to expect.",
            bg=theme.PANEL,
            fg=theme.TEXT_DIM,
            font=theme.FONT_BADGE,
            justify="left",
            anchor="w",
            wraplength=760,
        )
        self.notes_label.pack(fill="x", pady=(6, 0))
        self._render()

    # -- rendering ---------------------------------------------------------
    def _visible(self) -> list:
        vendor = self.vendor_var.get()
        family = self.family_var.get()
        needle = self.search_var.get().strip().lower()
        out = []
        for chip in ALL_CHIPS:
            if vendor != "All" and chip.vendor != vendor:
                continue
            if family != "All" and chip.family != family:
                continue
            if needle and needle not in " ".join((chip.name, chip.family, chip.vendor, chip.notes)).lower():
                continue
            out.append(chip)
        return out

    def _render(self) -> None:
        self.tree.delete(*self.tree.get_children())
        visible = self._visible()
        for chip in visible:
            usb = ", ".join("%04X:%04X" % pair for pair in chip.usb)
            self.tree.insert(
                "",
                "end",
                iid=chip.name,
                values=(chip.name, chip.vendor, chip.family, chip.protocol.upper(), usb, chip.year or ""),
            )
        self.status_label.configure(text="%d chipset(s) shown" % len(visible))

    def _on_select(self, _event=None) -> None:
        selection = self.tree.selection()
        if not selection:
            return
        chip = next((entry for entry in ALL_CHIPS if entry.name == selection[0]), None)
        if chip is None:
            return
        self.notes_label.configure(
            text="%s %s (%s, %s) - %s"
            % (
                chip.vendor,
                chip.name,
                chip.family,
                chip.protocol.upper(),
                chip.notes or "no special notes",
            )
        )

    # -- actions -----------------------------------------------------------
    def _detect(self) -> None:
        self.status_label.configure(text="Scanning USB...")

        def _done(devices: list[dict[str, Any]]) -> None:
            if not devices:
                self.status_label.configure(text="No MediaTek/Spreadtrum device in download mode found.")
                return
            self.status_label.configure(
                text="Detected: "
                + "; ".join("%s %s (%s)" % (d.get("vendor"), d.get("chip"), d.get("usb")) for d in devices)
            )
            first = devices[0]
            chip = first.get("chip")
            if chip and chip != "unknown" and self.tree.exists(chip):
                self.tree.selection_set(chip)
                self.tree.see(chip)

        self.controller.scan_usb_devices(_done)

    def on_show(self) -> None:
        self.family_box.configure(values=["All"] + families())
        self._render()
