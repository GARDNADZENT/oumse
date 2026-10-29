"""Path and runtime resolution shared by both front-ends."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from functools import lru_cache
from pathlib import Path

RUNNER_EXE_NAME = "BestMDMToolRunner.exe"


def _detect_root() -> Path:
    """Locate the application root for source checkouts and frozen builds."""
    override = os.environ.get("BESTMDMTOOL_ROOT") or os.environ.get("OUMSE_ROOT")
    if override:
        return Path(override).expanduser().resolve()

    if getattr(sys, "frozen", False):
        # PyInstaller layout: <app>\BestMDMTool\BestMDMTool.exe
        exe_dir = Path(sys.executable).resolve().parent
        for candidate in (exe_dir, exe_dir.parent, exe_dir.parent.parent, exe_dir.parent.parent.parent):
            if (candidate / "runtime" / "lib").is_dir():
                return candidate
        return exe_dir.parent

    return Path(__file__).resolve().parents[1]


ROOT = _detect_root()
RUNTIME_DIR = ROOT / "runtime"
LIB_DIR = RUNTIME_DIR / "lib"
BIN_DIR = RUNTIME_DIR / "bin"

DEFAULT_PYTHON = BIN_DIR / "python.exe"
SESSION_RUNNER = LIB_DIR / "oumse_brom_session_runner.py"
ONE_SHOT_RUNNER = LIB_DIR / "oumse_brom_runner.py"
SERVICE_RUNNER = ROOT / "servicecore" / "runner" / "service_runner.py"


def _override(name: str, default: Path) -> Path:
    raw = os.environ.get(name)
    return Path(raw).expanduser() if raw else default


@lru_cache(maxsize=8)
def _python_is_usable(candidate: str) -> bool:
    """True when the interpreter can load its C extension modules.

    The vendored ``runtime/bin`` Python ships without any ``*.pyd`` files, so
    binary modules such as hashlib/zlib fail to import and mtkclient cannot run.
    """
    try:
        result = subprocess.run(
            [candidate, "-c", "import hashlib, zlib, ctypes"],
            capture_output=True,
            timeout=15,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return result.returncode == 0


def python_executable() -> Path:
    """Return an interpreter that can actually run the device runners."""
    override = os.environ.get("OUMSE_PYTHON") or os.environ.get("SVC_PYTHON")
    if override:
        return Path(override).expanduser()

    if DEFAULT_PYTHON.exists() and _python_is_usable(str(DEFAULT_PYTHON)):
        return DEFAULT_PYTHON

    for name in ("python.exe", "python", "python3"):
        found = shutil.which(name)
        if found and _python_is_usable(found):
            return Path(found)

    if not getattr(sys, "frozen", False) and _python_is_usable(sys.executable):
        return Path(sys.executable)
    return DEFAULT_PYTHON


def frozen_runner_path() -> Path | None:
    """Return the packaged service runner executable, if present.

    The frozen runner bundles a complete CPython, so it does not depend on the
    stripped ``runtime/bin`` interpreter.
    """
    override = os.environ.get("SVC_RUNNER_EXE")
    if override:
        candidate = Path(override).expanduser()
        if candidate.is_file():
            return candidate

    candidates = (
        RUNTIME_DIR / "runner" / RUNNER_EXE_NAME,
        RUNTIME_DIR / "bin" / RUNNER_EXE_NAME,
        ROOT / "installer-bestmdmtool" / "frozen" / "BestMDMToolRunner" / RUNNER_EXE_NAME,
    )
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None


def runner_command() -> tuple[list[str], Path]:
    """Return ``(argv, cwd)`` for launching the device runner."""
    frozen = frozen_runner_path()
    if frozen is not None:
        return [str(frozen)], frozen.parent
    interpreter = python_executable()
    script = service_runner_path()
    return [str(interpreter), "-u", str(script)], script.parent


def session_runner_path() -> Path:
    return _override("OUMSE_SESSION_RUNNER", SESSION_RUNNER)


def one_shot_runner_path() -> Path:
    return _override("OUMSE_ONE_SHOT_RUNNER", ONE_SHOT_RUNNER)


def service_runner_path() -> Path:
    """Path to the superset runner used by the BestMDMTool interface."""
    return _override("BESTMDMTOOL_RUNNER", SERVICE_RUNNER)


def bundled_python() -> Path | None:
    """Return the bundled runtime interpreter when it is usable."""
    candidate = DEFAULT_PYTHON
    if candidate.exists() and _python_is_usable(str(candidate)):
        return candidate
    return None


def runtime_lib() -> Path:
    return LIB_DIR
