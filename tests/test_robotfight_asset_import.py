#!/usr/bin/env python3
"""Regression tests for safe extraction and malformed DCA rejection."""
import importlib.util
import pathlib
import struct
import tempfile
import unittest
import zlib

MODULE_PATH = pathlib.Path(__file__).resolve().parents[1] / "tools" / "import_robotfight_assets.py"
SPEC = importlib.util.spec_from_file_location("robotfight_importer", MODULE_PATH)
IMPORTER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(IMPORTER)


def make_dca(records, names=b"asset.bin\0"):
    records_offset = 28
    records_bytes = len(records) * 8
    strings_offset = records_offset + records_bytes
    file_offset = strings_offset + len(names)
    payload = b"asset-data"
    file_record = struct.pack("<III", zlib.crc32(payload) & 0xffffffff, 0, len(payload)) + payload
    directory = b"".join(struct.pack("<II", name_offset, file_offset) for name_offset in records)
    header = b"DCA\0" + struct.pack(
        "<6I", 1, 0, records_offset, records_bytes, strings_offset, len(names)
    )
    return header + directory + names + file_record


class ImporterHardeningTests(unittest.TestCase):
    def test_rejects_short_dca_header(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, "complete DCA"):
                IMPORTER.extract_dca(b"DCA\0", pathlib.Path(tmp))

    def test_rejects_directory_outside_archive(self):
        data = b"DCA\0" + struct.pack("<6I", 1, 0, 1000, 8, 28, 1)
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, "directory bounds"):
                IMPORTER.extract_dca(data, pathlib.Path(tmp))

    def test_rejects_duplicate_resource_names(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, "Duplicate DCA resource"):
                IMPORTER.extract_dca(make_dca([0, 0]), pathlib.Path(tmp))

    def test_extracts_valid_resource_and_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            count = IMPORTER.extract_dca(make_dca([0]), root)
            self.assertEqual(count, 1)
            self.assertEqual((root / "asset.bin").read_bytes(), b"asset-data")
            self.assertTrue((root / "_archive_manifest.json").is_file())

    def test_rejects_path_traversal(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, "Unsafe archive path"):
                IMPORTER.safe_target(pathlib.Path(tmp), "../escape.bin")


if __name__ == "__main__":
    unittest.main(verbosity=2)
