"""Firmware flasher: single image, batch queue, and raw offset writes."""

from __future__ import annotations

import os
import tkinter as tk
from tkinter import ttk
from typing import Any

from .. import theme
from ..widgets import ActionButton, Card, LabeledEntry, PathRow
from .base import BasePage


class FlasherPage(BasePage):
    key = "flasher"
    heading = "Firmware Flasher"
    description = "Write images to partitions or to raw flash offsets over the open session."

    def build(self) -> None:
        top = tk.Frame(self.content, bg=theme.BG)
        top.pack(fill="x")
        top.grid_columnconfigure(0, weight=1)
        top.grid_columnconfigure(1, weight=1)

        single = Card(top, "Flash image to partition")
        single.grid(row=0, column=0, sticky="nsew", padx=(0, 8))

        self.image_row = PathRow(single.body, "Image file (.img/.bin)", self._browse_image)
        self.image_row.pack(fill="x", pady=(0, 8))

        row = tk.Frame(single.body, bg=theme.PANEL)
        row.pack(fill="x", pady=(0, 8))
        tk.Label(
            row,
            text="Target partition",
            bg=theme.PANEL,
            fg=theme.TEXT_MUTED,
            font=theme.FONT_BADGE,
        ).pack(anchor="w")
        self.partition_var = tk.StringVar()
        self.partition_combo = ttk.Combobox(row, textvariable=self.partition_var, values=[], state="readonly")
        self.partition_combo.pack(fill="x", pady=(3, 0), ipady=3)

        self.reboot_after = tk.BooleanVar(value=False)
        tk.Checkbutton(
            single.body,
            text="Reboot device after flashing",
            variable=self.reboot_after,
            bg=theme.PANEL,
            fg=theme.TEXT_MUTED,
            activebackground=theme.PANEL,
            activeforeground=theme.TEXT,
            selectcolor=theme.PANEL_ALT,
            font=theme.FONT_UI_SMALL,
            bd=0,
            highlightthickness=0,
        ).pack(anchor="w", pady=(0, 8))

        ActionButton(single.body, "Flash image", self._flash_single, variant="accent").pack(fill="x")

        raw = Card(top, "Raw flash write (advanced)")
        raw.grid(row=0, column=1, sticky="nsew")

        self.raw_file = PathRow(raw.body, "Image file", self._browse_raw)
        self.raw_file.pack(fill="x", pady=(0, 8))
        self.raw_offset = LabeledEntry(raw.body, "Byte offset (decimal or 0x...)", initial="0")
        self.raw_offset.pack(fill="x", pady=(0, 8))
        tk.Label(
            raw.body,
            text="Absolute LBA/byte offset. The image is written as-is, with no\n"
            "partition table checks — verify the offset before continuing.",
            bg=theme.PANEL,
            fg=theme.TEXT_DIM,
            font=theme.FONT_BADGE,
            justify="left",
            anchor="w",
        ).pack(fill="x", pady=(0, 8))
        ActionButton(raw.body, "Write at offset", self._flash_raw, variant="warning").pack(fill="x")

        queue = Card(self.content, "Batch queue")
        queue.pack(fill="both", expand=True, pady=(10, 0))

        queue_toolbar = tk.Frame(queue.body, bg=theme.PANEL)
        queue_toolbar.pack(fill="x", pady=(0, 6))
        ActionButton(queue_toolbar, "Add images", self._add_images).pack(side="left")
        ActionButton(queue_toolbar, "Remove selected", self._remove_images, variant="ghost").pack(
            side="left", padx=(6, 0)
        )
        ActionButton(queue_toolbar, "Clear", self._clear_queue, variant="ghost").pack(side="left", padx=(6, 0))
        ActionButton(queue_toolbar, "Flash queue", self._flash_queue, variant="accent").pack(side="right")

        wrapper = tk.Frame(queue.body, bg=theme.PANEL)
        wrapper.pack(fill="both", expand=True)
        self.queue_tree = ttk.Treeview(
            wrapper,
            columns=("file", "partition", "size", "status"),
            show="headings",
            height=8,
            selectmode="extended",
        )
        for key, label, width, stretch in (
            ("file", "Image", 260, True),
            ("partition", "Target partition", 160, False),
            ("size", "Size", 100, False),
            ("status", "Status", 120, False),
        ):
            self.queue_tree.heading(key, text=label)
            self.queue_tree.column(key, width=width, anchor="w" if key == "file" else "center", stretch=stretch)
        scroll = ttk.Scrollbar(wrapper, orient="vertical", command=self.queue_tree.yview)
        self.queue_tree.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.queue_tree.pack(side="left", fill="both", expand=True)
        self.queue_tree.tag_configure("ok", foreground=theme.SUCCESS)
        self.queue_tree.tag_configure("fail", foreground=theme.DANGER)

        self._queue: list[str] = []

    # -- helpers -----------------------------------------------------------
    def on_show(self) -> None:
        self._refresh_partitions()

    def on_device(self, device: dict[str, Any]) -> None:
        self._refresh_partitions()

    def _refresh_partitions(self) -> None:
        names = [str(part.get("name")) for part in self.partitions()]
        self.partition_combo.configure(values=names)
        if names and self.partition_var.get() not in names:
            self.partition_var.set(names[0])

    def _browse_image(self) -> str:
        path = self.app.ask_open("Select image", [("Image files", "*.img *.bin"), ("All files", "*.*")])
        if path:
            self.image_row.set(path)
            self._auto_select_partition(path)
        return path

    def _browse_raw(self) -> str:
        path = self.app.ask_open("Select image", [("Image files", "*.img *.bin"), ("All files", "*.*")])
        if path:
            self.raw_file.set(path)
        return path

    def _auto_select_partition(self, path: str) -> None:
        stem = os.path.splitext(os.path.basename(path))[0].lower()
        names = [str(part.get("name")) for part in self.partitions()]
        for name in names:
            if name.lower() == stem:
                self.partition_var.set(name)
                return

    def _partition_entry(self, name: str) -> dict[str, Any]:
        for part in self.partitions():
            if str(part.get("name")) == name:
                return part
        return {}

    # -- actions -----------------------------------------------------------
    def _flash_single(self) -> None:
        session = self.require_session()
        if session is None:
            return
        source = self.image_row.get()
        part = self.partition_var.get().strip()
        if not source or not os.path.isfile(source):
            self.app.set_status("Choose a valid image file first.", "warn")
            return
        if not part:
            self.app.set_status("Choose a target partition.", "warn")
            return
        size = os.path.getsize(source)
        entry = self._partition_entry(part)
        message = "Flash %s (%s) to %s?" % (os.path.basename(source), self.format_size(size), part)
        if entry and int(entry.get("size") or 0) < size:
            message += "\n\nImage is larger than the partition — this usually fails or corrupts data."
        if not self.app.confirm("Confirm flash", message, danger=True):
            return
        self.log("Flashing %s -> %s" % (os.path.basename(source), part), "STEP")

        def _done(result) -> None:
            ok = bool(getattr(result, "ok", False))
            self.log(
                "Flash %s %s" % (part, "complete" if ok else "failed: %s" % getattr(result, "detail", "")),
                "OK" if ok else "ERROR",
            )
            if ok and self.reboot_after.get():
                self.controller.run_async("Rebooting device", lambda: session.reboot(0))
            self.app.set_progress(100, 100, "done")

        self.controller.run_async("Flashing %s" % part, lambda: session.write_partition(part, source), _done)

    def _flash_raw(self) -> None:
        session = self.require_session()
        if session is None:
            return
        source = self.raw_file.get()
        if not source or not os.path.isfile(source):
            self.app.set_status("Choose a valid image file first.", "warn")
            return
        try:
            offset = int(self.raw_offset.get() or "0", 0)
        except ValueError:
            self.app.set_status("Offset must be a decimal or 0x-prefixed number.", "warn")
            return
        size = os.path.getsize(source)
        if not self.app.confirm(
            "Raw write",
            "Write %s (%s) at byte offset 0x%X?\n\nThis bypasses partition checks."
            % (os.path.basename(source), self.format_size(size), offset),
            danger=True,
        ):
            return
        self.log("Raw write %s @ 0x%X" % (os.path.basename(source), offset), "STEP")
        self.controller.run_async(
            "Raw flash write",
            lambda: session.write_flash(source, offset),
            lambda result: self._log_result(result, "Raw write"),
        )

    def _add_images(self) -> None:
        from tkinter import filedialog

        paths = filedialog.askopenfilenames(
            title="Add images",
            filetypes=[("Image files", "*.img *.bin"), ("All files", "*.*")],
        )
        for path in paths or ():
            if path in self._queue:
                continue
            self._queue.append(path)
            stem = os.path.splitext(os.path.basename(path))[0].lower()
            match = next((str(p.get("name")) for p in self.partitions() if str(p.get("name")).lower() == stem), "")
            self.queue_tree.insert(
                "",
                "end",
                values=(os.path.basename(path), match or "—", self.format_size(os.path.getsize(path)), "queued"),
            )

    def _remove_images(self) -> None:
        for item in self.queue_tree.selection():
            values = self.queue_tree.item(item, "values")
            if values:
                for path in list(self._queue):
                    if os.path.basename(path) == str(values[0]):
                        self._queue.remove(path)
                        break
            self.queue_tree.delete(item)

    def _clear_queue(self) -> None:
        self._queue.clear()
        self.queue_tree.delete(*self.queue_tree.get_children())

    def _flash_queue(self) -> None:
        session = self.require_session()
        if session is None:
            return
        items = list(self.queue_tree.get_children())
        if not items:
            self.app.set_status("Queue is empty.", "warn")
            return
        missing = [
            self.queue_tree.item(i, "values")[0]
            for i in items
            if not str(self.queue_tree.item(i, "values")[1]).strip() or self.queue_tree.item(i, "values")[1] == "—"
        ]
        if missing:
            self.app.set_status("Unmapped images in queue: %s" % ", ".join(map(str, missing[:3])), "warn")
            return
        if not self.app.confirm("Flash queue", "Flash %d images in order?" % len(items), danger=True):
            return

        jobs = []
        for item in items:
            values = self.queue_tree.item(item, "values")
            path = next((p for p in self._queue if os.path.basename(p) == str(values[0])), "")
            if path:
                jobs.append((item, path, str(values[1])))

        def _work():
            results = []
            for item, path, part in jobs:
                self.controller.log("Queue: flashing %s -> %s" % (os.path.basename(path), part), "STEP")
                result = session.write_partition(part, path)
                results.append((item, part, result))
            return results

        def _done(results) -> None:
            for item, _part, result in results or []:
                ok = bool(getattr(result, "ok", False))
                self.queue_tree.set(item, "status", "done" if ok else "failed")
                self.queue_tree.item(item, tags=("ok",) if ok else ("fail",))
            self.app.set_status("Queue finished.", "ok")

        self.controller.run_async("Flashing queue", _work, _done)

    def _log_result(self, result, label: str) -> None:
        ok = bool(getattr(result, "ok", False))
        detail = getattr(result, "detail", "")
        self.log(
            "%s %s%s" % (label, "complete" if ok else "failed", (" — %s" % detail) if detail else ""),
            "OK" if ok else "ERROR",
        )
