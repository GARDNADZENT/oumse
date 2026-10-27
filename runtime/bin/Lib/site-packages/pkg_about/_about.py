# Copyright (c) 2020 Adam Karpierz
# SPDX-License-Identifier: Zlib

from __future__ import annotations

__all__ = ('about', 'about_from_setup')

import sys
import os
from typing import Any, NamedTuple
from typing_extensions import Self
from pathlib import Path
from functools import partial
from email.utils import getaddresses, parseaddr
if sys.version_info >= (3, 12, 6):
    getaddresses = partial(getaddresses, strict=False)
    parseaddr    = partial(parseaddr,    strict=False)
else: pass  # pragma: no cover
import importlib.metadata as importlib_metadata
import packaging.version
import build.util


class adict(dict[str, Any]):

    def __getattr__(self, name: str) -> Any:
        try:
            return self.__getitem__(name)
        except KeyError as exc:
            raise AttributeError(*exc.args) from None

    def __setattr__(self, name: str, value: Any) -> None:
        try:
            self.__setitem__(name, value)
        except KeyError as exc:  # pragma: no cover
            raise AttributeError(*exc.args) from None

    def __delattr__(self, name: str) -> None:
        try:
            self.__delitem__(name)
        except KeyError as exc:
            raise AttributeError(*exc.args) from None

    def __copy__(self) -> Self:
        return self.__class__(self)

    copy = __copy__


class version_info(NamedTuple):
    major: int
    minor: int
    micro: int
    releaselevel: str
    serial: int | str  # str only if "local" is not None


def about(package: str | None = None) -> adict:
    pkg_globals = sys._getframe(1).f_globals
    pkg_globals.pop("__builtins__", None)
    pkg_globals.pop("__cached__",   None)
    if package is None: package = pkg_globals.get("__package__", None)
    if package is None:  # pragma: no cover
        raise ValueError("A distribution name is required.")

    metadata = importlib_metadata.metadata(package)
    version = packaging.version.parse(importlib_metadata.version(package))

    pkg_metadata = __get_pkg_metadata(version, metadata)

    pkg_globals.update(pkg_metadata)
    pkg_globals.setdefault("__all__", [])
    pkg_globals["__all__"] += list(pkg_metadata.keys())
    pkg_metadata = pkg_metadata.copy()
    pkg_metadata.__metadata__ = metadata
    return pkg_metadata


class __Sentinel: pass     # noqa: E305
__sentinel = __Sentinel()  # noqa: E305

def about_from_setup(package_path: Path | str | int | None
                     | __Sentinel = __sentinel) -> adict:
    no_arg = (package_path is __sentinel)
    level = (1 if no_arg else
             # Potential backward incompatibility.
             # In previous versions, even when None was explicitly provided
             # as the value of 'package_path' (rare), the directory level
             # was set to 1.
             0 if package_path is None else
             package_path if isinstance(package_path, int) else None)
    pkg_globals = sys._getframe(1).f_globals
    if level is not None:
        package_path = Path(pkg_globals["__file__"]).resolve().parents[level]

    assert isinstance(package_path, (str, os.PathLike))

    metadata = build.util.project_wheel_metadata(package_path)
    version = packaging.version.parse(metadata["Version"])

    pkg_metadata = __get_pkg_metadata(version, metadata)

    # Potential backward incompatibility.
    # In previous versions, even when None was explicitly provided
    # as the value of 'package_path' (rare), or when 'package_path'
    # was of type Path | str, 'about' was passed one level up.
    if no_arg:
        pkg_globals["about"] = pkg_metadata
        pkg_globals.setdefault("__all__", [])
        pkg_globals["__all__"].append("about")
        pkg_metadata = pkg_metadata.copy()
    pkg_metadata.__metadata__ = metadata
    return pkg_metadata


def __get_pkg_metadata(version: packaging.version.Version,
                       metadata: importlib_metadata.PackageMetadata) -> adict:
    project_urls = {item.partition(",")[0].strip():
                    item.partition(",")[2].lstrip()
                    for item in metadata.get_all("Project-URL") or []}
    metadata_get = metadata.get  # type: ignore[attr-defined] # mypy bug
    release_levels = __release_levels
    pkg_metadata = adict(
        __title__        = metadata["Name"],
        __version__      = str(version),
        __version_info__ = version_info(
                               major=version.major,
                               minor=version.minor,
                               micro=version.micro,
                               releaselevel=release_levels[
                                   version.pre[0] if version.pre else
                                   "dev"   if version.dev is not None else
                                   "post"  if version.post is not None else
                                   "local" if version.local is not None else
                                   "final"],
                               serial=(
                                   version.pre[1] if version.pre else
                                   version.dev    if version.dev is not None else
                                   version.post   if version.post is not None else
                                   version.local  if version.local is not None else
                                   0)),
        __summary__      = metadata_get("Summary"),
        __uri__          = (metadata_get("Home-page")
                            or project_urls.get("Home-page")
                            or project_urls.get("Homepage")
                            or project_urls.get("Home")),
        __urls__         = adict(project_urls),
        __author__       = metadata_get("Author"),
        __email__        = None,
        __author_email__ = metadata_get("Author-email"),
        __maintainer__       = metadata_get("Maintainer"),
        __maintainer_email__ = metadata_get("Maintainer-email"),
        __license__      = (metadata_get("License-Expression")
                            or metadata_get("License")),
        __copyright__    = None,
    )
    email = pkg_metadata["__author_email__"] or ""
    names = ", ".join(name for name, _ in getaddresses([email]) if name)
    if names:
        if not pkg_metadata["__author__"]:
            pkg_metadata["__author__"] = names
        else:  # pragma: no cover
            pkg_metadata["__author__"] += ", " + names
    email = pkg_metadata["__maintainer_email__"] or ""
    names = ", ".join(name for name, _ in getaddresses([email]) if name)
    if names:
        if not pkg_metadata["__maintainer__"]:
            pkg_metadata["__maintainer__"] = names
        else:  # pragma: no cover
            pkg_metadata["__maintainer__"] += ", " + names
    pkg_metadata["__email__"] = pkg_metadata["__author_email__"]
    pkg_metadata["__copyright__"] = pkg_metadata["__author__"]
    return pkg_metadata


adict.__module__ = __package__
version_info.__module__ = __package__
about.__module__ = __package__
about_from_setup.__module__ = __package__

__release_levels: dict[str, str] = dict(
    a     = "alpha",
    b     = "beta",
    rc    = "candidate",
    dev   = "dev",
    post  = "post",
    local = "local",
    final = "final",
)
