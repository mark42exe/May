import unittest
from correlate_rccb_token_boundaries import analyze


class TokenBoundaryTests(unittest.TestCase):
    def test_finds_exact_prefix_and_relative_prefix_offsets(self):
        samples = {"scene_count": 1, "samples": [
            {"scene": "A.ccb", "table_index": 0, "record_offset": 100,
             "sample_length": 32, "marker": "CCSprite"},
            {"scene": "A.ccb", "table_index": 0, "record_offset": 200,
             "sample_length": 32, "marker": "CCLabelTTF"},
        ]}
        strings = {"scene_count": 1, "scenes": [{"file": "A.ccb", "tokens": [
            {"length_offset": 100, "payload_offset": 104, "byte_length": 8, "value": "CCSprite"},
            {"length_offset": 212, "payload_offset": 216, "byte_length": 4, "value": "text"},
        ]}]}
        report = analyze(samples, strings)
        self.assertEqual(report["records_with_tokens"], 2)
        self.assertEqual(report["records_starting_at_string_length_prefix"], 1)
        self.assertEqual(report["records"][0]["tokens"][0]["relative_payload_offset"], 4)
        self.assertEqual(report["records"][1]["tokens"][0]["relative_length_offset"], 12)

    def test_infers_visible_node_and_resource_markers(self):
        samples = {"scene_count": 1, "samples": [
            {"scene": "A.ccb", "table_index": 0, "record_offset": 100,
             "sample_length": 32, "ascii_runs": ["CCSprite", "robot.webp"]},
            {"scene": "A.ccb", "table_index": 0, "record_offset": 200,
             "sample_length": 32, "ascii_runs": ["robot.webp"]},
            {"scene": "A.ccb", "table_index": 0, "record_offset": 300,
             "sample_length": 32, "ascii_runs": ["arbitrary_identifier"]},
        ]}
        strings = {"scene_count": 1, "scenes": [{"file": "A.ccb", "tokens": [\n            {"length_offset": 104, "payload_offset": 108, "byte_length": 4, "value": "test"},\n            {"length_offset": 204, "payload_offset": 208, "byte_length": 4, "value": "test"},\n        ]}]}
        report = analyze(samples, strings)
        self.assertEqual(
            [record["marker"] for record in report["records"]],
            ["CCSprite", "resource:robot.webp", "unclassified"],
        )
        self.assertEqual(
            {entry["marker"] for entry in report["summary"]},
            {"CCSprite", "resource:robot.webp"},
        )

    def test_explicit_marker_takes_precedence(self):
        samples = {"scene_count": 1, "samples": [
            {"scene": "A.ccb", "table_index": 0, "record_offset": 100,
             "sample_length": 32, "marker": "manual", "ascii_runs": ["CCSprite"]},
        ]}
        strings = {"scene_count": 1, "scenes": [{"file": "A.ccb", "tokens": []}]}
        report = analyze(samples, strings)
        self.assertEqual(report["records"][0]["marker"], "manual")

    def test_rejects_scene_inventory_mismatch(self):
        with self.assertRaises(ValueError):
            analyze({"scene_count": 1, "samples": []}, {"scene_count": 2, "scenes": []})

    def test_rejects_missing_scene_string_data(self):
        with self.assertRaises(ValueError):
            analyze({"scene_count": 1, "samples": [
                {"scene": "missing.ccb", "table_index": 0, "record_offset": 0, "sample_length": 8}
            ]}, {"scene_count": 1, "scenes": []})


if __name__ == "__main__":
    unittest.main()
