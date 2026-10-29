"""Client for the persistent MTK service runner (``servicecore/runner``).

The GUI never talks to USB directly: it starts ``service_runner.py`` with the
bundled runtime Python and exchanges one JSON command per line, exactly like the
existing BROM session runner, but with a wider operation set.

Protocol (see ``servicecore/runner/service_runner.py``)::

    SVC_STEP / SVC_PROGRESS / SVC_LOG / SVC_INFO
    SVC_READY / SVC_OK / SVC_FAIL / SVC_DATA / SVC_BYE
"""

from __future__ import annotations

import json
import os
import queue
import subprocess
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .config import ROOT


@dataclass(frozen=True, slots=True)
class ServiceEvent:
    kind: str
    topic: str = ""
    message: str = ""
    payload: Any = None


@dataclass(slots=True)
class CommandResult:
    """Result of a single runner command."""

    op: str
    ok: bool
    detail: str = ""
    data: bytes = b""
    duration: float = 0.0
    events: list[ServiceEvent] = field(default_factory=list)


class ServiceSession:
    """Owns one ``service_runner.py`` process."""

    def __init__(
        self,
        python_exe: str | Path,
        runner_path: str | Path,
        *,
        cwd: str | Path | None = None,
        env: dict[str, str] | None = None,
    ) -> None:
        self.python_exe = Path(python_exe)
        self.runner_path = Path(runner_path)
        self.cwd = Path(cwd) if cwd else self.runner_path.parent
        self.env = dict(env or {})
        self.events: queue.Queue[ServiceEvent] = queue.Queue()
        self.device: dict[str, Any] = {}
        self.partitions: list[dict[str, Any]] = []
        self._proc: subprocess.Popen[str] | None = None
        self._reader: threading.Thread | None = None
        self._lock = threading.Lock()
        self._pending: dict[str, list[ServiceEvent]] = {}
        self._done: dict[str, CommandResult] = {}
        self._cond = threading.Condition()
        self._ready = threading.Event()
        self._finished = threading.Event()
        self._raw: list[str] = []
        self.last_error = ""

    # -- lifecycle ---------------------------------------------------------
    @property
    def is_running(self) -> bool:
        return self._proc is not None and self._proc.poll() is None

    def start(
        self,
        *,
        mode: str = "brom",
        loader: str | Path | None = None,
        auth: str | Path | None = None,
        transport: str = "auto",
        debug: bool = False,
        wait: float = 180.0,
        extra_env: dict[str, str] | None = None,
    ) -> bool:
        if self.is_running:
            raise RuntimeError("A device session is already running.")

        packaged = self.runner_path.suffix.lower() == ".exe"
        if packaged:
            if not self.runner_path.is_file():
                raise FileNotFoundError("Runner executable not found: %s" % self.runner_path)
            command = [str(self.runner_path)]
        else:
            if not self.python_exe.exists():
                raise FileNotFoundError("Python executable not found: %s" % self.python_exe)
            if not self.runner_path.is_file():
                raise FileNotFoundError("Runner not found: %s" % self.runner_path)
            command = [str(self.python_exe), "-u", str(self.runner_path)]

        popen_env = os.environ.copy()
        popen_env.update(self.env)
        popen_env["PYTHONUNBUFFERED"] = "1"
        popen_env["PYTHONIOENCODING"] = "utf-8"
        popen_env["SVC_BROM_MODE"] = mode
        popen_env["SVC_BROM_TRANSPORT"] = transport
        if loader:
            popen_env["SVC_MTK_LOADER"] = str(loader)
        else:
            popen_env.pop("SVC_MTK_LOADER", None)
        if auth:
            popen_env["SVC_MTK_AUTH"] = str(auth)
        else:
            popen_env.pop("SVC_MTK_AUTH", None)
        popen_env["SVC_LOG_DEBUG"] = "1" if debug else "0"
        for key, value in (extra_env or {}).items():
            if value is None:
                popen_env.pop(key, None)
            else:
                popen_env[str(key)] = str(value)
        # Tell the runner where the vendored runtime and DA loaders live.
        popen_env.setdefault("SVC_ROOT", str(ROOT))

        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        try:
            self._proc = subprocess.Popen(
                command,
                cwd=str(self.cwd),
                env=popen_env,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
                creationflags=creationflags,
            )
        except OSError as exc:
            self._proc = None
            self.last_error = "cannot start runner (%s): %s" % (command[0], exc)
            return False
        self._ready.clear()
        self._finished.clear()
        self.last_error = ""
        self._reader = threading.Thread(target=self._read_loop, name="svc-reader", daemon=True)
        self._reader.start()

        # Wait for a real SVC_READY, but stop immediately if the runner dies.
        deadline = time.monotonic() + wait
        while time.monotonic() < deadline:
            if self._ready.is_set() and self.is_running:
                return True
            if self._finished.is_set() or self._proc.poll() is not None:
                break
            self._ready.wait(0.2)
        if self._ready.is_set() and self.is_running:
            return True

        # The runner exited (or never reached READY): keep the log tail so the
        # caller can show the real reason instead of a blank "connected" state.
        self.last_error = self._failure_hint()
        self.stop()
        return False

    def stop(self, *, reboot: bool = False, timeout: float = 5.0) -> None:
        proc = self._proc
        if proc is None:
            return
        if proc.poll() is None:
            try:
                if reboot:
                    self.send({"op": "reboot"}, wait=60.0)
                else:
                    self.send({"op": "quit"}, wait=2.0)
            except Exception:
                pass
            try:
                proc.wait(timeout=timeout)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass
        self._close_streams(proc)
        if self._proc is proc:
            self._proc = None

    @staticmethod
    def _close_streams(proc: subprocess.Popen) -> None:
        """Release the pipes so a failed start never leaks file handles."""
        for stream in (proc.stdin, proc.stdout):
            try:
                if stream is not None:
                    stream.close()
            except Exception:
                pass

    # -- io ----------------------------------------------------------------
    def _read_loop(self) -> None:
        proc = self._proc
        if proc is None or proc.stdout is None:
            return
        try:
            for raw in proc.stdout:
                line = raw.rstrip("\n")
                if not line:
                    continue
                self._raw.append(line)
                del self._raw[:-500]
                event = self._parse(line)
                self.events.put(event)
                self._dispatch(event)
        except (ValueError, OSError):
            # The pipe was closed while shutting down; nothing left to read.
            pass
        finally:
            self._finished.set()
        with self._cond:
            self._cond.notify_all()

    @staticmethod
    def _parse(line: str) -> ServiceEvent:
        if not line.startswith("SVC_"):
            return ServiceEvent("raw", message=line)
        head, _, rest = line.partition(":")
        kind = head[4:].lower()
        if kind == "ready":
            try:
                return ServiceEvent("ready", payload=json.loads(rest))
            except Exception:
                return ServiceEvent("ready", message=rest)
        if kind == "data":
            # SVC_DATA carries a bare hex payload, no topic field.
            return ServiceEvent("data", message=rest)
        if kind in ("step", "progress", "log", "info", "ok", "fail"):
            topic, _, message = rest.partition(":")
            if kind == "log":
                level, _, text = rest.partition(":")
                return ServiceEvent("log", level if level else "INFO", text)
            return ServiceEvent(kind, topic, message)
        if kind == "bye":
            return ServiceEvent("bye")
        return ServiceEvent(kind, message=rest)

    def _dispatch(self, event: ServiceEvent) -> None:
        with self._cond:
            if event.kind == "ready":
                payload = event.payload if isinstance(event.payload, dict) else {}
                self._ready.set()
                # Keep every field the runner sent (engine, version, transport,
                # flash size ...); the UI decides which ones it shows.
                self.device = {key: value for key, value in payload.items() if key != "partitions"}
                self.device.setdefault("chip", "")
                self.partitions = list(payload.get("partitions") or [])
            if event.kind == "data":
                # SVC_DATA carries the peek payload; it is the completion signal.
                try:
                    payload = bytes.fromhex(event.message) if event.message else b""
                except ValueError:
                    payload = b""
                self._pending.setdefault("peek", []).append(event)
                self._done["peek"] = CommandResult(op="peek", ok=True, data=payload)
                self._cond.notify_all()
                return
            if event.kind in ("ok", "fail"):
                op = event.topic
                if event.kind == "ok" and op == "peek":
                    # Wait for SVC_DATA rather than completing with an empty body.
                    self._pending.setdefault(op, []).append(event)
                    return
                self._pending.setdefault(op, []).append(event)
                self._done[op] = CommandResult(
                    op=op, ok=event.kind == "ok", detail=event.message, data=b""
                )
                self._cond.notify_all()
                return

    # -- commands ----------------------------------------------------------
    def send(self, command: dict[str, Any], *, wait: float | None = None) -> CommandResult | None:
        proc = self._proc
        if proc is None or proc.stdin is None or proc.poll() is not None:
            raise RuntimeError("No device session is running.")
        op = str(command.get("op", "")).strip().lower()
        with self._lock:
            if op:
                with self._cond:
                    self._done.pop(op, None)
                    self._pending.pop(op, None)
            proc.stdin.write(json.dumps(command) + "\n")
            proc.stdin.flush()
        if wait is None:
            return None
        return self.wait(op, timeout=wait)

    def wait(self, op: str, *, timeout: float = 900.0) -> CommandResult:
        started = time.monotonic()
        deadline = started + timeout
        with self._cond:
            while True:
                result = self._done.pop(op, None)
                if result is not None:
                    payload = b""
                    for event in self._pending.pop(op, []):
                        if event.kind == "data" and event.message:
                            try:
                                payload += bytes.fromhex(event.message)
                            except Exception:
                                pass
                    if result.data:
                        payload = result.data
                    return CommandResult(
                        op=op,
                        ok=result.ok,
                        detail=result.detail,
                        data=payload,
                        duration=time.monotonic() - started,
                    )
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return CommandResult(op=op, ok=False, detail="timeout", duration=time.monotonic() - started)
                if self._proc is not None and self._proc.poll() is not None:
                    return CommandResult(op=op, ok=False, detail="runner exited", duration=time.monotonic() - started)
                self._cond.wait(min(remaining, 0.5))

    def run(self, command: dict[str, Any], *, timeout: float = 900.0) -> CommandResult:
        op = str(command.get("op", "")).strip().lower()
        self.send(command)
        return self.wait(op, timeout=timeout)

    # -- typed helpers -----------------------------------------------------
    def info(self, timeout: float = 60.0) -> CommandResult:
        return self.run({"op": "info"}, timeout=timeout)

    def refresh_gpt(self, timeout: float = 180.0) -> list[dict[str, Any]]:
        result = self.run({"op": "gpt"}, timeout=timeout)
        if result.ok:
            try:
                payload = json.loads(result.detail)
                self.partitions = list(payload.get("partitions") or [])
            except Exception:
                pass
        return self.partitions

    def read_partition(self, part: str, out: str, timeout: float = 7200.0) -> CommandResult:
        return self.run({"op": "read", "part": part, "out": out}, timeout=timeout)

    def write_partition(self, part: str, src: str, timeout: float = 7200.0) -> CommandResult:
        return self.run({"op": "write", "part": part, "in": src}, timeout=timeout)

    def erase(self, parts: list[str], timeout: float = 3600.0) -> CommandResult:
        return self.run({"op": "erase", "parts": parts}, timeout=timeout)

    def dump(self, directory: str, parts: list[str] | None = None, timeout: float = 14400.0) -> CommandResult:
        command: dict[str, Any] = {"op": "dump", "dir": directory}
        if parts:
            command["parts"] = parts
        return self.run(command, timeout=timeout)

    def export_gpt(self, out: str, timeout: float = 300.0) -> CommandResult:
        return self.run({"op": "gpt_export", "out": out}, timeout=timeout)

    def read_flash(self, offset: int, length: int, out: str, timeout: float = 7200.0) -> CommandResult:
        return self.run({"op": "readflash", "offset": offset, "length": length, "out": out}, timeout=timeout)

    def write_flash(self, src: str, offset: int, timeout: float = 7200.0) -> CommandResult:
        return self.run({"op": "writeflash", "in": src, "offset": offset}, timeout=timeout)

    def erase_flash(self, offset: int, length: int, timeout: float = 3600.0) -> CommandResult:
        return self.run({"op": "eraseflash", "offset": offset, "length": length}, timeout=timeout)

    def peek(self, addr: int, length: int = 0x100, timeout: float = 120.0) -> CommandResult:
        return self.run({"op": "peek", "addr": addr, "length": length}, timeout=timeout)

    def poke(self, addr: int, data: str, timeout: float = 120.0) -> CommandResult:
        return self.run({"op": "poke", "addr": addr, "data": data}, timeout=timeout)

    def seccfg(self, state: str, timeout: float = 600.0) -> CommandResult:
        return self.run({"op": "seccfg", "state": state}, timeout=timeout)

    def reboot(self, mode: int = 0, timeout: float = 120.0) -> CommandResult:
        return self.run({"op": "reboot", "mode": mode}, timeout=timeout)

    def recent_output(self, limit: int = 200) -> list[str]:
        return self._raw[-limit:]

    def _failure_hint(self) -> str:
        """Explain why the runner stopped before it was ready."""
        interesting = [
            line
            for line in self._raw
            if line.startswith(("SVC_FAIL", "OUMSE_FAIL", "Traceback", "ModuleNotFoundError", "ImportError"))
            or "Error" in line
        ]
        if not interesting:
            interesting = [line for line in self._raw if not line.startswith("SVC_")][-3:]
        if not interesting:
            if self._proc is not None and self._proc.poll() is not None:
                return "runner exited with code %s" % self._proc.returncode
            return "runner stopped before reporting ready"
        return " | ".join(line.strip() for line in interesting[-3:])[:400]


def find_partition(partitions: list[dict[str, Any]], name: str) -> dict[str, Any] | None:
    wanted = (name or "").strip().lower()
    for entry in partitions:
        if str(entry.get("name", "")).lower() == wanted:
            return entry
    return None
