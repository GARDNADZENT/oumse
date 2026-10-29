"""Build the whole interface headlessly and exercise every page action."""

from __future__ import annotations

import os
import queue
import tempfile
import time
import unittest

from tests.tk_stub import install_fake_tkinter


class FakeCommandResult:
    def __init__(self, op="op", ok=True, detail="", data=b""):
        self.op = op
        self.ok = ok
        self.detail = detail
        self.data = data
        self.duration = 0.01


class FakeSession:
    """Stands in for ServiceSession without touching USB."""

    def __init__(self) -> None:
        self.is_running = True
        self.events: queue.Queue = queue.Queue()
        self.device = {"chip": "MT6768", "hwcode": "0x707", "storage": "eMMC", "parts": 2, "pagesize": 512}
        self.partitions = [
            {"name": "boot", "sectors": 65536, "size": 33554432, "sector": 1024, "pagesize": 512},
            {"name": "userdata", "sectors": 2097152, "size": 1073741824, "sector": 2048, "pagesize": 512},
        ]
        self.calls: list[tuple] = []

    def _record(self, *args):
        self.calls.append(args)
        return FakeCommandResult(op=args[0])

    def read_partition(self, part, out, **kwargs):
        return self._record("read", part, out)

    def write_partition(self, part, src, **kwargs):
        return self._record("write", part, src)

    def erase(self, parts, **kwargs):
        return self._record("erase", tuple(parts))

    def dump(self, directory, parts=None, **kwargs):
        return self._record("dump", directory, tuple(parts or ()))

    def export_gpt(self, out, **kwargs):
        return self._record("gpt_export", out)

    def read_flash(self, offset, length, out, **kwargs):
        return self._record("readflash", offset, length, out)

    def write_flash(self, src, offset, **kwargs):
        return self._record("writeflash", src, offset)

    def erase_flash(self, offset, length, **kwargs):
        return self._record("eraseflash", offset, length)

    def peek(self, addr, length, **kwargs):
        return FakeCommandResult(op="peek", ok=True, detail="", data=b"\x01\x02\x03\x04")

    def poke(self, addr, data, **kwargs):
        return self._record("poke", addr, data)

    def seccfg(self, state, **kwargs):
        return self._record("seccfg", state)

    def reboot(self, mode=0, **kwargs):
        return self._record("reboot", mode)

    def refresh_gpt(self, **kwargs):
        return self.partitions

    def stop(self, reboot=False, **kwargs):
        self.is_running = False


class UiSmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        install_fake_tkinter()
        cls.tmp = tempfile.mkdtemp(prefix="bestmdm-ui-")
        image = os.path.join(cls.tmp, "boot.img")
        with open(image, "wb") as handle:
            handle.write(b"\x00" * 4096)
        os.makedirs(os.path.join(cls.tmp, "dir"), exist_ok=True)

        # The stubbed file dialogs point at this directory.
        os.makedirs("/tmp/smoke/dir", exist_ok=True)
        for name in ("image.bin", "boot.img"):
            with open(os.path.join("/tmp/smoke", name), "wb") as handle:
                handle.write(b"\x00" * 2048)

        from bestmdmtool.gui import BestMDMToolApp

        cls.app = BestMDMToolApp()
        cls.session = FakeSession()
        cls.app.controller.session = cls.session
        cls.app.controller.device = dict(cls.session.device)
        cls.app.controller.partitions = list(cls.session.partitions)
        cls.app._on_device(dict(cls.session.device))

    def _settle(self, seconds: float = 0.4) -> None:
        deadline = time.time() + seconds
        while time.time() < deadline:
            pending = [t for t in __import__("threading").enumerate() if t.name == "svc-worker" and t.is_alive()]
            if not pending:
                break
            time.sleep(0.02)
        time.sleep(0.05)

    def test_all_pages_build_and_raise(self) -> None:
        from bestmdmtool.ui.pages import PAGES

        for key in PAGES:
            with self.subTest(page=key):
                self.app.show_page(key)
                self.assertIn(key, self.app._pages)

    def test_partition_actions_reach_the_runner(self) -> None:
        page = self.app._pages["partitions"]
        page._render()
        page.tree.selection = lambda: ["item1"]  # type: ignore[assignment]
        page.tree.item = lambda *args, **kwargs: ("boot", "32 MB", 65536, 524288)  # type: ignore[assignment]

        self.assertEqual(page.selected_names(), ["boot"])
        page._update_selection_label()

        page._read_selected()
        self._settle()
        page._write_selected()
        self._settle()
        page._erase_selected()
        self._settle()
        page._export_gpt()
        self._settle()

        kinds = [call[0] for call in self.session.calls]
        self.assertIn("read", kinds)
        self.assertIn("write", kinds)
        self.assertIn("erase", kinds)
        self.assertIn("gpt_export", kinds)

    def test_flasher_page_actions(self) -> None:
        page = self.app._pages["flasher"]
        page.on_show()
        page.image_row.set(os.path.join(self.tmp, "boot.img"))
        page.partition_var.set("boot")
        page._flash_single()
        self._settle()

        page.raw_file.set(os.path.join(self.tmp, "boot.img"))
        page.raw_offset.set("0x1000")
        page._flash_raw()
        self._settle()

        page._add_images()
        page._flash_queue()
        self._settle()

        kinds = [call[0] for call in self.session.calls]
        self.assertIn("write", kinds)
        self.assertIn("writeflash", kinds)

    def test_advanced_page_actions(self) -> None:
        page = self.app._pages["advanced"]
        page.read_offset.set("0x0")
        page.read_length.set("long")
        page._read_range()  # invalid input must not raise
        page.read_length.set("4096")
        page._read_range()
        self._settle()

        page.erase_offset.set("0")
        page.erase_length.set("4096")
        page._erase_range()
        self._settle()

        page.mem_addr.set("0x1000")
        page.mem_len.set("16")
        page._peek()
        self._settle()

        page.poke_addr.set("0x1000")
        page.poke_data.set("00112233")
        page._poke()
        self._settle()

        kinds = [call[0] for call in self.session.calls]
        self.assertIn("readflash", kinds)
        self.assertIn("eraseflash", kinds)
        self.assertIn("poke", kinds)

    def test_bootloader_and_adb_pages(self) -> None:
        boot = self.app._pages["bootloader"]
        boot._seccfg("unlock")
        self._settle()
        self.assertIn("seccfg", [call[0] for call in self.session.calls])

        adb = self.app._pages["adb"]
        adb._run_shell()
        self._settle()

    def test_settings_save_roundtrip(self) -> None:
        page = self.app._pages["settings"]
        page.mode_var.set("preloader")
        page.transport_var.set("serial")
        page._save()
        self.assertEqual(self.app.controller.settings.mode, "preloader")
        page._reset()

    def test_controller_events_update_ui(self) -> None:
        from servicecore.service_session import ServiceEvent

        controller = self.app.controller
        controller._handle_event(ServiceEvent("step", "read", "boot"))
        controller._handle_event(ServiceEvent("progress", "4096"))
        controller._handle_event(ServiceEvent("ok", "read", "boot:4096"))
        controller._handle_event(ServiceEvent("fail", "write", "boot:refused"))
        controller._handle_event(ServiceEvent("info", "chip", "MT6768"))
        controller._handle_event(ServiceEvent("raw", message="mtkclient log line"))
        self.assertIn("MT6768", controller.device.values())


if __name__ == "__main__":
    unittest.main()
