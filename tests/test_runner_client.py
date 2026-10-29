"""End-to-end tests for the runner client against fake runner scripts.

Regression cover for the 0.3.0 bug where a runner that died during import was
reported as "Device connected. 0 partitions found."
"""

from __future__ import annotations

import os
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

from servicecore.service_session import ServiceSession

READY_RUNNER = """
import json, sys

partitions = [
    {"name": "boot", "sectors": 64, "size": 32768, "sector": 1024, "pagesize": 512},
    {"name": "userdata", "sectors": 128, "size": 65536, "sector": 2048, "pagesize": 512},
]
print("SVC_INFO:chip:MT6768", flush=True)
print("SVC_READY:" + json.dumps({"chip": "MT6768", "partitions": partitions}), flush=True)

for line in sys.stdin:
    line = line.strip()
    if not line:
        continue
    command = json.loads(line)
    op = command.get("op")
    if op == "quit":
        print("SVC_BYE", flush=True)
        break
    if op == "read":
        print("SVC_PROGRESS:4096", flush=True)
        print("SVC_OK:read:%s:4096" % command["part"], flush=True)
    elif op == "erase":
        bad = [p for p in command.get("parts", []) if p not in ("boot", "userdata")]
        if bad:
            print("SVC_FAIL:erase:unknown_partition:%s" % ",".join(bad), flush=True)
        else:
            print("SVC_OK:erase:%s" % ",".join(command["parts"]), flush=True)
    elif op == "peek":
        print("SVC_OK:peek:4", flush=True)
        print("SVC_DATA:00112233", flush=True)
    else:
        print("SVC_OK:%s" % op, flush=True)
"""

FAILING_RUNNER = """
import sys
print("OUMSE_FAIL:import:No module named '_socket'", flush=True)
sys.exit(3)
"""

SILENT_CRASH_RUNNER = """
raise SystemExit(1)
"""


class RunnerClientTests(unittest.TestCase):
    def _write(self, directory: str, name: str, source: str) -> Path:
        path = Path(directory) / name
        path.write_text(textwrap.dedent(source), encoding="utf-8")
        return path

    def _session(self, directory: str, source: str) -> ServiceSession:
        script = self._write(directory, "fake_runner.py", source)
        return ServiceSession(Path(sys.executable), script, cwd=directory)

    def test_runner_that_dies_before_ready_is_a_failure(self) -> None:
        """The reported bug: a crash at import looked like a successful connect."""
        with tempfile.TemporaryDirectory() as directory:
            session = self._session(directory, FAILING_RUNNER)
            ok = session.start(wait=20.0)
            self.assertFalse(ok)
            self.assertIn("_socket", session.last_error)
            session.stop()

    def test_silent_crash_is_a_failure(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            session = self._session(directory, SILENT_CRASH_RUNNER)
            self.assertFalse(session.start(wait=20.0))
            self.assertTrue(session.last_error)
            session.stop()

    def test_missing_runner_file_raises(self) -> None:
        session = ServiceSession(Path(sys.executable), "does-not-exist.py")
        with self.assertRaises(FileNotFoundError):
            session.start(wait=1.0)

    def test_ready_runner_exposes_device_and_partitions(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            session = self._session(directory, READY_RUNNER)
            self.assertTrue(session.start(wait=20.0))
            self.assertEqual(session.device["chip"], "MT6768")
            self.assertEqual([p["name"] for p in session.partitions], ["boot", "userdata"])
            session.stop()

    def test_commands_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            session = self._session(directory, READY_RUNNER)
            self.assertTrue(session.start(wait=20.0))

            read = session.read_partition("boot", os.path.join(directory, "boot.bin"), timeout=20.0)
            self.assertTrue(read.ok)

            erase = session.erase(["boot"], timeout=20.0)
            self.assertTrue(erase.ok)

            erase_bad = session.erase(["nope"], timeout=20.0)
            self.assertFalse(erase_bad.ok)
            self.assertIn("unknown_partition", erase_bad.detail)

            session.stop()

    def test_progress_events_reach_the_queue(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            session = self._session(directory, READY_RUNNER)
            self.assertTrue(session.start(wait=20.0))
            session.read_partition("boot", os.path.join(directory, "boot.bin"), timeout=20.0)

            kinds = []
            while not session.events.empty():
                kinds.append(session.events.get_nowait().kind)
            self.assertIn("progress", kinds)
            session.stop()

    def test_peek_payload_is_decoded_to_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            session = self._session(directory, READY_RUNNER)
            self.assertTrue(session.start(wait=20.0))
            result = session.peek(0x1000, 4, timeout=20.0)
            self.assertTrue(result.ok)
            self.assertEqual(result.data, b"\x00\x11\x22\x33")
            session.stop()

    def test_packaged_runner_uses_the_exe_directly(self) -> None:
        """An ``.exe`` runner must be launched without a Python interpreter."""
        with tempfile.TemporaryDirectory() as directory:
            fake_exe = Path(directory) / "BestMDMToolRunner.exe"
            fake_exe.write_text("", encoding="utf-8")
            session = ServiceSession(Path("missing-python"), fake_exe, cwd=directory)
            self.assertEqual(session.runner_path.suffix, ".exe")
            # The launch fails on a non-Windows host, but it must not complain
            # about the interpreter path.
            session.start(wait=5.0)
            self.assertNotIn("Python executable not found", session.last_error)
            session.stop()


if __name__ == "__main__":
    unittest.main()
