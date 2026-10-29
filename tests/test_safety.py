from __future__ import annotations

import unittest

from app.safety import (
    is_dangerous_partition,
    normalize_partition_names,
    validate_erase_targets,
    validate_partition_name,
)


class SafetyTests(unittest.TestCase):
    def test_valid_partition_name(self) -> None:
        self.assertIsNone(validate_partition_name("proinfo"))
        self.assertIsNone(validate_partition_name("boot_a"))

    def test_unsafe_partition_name(self) -> None:
        self.assertIsNotNone(validate_partition_name("../boot"))
        self.assertIsNotNone(validate_partition_name(""))
        self.assertIsNotNone(validate_partition_name("bad name"))

    def test_dangerous_partition_detection(self) -> None:
        self.assertTrue(is_dangerous_partition("preloader"))
        self.assertTrue(is_dangerous_partition("PRELOADER"))
        self.assertFalse(is_dangerous_partition("frp"))

    def test_erase_validation_blocks_critical_partitions(self) -> None:
        errors = validate_erase_targets(["frp", "preloader"])
        self.assertTrue(any("critical partition" in error for error in errors))

    def test_erase_validation_allows_service_partitions(self) -> None:
        self.assertEqual(validate_erase_targets(["frp", "metadata"]), [])

    def test_normalize_string(self) -> None:
        self.assertEqual(normalize_partition_names("frp"), ["frp"])


if __name__ == "__main__":
    unittest.main()
