#!/usr/bin/env python3
"""Build a portable ZIP of the no-login application.

This is not a Windows installer; it is a cross-platform packaging helper for
users who prefer a portable copy. The Inno Setup project produces the real
Windows .exe installer.
"""

from __future__ import annotations

import argparse
import hashlib
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INSTALLER_DIR = Path(__file__).resolve().parent
VERSION = (INSTALLER_DIR / "version.txt").read_text(encoding="utf-8").strip()
DEFAULT_OUTPUT = INSTALLER_DIR / "artifacts"

EXCLUDE_DIR_NAMES = {
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    "logs",
    "Scripts",
}
EXCLUDE_FILE_NAMES = {
    "get-pip.py",
    "hwparam.json",
    "python",
    "python312._pth",
}
EXCLUDE_SUFFIXES = {".pyc", ".pyo", ".log", ".bak", ".tmp"}

PORTABLE_README = """Oumse GSM Tool Pro - Community Edition (No Login)
=================================================

This is a portable copy. No installation is required.

Windows:
  1. Install Python 3.10 or newer with Tkinter.
  2. Double-click START_NO_LOGIN.bat, or run: py -3 -m app

Linux/macOS development only:
  ./run_gui.sh

The bundled runtime/bin Python is used for the headless BROM runner and does
not need Tkinter. This package intentionally contains no login, licensing,
heartbeat, or telemetry code. The legacy compiled client is not included.
"""


def should_exclude(path: Path) -> bool:
    if path.is_dir() and path.name in EXCLUDE_DIR_NAMES:
        return True
    if path.is_file():
        if path.name in EXCLUDE_FILE_NAMES:
            return True
        if path.suffix.lower() in EXCLUDE_SUFFIXES:
            return True
        if any(part in EXCLUDE_DIR_NAMES for part in path.parts[:-1]):
            return True
    return False


def add_file(archive: zipfile.ZipFile, source: Path, arcname: str, seen: set[str]) -> None:
    normalized = arcname.replace("\\", "/")
    if normalized in seen:
        return
    seen.add(normalized)
    archive.write(source, normalized)


def add_tree(
    archive: zipfile.ZipFile,
    source_dir: Path,
    arc_prefix: str,
    seen: set[str],
) -> None:
    for path in sorted(source_dir.rglob("*")):
        if should_exclude(path):
            continue
        if not path.is_file():
            continue
        relative = path.relative_to(source_dir)
        arcname = str(Path(arc_prefix) / relative)
        add_file(archive, path, arcname, seen)


def build(output_dir: Path) -> tuple[Path, str, int]:
    output_dir.mkdir(parents=True, exist_ok=True)
    archive_path = output_dir / f"OumseNoLogin-Portable-{VERSION}.zip"
    if archive_path.exists():
        archive_path.unlink()

    seen: set[str] = set()
    with zipfile.ZipFile(
        archive_path,
        "w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=6,
    ) as archive:
        add_tree(archive, ROOT / "app", "app", seen)
        add_tree(archive, ROOT / "servicecore", "servicecore", seen)
        add_tree(archive, ROOT / "runtime" / "bin", "runtime/bin", seen)
        add_tree(archive, ROOT / "runtime" / "lib", "runtime/lib", seen)
        add_tree(archive, ROOT / "Bin", "Bin", seen)
        add_tree(archive, ROOT / "adb_assets", "adb_assets", seen)
        add_tree(archive, ROOT / "certifi", "certifi", seen)
        add_tree(archive, INSTALLER_DIR / "launcher", "launcher", seen)

        # Override the stale developer-machine _pth with a portable one.
        add_file(
            archive,
            INSTALLER_DIR / "runtime" / "python312._pth",
            "runtime/bin/python312._pth",
            seen,
        )

        single_files = {
            "README.md": "README.md",
            "SECURITY.md": "SECURITY.md",
            "PROJECT_ANALYSIS.md": "PROJECT_ANALYSIS.md",
            "requirements.txt": "requirements.txt",
            "requirements-dev.txt": "requirements-dev.txt",
            "pyproject.toml": "pyproject.toml",
            "app_icon.ico": "app_icon.ico",
            "START_NO_LOGIN.bat": "START_NO_LOGIN.bat",
            "run_gui.sh": "run_gui.sh",
        }
        for source_name, arcname in single_files.items():
            source = ROOT / source_name
            if source.is_file():
                add_file(archive, source, arcname, seen)

        add_file(archive, INSTALLER_DIR / "README.md", "INSTALLER.md", seen)
        add_file(archive, INSTALLER_DIR / "version.txt", "VERSION.txt", seen)
        add_file(archive, ROOT / "runtime" / "lib" / "LICENSE", "LICENSE-mtkclient.txt", seen)

        archive.writestr("PORTABLE_README.txt", PORTABLE_README)

    digest = hashlib.sha256(archive_path.read_bytes()).hexdigest()
    (output_dir / f"{archive_path.name}.sha256").write_text(
        f"{digest}  {archive_path.name}\n", encoding="utf-8"
    )
    return archive_path, digest, len(seen)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"Output directory (default: {DEFAULT_OUTPUT})",
    )
    args = parser.parse_args()
    archive_path, digest, file_count = build(args.output)
    size_mib = archive_path.stat().st_size / (1024 * 1024)
    print(f"Built: {archive_path}")
    print(f"Files: {file_count}")
    print(f"Size:  {size_mib:.2f} MiB")
    print(f"SHA256: {digest}")


if __name__ == "__main__":
    main()
