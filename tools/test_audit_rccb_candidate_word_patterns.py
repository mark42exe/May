import json
import struct
import tempfile
import unittest
from pathlib import Path

from audit_rccb_candidate_word_patterns import build_report, classify_word


class CandidateWordPatternTests(unittest.TestCase):
    def test_classifies_zero_and_small_integer(self):
        self.assertEqual(classify_word(b"\0\0\0\0")["kind"], "zero")
        self.assertEqual(classify_word(struct.pack("<I", 7))["kind"], "small_integer")

    def test_classifies_printable_ascii(self):
        self.assertEqual(classify_word(b"ABCD")["kind"], "printable_ascii")

    def test_reports_cross_scene_relative_offsets(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data = bytearray(128)
            struct.pack_into("<I", data, 32, 1)
            struct.pack_into("<f", data, 36, 1.0)
            (root / "A.ccb").write_bytes(data)
            inventory = {"scenes": [{
                "file": "A.ccb", "size": len(data),
                "candidate_offset_tables": [{"offsets": [32, 4]}],
            }]}
            report = build_report(inventory, root, 16)
            self.assertEqual(report["candidate_count"], 1)
            self.assertEqual(report["relative_word_offsets"][0]["kind_counts"]["small_integer"], 1)
            self.assertEqual(report["relative_word_offsets"][1]["kind_counts"]["float_candidate"], 1)

    def test_rejects_out_of_bounds_candidate_window(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "A.ccb").write_bytes(bytes(32))
            inventory = {"scenes": [{
                "file": "A.ccb", "size": 32,
                "candidate_offset_tables": [{"offsets": [28, 4]}],
            }]}
            with self.assertRaises(ValueError):
                build_report(inventory, root, 16)

    def test_rejects_invalid_window(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                build_report({"scenes": [{"file": "A.ccb"}]}, Path(tmp), 6)


if __name__ == "__main__":
    unittest.main()
