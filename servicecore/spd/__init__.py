"""Spreadtrum/Unisoc (SPD) support: BSL protocol, PAC firmware, chip database.

MediaTek devices are handled by :mod:`servicecore.runner.service_runner` on top
of the bundled mtkclient. Spreadtrum/Unisoc devices speak a completely different
protocol (the Boot Strap Loader, "BSL"), so they get their own engine here.

Layout::

    crc.py         HDLC framing + CRC16 used on the wire
    constants.py   BSL command numbers and timeouts (one place to adjust)
    transport.py   serial / USB / in-memory transports
    protocol.py    BSL client: connect, read, write, erase, execute
    simulator.py   an in-memory BSL device used by tests and --simulate
    pac.py         Spreadtrum PAC firmware: read, verify, extract, build
    chipsets.py    SPD + MTK chip database and USB identification
"""

from __future__ import annotations

from .pac import PacEntry, PacError, PacFile

__all__ = ["PacEntry", "PacError", "PacFile"]
