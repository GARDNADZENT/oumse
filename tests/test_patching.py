from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from app.patching import (
    PatchError,
    apply_plan,
    load_patch_document,
    parse_patch_document,
    patch_file,
    sha256_bytes,
    validate_plan,
)


class PatchingTests(unittest.TestCase):
    def test_parse_and_apply_plan(self) -> None:
        plan = parse_patch_document(
            {
                "single_offsets": [{"offset": 0, "value": "0xFF"}],
                "fill_offsets": [{"start": 2, "end": 4, "value": 170}],
            }
        )
        data = bytes(range(16))
        patched, writes, changed = apply_plan(data, plan)

        self.assertEqual(plan.entry_count, 2)
        self.assertEqual(writes, 4)
        self.assertEqual(changed, 4)
        self.assertEqual(patched[0], 0xFF)
        self.assertEqual(patched[2:5], b"\xaa\xaa\xaa")
        self.assertEqual(patched[5:], data[5:])

    def test_negative_single_offset_is_rejected(self) -> None:
        plan = parse_patch_document({"single_offsets": [{"offset": -1, "value": 0}]})
        errors = validate_plan(plan, 16)
        self.assertTrue(any("out of bounds" in error for error in errors))
        with self.assertRaises(PatchError):
            apply_plan(bytes(16), plan)

    def test_out_of_bounds_fill_is_rejected(self) -> None:
        plan = parse_patch_document({"fill_offsets": [{"start": 10, "end": 20, "value": 0}]})
        errors = validate_plan(plan, 16)
        self.assertTrue(any("out of bounds" in error for error in errors))

    def test_value_must_be_a_byte(self) -> None:
        with self.assertRaises(PatchError):
            parse_patch_document({"single_offsets": [{"offset": 0, "value": 256}]})

    def test_reversed_fill_range_is_rejected(self) -> None:
        with self.assertRaises(PatchError):
            parse_patch_document({"fill_offsets": [{"start": 9, "end": 3, "value": 0}]})

    def test_empty_document_is_rejected(self) -> None:
        with self.assertRaises(PatchError):
            parse_patch_document({})

    def test_patch_file_creates_backup_and_checksums(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "input.bin"
            patches = root / "patches.json"
            output = root / "output.bin"
            source.write_bytes(bytes(range(16)))
            output.write_bytes(b"old-content")
            patches.write_text(
                json.dumps({"single_offsets": [{"offset": 1, "value": 0x7F}]}),
                encoding="utf-8",
            )

            plan = load_patch_document(patches)
            result = patch_file(source, output, plan)

            self.assertTrue(result.backup_path)
            self.assertTrue(Path(result.backup_path).is_file())
            self.assertEqual(result.file_size, 16)
            self.assertEqual(result.changed_bytes, 1)
            self.assertEqual(result.input_sha256, sha256_bytes(bytes(range(16))))
            self.assertEqual(result.output_sha256, sha256_bytes(output.read_bytes()))
            self.assertEqual(output.read_bytes()[1], 0x7F)

    def test_invalid_json_raises_patch_error(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            patches = Path(directory) / "bad.json"
            patches.write_text("{not json", encoding="utf-8")
            with self.assertRaises(PatchError):
                load_patch_document(patches)


if __name__ == "__main__":
    unittest.main()
