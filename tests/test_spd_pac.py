"""Tests for PAC firmware handling and the SPD runner command set."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from servicecore.spd import pac
from servicecore.spd.pac import PacError, PacFile


class PacBuildTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.work = Path(self._tmp.name)
        self.folder = self.work / "parts"
        self.folder.mkdir()
        (self.folder / "boot.bin").write_bytes(b"\x01" * 4096)
        (self.folder / "system.bin").write_bytes(b"\x02" * 9000)
        (self.folder / "uboot.bin").write_bytes(b"\x03" * 777)

    def test_build_parse_roundtrip(self) -> None:
        package = PacFile.from_folder(self.folder, version="Roundtrip 1.0")
        self.assertEqual(len(package.entries), 3)
        target = package.save(self.work / "out.pac")

        reopened = PacFile.open(target)
        self.assertEqual(len(reopened.entries), 3)
        self.assertTrue(reopened.verified, reopened.problems)
        self.assertEqual(reopened.version, "Roundtrip 1.0")
        for name in ("boot", "system", "uboot"):
            self.assertEqual(reopened.read_entry(name), (self.folder / ("%s.bin" % name)).read_bytes())

    def test_checksum_is_stored_and_checked(self) -> None:
        package = PacFile.from_folder(self.folder)
        target = package.save(self.work / "crc.pac")
        raw = bytearray(target.read_bytes())
        # Corrupt one byte inside the first partition payload (after the 512 byte
        # header and its 32 byte entry header); the stored CRC must catch it.
        raw[600] ^= 0xFF
        target.write_bytes(bytes(raw))

        reopened = PacFile.open(target)
        self.assertFalse(reopened.verified)
        self.assertTrue(reopened.problems)
        self.assertTrue(any("crc" in problem.lower() for problem in reopened.problems), reopened.problems)

    def test_padding_damage_is_reported_by_the_md5(self) -> None:
        package = PacFile.from_folder(self.folder)
        target = package.save(self.work / "md5.pac")
        raw = bytearray(target.read_bytes())
        raw[-10] ^= 0xFF  # inside the alignment padding of the last entry
        target.write_bytes(bytes(raw))
        reopened = PacFile.open(target)
        self.assertFalse(reopened.md5_matches)
        self.assertFalse(reopened.verified)

    def test_truncated_package_is_rejected(self) -> None:
        package = PacFile.from_folder(self.folder)
        target = package.save(self.work / "full.pac")
        data = target.read_bytes()
        target.write_bytes(data[: len(data) // 2])
        with self.assertRaises(PacError):
            PacFile.open(target)

    def test_non_pac_file_is_rejected(self) -> None:
        junk = self.work / "junk.pac"
        junk.write_bytes(b"not a package at all" * 40)
        with self.assertRaises(PacError):
            PacFile.open(junk)

    def test_extract_writes_every_partition(self) -> None:
        package = PacFile.from_folder(self.folder)
        target = package.save(self.work / "ex.pac")
        out = self.work / "extracted"
        written = PacFile.open(target).extract(out)
        self.assertEqual({path.name for path in written}, {"boot.bin", "system.bin", "uboot.bin"})
        self.assertEqual((out / "system.bin").stat().st_size, 9000)

    def test_flash_offsets_are_sequential(self) -> None:
        package = PacFile.from_folder(self.folder, flash_base=0x100000)
        offsets = [entry.flash_offset for entry in package.entries]
        self.assertEqual(offsets[0], 0x100000)
        self.assertEqual(offsets, sorted(offsets))

    def test_empty_folder_is_refused(self) -> None:
        empty = self.work / "empty"
        empty.mkdir()
        with self.assertRaises(PacError):
            PacFile.from_folder(empty)

    def test_describe_returns_json_friendly_data(self) -> None:
        target = PacFile.from_folder(self.folder).save(self.work / "d.pac")
        info = pac.describe(target)
        self.assertTrue(info["verified"])
        self.assertEqual(len(info["entries"]), 3)
        self.assertIn("total_size", info)

    def test_human_size(self) -> None:
        self.assertEqual(pac.human_size(512), "512 B")
        self.assertIn("KB", pac.human_size(4096))


class PacFlashTests(unittest.TestCase):
    def setUp(self) -> None:
        from servicecore.spd.device import SpdDevice

        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.work = Path(self._tmp.name)
        self.device = SpdDevice.connect(kind="simulator")
        self.addCleanup(self.device.close)
        self.device.read_partitions()

    def _package(self, names: dict[str, int]) -> Path:
        folder = self.work / "pkg"
        folder.mkdir(exist_ok=True)
        for name, size in names.items():
            (folder / ("%s.bin" % name)).write_bytes(bytes([len(name)]) * size)
        return PacFile.from_folder(folder).save(self.work / "fw.pac")

    def test_flash_writes_and_verifies(self) -> None:
        pac_path = self._package({"boot": 8192, "userdata": 4096})
        result = self.device.flash_pac(pac_path)
        self.assertEqual(sorted(result["written"]), ["boot", "userdata"])
        self.assertTrue(result["verified"])

    def test_unverified_package_is_refused(self) -> None:
        pac_path = self._package({"boot": 4096})
        raw = bytearray(pac_path.read_bytes())
        raw[-5] ^= 0xFF
        pac_path.write_bytes(bytes(raw))
        with self.assertRaises(Exception) as caught:
            self.device.flash_pac(pac_path)
        self.assertIn("verification", str(caught.exception))

    def test_partitions_outside_the_device_table_are_skipped(self) -> None:
        pac_path = self._package({"boot": 2048, "unknownpart": 512})
        result = self.device.flash_pac(pac_path)
        self.assertIn("boot", result["written"])
        self.assertEqual(result["skipped"][0]["partition"], "unknownpart")


class SpdRunnerTests(unittest.TestCase):
    def test_selftest_exits_zero_and_reports(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            report = Path(tmp) / "spd.json"
            completed = subprocess.run(
                [sys.executable, "servicecore/runner/spd_runner.py", "--selftest", str(report)],
                capture_output=True,
                text=True,
                timeout=180,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr[-800:])
            data = json.loads(report.read_text(encoding="utf-8"))
        self.assertTrue(data["ok"], data.get("error"))
        self.assertEqual(data["engine"], "spd")
        self.assertTrue(data["write_read_ok"])
        self.assertTrue(data["erase_ok"])
        self.assertTrue(data["pac_verified"])
        self.assertIn("pac_flash", data["operations"])

    def test_runner_serves_a_session_over_stdio(self) -> None:
        commands = [
            {"op": "partitions"},
            {"op": "writeflash", "offset": 0, "src": ""},
            {"op": "ping"},
            {"op": "quit"},
        ]
        env = {"SPD_TRANSPORT": "simulator", "PATH": "/usr/bin:/bin"}
        process = subprocess.run(
            [sys.executable, "servicecore/runner/spd_runner.py"],
            input="".join(json.dumps(command) + "\n" for command in commands),
            capture_output=True,
            text=True,
            timeout=180,
            env=env,
        )
        lines = process.stdout.splitlines()
        self.assertTrue(any(line.startswith("SVC_READY:") for line in lines), lines[:5])
        self.assertTrue(any(line.startswith("SVC_OK:partitions:") for line in lines), lines[:8])
        self.assertTrue(any(line.startswith("SVC_FAIL:writeflash:") for line in lines), lines)
        self.assertIn("SVC_OK:ping", lines)
        self.assertIn("SVC_BYE", lines)


if __name__ == "__main__":
    unittest.main()
