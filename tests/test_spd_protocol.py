"""Tests for the Spreadtrum BSL stack: framing, transfers and error handling."""

from __future__ import annotations

import unittest

from servicecore.spd import constants as C
from servicecore.spd.crc import FrameReader, crc16_xmodem, encode_frame, escape, unescape
from servicecore.spd.device import SpdDevice, SpdError
from servicecore.spd.protocol import BslClient, BslError, BslNack
from servicecore.spd.simulator import SimulatedDevice
from servicecore.spd.transport import TransportError, pair


class FramingTests(unittest.TestCase):
    def test_crc_known_vector(self) -> None:
        # CRC16-XMODEM of "123456789" is 0x31C3.
        self.assertEqual(crc16_xmodem(b"123456789"), 0x31C3)

    def test_escape_roundtrip(self) -> None:
        data = bytes(range(256))
        self.assertEqual(unescape(escape(data)), data)
        self.assertIn(b"\x7d", escape(b"\x7e\x7d"))

    def test_frame_roundtrip(self) -> None:
        payload = b"\x00\x7e\x7d\xff" * 10
        frame = encode_frame(payload)
        self.assertTrue(frame.startswith(b"\x7e") and frame.endswith(b"\x7e"))
        reader = FrameReader()
        self.assertEqual(reader.feed(frame), [payload])
        self.assertEqual(reader.checksum_errors, 0)

    def test_corrupt_frame_is_rejected(self) -> None:
        frame = bytearray(encode_frame(b"hello"))
        frame[3] ^= 0xFF
        reader = FrameReader()
        self.assertEqual(reader.feed(bytes(frame)), [])
        self.assertEqual(reader.checksum_errors, 1)

    def test_frames_split_across_reads(self) -> None:
        reader = FrameReader()
        frame = encode_frame(b"payload-chunk")
        self.assertEqual(reader.feed(frame[:4]), [])
        self.assertEqual(reader.feed(frame[4:]), [b"payload-chunk"])

    def test_oversized_payload_is_refused(self) -> None:
        with self.assertRaises(ValueError):
            encode_frame(b"\x00" * (0x20000))


class ClientTests(unittest.TestCase):
    def setUp(self) -> None:
        self.device = SimulatedDevice()
        self.client = BslClient(self.device.host)

    def test_connect_and_read_chip(self) -> None:
        self.assertEqual(self.client.connect(), b"BSL")
        info = self.client.read_chip_type()
        self.assertEqual(info.chip_id, 0x9832)
        self.assertEqual(info.flash_id, 0x00170000)
        self.assertEqual(self.client.read_version(), "SPL-SIM-1.0")

    def test_connect_times_out_without_a_device(self) -> None:
        host, _peer = pair()  # nothing attached to the other end
        client = BslClient(host, timeout_scale=0.2)
        with self.assertRaises(BslError):
            client.connect(retries=1)

    def test_write_then_read_roundtrip(self) -> None:
        self.client.connect()
        payload = bytes(range(256)) * 40
        self.client.write_flash(0x20000, payload)
        self.assertEqual(self.client.read_flash(0x20000, len(payload)), payload)

    def test_block_sized_transfer(self) -> None:
        self.client.connect()
        payload = b"\x5a" * (C.BLOCK_SIZE * 2 + 7)
        self.client.write_flash(0, payload)
        self.assertEqual(self.client.read_flash(0, len(payload)), payload)

    def test_erase_sets_flash_to_ff(self) -> None:
        self.client.connect()
        self.client.write_flash(0, b"\x11" * 4096)
        self.client.erase_flash(0, 4096)
        self.assertEqual(self.client.read_flash(0, 32), b"\xff" * 32)

    def test_nack_is_reported_with_the_reason(self) -> None:
        self.client.connect()
        with self.assertRaises(BslNack) as caught:
            self.device.write_protected = ("miscdata",)
            self.client.write_flash(0x7C0000, b"\x00" * 16)
        self.assertIn("write protected", str(caught.exception))

    def test_read_outside_flash_is_refused(self) -> None:
        self.client.connect()
        with self.assertRaises(BslNack):
            self.client.read_flash(len(self.device.flash) - 8, 64)

    def test_progress_callback_sees_steps(self) -> None:
        seen: list[int] = []
        client = BslClient(self.device.host, progress=seen.append)
        client.connect()
        client.write_flash(0, b"\x01" * (C.ROM_BLOCK_SIZE * 3))
        self.assertTrue(seen)
        self.assertEqual(max(seen), 100)


class DeviceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.device = SpdDevice.connect(kind="simulator")
        self.addCleanup(self.device.close)

    def test_handshake_reports_the_chip(self) -> None:
        self.assertTrue(self.device.connected)
        self.assertEqual(self.device.info.chip_id, 0x9832)
        self.assertEqual(self.device.info.version, "SPL-SIM-1.0")

    def test_partitions_come_from_the_loader(self) -> None:
        entries = self.device.read_partitions()
        self.assertGreaterEqual(len(entries), 4)
        self.assertEqual(entries[0].name, "splloader")
        self.assertEqual(self.device.partition_source, "fdl")

    def test_read_and_write_a_partition(self) -> None:
        import tempfile
        from pathlib import Path

        self.device.read_partitions()
        work = Path(tempfile.mkdtemp())
        image = work / "boot.bin"
        image.write_bytes(b"\x7fELF" + b"\x00" * 4092)

        result = self.device.write_partition("boot", image)
        self.assertEqual(result["size"], 4096)

        target = work / "readback.bin"
        self.device.read_partition("boot", target)
        self.assertEqual(target.read_bytes()[:8], image.read_bytes()[:8])

    def test_erase_partition(self) -> None:
        self.device.read_partitions()
        result = self.device.erase_partition("boot")
        self.assertTrue(result["partition"])

    def test_unknown_partition_is_reported(self) -> None:
        self.device.read_partitions()
        with self.assertRaises(SpdError):
            self.device.find("does-not-exist")

    def test_image_larger_than_partition_is_refused(self) -> None:
        import tempfile
        from pathlib import Path

        self.device.read_partitions()
        entry = self.device.find("miscdata")
        big = Path(tempfile.mkdtemp()) / "big.bin"
        big.write_bytes(b"\x00" * (entry.size + 512))
        with self.assertRaises(SpdError):
            self.device.write_partition("miscdata", big)

    def test_unsupported_transport_is_reported(self) -> None:
        with self.assertRaises(TransportError):
            SpdDevice.open_transport("no-such-transport")


if __name__ == "__main__":
    unittest.main()
