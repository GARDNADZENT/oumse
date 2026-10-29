"""Advanced tools: raw flash read/erase, memory peek and poke."""

from __future__ import annotations

import tkinter as tk

from .. import theme
from ..widgets import ActionButton, Card, LabeledEntry, PathRow
from .base import BasePage


def _hex_dump(data: bytes, base: int, width: int = 16) -> str:
    lines = []
    for offset in range(0, len(data), width):
        chunk = data[offset : offset + width]
        hex_part = " ".join("%02X" % byte for byte in chunk)
        text_part = "".join(chr(byte) if 32 <= byte < 127 else "." for byte in chunk)
        lines.append("%08X  %-*s  |%s|" % (base + offset, width * 3 - 1, hex_part, text_part))
    return "\n".join(lines)


class AdvancedPage(BasePage):
    key = "advanced"
    heading = "Advanced Tools"
    description = "Raw flash access and live memory inspection for authorized servicing."

    def build(self) -> None:
        grid = tk.Frame(self.content, bg=theme.BG)
        grid.pack(fill="x")
        grid.grid_columnconfigure(0, weight=1)
        grid.grid_columnconfigure(1, weight=1)

        read_card = Card(grid, "Read flash range")
        read_card.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        self.read_offset = LabeledEntry(read_card.body, "Offset (bytes)", initial="0")
        self.read_offset.pack(fill="x", pady=(0, 8))
        self.read_length = LabeledEntry(read_card.body, "Length (bytes)", initial="1048576")
        self.read_length.pack(fill="x", pady=(0, 8))
        self.read_out = PathRow(read_card.body, "Output file", self._browse_out)
        self.read_out.pack(fill="x", pady=(0, 10))
        ActionButton(read_card.body, "Read range", self._read_range, variant="accent").pack(fill="x")

        erase_card = Card(grid, "Erase flash range")
        erase_card.grid(row=0, column=1, sticky="nsew")
        self.erase_offset = LabeledEntry(erase_card.body, "Offset (bytes)", initial="0")
        self.erase_offset.pack(fill="x", pady=(0, 8))
        self.erase_length = LabeledEntry(erase_card.body, "Length (bytes)", initial="1048576")
        self.erase_length.pack(fill="x", pady=(0, 8))
        tk.Label(
            erase_card.body,
            text="Erases raw sectors. There is no undo — prefer erasing\nby partition name in the Partition Manager.",
            bg=theme.PANEL,
            fg=theme.TEXT_DIM,
            font=theme.FONT_BADGE,
            justify="left",
            anchor="w",
        ).pack(fill="x", pady=(0, 10))
        ActionButton(erase_card.body, "Erase range", self._erase_range, variant="danger").pack(fill="x")

        memory = Card(self.content, "Live memory (peek / poke)")
        memory.pack(fill="both", expand=True, pady=(10, 0))

        controls = tk.Frame(memory.body, bg=theme.PANEL)
        controls.pack(fill="x")
        self.mem_addr = LabeledEntry(controls, "Address", width=16, initial="0x0")
        self.mem_addr.pack(side="left", padx=(0, 8))
        self.mem_len = LabeledEntry(controls, "Length", width=10, initial="256")
        self.mem_len.pack(side="left", padx=(0, 8))
        ActionButton(controls, "Peek", self._peek, variant="accent").pack(side="left", pady=(14, 0))

        poke_row = tk.Frame(memory.body, bg=theme.PANEL)
        poke_row.pack(fill="x", pady=(10, 8))
        self.poke_addr = LabeledEntry(poke_row, "Address", width=16, initial="0x0")
        self.poke_addr.pack(side="left", padx=(0, 8))
        self.poke_data = LabeledEntry(poke_row, "Hex data", width=48, initial="")
        self.poke_data.pack(side="left", fill="x", expand=True, padx=(0, 8))
        ActionButton(poke_row, "Poke", self._poke, variant="warning").pack(side="left", pady=(14, 0))

        self.hex_view = tk.Text(
            memory.body,
            height=10,
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
        self.hex_view.pack(fill="both", expand=True)
        self.hex_view.configure(state="disabled")

    # -- helpers -----------------------------------------------------------
    def _browse_out(self) -> str:
        path = self.app.ask_save("Save range", defaultextension=".bin", filetypes=[("Binary", "*.bin")])
        if path:
            self.read_out.set(path)
        return path

    @staticmethod
    def _parse(value: str, default: int = 0) -> int:
        text = (value or "").strip()
        if not text:
            return default
        return int(text, 0)

    def _write_hex(self, text: str) -> None:
        self.hex_view.configure(state="normal")
        self.hex_view.delete("1.0", "end")
        self.hex_view.insert("1.0", text or "(no data)")
        self.hex_view.configure(state="disabled")

    # -- actions -----------------------------------------------------------
    def _read_range(self) -> None:
        session = self.require_session()
        if session is None:
            return
        try:
            offset = self._parse(self.read_offset.get())
            length = self._parse(self.read_length.get())
        except ValueError:
            self.app.set_status("Offset and length must be numbers.", "warn")
            return
        target = self.read_out.get() or self.app.ask_save("Save range", defaultextension=".bin")
        if not target:
            return
        if length <= 0:
            self.app.set_status("Length must be greater than zero.", "warn")
            return
        self.log("Reading 0x%X bytes at 0x%X" % (length, offset), "STEP")
        self.controller.run_async(
            "Reading flash range",
            lambda: session.read_flash(offset, length, target),
            lambda result: self._report(result, "Read range"),
        )

    def _erase_range(self) -> None:
        session = self.require_session()
        if session is None:
            return
        try:
            offset = self._parse(self.erase_offset.get())
            length = self._parse(self.erase_length.get())
        except ValueError:
            self.app.set_status("Offset and length must be numbers.", "warn")
            return
        if length <= 0:
            self.app.set_status("Length must be greater than zero.", "warn")
            return
        if not self.app.confirm(
            "Erase range",
            "Erase 0x%X bytes starting at 0x%X?\n\nData cannot be recovered." % (length, offset),
            danger=True,
        ):
            return
        self.log("Erasing 0x%X bytes at 0x%X" % (length, offset), "STEP")
        self.controller.run_async(
            "Erasing range",
            lambda: session.erase_flash(offset, length),
            lambda result: self._report(result, "Erase range"),
        )

    def _peek(self) -> None:
        session = self.require_session()
        if session is None:
            return
        try:
            addr = self._parse(self.mem_addr.get())
            length = self._parse(self.mem_len.get(), 256)
        except ValueError:
            self.app.set_status("Address and length must be numbers.", "warn")
            return
        length = max(1, min(length, 0x10000))
        self.controller.run_async(
            "Peeking memory",
            lambda: session.peek(addr, length),
            lambda result: self._show_peek(result, addr),
        )

    def _show_peek(self, result, addr: int) -> None:
        if result is None or not getattr(result, "ok", False):
            detail = getattr(result, "detail", "unknown error")
            self._write_hex("peek failed: %s" % detail)
            self.log("Peek failed: %s" % detail, "ERROR")
            return
        data = getattr(result, "data", b"") or b""
        self._write_hex(_hex_dump(data, addr))
        self.log("Peeked %d bytes at 0x%X" % (len(data), addr), "OK")

    def _poke(self) -> None:
        session = self.require_session()
        if session is None:
            return
        try:
            addr = self._parse(self.poke_addr.get())
        except ValueError:
            self.app.set_status("Address must be a number.", "warn")
            return
        data = self.poke_data.get().replace(" ", "").replace("0x", "")
        if not data:
            self.app.set_status("Enter hex data to write.", "warn")
            return
        if not self.app.confirm(
            "Poke memory",
            "Write %d byte(s) at 0x%X?\n\nPoking the wrong address can hard-brick the device." % (len(data) // 2, addr),
            danger=True,
        ):
            return
        self.controller.run_async(
            "Poking memory",
            lambda: session.poke(addr, data),
            lambda result: self._report(result, "Poke"),
        )

    def _report(self, result, label: str) -> None:
        ok = bool(getattr(result, "ok", False))
        detail = getattr(result, "detail", "")
        self.log(
            "%s %s%s" % (label, "complete" if ok else "failed", (" — %s" % detail) if detail and not ok else ""),
            "OK" if ok else "ERROR",
        )
        self.app.set_status("%s %s" % (label, "complete" if ok else "failed"), "ok" if ok else "error")
