#!/usr/bin/env python3
"""Regression tests for safe extraction and malformed DCA rejection."""
import importlib.util
import pathlib
import struct
import sys
import zipfile
from unittest import mock
from PIL import Image
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

    def test_webp_conversion_does_not_duplicate_or_overwrite_png_manifest_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            archive_path = root / "assets.zip"
            output = root / "out"
            png_path = root / "source.png"
            webp_path = root / "source.webp"
            Image.new("RGBA", (2, 2), (255, 0, 0, 255)).save(png_path, format="PNG")
            Image.new("RGBA", (2, 2), (0, 0, 255, 255)).save(webp_path, format="WEBP")
            with zipfile.ZipFile(archive_path, "w") as archive:
                archive.write(png_path, "bundle/icon.png")
                archive.write(webp_path, "bundle/icon.webp")
            with mock.patch.object(sys, "argv", [
                "import_robotfight_assets.py", "--input", str(archive_path),
                "--output", str(output)
            ]):
                IMPORTER.main()
            import json
            manifest = json.loads((output / "original_asset_manifest.json").read_text())
            self.assertEqual(manifest["files"], ["icon.png"])
            self.assertEqual(manifest["imported_files"], 1)
            with Image.open(output / "icon.png") as result:
                self.assertEqual(result.convert("RGBA").getpixel((0, 0)), (255, 0, 0, 255))
            self.assertEqual(manifest["counts"]["webp_png_name_collisions_skipped"], 1)

    def test_rejects_path_traversal(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, "Unsafe archive path"):
                IMPORTER.safe_target(pathlib.Path(tmp), "../escape.bin")


if __name__ == "__main__":
    unittest.main(verbosity=2)
