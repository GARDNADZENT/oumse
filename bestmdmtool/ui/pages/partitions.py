"""Partition manager: browse the GPT, read, write, erase, and back up."""

from __future__ import annotations

import os
import tkinter as tk
from tkinter import ttk
from typing import Any

from servicecore.safety import is_dangerous_partition

from .. import theme
from ..widgets import ActionButton, Card
from .base import BasePage

COLUMNS = (
    ("name", "Partition", 240),
    ("size", "Size", 110),
    ("sectors", "Sectors", 110),
    ("offset", "Offset (bytes)", 150),
)


class PartitionsPage(BasePage):
    key = "partitions"
    heading = "Partition Manager"
    description = "Read, back up, restore, or erase partitions over the open BROM/DA session."

    def build(self) -> None:
        toolbar = tk.Frame(self.content, bg=theme.BG)
        toolbar.pack(fill="x", pady=(0, 8))

        tk.Label(
            toolbar,
            text="Filter",
            bg=theme.BG,
            fg=theme.TEXT_MUTED,
            font=theme.FONT_BADGE,
        ).pack(side="left", padx=(0, 6))
        self.filter_var = tk.StringVar()
        entry = tk.Entry(
            toolbar,
            textvariable=self.filter_var,
            width=26,
            bg=theme.PANEL_ALT,
            fg=theme.TEXT,
            insertbackground=theme.TEXT,
            relief="flat",
            bd=0,
            highlightthickness=1,
            highlightbackground=theme.BORDER,
            highlightcolor=theme.ACCENT,
            font=theme.FONT_UI_SMALL,
        )
        entry.pack(side="left", ipady=4)
        self.filter_var.trace_add("write", lambda *_args: self._render())

        ActionButton(toolbar, "Refresh", self._refresh).pack(side="right", padx=(6, 0))
        ActionButton(toolbar, "Export GPT", self._export_gpt, variant="ghost").pack(side="right", padx=(6, 0))
        ActionButton(toolbar, "Backup all", self._backup_all, variant="ghost").pack(side="right", padx=(6, 0))
        ActionButton(toolbar, "Reboot", self._reboot, variant="ghost").pack(side="right", padx=(6, 0))

        table_card = Card(self.content, "Partition table")
        table_card.pack(fill="both", expand=True)

        wrapper = tk.Frame(table_card.body, bg=theme.PANEL)
        wrapper.pack(fill="both", expand=True)
        self.tree = ttk.Treeview(
            wrapper,
            columns=[column[0] for column in COLUMNS],
            show="headings",
            selectmode="extended",
            height=16,
        )
        for key, label, width in COLUMNS:
            self.tree.heading(key, text=label)
            self.tree.column(key, width=width, anchor="w" if key == "name" else "e", stretch=key == "name")
        scroll = ttk.Scrollbar(wrapper, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.tree.pack(side="left", fill="both", expand=True)
        self.tree.tag_configure("danger", foreground=theme.WARNING)
        self.tree.bind("<<TreeviewSelect>>", lambda _event: self._update_selection_label())
        self.tree.bind("<Double-1>", lambda _event: self._read_selected())

        actions = tk.Frame(self.content, bg=theme.BG)
        actions.pack(fill="x", pady=(10, 0))

        self.selection_label = tk.Label(
            actions,
            text="No partition selected.",
            bg=theme.BG,
            fg=theme.TEXT_MUTED,
            font=theme.FONT_UI_SMALL,
            anchor="w",
        )
        self.selection_label.pack(side="left")

        ActionButton(actions, "Erase", self._erase_selected, variant="danger").pack(side="right", padx=(6, 0))
        ActionButton(actions, "Write image", self._write_selected, variant="warning").pack(side="right", padx=(6, 0))
        ActionButton(actions, "Read to file", self._read_selected, variant="accent").pack(side="right", padx=(6, 0))

    # -- rendering ---------------------------------------------------------
    def on_show(self) -> None:
        self._render()

    def on_device(self, device: dict[str, Any]) -> None:
        self._render()

    def _visible_partitions(self) -> list[dict[str, Any]]:
        needle = self.filter_var.get().strip().lower()
        parts = self.partitions()
        if needle:
            parts = [part for part in parts if needle in str(part.get("name", "")).lower()]
        return parts

    def _render(self) -> None:
        selected = set(self.selected_names())
        self.tree.delete(*self.tree.get_children())
        for part in self._visible_partitions():
            name = str(part.get("name", ""))
            sector = part.get("sector")
            pagesize = part.get("pagesize") or 512
            offset = int(sector) * int(pagesize) if sector is not None else ""
            tags = ("danger",) if is_dangerous_partition(name) else ()
            item = self.tree.insert(
                "",
                "end",
                values=(
                    name,
                    self.format_size(int(part.get("size") or 0)),
                    part.get("sectors", ""),
                    offset,
                ),
                tags=tags,
            )
            if name in selected:
                self.tree.selection_add(item)
        self._update_selection_label()

    def _update_selection_label(self) -> None:
        names = self.selected_names()
        if not names:
            total = len(self.partitions())
            self.selection_label.configure(
                text=("No partition selected. %d entries in GPT." % total) if total else "No partition table loaded.",
                fg=theme.TEXT_MUTED,
            )
            return
        if len(names) == 1:
            part = next((p for p in self.partitions() if p.get("name") == names[0]), {})
            text = "%s · %s · sector %s" % (
                names[0],
                self.format_size(int(part.get("size") or 0)),
                part.get("sector", "?"),
            )
        else:
            text = "%d partitions selected" % len(names)
        danger = [name for name in names if is_dangerous_partition(name)]
        if danger:
            text += "  ·  protected: %s" % ", ".join(danger)
        self.selection_label.configure(text=text, fg=theme.WARNING if danger else theme.TEXT)

    def selected_names(self) -> list[str]:
        out = []
        for item in self.tree.selection():
            try:
                values = self.tree.item(item, "values")
            except tk.TclError:
                continue
            if values:
                out.append(str(values[0]))
        return out

    # -- operations --------------------------------------------------------
    def _refresh(self) -> None:
        if self.require_session():
            self.controller.refresh_partitions(lambda _parts: self._render())

    def _read_selected(self) -> None:
        session = self.require_session()
        names = self.selected_names()
        if session is None or not names:
            if session is not None:
                self.app.set_status("Select a partition first.", "warn")
            return
        part = names[0]
        target = self.app.ask_save(
            "Save %s image" % part,
            defaultextension=".bin",
            filetypes=[("Binary image", "*.bin"), ("All files", "*.*")],
        )
        if not target:
            return
        self.controller.settings.last_dir = os.path.dirname(target)
        self.controller.settings.save()
        self.log("Reading %s -> %s" % (part, target), "STEP")
        self.controller.run_async(
            "Reading %s" % part,
            lambda: session.read_partition(part, target),
            lambda result: self._after_result(result, "Read %s" % part),
        )

    def _write_selected(self) -> None:
        session = self.require_session()
        names = self.selected_names()
        if session is None or not names:
            if session is not None:
                self.app.set_status("Select a partition first.", "warn")
            return
        part = names[0]
        source = self.app.ask_open("Choose image for %s" % part, [("Image files", "*.bin *.img"), ("All files", "*.*")])
        if not source:
            return
        if not os.path.isfile(source):
            self.log("File not found: %s" % source, "ERROR")
            return
        size = os.path.getsize(source)
        part_info = next((p for p in self.partitions() if p.get("name") == part), {})
        part_size = int(part_info.get("size") or 0)
        warning = "Write %s (%s) to partition %s?" % (os.path.basename(source), self.format_size(size), part)
        if part_size and size > part_size:
            warning += "\n\nThe image is larger than the partition and will be truncated by the device."
        if is_dangerous_partition(part):
            warning += "\n\n%s is a protected partition. Writing it can brick the device." % part
        if not self.app.confirm("Write partition", warning, danger=True):
            return
        self.log("Writing %s -> %s" % (os.path.basename(source), part), "STEP")
        self.controller.run_async(
            "Writing %s" % part,
            lambda: session.write_partition(part, source),
            lambda result: self._after_result(result, "Write %s" % part),
        )

    def _erase_selected(self) -> None:
        session = self.require_session()
        names = self.selected_names()
        if session is None or not names:
            if session is not None:
                self.app.set_status("Select a partition first.", "warn")
            return
        danger = [name for name in names if is_dangerous_partition(name)]
        message = "Erase %d partition(s)?\n\n%s" % (len(names), ", ".join(names))
        if danger:
            message += "\n\nProtected partitions selected: %s" % ", ".join(danger)
        if not self.app.confirm("Erase partitions", message, danger=True):
            return
        self.log("Erasing %s" % ", ".join(names), "STEP")
        self.controller.run_async(
            "Erasing partitions",
            lambda: session.erase(names),
            lambda result: self._after_result(result, "Erase"),
        )

    def _backup_all(self) -> None:
        session = self.require_session()
        if session is None:
            return
        directory = self.app.ask_dir("Choose backup folder")
        if not directory:
            return
        parts = [str(part.get("name")) for part in self.partitions()]
        if not parts:
            self.app.set_status("Partition table is empty.", "warn")
            return
        if not self.app.confirm(
            "Full backup",
            "Back up %d partitions to:\n%s\n\nThis can take a long time and needs disk space."
            % (len(parts), directory),
            danger=True,
        ):
            return
        self.log("Backing up %d partitions to %s" % (len(parts), directory), "STEP")
        self.controller.run_async(
            "Backing up partitions",
            lambda: session.dump(directory, parts),
            lambda result: self._after_result(result, "Backup"),
        )

    def _export_gpt(self) -> None:
        session = self.require_session()
        if session is None:
            return
        target = self.app.ask_save("Export GPT", defaultextension=".bin", filetypes=[("Binary", "*.bin")])
        if not target:
            return
        self.controller.run_async(
            "Exporting GPT",
            lambda: session.export_gpt(target),
            lambda result: self._after_result(result, "Export GPT"),
        )

    def _reboot(self) -> None:
        session = self.require_session()
        if session is None:
            return
        if not self.app.confirm("Reboot", "Reboot the device now?", danger=True):
            return
        self.controller.run_async("Rebooting device", lambda: session.reboot(0))

    def _after_result(self, result, label: str) -> None:
        if result is None:
            return
        if getattr(result, "ok", False):
            detail = getattr(result, "detail", "")
            self.log("%s complete%s" % (label, (" — %s" % detail) if detail else ""), "OK")
            self.app.set_status("%s complete." % label, "ok")
            self.app.clear_progress()
        else:
            self.log("%s failed: %s" % (label, getattr(result, "detail", "unknown error")), "ERROR")
            self.app.set_status("%s failed." % label, "error")
