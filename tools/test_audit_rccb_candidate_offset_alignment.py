import unittest
import tempfile
from pathlib import Path

from audit_rccb_candidate_offset_alignment import analyze


class CandidateOffsetAlignmentTests(unittest.TestCase):
    def test_reports_nearest_class_and_resource_without_semantics(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "A.ccb").write_bytes(bytes(256))
            inventory = {"scenes": [{
                "file": "A.ccb", "size": 256,
                "strings": [
                    {"offset": 44, "value": "CCSprite", "encoding": "ascii"},
                    {"offset": 70, "value": "button.webp", "encoding": "ascii"},
                ],
                "candidate_offset_tables": [{"offsets": [40, 100, 4]}],
            }]}
            report = analyze(inventory, root, 32)
            self.assertEqual(report["candidate_offset_count"], 2)
            self.assertEqual(report["candidate_offsets_with_node_class_nearby"], 1)
            self.assertEqual(report["candidate_offsets_with_resource_nearby"], 2)
            self.assertEqual(report["candidate_offsets_exactly_at_node_class_string"], 0)
            self.assertEqual(report["candidate_offsets_with_token_by_radius"][0]["node_class"], 0)
            self.assertIn("limitations", report)

    def test_rejects_scene_size_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "A.ccb").write_bytes(bytes(8))
            inventory = {"scenes": [{"file": "A.ccb", "size": 9, "strings": [],
                         "candidate_offset_tables": []}]}
            with self.assertRaises(ValueError):
                analyze(inventory, root)

    def test_rejects_out_of_bounds_candidate(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "A.ccb").write_bytes(bytes(8))
            inventory = {"scenes": [{"file": "A.ccb", "size": 8, "strings": [],
                         "candidate_offset_tables": [{"offsets": [8, 4]}]}]}
            with self.assertRaises(ValueError):
                analyze(inventory, root)

    def test_rejects_invalid_distance(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                analyze({"scenes": [{"file": "A.ccb"}]}, Path(tmp), 5000)


if __name__ == "__main__":
    unittest.main()
