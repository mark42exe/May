import importlib.util
import unittest
from pathlib import Path

SPEC = importlib.util.spec_from_file_location(
    "correlate_rccb_strings_to_records",
    Path(__file__).with_name("correlate_rccb_strings_to_records.py"))
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class TokenCorrelationTests(unittest.TestCase):
    def test_joins_only_tokens_inside_record_window(self):
        samples = {"samples": [{"scene": "A.ccb", "table_index": 0,
            "record_offset": 100, "sample_length": 32, "ascii_runs": ["CCSprite"]}]}
        strings = {"scenes": [{"file": "A.ccb", "tokens": [
            {"payload_offset": 104, "value": "CCSprite", "byte_length": 8},
            {"payload_offset": 132, "value": "outside", "byte_length": 7}]}]}
        joined = MODULE.collect_record_tokens(samples, strings)
        self.assertEqual(len(joined[0]["tokens"]), 1)
        self.assertEqual(joined[0]["tokens"][0]["relative_payload_offset"], 4)

    def test_correlates_repeated_offset_and_value(self):
        joined = [
            {"table_index": 0, "marker": "CCSprite", "scene": "A", "tokens":[
                {"relative_payload_offset": 8, "value": "CCSprite"}]},
            {"table_index": 0, "marker": "CCSprite", "scene": "B", "tokens":[
                {"relative_payload_offset": 8, "value": "CCSprite"}]},
            {"table_index": 0, "marker": "CCSprite", "scene": "C", "tokens":[
                {"relative_payload_offset": 8, "value": "CCSprite"}]},
        ]
        result = MODULE.summarize(joined, 3, 0.75)
        token = result["groups"][0]["frequent_relative_tokens"][0]
        self.assertEqual(token["relative_payload_offset"], 8)
        self.assertEqual(token["support"], 1.0)

    def test_deduplicates_token_within_record(self):
        joined = [{"table_index": 0, "marker": "CCNode", "scene": "A", "tokens":[
            {"relative_payload_offset": 4, "value": "CCNode"},
            {"relative_payload_offset": 4, "value": "CCNode"}]}]
        result = MODULE.summarize(joined, 1, 1.0)
        self.assertEqual(result["groups"][0]["frequent_relative_tokens"][0]["record_count"], 1)

    def test_marker_class_and_resource_fallback(self):
        self.assertEqual(MODULE.record_marker({"ascii_runs": ["bg.webp", "CCNode"]}), "CCNode")
        self.assertEqual(MODULE.record_marker({"ascii_runs": ["bg.webp"]}), "resource:bg.webp")


if __name__ == "__main__":
    unittest.main()
