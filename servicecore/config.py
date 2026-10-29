from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNTIME_DIR = ROOT / "runtime"
LIB_DIR = RUNTIME_DIR / "lib"
BIN_DIR = RUNTIME_DIR / "bin"

DEFAULT_PYTHON = BIN_DIR / "python.exe"
SESSION_RUNNER = LIB_DIR / "oumse_brom_session_runner.py"
ONE_SHOT_RUNNER = LIB_DIR / "oumse_brom_runner.py"


def _override(name: str, default: Path) -> Path:
    raw = os.environ.get(name)
    return Path(raw).expanduser() if raw else default


def python_executable() -> Path:
    """Return the interpreter used to launch the device runners."""
    candidate = _override("OUMSE_PYTHON", DEFAULT_PYTHON)
    if candidate.exists():
        return candidate
    return Path(sys.executable)


def session_runner_path() -> Path:
    return _override("OUMSE_SESSION_RUNNER", SESSION_RUNNER)


def one_shot_runner_path() -> Path:
    return _override("OUMSE_ONE_SHOT_RUNNER", ONE_SHOT_RUNNER)


def runtime_lib() -> Path:
    return LIB_DIR
