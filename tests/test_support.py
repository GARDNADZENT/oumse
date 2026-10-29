"""Tests for the support bundle offered from Settings."""

from __future__ import annotations

import json
import logging
import os
import tempfile
import unittest
import zipfile
from pathlib import Path

from bestmdmtool import applog, support

DEVICE = {"chip": "MT6768", "hwcode": "0x0707", "storage": "UFS"}
PARTITIONS = [
    {"name": "boot", "sectors": 65536, "size": 33554432},
    {"name": "userdata", "sectors": 4194304, "size": 2147483648},
]


class SupportBundleTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.directory = Path(self._tmp.name)
        previous = os.environ.get("BESTMDMTOOL_LOG_DIR")
        os.environ["BESTMDMTOOL_LOG_DIR"] = str(self.directory / "logs")
        if previous is None:
            self.addCleanup(os.environ.pop, "BESTMDMTOOL_LOG_DIR", None)
        else:
            self.addCleanup(os.environ.__setitem__, "BESTMDMTOOL_LOG_DIR", previous)
        logger = logging.getLogger(applog.LOGGER_NAME)
        self.addCleanup(self._shutdown, logger)

    @staticmethod
    def _shutdown(logger: logging.Logger) -> None:
        for handler in list(logger.handlers):
            logger.removeHandler(handler)
            handler.close()

    def test_default_target_is_timestamped(self) -> None:
        first = support.default_target(self.directory)
        self.assertEqual(first.parent, self.directory)
        self.assertTrue(first.name.startswith(support.BUNDLE_STEM))
        self.assertTrue(first.suffix == ".zip")

    def test_bundle_contains_logs_self_test_and_device(self) -> None:
        applog.configure()
        applog.record("Device connected. 2 partitions found.", "OK")
        applog.write_crash("Traceback: boom")
        logging.getLogger(applog.LOGGER_NAME).handlers[0].flush()

        target = self.directory / "bundle.zip"
        path = support.build(
            device=DEVICE,
            partitions=PARTITIONS,
            settings={"mode": "brom"},
            selftest={"ok": True, "libusb_backend": True},
            target=target,
        )
        self.assertEqual(path, target)
        with zipfile.ZipFile(target) as archive:
            names = archive.namelist()
            self.assertIn("activity.log", names)
            self.assertIn("system.txt", names)
            self.assertIn("device.json", names)
            self.assertIn("selftest.json", names)
            self.assertTrue(any(name.startswith("crash-") for name in names), names)

            system = archive.read("system.txt").decode("utf-8")
            self.assertIn("platform:", system)
            self.assertIn("frozen:", system)

            device = json.loads(archive.read("device.json").decode("utf-8"))
            self.assertEqual(device["device"]["chip"], "MT6768")
            self.assertEqual(device["partitions"], 2)
            self.assertEqual(device["partition_names"], ["boot", "userdata"])

            selftest = json.loads(archive.read("selftest.json").decode("utf-8"))
            self.assertTrue(selftest["ok"])

            activity = archive.read("activity.log").decode("utf-8")
            self.assertIn("Device connected. 2 partitions found.", activity)

    def test_bundle_without_logs_still_builds(self) -> None:
        target = self.directory / "empty.zip"
        support.build(target=target)
        with zipfile.ZipFile(target) as archive:
            self.assertIn("device.json", archive.namelist())
            self.assertNotIn("activity.log", archive.namelist())


if __name__ == "__main__":
    unittest.main()
