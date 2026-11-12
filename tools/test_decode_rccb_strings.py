#!/usr/bin/env python3
"""Unit tests for the conservative RCCB string-token scanner."""
from __future__ import annotations
import importlib.util
import struct
import tempfile
import unittest
from pathlib import Path

MODULE_PATH = Path(__file__).with_name("decode_rccb_strings.py")
SPEC = importlib.util.spec_from_file_location("decode_rccb_strings", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


class DecodeRCCBStringsTests(unittest.TestCase):
    def decode_bytes(self, data: bytes):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "fixture.ccb"
            path.write_bytes(data)
            return MODULE.decode(path)

    def test_decodes_length_prefixed_ascii(self):
        value = b"RFBattleLayer"
        tokens = self.decode_bytes(struct.pack("<I", len(value)) + value + b"\0")
        self.assertEqual(len(tokens), 1)
        self.assertEqual(tokens[0]["value"], value.decode("ascii"))
        self.assertTrue(tokens[0]["nul_terminated"])

    def test_ignores_missing_nul_terminator(self):
        value = b"RFBattleLayer"
        tokens = self.decode_bytes(struct.pack("<I", len(value)) + value + b"!")
        self.assertEqual(tokens, [])

    def test_ignores_non_printable_payload(self):
        value = b"Battle\x00Layer"
        tokens = self.decode_bytes(struct.pack("<I", len(value)) + value + b"\0")
        self.assertEqual(tokens, [])

    def test_ignores_oversized_length(self):
        value = b"A" * (MODULE.MAX_STRING_BYTES + 1)
        tokens = self.decode_bytes(struct.pack("<I", len(value)) + value + b"\0")
        self.assertEqual(tokens, [])

    def test_preserves_exact_payload_offset(self):
        value = b"CCSprite"
        prefix = b"\x99\x88\x77"
        tokens = self.decode_bytes(prefix + struct.pack("<I", len(value)) + value + b"\0")
        self.assertEqual(len(tokens), 1)
        self.assertEqual(tokens[0]["payload_offset"], len(prefix) + 4)


if __name__ == "__main__":
    unittest.main(verbosity=2)
