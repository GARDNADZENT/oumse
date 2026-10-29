"""Tests for on-disk logging and crash reports.

The windowed build has no console, so a bug report is only useful if the log
file and the crash report actually contain something.
"""

from __future__ import annotations

import logging
import os
import tempfile
import unittest
from pathlib import Path

from bestmdmtool import applog


class AppLogTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self._previous = os.environ.get("BESTMDMTOOL_LOG_DIR")
        os.environ["BESTMDMTOOL_LOG_DIR"] = self._tmp.name
        self.addCleanup(self._restore_env)
        logger = logging.getLogger(applog.LOGGER_NAME)
        self.addCleanup(self._shutdown_logger, logger)

    def _restore_env(self) -> None:
        if self._previous is None:
            os.environ.pop("BESTMDMTOOL_LOG_DIR", None)
        else:
            os.environ["BESTMDMTOOL_LOG_DIR"] = self._previous

    @staticmethod
    def _shutdown_logger(logger: logging.Logger) -> None:
        for handler in list(logger.handlers):
            logger.removeHandler(handler)
            handler.close()

    def test_log_directory_follows_the_override(self) -> None:
        self.assertEqual(applog.log_dir(), Path(self._tmp.name))
        self.assertEqual(applog.log_path(), Path(self._tmp.name) / "activity.log")

    def test_activity_lines_reach_disk(self) -> None:
        applog.configure()
        applog.record("Device connected. 41 partitions found.", "OK")
        applog.record("read failed: timeout", "ERROR")
        logging.getLogger(applog.LOGGER_NAME).handlers[0].flush()

        text = applog.log_path().read_text(encoding="utf-8")
        self.assertIn("Device connected. 41 partitions found.", text)
        self.assertIn("read failed: timeout", text)

    def test_record_without_configuration_is_a_no_op(self) -> None:
        applog.record("nothing listens yet", "INFO")  # must not raise or write
        self.assertFalse(applog.log_path().exists())

    def test_crash_report_has_context(self) -> None:
        applog.configure()
        target = applog.write_crash("Traceback (most recent call last):\n  boom")
        self.assertTrue(target.is_file())
        text = target.read_text(encoding="utf-8")
        self.assertIn("crash report", text)
        self.assertIn("platform:", text)
        self.assertIn("boom", text)
        self.assertIn("python:", text)

    def test_logging_levels_are_mapped(self) -> None:
        applog.configure()
        applog.record("warned", "WARN")
        applog.record("failed", "ERROR")
        logging.getLogger(applog.LOGGER_NAME).handlers[0].flush()
        text = applog.log_path().read_text(encoding="utf-8")
        self.assertIn("WARNING warned", text)
        self.assertIn("ERROR   failed", text)


if __name__ == "__main__":
    unittest.main()
