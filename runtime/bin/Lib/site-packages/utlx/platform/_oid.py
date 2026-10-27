# Copyright (c) 1994 Adam Karpierz
# SPDX-License-Identifier: Zlib

from typing import Any
import ctypes

from ._detect import is_cpython

__all__ = ('from_oid',)

if is_cpython:

    def from_oid(oid: int | None, *, __ct: Any = ctypes) -> object | None:
        return __ct.cast(oid, __ct.py_object).value if oid else None

else:

    def from_oid(oid: int | None, *, __ct: Any = ctypes) -> object | None:
        from platform import python_implementation
        raise NotImplementedError("from_oid() currently works only on CPython!\n"
                                  f"Current interpreter: {python_implementation()}")

del Any, ctypes, is_cpython
