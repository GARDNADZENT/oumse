"""Page registry for the BestMDMTool interface."""

from __future__ import annotations

from .about import AboutPage
from .adb_tools import AdbPage
from .advanced import AdvancedPage
from .base import BasePage
from .bootloader import BootloaderPage
from .chipsets import ChipsetsPage
from .dashboard import DashboardPage
from .diag import DiagPage
from .flasher import FlasherPage
from .pac import PacPage
from .partitions import PartitionsPage
from .settings_page import SettingsPage
from .spd import SpdPage

PAGES = {
    "dashboard": DashboardPage,
    "partitions": PartitionsPage,
    "flasher": FlasherPage,
    "advanced": AdvancedPage,
    "bootloader": BootloaderPage,
    "adb": AdbPage,
    "settings": SettingsPage,
    "about": AboutPage,
    # Spreadtrum/Unisoc workspace
    "spd": SpdPage,
    "pac": PacPage,
    "diag": DiagPage,
    "chipsets": ChipsetsPage,
}

__all__ = [
    "BasePage",
    "AboutPage",
    "PAGES",
    "DashboardPage",
    "PartitionsPage",
    "FlasherPage",
    "AdvancedPage",
    "BootloaderPage",
    "AdbPage",
    "SettingsPage",
    "SpdPage",
    "PacPage",
    "DiagPage",
    "ChipsetsPage",
]
