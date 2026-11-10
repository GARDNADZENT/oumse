"""Tests for the workspace shell: sections, operations, languages, notices."""

from __future__ import annotations

import queue
import time
import unittest

from tests.tk_stub import install_fake_tkinter

install_fake_tkinter()  # no display in CI: stub tkinter before importing the UI

from bestmdmtool.ui import i18n  # noqa: E402
from bestmdmtool.ui.pages import PAGES  # noqa: E402
from bestmdmtool.ui.sections import (  # noqa: E402
    QUICK_ACTIONS,
    SECTIONS,
    VISIBLE_SECTIONS,
    factory_reset,
    page_action,
)


class FakeResult:
    def __init__(self, op="erase", ok=True, detail="done", data=b""):
        self.op = op
        self.ok = ok
        self.detail = detail
        self.data = data
        self.duration = 0.01


class FakeSession:
    """Minimal stand-in for ServiceSession."""

    def __init__(self) -> None:
        self.is_running = True
        self.events: queue.Queue = queue.Queue()
        self.calls: list[tuple] = []
        self.device = {"chip": "MT6768", "parts": 3}
        self.partitions: list[dict] = []

    def erase(self, parts, **kwargs):
        self.calls.append(("erase", tuple(parts)))
        return FakeResult()

    def stop(self, reboot=False, **kwargs):
        self.is_running = False


class ShellTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from bestmdmtool import branding
        from bestmdmtool.ui.main_window import MainWindow

        cls.app = MainWindow(
            product_name=branding.PRODUCT_NAME,
            product_title=branding.PRODUCT_TITLE,
            product_version=branding.PRODUCT_VERSION,
            product_subtitle=branding.PRODUCT_SUBTITLE,
            authorized_use=branding.AUTHORIZED_USE,
        )
        cls.app.controller.settings.language = "en"
        cls.app.set_language("en")

    def setUp(self) -> None:
        self.app.controller.session = None
        self.app.controller.partitions = []
        self.app.controller.device = {}

    def _settle(self, seconds: float = 0.3) -> None:
        deadline = time.time() + seconds
        while time.time() < deadline:
            pending = [t for t in __import__("threading").enumerate() if t.name == "svc-worker"]
            if not pending:
                break
            time.sleep(0.02)

    # -- structure ---------------------------------------------------------
    def test_every_section_points_at_a_real_page(self) -> None:
        for section in VISIBLE_SECTIONS:
            with self.subTest(section=section.key):
                self.assertIn(section.page, self.app._pages)
                self.assertTrue(section.label.startswith("nav."))
        self.assertEqual(len({section.key for section in VISIBLE_SECTIONS}), len(VISIBLE_SECTIONS))

    def test_notice_sections_explain_themselves(self) -> None:
        notices = [section for section in SECTIONS if section.notice]
        self.assertTrue(notices)
        for section in notices:
            with self.subTest(section=section.key):
                self.assertTrue(section.note)
                self.assertIn(section.note, i18n.STRINGS)
                self.assertIsNotNone(section.alt)

    def test_operation_buttons_have_actions(self) -> None:
        for section in SECTIONS:
            for op in section.ops:
                with self.subTest(section=section.key, op=op.label):
                    self.assertIn(op.label, i18n.STRINGS)
                    if op.kind == "group":
                        self.assertIsNone(op.action)
                    else:
                        self.assertTrue(callable(op.action))

    def test_shell_strings_exist_in_every_language(self) -> None:
        keys = {"app.tools", "app.workspace", "app.ops_mtk", "app.ops_spd", "notice.title"}
        for section in SECTIONS:
            keys.add(section.label)
            if section.note:
                keys.add(section.note)
            for op in section.ops:
                keys.add(op.label)
        for page_ops in QUICK_ACTIONS.values():
            for label, _action, _variant in page_ops:
                keys.add(label)
        for key in sorted(keys):
            with self.subTest(key=key):
                table = i18n.STRINGS.get(key)
                self.assertIsNotNone(table, "missing translation key %s" % key)
                for code in i18n.LANGUAGES:
                    self.assertTrue(table.get(code), "%s has no %s text" % (key, code))

    def test_navigation_lists_every_visible_section(self) -> None:
        self.assertEqual(set(self.app._nav_rows), {section.key for section in VISIBLE_SECTIONS})
        self.assertGreaterEqual(len(self.app._nav_rows), 18)

    # -- navigation --------------------------------------------------------
    def test_show_section_switches_page_and_operations(self) -> None:
        self.app.show_section("spd_parts")
        self.assertEqual(self.app._current, "spd")
        self.assertEqual(self.app._active_section, "spd_parts")
        self.assertIn("SPD", self.app.ops_title._config.get("text", ""))

    def test_shared_pages_keep_their_own_section(self) -> None:
        self.app.show_section("tecno")
        self.assertEqual(self.app._current, "bootloader")
        self.app.show_section("spd_unlock")
        self.assertEqual(self.app._current, "bootloader")
        self.assertEqual(self.app._active_section, "spd_unlock")

    def test_show_page_matches_page_registry(self) -> None:
        for key in PAGES:
            with self.subTest(page=key):
                self.app.show_page(key)
                self.assertEqual(self.app._current, key)

    def test_notice_section_raises_explanation_page(self) -> None:
        self.app.show_section("mdm")
        self.assertEqual(self.app._current, "notice:mdm")
        self.assertEqual(self.app.card_title._config.get("text"), i18n.t("notice.title", "en"))

    # -- language ----------------------------------------------------------
    def test_language_switch_updates_labels_and_settings(self) -> None:
        try:
            self.app.set_language("fr")
            self.assertEqual(self.app.controller.settings.language, "fr")
            row = self.app._nav_rows["partitions"]
            french = i18n.t("nav.partitions", "fr")
            self.assertEqual(row._text._config.get("text"), french)
            self.assertEqual(self.app.btn_connect._config.get("text"), "Connecter")
            self.app.show_section("spd_parts")
            self.assertIn("SPD", self.app.ops_title._config.get("text", ""))
        finally:
            self.app.set_language("en")
        self.assertEqual(self.app.btn_connect._config.get("text"), "Connect")
        self.assertEqual(
            self.app._nav_rows["partitions"]._text._config.get("text"),
            i18n.t("nav.partitions", "en"),
        )

    def test_arabic_and_portuguese_are_supported(self) -> None:
        try:
            for code in ("ar", "pt"):
                self.app.set_language(code)
                self.assertEqual(self.app.language, code)
                self.assertTrue(self.app.btn_connect._config.get("text"))
        finally:
            self.app.set_language("en")

    # -- actions -----------------------------------------------------------
    def test_quick_actions_cover_every_page(self) -> None:
        missing = [key for key in PAGES if key not in QUICK_ACTIONS]
        self.assertFalse(missing, "pages without a quick action row: %s" % missing)
        for page, actions in QUICK_ACTIONS.items():
            with self.subTest(page=page):
                self.assertEqual(len(actions), 4)
                for label, action, variant in actions:
                    self.assertIn(label, i18n.STRINGS)
                    self.assertTrue(callable(action))
                    self.assertIn(variant, {"default", "accent", "info", "success", "danger"})

    def test_select_all_and_none_touch_the_tree(self) -> None:
        self.app.show_page("partitions")
        page = self.app._pages["partitions"]
        page.tree.delete()
        page.tree.insert("", "end", iid="boot", values=("boot", "32 MB", 65536, 524288))
        self.app._select_all()
        self.assertEqual(page.tree.selection(), ("boot",))
        self.app._select_none()
        self.assertEqual(page.tree.selection(), ())

    def test_factory_reset_erases_the_expected_partitions(self) -> None:
        session = FakeSession()
        self.app.controller.session = session
        self.app.controller.partitions = [
            {"name": "userdata"},
            {"name": "metadata"},
            {"name": "boot"},
        ]
        factory_reset(self.app)
        self._settle()
        self.assertIn(("erase", ("userdata", "metadata")), session.calls)

    def test_factory_reset_needs_a_session(self) -> None:
        self.app.controller.session = None
        factory_reset(self.app)
        self.assertIn("Connect a device first.", self.app.status_label._config.get("text", ""))

    def test_stop_closes_the_session(self) -> None:
        session = FakeSession()
        self.app.controller.session = session
        self.app.stop_all()
        self._settle()
        self.assertFalse(session.is_running)

    def test_page_action_warns_when_a_hook_is_missing(self) -> None:
        action = page_action("about", "_does_not_exist")
        action(self.app)
        self.assertEqual(self.app._current, "about")


class SectionCopyTests(unittest.TestCase):
    """The tool list must keep the OumseGSM wording, including the safe stubs."""

    def test_tool_list_matches_the_original_order(self) -> None:
        labels = [i18n.t(section.label, "en") for section in VISIBLE_SECTIONS]
        self.assertEqual(
            labels[:12],
            [
                "Partition Manager MTK & SPD",
                "MDM Regional Patcher",
                "Partition BROM mode",
                "Direct Bypass MTK",
                "Direct Permanent MTK",
                "Tecno / Infinix Bootloader Unlock",
                "SPD / Unisoc Bootloader Unlock",
                "Partition SPD / Unisoc & OF",
                "SPD Partition Diag Mode",
                "Transsion ROM Maker",
                "Transsion SPD ROM Maker",
                "Fastboot OGT Flasher",
            ],
        )

    def test_unavailable_entries_have_no_page_of_their_own(self) -> None:
        for section in SECTIONS:
            if section.notice:
                continue
            self.assertIn(section.page, PAGES)


if __name__ == "__main__":
    unittest.main()
