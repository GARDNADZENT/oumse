"""Headless smoke tests for the real BestMDMTool window.

Tkinter has no display in CI, so these tests install the stub and then build the
actual window, switch through all eight pages, feed it a simulated device and
drive the page actions. Anything that would raise ``AttributeError`` on a real
Windows desktop raises here too.
"""

from __future__ import annotations

import ast
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from tests.tk_stub import install_fake_tkinter

ROOT = Path(__file__).resolve().parents[1]

PARTITIONS = [
    {"name": "boot", "sectors": 65536, "size": 33554432, "sector": 1024, "pagesize": 512},
    {"name": "super", "sectors": 2097152, "size": 1073741824, "sector": 66560, "pagesize": 512},
    {"name": "userdata", "sectors": 4194304, "size": 2147483648, "sector": 2163712, "pagesize": 512},
]


def _wait_for(predicate, timeout: float = 5.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.02)
    return predicate()


class WindowSmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        install_fake_tkinter(force=True)
        from bestmdmtool import branding
        from bestmdmtool.ui.main_window import MainWindow

        cls.app = MainWindow(
            product_name=branding.PRODUCT_NAME,
            product_title=branding.PRODUCT_TITLE,
            product_version=branding.PRODUCT_VERSION,
            product_subtitle=branding.PRODUCT_SUBTITLE,
            authorized_use=branding.AUTHORIZED_USE,
        )

    def setUp(self) -> None:
        self.logs: list[tuple[str, str]] = []
        controller = self.app.controller
        original = controller._log

        def _record(message: str, level: str = "INFO") -> None:
            self.logs.append((level, message))
            original(message, level)

        controller._log = _record
        self.addCleanup(setattr, controller, "_log", original)
        self.addCleanup(setattr, controller, "session", None)

    def _errors(self) -> list[str]:
        return [text for level, text in self.logs if level == "ERROR"]

    def test_every_page_builds_and_shows(self) -> None:
        from bestmdmtool.ui.pages import PAGES

        self.assertEqual(set(self.app._pages), set(PAGES))
        for key in PAGES:
            self.app.show_page(key)
            self.assertEqual(self.app._current, key)
            self.app._pages[key].on_show()

    def test_device_and_busy_callbacks_reach_every_page(self) -> None:
        device = {"chip": "MT6768", "hwcode": "0x0707", "storage": "UFS", "mode": "brom"}
        self.app._on_device(device)
        for page in self.app._pages.values():
            page.on_device(device)
        self.app._on_busy(True, "Working")
        self.app._on_busy(False, "")
        self.app._on_progress(4096, 0)
        self.assertFalse([message for message in self._errors()])

    def test_partition_page_renders_a_real_table(self) -> None:
        page = self.app._pages["partitions"]
        self.app.controller.partitions = list(PARTITIONS)
        page._render()
        page._update_selection_label()
        self.assertEqual(page._visible_partitions()[0]["name"], "boot")

    def test_flasher_matches_an_image_to_its_partition(self) -> None:
        page = self.app._pages["flasher"]
        self.app.controller.partitions = list(PARTITIONS)
        page._auto_select_partition(r"C:\images\boot.img")
        page._auto_select_partition(r"C:\images\unknown-image.img")
        self.assertFalse(self._errors(), self._errors())

    def test_advanced_parsers(self) -> None:
        page = self.app._pages["advanced"]
        self.assertEqual(page._parse("0x1000"), 4096)
        self.assertEqual(page._parse("4096"), 4096)
        self.assertEqual(page._parse("", default=7), 7)
        # Bad input must raise so the page can warn instead of silently using 0.
        with self.assertRaises(ValueError):
            page._parse("nonsense")

    def test_settings_page_reports_paths(self) -> None:
        page = self.app._pages["settings"]
        page._refresh_paths()
        text = page.paths_text.get("1.0", "end")
        self.assertIn("Runner", text)
        self.assertIn("Runner mode", text)

    def test_dashboard_refresh_without_a_device_is_graceful(self) -> None:
        page = self.app._pages["dashboard"]
        self.app.controller.session = None
        page._refresh()
        self.assertTrue(
            any("Connect a device first" in text for _lvl, text in self.logs),
            self.logs,
        )

    def test_page_actions_use_the_session_and_log_results(self) -> None:
        page = self.app._pages["partitions"]
        session = MagicMock()
        session.is_running = True
        session.read_partition.return_value = MagicMock(ok=True, op="read", detail="boot", data=b"")
        self.app.controller.session = session
        self.app.controller.partitions = list(PARTITIONS)

        page.tree.selection = lambda: (("boot",),)
        page.tree.item = lambda _item, *_args: ("boot",)
        self.app.ask_save = lambda *args, **kwargs: "/tmp/smoke/boot.img"

        settings_cls = type(self.app.controller.settings)
        with patch.object(settings_cls, "save", lambda _self: None):
            page._read_selected()
        self.assertTrue(
            _wait_for(lambda: session.read_partition.called),
            "the partition page never asked the session to read anything",
        )
        self.assertFalse(self._errors(), self._errors())
        self.app.controller.session = None


