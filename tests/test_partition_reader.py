"""Tests for the single-purpose MTK BootROM reader window."""

from __future__ import annotations

import time
import unittest
from unittest.mock import patch

from tests.tk_stub import install_fake_tkinter


class PartitionReaderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        install_fake_tkinter(force=True)
        from bestmdmtool.gui import BestMDMToolApp

        cls.app = BestMDMToolApp()

    def setUp(self) -> None:
        self.app.last_scan = {}
        self.app.partition_tree.delete(*self.app.partition_tree.get_children())

    def test_app_exposes_only_the_read_only_reader(self) -> None:
        self.assertNotIn("controller", vars(self.app))
        self.assertNotIn("nav", vars(self.app))
        self.assertNotIn("ops_body", vars(self.app))
        self.assertEqual(self.app.partition_tree.get_children(), ())
        self.assertEqual(self.app.read_button._config.get("state"), "disabled")

    def test_passive_scan_can_recognize_brom_without_opening_a_session(self) -> None:
        report = {
            "relevant": [
                {
                    "vendor": "MTK",
                    "protocol": "BROM",
                    "usb": "0E8D:2000",
                    "service": "WinUSB",
                    "port": "",
                }
            ]
        }
        self.app._finish_scan(report)
        self.assertIn("MTK BROM detected", self.app.device_status._config["text"])
        self.assertIn("0E8D:2000", self.app.device_status._config["text"])
        self.assertIn("no session opened", self.app.status_label._config["text"])
        self.assertEqual(self.app.partition_tree.get_children(), ())
        self.assertEqual(self.app.read_button._config.get("state"), "disabled")

    def test_preloader_and_spd_are_not_mtk_brom(self) -> None:
        self.app._finish_scan(
            {
                "relevant": [
                    {"vendor": "MTK", "protocol": "PreLoader", "usb": "0E8D:0003"},
                    {"vendor": "SPD", "protocol": "BSL", "usb": "1782:4D00"},
                ]
            }
        )
        self.assertIn("not in BootROM mode", self.app.device_status._config["text"])
        self.assertEqual(self.app.read_button._config.get("state"), "disabled")

    def test_unavailable_read_fails_closed_with_clear_status(self) -> None:
        self.app._read_selected()
        self.assertIn("disabled pending independent MTK security review", self.app.status_label._config["text"])

    def test_scan_uses_passive_discovery_only(self) -> None:
        report = {"relevant": [{"vendor": "MTK", "protocol": "BROM", "usb": "0E8D:2000"}]}
        with patch("bestmdmtool.ui.partition_reader.scan_report", return_value=report) as scan:
            self.app.scan_usb()
            deadline = time.monotonic() + 2
            while self.app._scan_in_progress and time.monotonic() < deadline:
                time.sleep(0.01)
        scan.assert_called_once_with()
        self.assertNotIn("controller", vars(self.app))
        self.assertIn("MTK BROM detected", self.app.device_status._config["text"])


if __name__ == "__main__":
    unittest.main()
