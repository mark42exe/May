#!/usr/bin/env python3
"""Tests for RCCB candidate span/token containment audit."""
import unittest

from audit_rccb_record_spans import build_report


class RecordSpanTests(unittest.TestCase):
    def fixtures(self):
        inventory = {
            "scene_count": 1,
            "scenes": [{
                "file": "scene.ccb",
                "size": 128,
                "candidate_offset_tables": [{
                    "table_offset": 32,
                    "targets": [{"offset": 96}, {"offset": 64}, {"offset": 40}],
                }],
            }],
        }
        strings = {
            "scene_count": 1,
            "scenes": [{
                "file": "scene.ccb",
                "tokens": [
                    {"length_offset": 70, "byte_length": 8, "value": "CCSprite", "nul_terminated": True},
                    {"length_offset": 42, "byte_length": 9, "value": "part.webp", "nul_terminated": True},
                    {"length_offset": 20, "byte_length": 4, "value": "test", "nul_terminated": True},
                ],
            }],
        }
        return inventory, strings

    def test_builds_non_overlapping_spans_within_one_table(self):
        inventory, strings = self.fixtures()
        report = build_report(inventory, strings)
        spans = report["records"]
        self.assertEqual([(x["candidate_start"], x["candidate_end_exclusive"])
                          for x in spans], [(96, 128), (64, 96), (40, 64)])

    def test_assigns_only_wholly_contained_tokens(self):
        inventory, strings = self.fixtures()
        report = build_report(inventory, strings)
        by_start = {x["candidate_start"]: x for x in report["records"]}
        self.assertEqual(by_start[64]["node_class_tokens"], ["CCSprite"])
        self.assertEqual(by_start[40]["resource_tokens"], ["part.webp"])
        self.assertEqual(by_start[96]["contained_token_count"], 0)

    def test_rejects_scene_count_mismatch(self):
        inventory, strings = self.fixtures()
        strings["scene_count"] = 2
        with self.assertRaisesRegex(ValueError, "scene counts differ"):
            build_report(inventory, strings)

    def test_rejects_token_outside_scene(self):
        inventory, strings = self.fixtures()
        strings["scenes"][0]["tokens"][0]["length_offset"] = 124
        with self.assertRaisesRegex(ValueError, "token outside scene bounds"):
            build_report(inventory, strings)


if __name__ == "__main__":
    unittest.main()
