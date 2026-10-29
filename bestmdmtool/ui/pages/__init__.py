"""Page registry for the BestMDMTool interface."""

from __future__ import annotations

from .about import AboutPage
from .adb_tools import AdbPage
from .advanced import AdvancedPage
from .base import BasePage
from .bootloader import BootloaderPage
from .dashboard import DashboardPage
from .flasher import FlasherPage
from .partitions import PartitionsPage
from .settings_page import SettingsPage

PAGES = {
    "dashboard": DashboardPage,
    "partitions": PartitionsPage,
    "flasher": FlasherPage,
    "advanced": AdvancedPage,
    "bootloader": BootloaderPage,
    "adb": AdbPage,
    "settings": SettingsPage,
    "about": AboutPage,
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
]
