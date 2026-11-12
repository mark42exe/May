#!/usr/bin/env python3
"""Unit tests for RCCB missing-asset family analysis."""
import tempfile
import unittest
from pathlib import Path

from audit_rccb_asset_families import build_report, family_key


class AssetFamilyTests(unittest.TestCase):
    def test_strips_trailing_numeric_variant(self):
        self.assertEqual(family_key("editor_stats_panel_weight_06.webp"),
                         ("editor", "stats", "panel", "weight"))

    def test_keeps_non_numeric_suffix(self):
        self.assertEqual(family_key("btn_quest_pressed.webp"),
                         ("btn", "quest", "pressed"))

    def test_groups_only_exact_family_siblings(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "editor_stats_panel_weight_01.png").write_bytes(b"a")
            (root / "editor_stats_panel_weight_03.png").write_bytes(b"b")
            (root / "editor_stats_panel_height_01.png").write_bytes(b"c")
            report = build_report(root, {"missing_references": [
                {"reference": "editor_stats_panel_weight_06.webp", "scene_count": 2}
            ]})
            record = report["records"][0]
            self.assertEqual(record["sibling_count"], 2)
            self.assertEqual(report["automatic_repairs"], 0)
            self.assertFalse(record["replacement_selected"])

    def test_no_candidate_is_not_reported_as_repaired(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = build_report(Path(tmp), {"missing_references": [
                {"reference": "controller_battery_bar01.webp", "scene_count": 1}
            ]})
            self.assertEqual(report["references_without_existing_family_siblings"], 1)
            self.assertEqual(report["automatic_repairs"], 0)


if __name__ == "__main__":
    unittest.main()
