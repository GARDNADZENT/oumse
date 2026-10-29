"""Protocol tests for the service runner and its client session."""

from __future__ import annotations

import json
import unittest

from servicecore.service_session import CommandResult, ServiceEvent, ServiceSession, find_partition


class ParseTests(unittest.TestCase):
    def test_ready_event_is_decoded(self) -> None:
        payload = {"chip": "MT6768", "partitions": [{"name": "boot", "size": 1024}]}
        event = ServiceSession._parse("SVC_READY:%s" % json.dumps(payload))
        self.assertEqual(event.kind, "ready")
        self.assertEqual(event.payload["chip"], "MT6768")

    def test_step_and_log_events(self) -> None:
        step = ServiceSession._parse("SVC_STEP:read:boot")
        self.assertEqual((step.kind, step.topic, step.message), ("step", "read", "boot"))

        log = ServiceSession._parse("SVC_LOG:WARN:da rejected")
        self.assertEqual((log.kind, log.topic, log.message), ("log", "WARN", "da rejected"))

    def test_ok_and_fail_events(self) -> None:
        ok = ServiceSession._parse("SVC_OK:read:boot:33554432")
        self.assertEqual((ok.kind, ok.topic, ok.message), ("ok", "read", "boot:33554432"))

        bad = ServiceSession._parse("SVC_FAIL:write:refused")
        self.assertEqual((bad.kind, bad.topic, bad.message), ("fail", "write", "refused"))

    def test_peek_payload_and_raw_lines(self) -> None:
        peek = ServiceSession._parse("SVC_OK:peek:4")
        self.assertEqual(peek.topic, "peek")
        data = ServiceSession._parse("SVC_DATA:00112233")
        self.assertEqual(data.kind, "data")
        self.assertEqual(data.message, "00112233")

        raw = ServiceSession._parse("mtkclient: hello")
        self.assertEqual(raw.kind, "raw")


class DispatchTests(unittest.TestCase):
    def _session(self) -> ServiceSession:
        return ServiceSession("python", "service_runner.py")

    def test_ready_populates_device_and_partitions(self) -> None:
        session = self._session()
        session._dispatch(
            ServiceEvent("ready", payload={"chip": "MT6835", "partitions": [{"name": "boot"}]})
        )
        self.assertEqual(session.device["chip"], "MT6835")
        self.assertEqual(session.partitions[0]["name"], "boot")

    def test_ok_result_is_recorded_for_waiters(self) -> None:
        session = self._session()
        session._dispatch(ServiceEvent("ok", "read", "boot:4096"))
        result = session._done.pop("read")
        self.assertTrue(result.ok)
        self.assertEqual(result.detail, "boot:4096")

    def test_fail_result_is_recorded(self) -> None:
        session = self._session()
        session._dispatch(ServiceEvent("fail", "erase", "unknown_partition:foo"))
        result = session._done.pop("erase")
        self.assertFalse(result.ok)
        self.assertIn("unknown_partition", result.detail)


class HelperTests(unittest.TestCase):
    def test_find_partition_is_case_insensitive(self) -> None:
        parts = [{"name": "Boot"}, {"name": "userdata"}]
        self.assertEqual(find_partition(parts, "boot")["name"], "Boot")
        self.assertEqual(find_partition(parts, "USERDATA")["name"], "userdata")
        self.assertIsNone(find_partition(parts, "missing"))
        self.assertIsNone(find_partition(parts, ""))


class CommandResultTests(unittest.TestCase):
    def test_defaults(self) -> None:
        result = CommandResult(op="read", ok=True)
        self.assertEqual(result.data, b"")
        self.assertEqual(result.events, [])


class RunnerSourceTests(unittest.TestCase):
    """Static checks on the runner so protocol drift is caught without USB."""

    def setUp(self) -> None:
        from pathlib import Path

        self.source = (Path(__file__).resolve().parents[1] / "servicecore" / "runner" / "service_runner.py").read_text(
            encoding="utf-8"
        )

    def test_supported_operations_are_registered(self) -> None:
        for op in (
            "info",
            "gpt",
            "gpt_export",
            "read",
            "write",
            "erase",
            "dump",
            "readflash",
            "writeflash",
            "eraseflash",
            "peek",
            "poke",
            "seccfg",
            "reboot",
        ):
            with self.subTest(op=op):
                self.assertIn('"%s": op_' % op, self.source)

    def test_runner_reuses_field_tested_serial_patches(self) -> None:
        self.assertIn("oumse_brom_session_runner", self.source)
        self.assertIn("COMPAT_PATCHES", self.source)

    def test_runner_has_no_network_or_login_logic(self) -> None:
        for token in ("/api/", "heartbeat", "socket", "requests", "urllib", "_show_login"):
            with self.subTest(token=token):
                self.assertNotIn(token, self.source)

    def test_dangerous_ops_require_explicit_arguments(self) -> None:
        self.assertIn('missing_args', self.source)
        self.assertIn('no_such_partition', self.source)
        self.assertIn('state_must_be_unlock_or_lock', self.source)


if __name__ == "__main__":
    unittest.main()