class PageActionTests(unittest.TestCase):
    """Drive the real button callbacks with a simulated device behind them."""

    @classmethod
    def setUpClass(cls) -> None:
        install_fake_tkinter(force=True)
        from bestmdmtool import branding
        from bestmdmtool.ui.main_window import MainWindow

        cls.app = MainWindow(
            product_name=branding.PRODUCT_NAME,
            product_title=branding.PRODUCT_TITLE,
            product_version=branding.PRODUCT_VERSION,
            product_subtitle=branding.PRODUCT_SUBTITLE,
            authorized_use=branding.AUTHORIZED_USE,
        )

    def _install_session(self) -> MagicMock:
        session = MagicMock()
        session.is_running = True
        for name in ("read_partition", "write_partition", "erase", "read_flash", "write_flash", "erase_flash",
                     "peek", "poke", "seccfg", "reboot", "export_gpt", "refresh_gpt", "dump", "read"):
            getattr(session, name).return_value = MagicMock(ok=True, op=name, detail="", data=b"\x00" * 16)
        self.app.controller.session = session
        self.app.controller.partitions = list(PARTITIONS)
        self.app.confirm = lambda *args, **kwargs: True
        self.app.ask_open = lambda *args, **kwargs: str(self.image)
        self.app.ask_save = lambda *args, **kwargs: "/tmp/smoke/out.bin"
        self.addCleanup(setattr, self.app.controller, "session", None)
        return session

    def _errors(self) -> list[str]:
        return [text for level, text in self._logs if level == "ERROR" and "failed" in text.lower()]

    def setUp(self) -> None:
        self._logs: list[tuple[str, str]] = []
        controller = self.app.controller
        original = controller._log

        def _record(message: str, level: str = "INFO") -> None:
            self._logs.append((level, message))
            original(message, level)

        controller._log = _record
        self.addCleanup(setattr, controller, "_log", original)
        self.app._pages["partitions"].tree.selection = lambda: (("boot",),)
        self.app._pages["partitions"].tree.item = lambda _item, *_args: ("boot",)
        # The flasher refuses paths that do not exist, so give it a real file.
        self._workspace = tempfile.TemporaryDirectory()
        self.addCleanup(self._workspace.cleanup)
        self.image = Path(self._workspace.name) / "boot.img"
        self.image.write_bytes(b"\x00" * 4096)

    def test_partition_actions_reach_the_session(self) -> None:
        from bestmdmtool.settings import Settings

        session = self._install_session()
        page = self.app._pages["partitions"]
        page._render()

        with patch.object(Settings, "save", lambda _self: None):
            page._read_selected()
            page._backup_all()
            page._erase_selected()
            page._export_gpt()

        self.assertTrue(
            _wait_for(lambda: session.read_partition.called and session.erase.called),
            "partition actions never reached the session",
        )
        self.assertFalse(self._errors(), self._errors())

    def test_advanced_actions_reach_the_session(self) -> None:
        session = self._install_session()
        page = self.app._pages["advanced"]
        page.read_offset.var.set("0x1000")
        page.read_length.var.set("4096")
        page.read_out.set("/tmp/smoke/range.bin")
        page.peek_addr.var.set("0x80000000")
        page.peek_len.var.set("16")

        page._read_range()
        page._peek()

        self.assertTrue(_wait_for(lambda: session.read_flash.called), "read range never reached the session")
        self.assertFalse(self._errors(), self._errors())

    def test_flasher_actions_reach_the_session(self) -> None:
        session = self._install_session()
        page = self.app._pages["flasher"]
        page.image_row.set(str(self.image))
        page.partition_var.set("boot")

        page._flash_single()

        self.assertTrue(_wait_for(lambda: session.write_partition.called), "flash never reached the session")
        self.assertFalse(self._errors(), self._errors())

    def test_bootloader_and_adb_actions_are_graceful(self) -> None:
        session = self._install_session()
        boot = self.app._pages["bootloader"]

        boot._check_state()
        with patch.object(type(self.app.controller.settings), "save", lambda _self: None):
            boot._seccfg("unlock")

        self.assertTrue(_wait_for(lambda: session.seccfg.called), "seccfg never reached the session")
        self.assertFalse([text for text in self._errors() if "seccfg" not in text.lower()], self._errors())

    def test_window_state_is_restored(self) -> None:
        from bestmdmtool import branding
        from bestmdmtool.settings import Settings
        from bestmdmtool.ui.main_window import MainWindow

        settings = Settings(window_geometry="1280x800+40+60", log_expanded=False)
        with patch.object(Settings, "load", classmethod(lambda cls: settings)):
            window = MainWindow(
                product_name=branding.PRODUCT_NAME,
                product_title=branding.PRODUCT_TITLE,
                product_version=branding.PRODUCT_VERSION,
                product_subtitle=branding.PRODUCT_SUBTITLE,
                authorized_use=branding.AUTHORIZED_USE,
            )
        self.assertFalse(window._log_visible, "the collapsed log dock was not restored")

    def test_support_bundle_button_writes_and_reports(self) -> None:
        from bestmdmtool import support

        page = self.app._pages["settings"]
        target = Path("/tmp/smoke/support.zip")
        original_build = support.build
        original_run = self.app.controller.run_backend_selftest
        calls: list[Path] = []

        def _fake_build(**kwargs):
            calls.append(target)
            return target

        from servicecore import selfcheck

        original_selfcheck = selfcheck.run
        selfcheck.run = lambda *args, **kwargs: {"ok": True}
        support.build = _fake_build
        self.addCleanup(setattr, support, "build", original_build)
        self.addCleanup(setattr, selfcheck, "run", original_selfcheck)
        self.addCleanup(setattr, self.app.controller, "run_backend_selftest", original_run)

        page._export_bundle()
        self.assertTrue(_wait_for(lambda: bool(calls)), "the support bundle was never written")
        self.assertTrue(any("Support bundle" in text and level == "OK" for level, text in self._logs), self._logs)

    def test_settings_actions_are_graceful(self) -> None:
        from servicecore import selfcheck

        page = self.app._pages["settings"]
        original = selfcheck.run
        selfcheck.run = lambda *args, **kwargs: {"ok": True, "lines": ["mtkclient: yes"], "duration": 0.1}
        self.addCleanup(setattr, selfcheck, "run", original)

        page._refresh_paths()
        page._run_selftest()
        self.assertFalse(self._errors(), self._errors())


