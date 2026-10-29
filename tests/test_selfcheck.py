"""Tests for the backend self-test plumbing.

The 0.3.0 release shipped a device runner that could not import its own
dependencies. The UI still claimed a device was connected. The self-test exists
so a broken installation names its own cause, and these tests pin that down.
"""

from __future__ import annotations

import json
import sys
import tempfile
import textwrap
import time
import unittest
from pathlib import Path

from servicecore import selfcheck
from servicecore.config import selfcheck_command

GOOD_REPORT = {
    "ok": True,
    "frozen": True,
    "python": "3.12.8 (main,  2024)",
    "mtkclient": True,
    "libusb_backend": True,
    "libusb_dll": r"C:\app\runtime\runner\libusb-1.0.dll",
    "usb_devices": 1,
    "runtime_lib": r"C:\app\runtime\lib",
    "da_v5": True,
    "da_v6": True,
    "operations": ["dump", "erase", "gpt", "peek", "poke", "read", "reboot", "seccfg", "write"],
}


def _write_script(directory: Path, body: str) -> Path:
    script = directory / "fake_runner.py"
    script.write_text(textwrap.dedent(body), encoding="utf-8")
    return script


class SelfcheckCommandTests(unittest.TestCase):
    def test_source_checkout_command_uses_runner_entry(self) -> None:
        command = selfcheck_command()
        self.assertIsNotNone(command)
        argv, cwd = command
        self.assertIn("--selftest", argv)
        self.assertTrue(any(part.endswith("runner_entry.py") for part in argv), argv)
        self.assertTrue(Path(cwd).is_dir())


class SelfcheckRunTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.directory = Path(self._tmp.name)
        self._original = selfcheck.selfcheck_command
        self.addCleanup(setattr, selfcheck, "selfcheck_command", self._original)

    def _point_at(self, script: Path) -> None:
        selfcheck.selfcheck_command = lambda: ([sys.executable, str(script)], self.directory)

    def test_parses_a_healthy_report(self) -> None:
        script = _write_script(
            self.directory,
            f"""
            import json, sys
            json.dump({GOOD_REPORT!r}, open(sys.argv[1], "w"))
            """,
        )
        self._point_at(script)
        report = selfcheck.run(self.directory / "report.json")
        self.assertTrue(report["ok"])
        self.assertEqual(report["exit_code"], 0)
        self.assertTrue(selfcheck.is_healthy(report))
        self.assertIn("mtkclient: yes", "\\n".join(report["lines"]))
        self.assertIn("libusb backend: yes", "\\n".join(report["lines"]))
        self.assertIsInstance(report["duration"], float)

    def test_failure_names_the_missing_piece(self) -> None:
        broken = dict(GOOD_REPORT, ok=False, libusb_backend=False, libusb_dll=None)
        script = _write_script(
            self.directory,
            f"""
            import json, sys
            json.dump({broken!r}, open(sys.argv[1], "w"))
            """,
        )
        self._point_at(script)
        report = selfcheck.run(self.directory / "report.json")
        self.assertFalse(report["ok"])
        self.assertFalse(selfcheck.is_healthy(report))
        self.assertIn("libusb", selfcheck.describe_failure(report))
        self.assertTrue(any("libusb backend: NO" in line for line in report["lines"]))

    def test_missing_report_uses_the_exit_code(self) -> None:
        script = _write_script(self.directory, "import sys\nsys.exit(5)\n")
        self._point_at(script)
        report = selfcheck.run(self.directory / "report.json")
        self.assertFalse(report["ok"])
        self.assertEqual(report["exit_code"], 5)
        self.assertIn("5", report["error"])

    def test_stale_report_is_never_trusted(self) -> None:
        stale = self.directory / "bestmdmtool-selftest.json"
        stale.write_text(json.dumps(GOOD_REPORT), encoding="utf-8")
        script = _write_script(self.directory, "import sys\nsys.exit(9)\n")
        self._point_at(script)
        original = selfcheck.tempfile.gettempdir
        selfcheck.tempfile.gettempdir = lambda: str(self.directory)
        self.addCleanup(setattr, selfcheck.tempfile, "gettempdir", original)

        report = selfcheck.run()
        self.assertFalse(report["ok"], "a report left over from an earlier run must not count")

    def test_no_runner_installed(self) -> None:
        selfcheck.selfcheck_command = lambda: None
        report = selfcheck.run()
        self.assertFalse(report["ok"])
        self.assertIn("no device runner", report["error"])

    def test_unstartable_runner_is_reported(self) -> None:
        selfcheck.selfcheck_command = lambda: ([str(self.directory / "does-not-exist.exe")], self.directory)
        report = selfcheck.run()
        self.assertFalse(report["ok"])
        self.assertIn("cannot start", report["error"])

    def test_healthy_requires_every_key(self) -> None:
        self.assertTrue(selfcheck.is_healthy(dict(GOOD_REPORT)))
        for key in selfcheck.REQUIRED_KEYS:
            weaker = dict(GOOD_REPORT)
            weaker[key] = False
            self.assertFalse(selfcheck.is_healthy(weaker), key)


class ControllerSelftestTests(unittest.TestCase):
    def test_controller_logs_the_self_test(self) -> None:
        from tests.tk_stub import install_fake_tkinter

        install_fake_tkinter(force=True)
        from bestmdmtool.ui.controller import Controller

        logs: list[tuple[str, str]] = []
        controller = Controller(
            log=lambda message, level: logs.append((level, message)),
            on_device=lambda device: None,
            on_disconnect=lambda reason: None,
            on_progress=lambda done, total: None,
            on_busy=lambda busy, text: None,
            schedule=lambda action: action(),
        )
        original = selfcheck.run
        selfcheck.run = lambda *args, **kwargs: dict(GOOD_REPORT, duration=0.5, lines=["mtkclient: yes"])
        self.addCleanup(setattr, selfcheck, "run", original)

        seen: list[dict] = []
        controller.run_backend_selftest(seen.append)

        deadline = time.monotonic() + 5.0
        while not seen and time.monotonic() < deadline:
            time.sleep(0.02)

        self.assertTrue(seen, "the completion callback never ran")
        self.assertTrue(any("Backend self-test passed" in message for _level, message in logs))
        self.assertTrue(any(level == "OK" for level, _message in logs))


if __name__ == "__main__":
    unittest.main()
