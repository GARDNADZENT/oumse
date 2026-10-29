from __future__ import annotations

import json
import os
import queue
import subprocess
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class RunnerEvent:
    kind: str
    topic: str
    message: str
    payload: dict[str, Any] | None = None


class BromSession:
    """Manage the persistent JSON-over-stdin BROM runner as a subprocess."""

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
        self.events: queue.Queue[RunnerEvent] = queue.Queue()
        self._proc: subprocess.Popen[str] | None = None
        self._reader: threading.Thread | None = None

    @property
    def is_running(self) -> bool:
        return self._proc is not None and self._proc.poll() is None

    def start(
        self,
        *,
        mode: str = "brom",
        loader: str | Path | None = None,
        auth: str | Path | None = None,
        debug: bool = False,
    ) -> None:
        if self.is_running:
            raise RuntimeError("A BROM session is already running.")
        if not self.python_exe.exists():
            raise FileNotFoundError(f"Python executable not found: {self.python_exe}")
        if not self.runner_path.is_file():
            raise FileNotFoundError(f"Runner not found: {self.runner_path}")

        popen_env = os.environ.copy()
        popen_env.update(self.env)
        popen_env["PYTHONUNBUFFERED"] = "1"
        popen_env["PYTHONIOENCODING"] = "utf-8"
        popen_env["OUMSE_BROM_MODE"] = mode
        if loader:
            popen_env["OUMSE_MTK_LOADER"] = str(loader)
        else:
            popen_env.pop("OUMSE_MTK_LOADER", None)
        if auth:
            popen_env["OUMSE_MTK_AUTH"] = str(auth)
        else:
            popen_env.pop("OUMSE_MTK_AUTH", None)
        if debug:
            popen_env["OUMSE_LAB_DEBUG"] = "1"
            popen_env["OUMSE_LOG_DEBUG"] = "1"
        else:
            popen_env.pop("OUMSE_LAB_DEBUG", None)
            popen_env.pop("OUMSE_LOG_DEBUG", None)

        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        self._proc = subprocess.Popen(
            [str(self.python_exe), "-u", str(self.runner_path)],
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
        self._reader = threading.Thread(
            target=self._read_loop,
            name="oumse-runner-reader",
            daemon=True,
        )
        self._reader.start()
        self.events.put(
            RunnerEvent("info", "session", f"Started {self.runner_path.name} in {mode} mode.")
        )

    def _read_loop(self) -> None:
        proc = self._proc
        if proc is None or proc.stdout is None:
            return
        try:
            for line in proc.stdout:
                clean = line.rstrip("\r\n")
                if clean:
                    self.events.put(self._parse_line(clean))
            code = proc.wait()
            self.events.put(RunnerEvent("exit", "session", f"Runner exited with code {code}."))
        except Exception as exc:  # pragma: no cover - defensive subprocess handling
            self.events.put(RunnerEvent("fail", "session", f"Runner reader failed: {exc}"))

    def send(self, command: dict[str, Any]) -> None:
        if not self.is_running or self._proc is None or self._proc.stdin is None:
            raise RuntimeError("BROM session is not running.")
        payload = json.dumps(command, separators=(",", ":"), ensure_ascii=False)
        self._proc.stdin.write(payload + "\n")
        self._proc.stdin.flush()

    def stop(self) -> None:
        if not self.is_running or self._proc is None:
            return
        try:
            self.send({"op": "quit"})
        except Exception:
            pass
        try:
            if self._proc.poll() is None:
                self._proc.terminate()
        except Exception:
            pass
        try:
            if self._proc.stdin is not None:
                self._proc.stdin.close()
        except Exception:
            pass

    @staticmethod
    def _parse_line(line: str) -> RunnerEvent:
        clean = line.strip()
        if clean.startswith("OUMSE_READY:"):
            rest = clean[len("OUMSE_READY:") :].strip()
            try:
                payload = json.loads(rest)
                if not isinstance(payload, dict):
                    raise ValueError("payload is not an object")
            except (json.JSONDecodeError, ValueError) as exc:
                return RunnerEvent("fail", "runner", f"Invalid OUMSE_READY payload: {exc}")
            return RunnerEvent("ready", "runner", "Session ready.", payload)

        if clean.startswith("OUMSE_RESULT:"):
            rest = clean[len("OUMSE_RESULT:") :].strip()
            kind = "fail" if rest.upper().startswith("FAIL") else "ok"
            return RunnerEvent(kind, "runner", rest)

        prefixes = (
            ("OUMSE_OK:", "ok"),
            ("OUMSE_FAIL:", "fail"),
            ("OUMSE_STEP:", "step"),
            ("OUMSE_INFO:", "info"),
            ("OUMSE_WARN:", "warn"),
            ("OUMSE_DBG:", "debug"),
            ("OUMSE_READLEN:", "info"),
            ("OUMSE_PATCHED:", "info"),
        )
        for prefix, kind in prefixes:
            if clean.startswith(prefix):
                return RunnerEvent(kind, "runner", clean[len(prefix) :].strip())
        return RunnerEvent("log", "runner", clean)
