from __future__ import annotations

import json
import unittest

from app.session import BromSession


class SessionParsingTests(unittest.TestCase):
    def test_ready_event(self) -> None:
        payload = {
            "chip": "MT6835",
            "partitions": [{"name": "proinfo", "size": 1024, "sectors": 2}],
        }
        event = BromSession._parse_line("OUMSE_READY:" + json.dumps(payload))
        self.assertEqual(event.kind, "ready")
        self.assertEqual(event.payload, payload)

    def test_invalid_ready_payload(self) -> None:
        event = BromSession._parse_line("OUMSE_READY:{broken")
        self.assertEqual(event.kind, "fail")
        self.assertIn("Invalid OUMSE_READY", event.message)

    def test_ok_and_fail_events(self) -> None:
        ok_event = BromSession._parse_line("OUMSE_OK:read:proinfo:1024")
        fail_event = BromSession._parse_line("OUMSE_FAIL:write:refused")
        self.assertEqual(ok_event.kind, "ok")
        self.assertEqual(ok_event.message, "read:proinfo:1024")
        self.assertEqual(fail_event.kind, "fail")
        self.assertEqual(fail_event.message, "write:refused")

    def test_result_marker(self) -> None:
        ok_event = BromSession._parse_line("OUMSE_RESULT:OK")
        fail_event = BromSession._parse_line("OUMSE_RESULT:FAIL:boom")
        self.assertEqual(ok_event.kind, "ok")
        self.assertEqual(fail_event.kind, "fail")

    def test_unknown_line_is_log(self) -> None:
        event = BromSession._parse_line("Status: Handshake failed, retrying...")
        self.assertEqual(event.kind, "log")
        self.assertEqual(event.message, "Status: Handshake failed, retrying...")


if __name__ == "__main__":
    unittest.main()
