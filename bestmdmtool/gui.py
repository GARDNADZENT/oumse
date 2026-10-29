from __future__ import annotations

import json
import queue
from functools import partial
from pathlib import Path
from typing import Any

try:
    import tkinter as tk
    from tkinter import filedialog, messagebox, scrolledtext, simpledialog, ttk
except ImportError as exc:  # pragma: no cover - depends on the host Python install
    raise ImportError(
        "The no-login GUI requires a Python interpreter with Tkinter. "
        "On Debian/Ubuntu install python3-tk; on Windows use the official "
        "CPython installer."
    ) from exc

from servicecore.config import ROOT, python_executable, runtime_lib, session_runner_path
from servicecore.patching import (
    PatchError,
    load_patch_document,
    patch_file,
    validate_plan,
)
from servicecore.safety import is_dangerous_partition, validate_erase_targets
from servicecore.session import BromSession, RunnerEvent

from .branding import AUTHORIZED_USE, PRODUCT_NAME, PRODUCT_SUBTITLE, PRODUCT_TITLE

BINARY_FILES = (("Binary files", "*.bin"), ("All files", "*.*"))
JSON_FILES = (("JSON files", "*.json"), ("All files", "*.*"))


class BestMDMToolApp(tk.Tk):
    """BestMDMTool: a directly opening, offline, authorized-service front-end."""

    def __init__(self) -> None:
        super().__init__()
        self.title(PRODUCT_TITLE)
        self.geometry("1000x680")
        self.minsize(880, 560)
        self.configure(bg="#1e1e2e")

        self.session: BromSession | None = None
        self._closing = False
        self._last_parts: list[dict[str, Any]] = []
        self._iid_to_part: dict[str, dict[str, Any]] = {}
        self._last_patched_file: Path | None = None
        self._log_line_count = 0

        self._status_var = tk.StringVar(value="Ready. No login required. Authorized devices only.")
        self._selected_var = tk.StringVar(value="No partition selected")
        self._mode_var = tk.StringVar(value="brom")
        self._loader_var = tk.StringVar()
        self._auth_var = tk.StringVar()
        self._input_var = tk.StringVar()
        self._patches_var = tk.StringVar()
        self._output_var = tk.StringVar()
        self._debug_var = tk.BooleanVar(value=False)
        self._autoscroll_var = tk.BooleanVar(value=True)

        self._action_buttons: list[ttk.Button] = []
        self._build_style()
        self._build_ui()
        self._set_session_controls(False)
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.after(100, self._poll_events)

    # ------------------------------------------------------------------ UI --
    def _build_style(self) -> None:
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("TFrame", background="#1e1e2e")
        style.configure("TLabel", background="#1e1e2e", foreground="#e6e6f0")
        style.configure("TLabelframe", background="#1e1e2e", foreground="#e6e6f0")
        style.configure("TLabelframe.Label", background="#1e1e2e", foreground="#9cdcfe")
        style.configure("TButton", padding=6)
        style.configure("TCheckbutton", background="#1e1e2e", foreground="#e6e6f0")
        style.configure(
            "Treeview",
            background="#252536",
            fieldbackground="#252536",
            foreground="#e6e6f0",
        )
        style.map("Treeview", background=[("selected", "#3a3a5a")])

    def _build_ui(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        header = ttk.Frame(self, padding=(16, 12))
        header.grid(row=0, column=0, sticky="ew")
        ttk.Label(
            header,
            text=PRODUCT_NAME,
            font=("Segoe UI", 18, "bold"),
        ).pack(anchor="w")
        ttk.Label(
            header,
            text=PRODUCT_SUBTITLE,
            font=("Segoe UI", 10),
            foreground="#9cdcfe",
        ).pack(anchor="w", pady=(2, 0))

        notebook = ttk.Notebook(self)
        notebook.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 8))
        self._build_session_tab(notebook)
        self._build_partitions_tab(notebook)
        self._build_patch_tab(notebook)
        self._build_logs_tab(notebook)

        status = ttk.Label(
            self,
            textvariable=self._status_var,
            relief=tk.SUNKEN,
            anchor="w",
            padding=(8, 4),
        )
        status.grid(row=2, column=0, sticky="ew")

    def _build_session_tab(self, notebook: ttk.Notebook) -> None:
        frame = ttk.Frame(notebook, padding=16)
        notebook.add(frame, text="Session")

        config = ttk.LabelFrame(frame, text="Runner configuration", padding=12)
        config.pack(fill="x", pady=(0, 12))
        config.columnconfigure(1, weight=1)

        ttk.Label(config, text="Mode:").grid(row=0, column=0, sticky="w", pady=4)
        mode = ttk.Combobox(
            config,
            textvariable=self._mode_var,
            values=("brom", "preloader"),
            state="readonly",
        )
        mode.grid(row=0, column=1, sticky="ew", pady=4)

        ttk.Label(config, text="Custom DA loader:").grid(row=1, column=0, sticky="w", pady=4)
        ttk.Entry(config, textvariable=self._loader_var).grid(row=1, column=1, sticky="ew", pady=4)
        ttk.Button(
            config,
            text="Browse…",
            command=lambda: self._browse_open_file(
                self._loader_var, "Select DA loader", BINARY_FILES
            ),
        ).grid(row=1, column=2, padx=(6, 0), pady=4)

        ttk.Label(config, text="Auth file:").grid(row=2, column=0, sticky="w", pady=4)
        ttk.Entry(config, textvariable=self._auth_var).grid(row=2, column=1, sticky="ew", pady=4)
        ttk.Button(
            config,
            text="Browse…",
            command=lambda: self._browse_open_file(
                self._auth_var, "Select auth file", BINARY_FILES
            ),
        ).grid(row=2, column=2, padx=(6, 0), pady=4)

        ttk.Checkbutton(
            config,
            text="Enable verbose runner debugging",
            variable=self._debug_var,
        ).grid(row=3, column=1, sticky="w", pady=(8, 0))

        buttons = ttk.Frame(frame)
        buttons.pack(fill="x", pady=(0, 12))
        self._start_button = ttk.Button(buttons, text="Start session", command=self._start_session)
        self._start_button.pack(side="left", padx=(0, 6))
        self._stop_button = ttk.Button(buttons, text="Stop session", command=self._stop_session)
        self._stop_button.pack(side="left")

        info = ttk.LabelFrame(frame, text="Resolved paths", padding=12)
        info.pack(fill="both", expand=True)
        ttk.Label(info, text=f"Python: {python_executable()}", wraplength=900).pack(anchor="w")
        ttk.Label(info, text=f"Runner: {session_runner_path()}", wraplength=900).pack(anchor="w")
        ttk.Label(info, text=f"Runtime library: {runtime_lib()}", wraplength=900).pack(anchor="w")
        ttk.Label(
            info,
            text=(
                "BestMDMTool never contacts a licensing server and never displays a login "
                "screen. " + AUTHORIZED_USE
            ),
            wraplength=900,
            foreground="#9cdcfe",
        ).pack(anchor="w", pady=(10, 0))

    def _build_partitions_tab(self, notebook: ttk.Notebook) -> None:
        frame = ttk.Frame(notebook, padding=16)
        notebook.add(frame, text="Partitions")
        frame.rowconfigure(1, weight=1)
        frame.columnconfigure(0, weight=1)

        top = ttk.Frame(frame)
        top.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        ttk.Label(top, textvariable=self._selected_var).pack(side="left")
        ttk.Button(top, text="Refresh view", command=self._refresh_partitions).pack(side="right")

        tree_frame = ttk.Frame(frame)
        tree_frame.grid(row=1, column=0, sticky="nsew")
        self._part_tree = ttk.Treeview(
            tree_frame,
            columns=("name", "size", "sectors"),
            show="headings",
            selectmode="extended",
        )
        self._part_tree.heading("name", text="Partition")
        self._part_tree.heading("size", text="Size")
        self._part_tree.heading("sectors", text="Sectors")
        self._part_tree.column("name", width=260, anchor="w")
        self._part_tree.column("size", width=160, anchor="e")
        self._part_tree.column("sectors", width=140, anchor="e")
        self._part_tree.tag_configure("dangerous", foreground="#ff8787")
        scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self._part_tree.yview)
        self._part_tree.configure(yscrollcommand=scrollbar.set)
        self._part_tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        self._part_tree.bind("<<TreeviewSelect>>", lambda _: self._update_selected_label())

        actions = ttk.Frame(frame)
        actions.grid(row=2, column=0, sticky="ew", pady=(10, 0))
        specs = (
            ("Read selected", self._read_partition),
            ("Write file…", self._write_partition),
            ("Erase selected…", self._erase_partitions),
            ("Reboot device", self._reboot),
        )
        for text, command in specs:
            button = ttk.Button(actions, text=text, command=command)
            button.pack(side="left", padx=(0, 6))
            self._action_buttons.append(button)

    def _build_patch_tab(self, notebook: ttk.Notebook) -> None:
        frame = ttk.Frame(notebook, padding=16)
        notebook.add(frame, text="Patch file")
        frame.columnconfigure(1, weight=1)
        frame.rowconfigure(5, weight=1)

        rows = (
            ("Input file:", self._input_var, "Browse…", "input", BINARY_FILES),
            ("Patches JSON:", self._patches_var, "Browse…", "patches", JSON_FILES),
            ("Output file:", self._output_var, "Save as…", "output", BINARY_FILES),
        )
        for row, (label, variable, button_text, kind, filetypes) in enumerate(rows):
            ttk.Label(frame, text=label).grid(row=row, column=0, sticky="w", pady=5)
            ttk.Entry(frame, textvariable=variable).grid(row=row, column=1, sticky="ew", pady=5)
            if kind == "output":
                command = partial(self._browse_save_file, variable, "Save patched file", filetypes)
            else:
                command = partial(self._browse_open_file, variable, "Select file", filetypes)
            ttk.Button(frame, text=button_text, command=command).grid(
                row=row, column=2, padx=(6, 0), pady=5
            )

        controls = ttk.Frame(frame)
        controls.grid(row=3, column=0, columnspan=3, sticky="w", pady=(10, 6))
        ttk.Button(controls, text="Validate plan", command=self._validate_patch).pack(
            side="left", padx=(0, 6)
        )
        ttk.Button(controls, text="Apply patch to local file", command=self._apply_patch).pack(
            side="left", padx=(0, 6)
        )
        write_button = ttk.Button(
            controls,
            text="Write patched file to selected partition",
            command=self._write_patched_file,
        )
        write_button.pack(side="left")
        self._action_buttons.append(write_button)

        ttk.Label(frame, text="Result / validation:").grid(
            row=4, column=0, sticky="nw", pady=(6, 4)
        )
        self._patch_result_text = tk.Text(
            frame,
            height=12,
            wrap="word",
            bg="#252536",
            fg="#e6e6f0",
            insertbackground="#e6e6f0",
            state="disabled",
        )
        self._patch_result_text.grid(row=5, column=0, columnspan=3, sticky="nsew")
        scrollbar = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=self._patch_result_text.yview)
        self._patch_result_text.configure(yscrollcommand=scrollbar.set)
        scrollbar.grid(row=5, column=3, sticky="ns")

    def _build_logs_tab(self, notebook: ttk.Notebook) -> None:
        frame = ttk.Frame(notebook, padding=16)
        notebook.add(frame, text="Logs")
        frame.rowconfigure(1, weight=1)
        frame.columnconfigure(0, weight=1)

        controls = ttk.Frame(frame)
        controls.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        ttk.Button(controls, text="Clear logs", command=self._clear_log).pack(side="left")
        ttk.Checkbutton(
            controls,
            text="Auto-scroll",
            variable=self._autoscroll_var,
        ).pack(side="left", padx=(12, 0))

        self._log_text = scrolledtext.ScrolledText(
            frame,
            wrap="word",
            bg="#161622",
            fg="#d6d6e6",
            insertbackground="#d6d6e6",
            state="disabled",
        )
        self._log_text.grid(row=1, column=0, sticky="nsew")
        for tag, color in (
            ("info", "#9cdcfe"),
            ("ok", "#8ce99a"),
            ("warn", "#ffd43b"),
            ("fail", "#ff8787"),
            ("debug", "#b197fc"),
            ("step", "#74c0fc"),
        ):
            self._log_text.tag_configure(tag, foreground=color)

    # -------------------------------------------------------------- Helpers --
    def _browse_open_file(
        self,
        variable: tk.StringVar,
        title: str,
        filetypes: tuple[tuple[str, str], ...],
    ) -> None:
        path = filedialog.askopenfilename(
            parent=self, title=title, initialdir=ROOT, filetypes=filetypes
        )
        if path:
            variable.set(path)

    def _browse_save_file(
        self,
        variable: tk.StringVar,
        title: str,
        filetypes: tuple[tuple[str, str], ...],
    ) -> None:
        path = filedialog.asksaveasfilename(
            parent=self,
            title=title,
            initialdir=ROOT,
            filetypes=filetypes,
            defaultextension=".bin",
        )
        if path:
            variable.set(path)

    def _confirm_typed(self, title: str, prompt: str, expected: str) -> bool:
        value = simpledialog.askstring(title, prompt, parent=self, show="*")
        return value == expected

    def _set_status(self, message: str) -> None:
        self._status_var.set(message)

    def _set_session_controls(self, active: bool) -> None:
        self._start_button.configure(state="disabled" if active else "normal")
        self._stop_button.configure(state="normal" if active else "disabled")
        for button in self._action_buttons:
            button.configure(state="normal" if active else "disabled")

    def _set_patch_result(self, data: dict[str, Any]) -> None:
        text = json.dumps(data, indent=2, ensure_ascii=False, default=str)
        self._patch_result_text.configure(state="normal")
        self._patch_result_text.delete("1.0", tk.END)
        self._patch_result_text.insert(tk.END, text)
        self._patch_result_text.configure(state="disabled")

    def _append_log(self, message: str, tag: str = "log") -> None:
        self._log_text.configure(state="normal")
        self._log_text.insert(tk.END, message + "\n", tag)
        self._log_line_count += 1
        if self._log_line_count > 2000:
            self._log_text.delete("1.0", "500.0")
            self._log_line_count -= 500
        if self._autoscroll_var.get():
            self._log_text.see(tk.END)
        self._log_text.configure(state="disabled")

    def _clear_log(self) -> None:
        self._log_text.configure(state="normal")
        self._log_text.delete("1.0", tk.END)
        self._log_text.configure(state="disabled")
        self._log_line_count = 0

    @staticmethod
    def _format_size(size: int) -> str:
        value = float(size)
        for unit in ("B", "KiB", "MiB", "GiB"):
            if value < 1024 or unit == "GiB":
                return f"{value:.1f} {unit}" if unit != "B" else f"{int(value)} B"
            value /= 1024
        return f"{size} B"

    @staticmethod
    def _event_tag(kind: str) -> str:
        return {
            "ok": "ok",
            "fail": "fail",
            "warn": "warn",
            "info": "info",
            "debug": "debug",
            "step": "step",
        }.get(kind, "log")

    # ------------------------------------------------------------- Session --
    def _start_session(self) -> None:
        if self.session is not None and self.session.is_running:
            messagebox.showinfo("Session", "A session is already running.", parent=self)
            return

        python_exe = python_executable()
        runner = session_runner_path()
        if not runner.is_file():
            messagebox.showerror("Session", f"Runner not found:\n{runner}", parent=self)
            return

        mode = self._mode_var.get().strip().lower() or "brom"
        loader = self._loader_var.get().strip() or None
        auth = self._auth_var.get().strip() or None
        session = BromSession(
            python_exe,
            runner,
            cwd=runtime_lib(),
            env={"PYTHONPATH": str(runtime_lib())},
        )
        try:
            session.start(mode=mode, loader=loader, auth=auth, debug=self._debug_var.get())
        except (OSError, RuntimeError, ValueError) as exc:
            messagebox.showerror("Session", f"Could not start runner:\n{exc}", parent=self)
            return

        self.session = session
        self._set_session_controls(True)
        self._set_status(f"Runner started in {mode} mode; waiting for device…")
        self._append_log(
            "Session started. Connect only a device you own or are authorized to service.", "info"
        )

    def _stop_session(self) -> None:
        if self.session is None:
            return
        try:
            self.session.stop()
            self._append_log("Stop requested.", "warn")
        except Exception as exc:  # pragma: no cover - defensive UI handling
            self._append_log(f"Stop failed: {exc}", "fail")

    def _require_session(self) -> bool:
        if self.session is None or not self.session.is_running:
            messagebox.showwarning("Session", "Start a BROM session first.", parent=self)
            return False
        return True

    def _require_partition(self) -> str | None:
        partitions = self._selected_partitions()
        if not partitions:
            messagebox.showwarning("Partitions", "Select a partition first.", parent=self)
            return None
        return partitions[0]

    def _send_command(self, command: dict[str, Any]) -> bool:
        if not self._require_session() or self.session is None:
            return False
        try:
            self.session.send(command)
            return True
        except (OSError, RuntimeError, TypeError, ValueError) as exc:
            messagebox.showerror("Session", f"Could not send command:\n{exc}", parent=self)
            return False

    def _selected_partitions(self) -> list[str]:
        return [
            self._iid_to_part[iid]["name"]
            for iid in self._part_tree.selection()
            if iid in self._iid_to_part
        ]

    def _update_selected_label(self) -> None:
        names = self._selected_partitions()
        if not names:
            self._selected_var.set("No partition selected")
        elif len(names) == 1:
            self._selected_var.set(f"Selected: {names[0]}")
        else:
            self._selected_var.set(f"Selected {len(names)} partitions")

    def _populate_partitions(self, parts: list[dict[str, Any]]) -> None:
        self._part_tree.delete(*self._part_tree.get_children())
        self._iid_to_part.clear()
        self._last_parts = [part for part in parts if isinstance(part, dict)]
        for index, part in enumerate(
            sorted(self._last_parts, key=lambda item: str(item.get("name", "")))
        ):
            name = str(part.get("name", "")).strip()
            if not name:
                continue
            try:
                size = int(part.get("size", 0))
            except (TypeError, ValueError):
                size = 0
            try:
                sectors = int(part.get("sectors", 0))
            except (TypeError, ValueError):
                sectors = 0
            iid = f"part-{index}"
            tags = ("dangerous",) if is_dangerous_partition(name) else ()
            self._part_tree.insert(
                "",
                tk.END,
                iid=iid,
                values=(name, self._format_size(size), f"{sectors:,}"),
                tags=tags,
            )
            self._iid_to_part[iid] = {"name": name, "size": size, "sectors": sectors}
        self._update_selected_label()

    def _refresh_partitions(self) -> None:
        self._populate_partitions(self._last_parts)
        self._set_status(f"Partition view refreshed ({len(self._last_parts)} entries).")

    def _read_partition(self) -> None:
        part = self._require_partition()
        if part is None or not self._require_session():
            return
        output = filedialog.asksaveasfilename(
            parent=self,
            title="Save partition dump",
            initialdir=ROOT,
            initialfile=f"{part}.bin",
            filetypes=BINARY_FILES,
            defaultextension=".bin",
        )
        if not output:
            return
        if self._send_command({"op": "read", "part": part, "out": output}):
            self._append_log(f"Requested read of {part} -> {output}", "step")

    def _write_partition(self) -> None:
        part = self._require_partition()
        if part is None or not self._require_session():
            return
        source = filedialog.askopenfilename(
            parent=self, title="Select file to write", initialdir=ROOT, filetypes=BINARY_FILES
        )
        if not source:
            return
        if Path(source).stat().st_size == 0:
            messagebox.showerror("Write", "The selected file is empty.", parent=self)
            return
        if is_dangerous_partition(part) and not self._confirm_typed(
            "Critical partition",
            f"Writing {part} can brick the device.\nType WRITE to continue.",
            "WRITE",
        ):
            return
        if not messagebox.askyesno(
            "Write partition",
            f"Write {source}\nto partition {part}?",
            parent=self,
        ):
            return
        if self._send_command({"op": "write", "part": part, "in": source}):
            self._append_log(f"Requested write of {part} <- {source}", "warn")

    def _write_patched_file(self) -> None:
        part = self._require_partition()
        if part is None or not self._require_session():
            return
        source = self._last_patched_file
        if source is None or not source.is_file():
            chosen = filedialog.askopenfilename(
                parent=self,
                title="Select patched file",
                initialdir=ROOT,
                filetypes=BINARY_FILES,
            )
            if not chosen:
                return
            source = Path(chosen)
        if is_dangerous_partition(part) and not self._confirm_typed(
            "Critical partition",
            f"Writing {part} can brick the device.\nType WRITE to continue.",
            "WRITE",
        ):
            return
        if not messagebox.askyesno(
            "Write patched file",
            f"Write {source}\nto partition {part}?",
            parent=self,
        ):
            return
        if self._send_command({"op": "write", "part": part, "in": str(source)}):
            self._append_log(f"Requested write of patched file to {part}", "warn")

    def _erase_partitions(self) -> None:
        parts = self._selected_partitions()
        if not parts:
            messagebox.showwarning("Erase", "Select at least one partition.", parent=self)
            return
        errors = validate_erase_targets(parts)
        if errors:
            messagebox.showerror("Erase refused", "\n".join(errors), parent=self)
            return
        if not self._confirm_typed(
            "Erase partitions",
            "Type ERASE to confirm erasing:\n" + ", ".join(parts),
            "ERASE",
        ):
            return
        if self._send_command({"op": "erase", "parts": parts}):
            self._append_log("Requested erase: " + ", ".join(parts), "warn")

    def _reboot(self) -> None:
        if not self._require_session():
            return
        if not messagebox.askyesno("Reboot", "Send reboot command to the device?", parent=self):
            return
        if self._send_command({"op": "reboot"}):
            self._append_log("Requested device reboot.", "step")

    # --------------------------------------------------------------- Patch --
    def _validate_patch(self) -> None:
        source = Path(self._input_var.get())
        patches = Path(self._patches_var.get())
        if not source.is_file() or not patches.is_file():
            messagebox.showerror(
                "Patch", "Select both an input file and a patches JSON file.", parent=self
            )
            return
        try:
            plan = load_patch_document(patches)
            errors = validate_plan(plan, source.stat().st_size)
        except (PatchError, OSError) as exc:
            self._set_patch_result({"error": str(exc)})
            self._set_status("Patch validation failed.")
            return

        result: dict[str, Any] = {
            "input": str(source),
            "size": source.stat().st_size,
            "entries": plan.entry_count,
            "writes": plan.write_count,
            "errors": errors,
            "plan": plan.to_dict(),
        }
        self._set_patch_result(result)
        self._set_status("Patch plan valid." if not errors else "Patch plan has errors.")

    def _apply_patch(self) -> None:
        source = Path(self._input_var.get())
        patches = Path(self._patches_var.get())
        output = Path(self._output_var.get())
        if not source.is_file() or not patches.is_file() or not output.name:
            messagebox.showerror(
                "Patch",
                "Select an input file, a patches JSON file, and an output path.",
                parent=self,
            )
            return
        try:
            plan = load_patch_document(patches)
            result = patch_file(source, output, plan)
        except (PatchError, OSError) as exc:
            messagebox.showerror("Patch", f"Could not apply patch:\n{exc}", parent=self)
            self._set_patch_result({"error": str(exc)})
            self._set_status("Patch failed.")
            return

        self._last_patched_file = Path(result.output_path)
        self._set_patch_result(result.to_dict())
        status = (
            f"Patched file written; {result.changed_bytes} bytes changed; "
            f"SHA-256 {result.output_sha256[:12]}…"
        )
        self._set_status(status)
        messagebox.showinfo(
            "Patch applied",
            f"Output: {result.output_path}\nChanged bytes: {result.changed_bytes}",
            parent=self,
        )

    # -------------------------------------------------------------- Events --
    def _handle_event(self, event: RunnerEvent) -> None:
        tag = self._event_tag(event.kind)
        prefix = f"[{event.kind.upper()}] " if event.kind != "log" else ""
        self._append_log(prefix + event.message, tag)

        if event.kind == "ready":
            payload = event.payload or {}
            parts = payload.get("partitions", [])
            if not isinstance(parts, list):
                parts = []
            self._populate_partitions(parts)
            chip = payload.get("chip", "MediaTek")
            self._set_status(f"Connected: {chip}; {len(self._last_parts)} partitions.")
        elif event.kind == "exit":
            self.session = None
            self._set_session_controls(False)
            self._set_status("Runner stopped.")
        elif event.kind in {"ok", "fail", "step", "warn"}:
            self._set_status(event.message)

    def _poll_events(self) -> None:
        if self._closing:
            return
        session = self.session
        if session is not None:
            while True:
                try:
                    event = session.events.get_nowait()
                except queue.Empty:
                    break
                self._handle_event(event)
        self.after(100, self._poll_events)

    def _on_close(self) -> None:
        self._closing = True
        self._stop_session()
        self.destroy()


def main() -> None:
    try:
        app = BestMDMToolApp()
    except tk.TclError as exc:
        raise SystemExit(f"Cannot start GUI: {exc}") from exc
    app.mainloop()


if __name__ == "__main__":
    main()
