"""Section map for the BestMDMTool shell.

The window is organised like the OumseGSM workspace: a tall tool list on the
left, the operations for the selected tool in the middle, and the live page on
the right. Every button here calls a real page action; anything that would need
a lock or account bypass keeps its place in the list but opens an explanation.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

RESET_PARTITIONS = ("userdata", "metadata", "cache")


@dataclass(frozen=True)
class Op:
    """One button in the operations column."""

    label: str
    action: Callable[[Any], None] | None = None
    variant: str = "default"
    kind: str = "button"  # button | primary | group


@dataclass(frozen=True)
class Section:
    """A tool entry in the left-hand list."""

    key: str
    label: str
    page: str
    ops: tuple[Op, ...] = field(default_factory=tuple)
    group: str = "tools"
    engine: str = ""
    note: str = ""
    alt: tuple[str, str] | None = None  # (label key, section key)

    @property
    def notice(self) -> bool:
        return self.page.startswith("notice:")


# -- action plumbing -------------------------------------------------------
def page_action(page: str, method: str, *args: Any) -> Callable[[Any], None]:
    """Open ``page`` and run ``method`` on it, reporting a missing hook."""

    def _run(app: Any) -> None:
        app.show_page(page)
        target = app._pages.get(page)
        handler = getattr(target, method, None) if target is not None else None
        if callable(handler):
            handler(*args)
        else:
            app.log("This action is not available on this build.", "WARN")

    return _run


def open_section(section_key: str) -> Callable[[Any], None]:
    def _run(app: Any) -> None:
        app.show_section(section_key)

    return _run


def factory_reset(app: Any) -> None:
    """Erase the partitions a factory reset touches, on an authorized device."""

    session = getattr(app.controller, "session", None)
    if session is None or not getattr(session, "is_running", False):
        app.set_status("Connect a device first.", "warn")
        app.log("Factory reset needs an open device session.", "WARN")
        return

    known = {str(part.get("name", "")).lower() for part in app.controller.partitions}
    targets = [name for name in RESET_PARTITIONS if not known or name in known]
    if not targets:
        known_text = ", ".join(sorted(known)[:6]) or "none"
        app.log("No factory-reset partitions found in this table (%s)." % known_text, "WARN")
        return
    if not app.confirm(
        "Factory reset",
        "Erase %s and reboot? Every user file on the phone will be lost." % ", ".join(targets),
        danger=True,
    ):
        return

    def _work() -> Any:
        return session.erase(targets)

    app.controller.run_async(
        "Erasing %s" % ", ".join(targets),
        _work,
        lambda result: app.log(
            "Factory reset finished: %s" % getattr(result, "detail", "done"),
            "OK" if getattr(result, "ok", False) else "ERROR",
        ),
    )


# -- shared operation blocks ----------------------------------------------
PARTITION_OPS: tuple[Op, ...] = (
    Op("op.partition_manager", page_action("partitions", "_refresh"), "accent", "primary"),
    Op("app.group_device", kind="group"),
    Op("op.read_info", page_action("dashboard", "_diagnostics")),
    Op("op.enable_adb", page_action("adb", "_enable_adb")),
    Op("op.disable_adb", open_section("no_adb_off")),
    Op("app.group_reset", kind="group"),
    Op("op.reset_frp", open_section("frp")),
    Op("op.factory_reset", factory_reset, "danger"),
    Op("op.factory_frp", open_section("frp")),
)

BROM_OPS: tuple[Op, ...] = (
    Op("op.partition_manager", page_action("partitions", "_refresh"), "accent", "primary"),
    Op("app.group_device", kind="group"),
    Op("op.read_selected", page_action("partitions", "_read_selected")),
    Op("op.write_selected", page_action("partitions", "_write_selected")),
    Op("op.erase_selected", page_action("partitions", "_erase_selected"), "danger"),
    Op("op.export_gpt", page_action("partitions", "_export_gpt")),
    Op("op.backup_all", page_action("partitions", "_backup_all")),
    Op("app.group_diag", kind="group"),
    Op("op.read_info", page_action("dashboard", "_diagnostics")),
    Op("op.reboot", page_action("partitions", "_reboot"), "warning"),
)

UNLOCK_OPS: tuple[Op, ...] = (
    Op("op.boot_state", page_action("bootloader", "_check_state"), "accent", "primary"),
    Op("app.group_unlock", kind="group"),
    Op("op.fastboot_devices", page_action("bootloader", "_fastboot_devices")),
    Op("op.fastboot_unlock", page_action("bootloader", "_fastboot_unlock"), "warning"),
    Op("op.seccfg_unlock", page_action("bootloader", "_seccfg", "unlock"), "warning"),
    Op("op.seccfg_lock", page_action("bootloader", "_seccfg", "lock")),
    Op("op.reboot", page_action("dashboard", "_reboot"), "danger"),
)

SPD_UNLOCK_OPS: tuple[Op, ...] = (
    Op("op.boot_state", page_action("bootloader", "_check_state"), "accent", "primary"),
    Op("app.group_unlock", kind="group"),
    Op("op.fastboot_devices", page_action("bootloader", "_fastboot_devices")),
    Op("op.fastboot_unlock", page_action("bootloader", "_fastboot_unlock"), "warning"),
    Op("app.group_device", kind="group"),
    Op("op.detect_usb", page_action("chipsets", "_detect")),
    Op("op.reboot", page_action("dashboard", "_reboot"), "danger"),
)

SPD_OPS: tuple[Op, ...] = (
    Op("op.refresh_table", page_action("spd", "_load_partitions"), "accent", "primary"),
    Op("app.group_device", kind="group"),
    Op("op.read_selected", page_action("spd", "_read_selected")),
    Op("op.write_selected", page_action("spd", "_write_selected")),
    Op("op.erase_selected", page_action("spd", "_erase_selected"), "danger"),
    Op("op.reboot", page_action("spd", "_reboot"), "warning"),
    Op("app.group_flash", kind="group"),
    Op("op.open_pac", page_action("pac", "_open_pac")),
    Op("op.flash_pac", page_action("pac", "_flash_pac"), "danger"),
    Op("app.group_diag", kind="group"),
    Op("op.diag_console", page_action("diag", "_identify")),
    Op("op.detect_usb", page_action("chipsets", "_detect")),
)

DIAG_OPS: tuple[Op, ...] = (
    Op("op.identify", page_action("diag", "_identify"), "accent", "primary"),
    Op("app.group_diag", kind="group"),
    Op("op.diag_console", page_action("diag", "_open")),
    Op("op.detect_usb", page_action("chipsets", "_detect")),
    Op("app.group_device", kind="group"),
    Op("op.read_info", page_action("dashboard", "_diagnostics")),
)

ROM_OPS: tuple[Op, ...] = (
    Op("op.open_pac", page_action("pac", "_open_pac"), "accent", "primary"),
    Op("app.group_flash", kind="group"),
    Op("op.flash_pac", page_action("pac", "_flash_pac"), "danger"),
    Op("op.extract_pac", page_action("pac", "_extract")),
    Op("op.build_pac", page_action("pac", "_build_pac")),
    Op("app.group_device", kind="group"),
    Op("op.reboot", page_action("spd", "_reboot"), "warning"),
)

ADB_OPS: tuple[Op, ...] = (
    Op("op.fastboot_devices", page_action("bootloader", "_fastboot_devices"), "accent", "primary"),
    Op("app.group_device", kind="group"),
    Op("op.adb_shell", page_action("adb", "_run_shell")),
    Op("op.install_apk", page_action("adb", "_install_apk")),
    Op("op.enable_adb", page_action("adb", "_enable_adb")),
    Op("app.group_diag", kind="group"),
    Op("op.read_info", page_action("dashboard", "_diagnostics")),
)

DASHBOARD_OPS: tuple[Op, ...] = (
    Op("op.read_info", page_action("dashboard", "_diagnostics"), "accent", "primary"),
    Op("app.group_device", kind="group"),
    Op("op.refresh_table", page_action("dashboard", "_refresh")),
    Op("op.reboot", page_action("dashboard", "_reboot"), "warning"),
    Op("app.group_diag", kind="group"),
    Op("op.selftest", page_action("settings", "_run_selftest")),
)

FLASH_OPS: tuple[Op, ...] = (
    Op("op.flash_raw", page_action("flasher", "_flash_raw"), "accent", "primary"),
    Op("app.group_flash", kind="group"),
    Op("op.flash_queue", page_action("flasher", "_flash_queue"), "warning"),
    Op("op.read_selected", page_action("partitions", "_read_selected")),
    Op("app.group_device", kind="group"),
    Op("op.reboot", page_action("partitions", "_reboot"), "warning"),
)

ADVANCED_OPS: tuple[Op, ...] = (
    Op("op.peek", page_action("advanced", "_peek"), "accent", "primary"),
    Op("app.group_device", kind="group"),
    Op("op.poke", page_action("advanced", "_poke"), "warning"),
    Op("op.read_selected", page_action("advanced", "_read_range")),
    Op("op.erase_selected", page_action("advanced", "_erase_range"), "danger"),
)

CHIPSET_OPS: tuple[Op, ...] = (
    Op("op.detect_usb", page_action("chipsets", "_detect"), "accent", "primary"),
    Op("app.group_diag", kind="group"),
    Op("op.diag_console", page_action("diag", "_identify")),
    Op("op.selftest", page_action("settings", "_run_selftest")),
)

SETTINGS_OPS: tuple[Op, ...] = (
    Op("op.save_settings", page_action("settings", "_save"), "accent", "primary"),
    Op("app.group_diag", kind="group"),
    Op("op.selftest", page_action("settings", "_run_selftest")),
    Op("op.support_bundle", page_action("settings", "_export_bundle")),
    Op("op.open_logs", page_action("settings", "_open_logs")),
)

ABOUT_OPS: tuple[Op, ...] = (
    Op("op.support_bundle", page_action("settings", "_export_bundle"), "accent", "primary"),
    Op("app.group_diag", kind="group"),
    Op("op.open_logs", page_action("settings", "_open_logs")),
)


SECTIONS: tuple[Section, ...] = (
    Section("partitions", "nav.partitions", "partitions", PARTITION_OPS, engine="mtk"),
    Section(
        "mdm",
        "nav.mdm",
        "notice:mdm",
        note="notice.mdm.body",
        alt=("nav.partitions", "partitions"),
    ),
    Section("brom", "nav.brom", "partitions", BROM_OPS, engine="mtk"),
    Section(
        "bypass",
        "nav.bypass",
        "notice:bypass",
        note="notice.bypass.body",
        alt=("nav.brom", "brom"),
    ),
    Section(
        "permanent",
        "nav.permanent",
        "notice:permanent",
        note="notice.permanent.body",
        alt=("nav.brom", "brom"),
    ),
    Section("tecno", "nav.tecno", "bootloader", UNLOCK_OPS, engine="mtk"),
    Section("spd_unlock", "nav.spd_unlock", "bootloader", SPD_UNLOCK_OPS, engine="spd"),
    Section("spd_parts", "nav.spd_parts", "spd", SPD_OPS, engine="spd"),
    Section("spd_diag", "nav.spd_diag", "diag", DIAG_OPS, engine="spd"),
    Section("rom", "nav.rom", "pac", ROM_OPS, engine="spd"),
    Section("spd_rom", "nav.spd_rom", "pac", ROM_OPS, engine="spd"),
    Section("fastboot", "nav.fastboot", "adb", ADB_OPS, engine="mtk"),
    Section(
        "frp",
        "nav.about",
        "notice:frp",
        note="notice.frp.body",
        alt=("nav.partitions", "partitions"),
        group="hidden",
    ),
    Section(
        "no_adb_off",
        "nav.about",
        "notice:no_adb_off",
        note="notice.adb_disable.body",
        alt=("nav.fastboot", "fastboot"),
        group="hidden",
    ),
    Section("dashboard", "nav.dashboard", "dashboard", DASHBOARD_OPS, group="workspace"),
    Section("flasher", "nav.flasher", "flasher", FLASH_OPS, group="workspace"),
    Section("advanced", "nav.advanced", "advanced", ADVANCED_OPS, group="workspace"),
    Section("chipsets", "nav.chipsets", "chipsets", CHIPSET_OPS, group="workspace"),
    Section("settings", "nav.settings", "settings", SETTINGS_OPS, group="workspace"),
    Section("about", "nav.about", "about", ABOUT_OPS, group="workspace"),
)

VISIBLE_SECTIONS: tuple[Section, ...] = tuple(s for s in SECTIONS if s.group != "hidden")

SECTIONS_BY_KEY: dict[str, Section] = {section.key: section for section in SECTIONS}


def sections_for_group(group: str) -> tuple[Section, ...]:
    return tuple(section for section in VISIBLE_SECTIONS if section.group == group)


def section_for_page(page: str) -> Section | None:
    for section in VISIBLE_SECTIONS:
        if section.page == page:
            return section
    return None


# -- contextual action strip ----------------------------------------------
# Four coloured buttons under the workspace, mirroring the Read / Write /
# Erase / Enable ADB row of the original tool.
QUICK_ACTIONS: dict[str, tuple[tuple[str, Callable[[Any], None], str], ...]] = {
    "partitions": (
        ("op.read_selected", page_action("partitions", "_read_selected"), "info"),
        ("op.write_selected", page_action("partitions", "_write_selected"), "accent"),
        ("op.erase_selected", page_action("partitions", "_erase_selected"), "danger"),
        ("op.enable_adb", page_action("adb", "_enable_adb"), "success"),
    ),
    "spd": (
        ("op.read_selected", page_action("spd", "_read_selected"), "info"),
        ("op.write_selected", page_action("spd", "_write_selected"), "accent"),
        ("op.erase_selected", page_action("spd", "_erase_selected"), "danger"),
        ("op.reboot", page_action("spd", "_reboot"), "success"),
    ),
    "flasher": (
        ("op.write_selected", page_action("flasher", "_flash_single"), "accent"),
        ("op.flash_raw", page_action("flasher", "_flash_raw"), "info"),
        ("op.flash_queue", page_action("flasher", "_flash_queue"), "success"),
        ("op.erase_selected", page_action("partitions", "_erase_selected"), "danger"),
    ),
    "pac": (
        ("op.open_pac", page_action("pac", "_open_pac"), "info"),
        ("op.flash_pac", page_action("pac", "_flash_pac"), "accent"),
        ("op.extract_pac", page_action("pac", "_extract"), "success"),
        ("op.build_pac", page_action("pac", "_build_pac"), "default"),
    ),
    "advanced": (
        ("op.peek", page_action("advanced", "_peek"), "info"),
        ("op.poke", page_action("advanced", "_poke"), "accent"),
        ("op.erase_selected", page_action("advanced", "_erase_range"), "danger"),
        ("op.read_selected", page_action("advanced", "_read_range"), "success"),
    ),
    "bootloader": (
        ("op.boot_state", page_action("bootloader", "_check_state"), "info"),
        ("op.seccfg_unlock", page_action("bootloader", "_seccfg", "unlock"), "accent"),
        ("op.seccfg_lock", page_action("bootloader", "_seccfg", "lock"), "danger"),
        ("op.fastboot_devices", page_action("bootloader", "_fastboot_devices"), "success"),
    ),
    "adb": (
        ("op.adb_shell", page_action("adb", "_run_shell"), "info"),
        ("op.install_apk", page_action("adb", "_install_apk"), "accent"),
        ("op.enable_adb", page_action("adb", "_enable_adb"), "success"),
        ("op.detect_usb", page_action("chipsets", "_detect"), "default"),
    ),
    "diag": (
        ("op.identify", page_action("diag", "_identify"), "info"),
        ("op.diag_console", page_action("diag", "_open"), "accent"),
        ("op.detect_usb", page_action("chipsets", "_detect"), "success"),
        ("op.read_info", page_action("dashboard", "_diagnostics"), "default"),
    ),
    "chipsets": (
        ("op.detect_usb", page_action("chipsets", "_detect"), "info"),
        ("op.selftest", page_action("settings", "_run_selftest"), "accent"),
        ("op.diag_console", page_action("diag", "_identify"), "success"),
        ("op.read_info", page_action("dashboard", "_diagnostics"), "default"),
    ),
    "dashboard": (
        ("op.read_info", page_action("dashboard", "_diagnostics"), "info"),
        ("op.refresh_table", page_action("dashboard", "_refresh"), "accent"),
        ("op.reboot", page_action("dashboard", "_reboot"), "danger"),
        ("op.selftest", page_action("settings", "_run_selftest"), "success"),
    ),
    "settings": (
        ("op.save_settings", page_action("settings", "_save"), "info"),
        ("op.selftest", page_action("settings", "_run_selftest"), "accent"),
        ("op.support_bundle", page_action("settings", "_export_bundle"), "success"),
        ("op.open_logs", page_action("settings", "_open_logs"), "default"),
    ),
    "about": (
        ("op.support_bundle", page_action("settings", "_export_bundle"), "info"),
        ("op.open_logs", page_action("settings", "_open_logs"), "accent"),
        ("op.selftest", page_action("settings", "_run_selftest"), "success"),
        ("op.detect_usb", page_action("chipsets", "_detect"), "default"),
    ),
}