class UiContractTests(unittest.TestCase):
    """Static checks that the pages only touch members that actually exist."""

    @classmethod
    def setUpClass(cls) -> None:
        install_fake_tkinter(force=True)
        from bestmdmtool.ui import theme
        from bestmdmtool.ui.controller import Controller
        from bestmdmtool.ui.main_window import MainWindow

        cls.theme = theme
        cls.controller = Controller(
            log=lambda message, level="INFO": None,
            on_device=lambda device: None,
            on_disconnect=lambda reason: None,
            on_progress=lambda done, total: None,
            on_busy=lambda busy, text: None,
            schedule=lambda action: action(),
        )
        cls.window_cls = MainWindow

    def _attribute_uses(self, path: Path, owner: str) -> set[str]:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        found: set[str] = set()
        for node in ast.walk(tree):
            if not isinstance(node, ast.Attribute):
                continue
            value = node.value
            if isinstance(value, ast.Attribute) and value.attr == owner and isinstance(value.value, ast.Name):
                found.add(node.attr)
        return found

    def test_pages_only_use_real_controller_members(self) -> None:
        missing: dict[str, list[str]] = {}
        for path in sorted((ROOT / "bestmdmtool" / "ui" / "pages").glob("*.py")):
            if path.name in ("__init__.py",):
                continue
            used = self._attribute_uses(path, "controller")
            absent = sorted(name for name in used if not hasattr(self.controller, name))
            if absent:
                missing[path.name] = absent
        self.assertEqual(missing, {}, "pages call controller members that do not exist")

    def test_pages_only_use_real_window_members(self) -> None:
        missing: dict[str, list[str]] = {}
        for path in sorted((ROOT / "bestmdmtool" / "ui" / "pages").glob("*.py")):
            if path.name in ("__init__.py",):
                continue
            used = self._attribute_uses(path, "app")
            absent = sorted(name for name in used if not hasattr(self.window_cls, name))
            if absent:
                missing[path.name] = absent
        self.assertEqual(missing, {}, "pages call window members that do not exist")

    def test_theme_names_all_exist(self) -> None:
        constants = {name for name in dir(self.theme) if name.isupper()}
        missing: dict[str, list[str]] = {}
        for path in sorted((ROOT / "bestmdmtool" / "ui").rglob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            used = {
                node.attr
                for node in ast.walk(tree)
                if isinstance(node, ast.Attribute)
                and isinstance(node.value, ast.Name)
                and node.value.id == "theme"
                and node.attr.isupper()
            }
            absent = sorted(used - constants)
            if absent:
                missing[path.name] = absent
        self.assertEqual(missing, {}, "unknown theme constants")


if __name__ == "__main__":
    unittest.main()
