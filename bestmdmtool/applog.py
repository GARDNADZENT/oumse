"""On-disk logging and crash reports.

A windowed build has no console, so anything worth investigating has to land in
a file. Every activity-log line is mirrored here, and an unexpected exception
produces a timestamped crash report plus a dialog instead of a vanished window.
"""

from __future__ import annotations

import logging
import os
import platform
import sys
import traceback
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path

from .branding import PRODUCT_NAME, PRODUCT_VERSION

LOGGER_NAME = "bestmdmtool"
_MAX_BYTES = 1_000_000
_BACKUPS = 3


def log_dir() -> Path:
    """Return the per-user log directory, creating it if needed."""
    override = os.environ.get("BESTMDMTOOL_LOG_DIR")
    if override:
        directory = Path(override).expanduser()
    elif os.name == "nt":
        base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA") or str(Path.home())
        directory = Path(base) / PRODUCT_NAME / "logs"
    else:
        directory = Path.home() / ".local" / "share" / PRODUCT_NAME / "logs"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def log_path() -> Path:
    return log_dir() / "activity.log"


def configure(level: str = "INFO") -> Path:
    """Attach a rotating file handler to the application logger."""
    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    target = log_path()

    for handler in list(logger.handlers):
        if isinstance(handler, RotatingFileHandler):
            logger.removeHandler(handler)
            handler.close()

    handler = RotatingFileHandler(target, maxBytes=_MAX_BYTES, backupCount=_BACKUPS, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)-7s %(message)s", "%Y-%m-%d %H:%M:%S"))
    logger.addHandler(handler)
    logger.propagate = False
    logger.info("=== %s %s starting on %s ===", PRODUCT_NAME, PRODUCT_VERSION, platform.platform())
    return target


def record(message: str, level: str = "INFO") -> None:
    """Mirror one activity-log line into the file log."""
    logger = logging.getLogger(LOGGER_NAME)
    if not logger.handlers:
        return
    mapped = {
        "ERROR": logging.ERROR,
        "WARN": logging.WARNING,
        "DEBUG": logging.DEBUG,
        "OK": logging.INFO,
        "STEP": logging.INFO,
    }.get((level or "INFO").upper(), logging.INFO)
    logger.log(mapped, message)


def write_crash(details: str | None = None) -> Path:
    """Write a crash report and return its path."""
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    target = log_dir() / ("crash-%s.log" % stamp)
    body = details if details is not None else traceback.format_exc()
    header = [
        "%s %s crash report" % (PRODUCT_NAME, PRODUCT_VERSION),
        "when: %s" % datetime.now().isoformat(timespec="seconds"),
        "python: %s" % sys.version.replace("\n", " "),
        "platform: %s" % platform.platform(),
        "frozen: %s" % bool(getattr(sys, "frozen", False)),
        "-" * 60,
    ]
    try:
        target.write_text("\n".join(header) + "\n" + body + "\n", encoding="utf-8")
    except OSError:
        return log_path()
    logging.getLogger(LOGGER_NAME).error("crash report written to %s", target)
    return target


def open_log_folder() -> None:
    """Open the log folder in the platform file manager."""
    directory = str(log_dir())
    if os.name == "nt":
        os.startfile(directory)  # type: ignore[attr-defined]  # noqa: S606
    elif sys.platform == "darwin":
        os.system("open '%s'" % directory)  # noqa: S605
    else:
        os.system("xdg-open '%s'" % directory)  # noqa: S605
