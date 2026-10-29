"""Backward-compatible configuration exports for the original no-login app."""

from __future__ import annotations

from servicecore.config import (
    BIN_DIR,
    DEFAULT_PYTHON,
    LIB_DIR,
    ONE_SHOT_RUNNER,
    ROOT,
    RUNTIME_DIR,
    SESSION_RUNNER,
    one_shot_runner_path,
    python_executable,
    runtime_lib,
    session_runner_path,
)

__all__ = [
    "BIN_DIR",
    "DEFAULT_PYTHON",
    "LIB_DIR",
    "ONE_SHOT_RUNNER",
    "ROOT",
    "RUNTIME_DIR",
    "SESSION_RUNNER",
    "one_shot_runner_path",
    "python_executable",
    "runtime_lib",
    "session_runner_path",
]
