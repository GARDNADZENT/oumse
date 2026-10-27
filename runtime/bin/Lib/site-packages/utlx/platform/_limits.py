# Copyright (c) 1994 Adam Karpierz
# SPDX-License-Identifier: Zlib

import ctypes

from ._detect import is_graalpy

__all__ = (
    'USHRT_MAX',  'SHRT_MAX',  'SHRT_MIN',
    'UINT_MAX',   'INT_MAX',   'INT_MIN',
    'ULONG_MAX',  'LONG_MAX',  'LONG_MIN',
    'ULLONG_MAX', 'LLONG_MAX', 'LLONG_MIN',
)

# include <limits.h>
USHRT_MAX  = ctypes.c_ushort(-1).value
SHRT_MAX   = USHRT_MAX >> 1
SHRT_MIN   = -SHRT_MAX - 1
UINT_MAX   = ctypes.c_uint(-1).value
INT_MAX    = UINT_MAX >> 1
INT_MIN    = -INT_MAX - 1
ULONG_MAX  = ctypes.c_ulong(-1).value
LONG_MAX   = ULONG_MAX >> 1
LONG_MIN   = -LONG_MAX - 1
ULLONG_MAX = (((ULONG_MAX << ((ctypes.sizeof(ctypes.c_ulonglong)
                               - ctypes.sizeof(ctypes.c_ulong)) * 8)) + ULONG_MAX)
              if is_graalpy else
              ctypes.c_ulonglong(-1).value)
LLONG_MAX  = ULLONG_MAX >> 1
LLONG_MIN  = -LLONG_MAX - 1

del ctypes, is_graalpy
