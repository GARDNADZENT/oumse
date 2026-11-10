"""Legacy multi-page workspace registry, imported only when requested.

The launched BestMDMTool app uses the single-purpose partition-reader window.
Keep legacy page imports lazy so headless tooling can discover this package
without importing Tkinter or loading the retired multi-tool workspace.
"""

from __future__ import annotations

from importlib import import_module

_PAGE_MODULES = {
    "BasePage": "base",
    "AboutPage": "about",
    "DashboardPage": "dashboard",
    "PartitionsPage": "partitions",
    "FlasherPage": "flasher",
    "AdvancedPage": "advanced",
    "BootloaderPage": "bootloader",
    "AdbPage": "adb_tools",
    "SettingsPage": "settings_page",
    "SpdPage": "spd",
    "PacPage": "pac",
    "DiagPage": "diag",
    "ChipsetsPage": "chipsets",
}

__all__ = ["PAGES", *_PAGE_MODULES]


def __getattr__(name: str):
    if name == "PAGES":
        pages = {key: getattr(import_module(".%s" % module, __name__), key) for key, module in _PAGE_MODULES.items()}
        return {
            "dashboard": pages["DashboardPage"],
            "partitions": pages["PartitionsPage"],
            "flasher": pages["FlasherPage"],
            "advanced": pages["AdvancedPage"],
            "bootloader": pages["BootloaderPage"],
            "adb": pages["AdbPage"],
            "settings": pages["SettingsPage"],
            "about": pages["AboutPage"],
            "spd": pages["SpdPage"],
            "pac": pages["PacPage"],
            "diag": pages["DiagPage"],
            "chipsets": pages["ChipsetsPage"],
        }
    module = _PAGE_MODULES.get(name)
    if module is None:
        raise AttributeError(name)
    return getattr(import_module(".%s" % module, __name__), name)
