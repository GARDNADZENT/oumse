"""Tests for the chipset database and the SPD DIAG/AT console."""

from __future__ import annotations

import unittest

from servicecore import chipsets
from servicecore.spd.diag import AtConsole, AtReply, DiagError


class ChipsetTests(unittest.TestCase):
    def test_both_families_are_present(self) -> None:
        summary = chipsets.summary()
        self.assertGreater(summary["mtk"], 10)
        self.assertGreater(summary["spd"], 10)
        self.assertEqual(summary["total"], summary["mtk"] + summary["spd"])

    def test_every_chip_declares_a_protocol_and_usb_ids(self) -> None:
        for chip in chipsets.ALL_CHIPS:
            with self.subTest(chip=chip.name):
                self.assertIn(chip.protocol, ("brom", "bsl"))
                self.assertEqual(chip.vendor, "MTK" if chip.protocol == "brom" else "SPD")
                self.assertTrue(chip.usb or chip.protocol == "bsl")

    def test_identify_known_parts(self) -> None:
        self.assertEqual(chipsets.identify(chipsets.MTK_VID, 0x2000).vendor, "MTK")
        self.assertEqual(chipsets.identify(chipsets.SPD_VID, 0x4D00).vendor, "SPD")
        self.assertIsNone(chipsets.identify(0x1234, 0x5678))

    def test_by_name_is_case_insensitive(self) -> None:
        self.assertEqual(chipsets.by_name("mt6768").name, "MT6768")
        self.assertEqual(chipsets.by_name("sc9863a").vendor, "SPD")
        self.assertIsNone(chipsets.by_name("nope"))

    def test_search_and_filters(self) -> None:
        helio = chipsets.search("helio")
        self.assertTrue(helio)
        self.assertTrue(all("helio" in (c.family + c.notes).lower() for c in helio))
        self.assertTrue(all(chip.vendor == "SPD" for chip in chipsets.search("", vendor="SPD")))
        self.assertIn("T-series", chipsets.families("SPD"))

    def test_serialisation_for_the_ui(self) -> None:
        payload = chipsets.by_name("MT6768").as_dict()
        self.assertEqual(payload["vendor"], "MTK")
        self.assertTrue(payload["usb"])
        self.assertIn(":", payload["usb"][0])

    def test_scan_usb_never_raises(self) -> None:
        self.assertIsInstance(chipsets.scan_usb(), list)


class _FakePort:
    """Minimal serial stand-in: answers each command from a script."""

    def __init__(self, script: dict[str, bytes]) -> None:
        self.script = script
        self.written: list[bytes] = []
        self._pending = b""
        self.closed = False

    def write(self, data: bytes) -> None:
        self.written.append(data)
        command = data.decode("ascii").strip()
        self._pending = self.script.get(command, b"\r\nERROR\r\n")

    def read(self, size: int) -> bytes:
        if not self._pending:
            return b""
        out, self._pending = self._pending[:size], self._pending[size:]
        return out

    def flush(self) -> None:
        return None

    def close(self) -> None:
        self.closed = True


class DiagTests(unittest.TestCase):
    def test_send_collects_the_reply(self) -> None:
        port = _FakePort({"ATI": b"\r\nUnisoc\r\nSC9863A\r\n\r\nOK\r\n"})
        console = AtConsole(port)
        reply = console.send("ATI")
        self.assertIsInstance(reply, AtReply)
        self.assertTrue(reply.ok)
        self.assertIn("SC9863A", reply.text)
        self.assertEqual(port.written, [b"ATI\r"])

    def test_error_reply_is_not_ok(self) -> None:
        port = _FakePort({})
        reply = AtConsole(port).send("AT+BOGUS")
        self.assertFalse(reply.ok)
        self.assertIn("ERROR", reply.text)

    def test_silence_reports_no_answer(self) -> None:
        class Silent:
            def write(self, _data):  # noqa: ANN001
                return None

            def read(self, _size):  # noqa: ANN001
                return b""

            def close(self):
                return None

        reply = AtConsole(Silent()).send("AT", timeout=0.15)
        self.assertFalse(reply.ok)
        self.assertIn("no answer", reply.text)

    def test_identify_collects_fields(self) -> None:
        port = _FakePort(
            {
                "AT+CGMM": b"\r\nSC9863A\r\nOK\r\n",
                "AT+CGMI": b"\r\nUnisoc\r\nOK\r\n",
                "AT+CGMR": b"\r\nSPRD-1.0\r\nOK\r\n",
                "AT+CGSN": b"\r\n123456789012345\r\nOK\r\n",
                "AT+CPIN?": b"\r\n+CPIN: READY\r\nOK\r\n",
            }
        )
        values = AtConsole(port).identify()
        self.assertEqual(values["model"], "SC9863A")
        self.assertEqual(values["manufacturer"], "Unisoc")
        self.assertEqual(values["imei"], "123456789012345")

    def test_empty_command_is_refused(self) -> None:
        with self.assertRaises(DiagError):
            AtConsole(_FakePort({})).send("   ")

    def test_presets_are_labelled(self) -> None:
        for command, label in __import__("servicecore.spd.diag", fromlist=["PRESETS"]).PRESETS:
            self.assertTrue(command.startswith("AT"))
            self.assertTrue(label)


if __name__ == "__main__":
    unittest.main()
