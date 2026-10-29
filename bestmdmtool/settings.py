"""Persistent user settings for BestMDMTool."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path


def settings_dir() -> Path:
    base = os.environ.get("LOCALAPPDATA") or os.environ.get("XDG_CONFIG_HOME")
    if base:
        return Path(base) / "BestMDMTool"
    return Path.home() / ".bestmdmtool"


@dataclass(slots=True)
class Settings:
    mode: str = "brom"
    transport: str = "auto"
    loader: str = ""
    auth: str = ""
    debug_log: bool = False
    confirm_destructive: bool = True
    last_dir: str = ""
    last_image_dir: str = ""
    log_expanded: bool = True
    window_geometry: str = ""
    extra: dict = field(default_factory=dict)

    @classmethod
    def path(cls) -> Path:
        return settings_dir() / "settings.json"

    @classmethod
    def load(cls) -> Settings:
        path = cls.path()
        if not path.is_file():
            return cls()
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return cls()
        known = {field_name for field_name in cls.__dataclass_fields__}
        payload = {key: value for key, value in data.items() if key in known}
        try:
            return cls(**payload)
        except TypeError:
            return cls()

    def save(self) -> None:
        try:
            path = self.path()
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")
        except OSError:
            pass
