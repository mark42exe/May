import unittest
from audit_rccb_candidate_token_anchors import analyze


class CandidateTokenAnchorTests(unittest.TestCase):
    def fixture(self):
        samples = {"scene_count": 1, "samples": [
            {"scene": "A.ccb", "table_index": 0, "record_offset": 100},
            {"scene": "A.ccb", "table_index": 1, "record_offset": 200},
        ]}
        strings = {"scene_count": 1, "scenes": [{"file": "A.ccb", "tokens": [
            {"length_offset": 100, "payload_offset": 104, "value": "CCSprite"},
            {"length_offset": 196, "payload_offset": 200, "value": "robot.webp"},
            {"length_offset": 216, "payload_offset": 220, "value": "label"},
        ]}]}
        return samples, strings

    def test_counts_exact_prefix_and_payload_matches_separately(self):
        samples, strings = self.fixture()
        report = analyze(samples, strings)
        self.assertEqual(report["exact_length_prefix_matches"], 1)
        self.assertEqual(report["exact_payload_start_matches"], 1)
        self.assertEqual(report["exact_matches_by_anchor_and_kind"]["length_prefix"], {"node_class": 1})
        self.assertEqual(report["exact_matches_by_anchor_and_kind"]["payload_start"], {"resource": 1})

    def test_nearby_histograms_respect_radius(self):
        samples, strings = self.fixture()
        report = analyze(samples, strings, radius=4)
        prefix = {x["delta_bytes"]: x["occurrences"] for x in report["nearby_delta_histograms"]["length_prefix"]}
        self.assertEqual(prefix, {0: 1, 16: 0} if False else {0: 1, -4: 1})
        payload = {x["delta_bytes"]: x["occurrences"] for x in report["nearby_delta_histograms"]["payload_start"]}
        self.assertEqual(payload, {4: 1, 0: 1})

    def test_rejects_inventory_mismatch_and_negative_radius(self):
        samples, strings = self.fixture()
        with self.assertRaises(ValueError):
            analyze(samples, {"scene_count": 2, "scenes": []})
        with self.assertRaises(ValueError):
            analyze(samples, strings, radius=-1)

    def test_rejects_missing_scene(self):
        samples, strings = self.fixture()
        samples["samples"][0]["scene"] = "missing.ccb"
        with self.assertRaises(ValueError):
            analyze(samples, strings)


if __name__ == "__main__":
    unittest.main()
