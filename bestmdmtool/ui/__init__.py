"""BestMDMTool user interface package.

Keep imports lazy so command-line tooling can inspect source packages without
requiring Tkinter. The launched product uses the minimal partition-reader
window; the older workspace shell is not used by the product entry point.
"""

from __future__ import annotations

__all__ = ["MainWindow", "PartitionReaderWindow"]


def __getattr__(name: str):
    if name == "MainWindow":
        from .main_window import MainWindow

        return MainWindow
    if name == "PartitionReaderWindow":
        from .partition_reader import PartitionReaderWindow

        return PartitionReaderWindow
    raise AttributeError(name)
