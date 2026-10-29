"""Product configuration for BestMDMTool."""

from __future__ import annotations

from servicecore.config import ROOT, python_executable, runtime_lib, session_runner_path

from .branding import PRODUCT_NAME

PRODUCT_ROOT = ROOT

__all__ = [
    "PRODUCT_NAME",
    "PRODUCT_ROOT",
    "ROOT",
    "python_executable",
    "runtime_lib",
    "session_runner_path",
]
