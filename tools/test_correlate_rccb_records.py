import importlib.util
import unittest
from pathlib import Path

SPEC = importlib.util.spec_from_file_location(
    "correlate_rccb_records", Path(__file__).with_name("correlate_rccb_records.py"))
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def record(hex_data, digest):
    return {"sample_hex": hex_data, "sample_length": len(bytes.fromhex(hex_data)),
            "sample_sha256": digest}


class CorrelationTests(unittest.TestCase):
    def test_entropy_constant_and_binary(self):
        self.assertEqual(MODULE.entropy([7, 7, 7]), 0.0)
        self.assertEqual(MODULE.entropy([0, 1]), 1.0)

    def test_stable_u32_field_has_no_guessed_semantics(self):
        records = [record("01000000aabbccdd", str(i)) for i in range(4)]
        summary = MODULE.summarize(records, 8, 0.75)
        field = summary["stable_u32_positions"][0]
        self.assertEqual(field["byte_offset"], 0)
        self.assertEqual(field["common_u32_le"], 1)
        self.assertNotIn("meaning", field)

    def test_threshold_controls_stability(self):
        records = [record("01000000", "a"), record("01000000", "b"),
                   record("02000000", "c"), record("03000000", "d")]
        self.assertTrue(MODULE.summarize(records, 4, 0.5)["stable_u32_positions"])
        self.assertFalse(MODULE.summarize(records, 4, 0.75)["stable_u32_positions"])

    def test_marker_prefers_node_class(self):
        self.assertEqual(MODULE.marker({"ascii_runs": ["button.webp", "CCSprite"]}), "CCSprite")

    def test_marker_falls_back_to_resource(self):
        self.assertEqual(MODULE.marker({"ascii_runs": ["button.webp"]}), "resource:button.webp")


if __name__ == "__main__":
    unittest.main()
