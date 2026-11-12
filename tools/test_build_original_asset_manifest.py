#!/usr/bin/env python3
"""Unit tests for original asset integrity manifest generation."""
from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path

from build_original_asset_manifest import build_manifest


class OriginalAssetManifestTests(unittest.TestCase):
    def test_hashes_and_sizes_files_deterministically(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "assets"
            root.mkdir()
            (root / "b.png").write_bytes(b"image-b")
            nested = root / "audio"
            nested.mkdir()
            (nested / "a.ogg").write_bytes(b"audio-a")
            output = root / "manifest.json"

            first = build_manifest(root, output)
            second = build_manifest(root, output)
            self.assertEqual(first, second)
            self.assertEqual(first["file_count"], 2)
            self.assertEqual(first["total_bytes"], 14)
            self.assertEqual(first["files"][0]["path"], "audio/a.ogg")
            self.assertEqual(first["files"][0]["sha256"],
                             hashlib.sha256(b"audio-a").hexdigest())

    def test_excludes_output_manifest(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "one.dat").write_bytes(b"x")
            output = root / "integrity.json"
            output.write_text("{}")
            report = build_manifest(root, output)
            self.assertEqual([item["path"] for item in report["files"]], ["one.dat"])

    def test_rejects_case_insensitive_collisions(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "Asset.png").write_bytes(b"a")
            (root / "asset.png").write_bytes(b"b")
            with self.assertRaisesRegex(ValueError, "case-insensitive path collision"):
                build_manifest(root, root / "manifest.json")

    def test_rejects_symlinks(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            target = root / "target.bin"
            target.write_bytes(b"x")
            link = root / "linked.bin"
            try:
                link.symlink_to(target)
            except (OSError, NotImplementedError):
                self.skipTest("symlinks unavailable")
            with self.assertRaisesRegex(ValueError, "symlink is not allowed"):
                build_manifest(root, root / "manifest.json")


if __name__ == "__main__":
    unittest.main()
