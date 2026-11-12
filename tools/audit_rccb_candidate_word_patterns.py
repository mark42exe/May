#!/usr/bin/env python3
"""Cross-scene byte-pattern survey at RCCB candidate record starts.

This is schema research, not a decoder: candidate offsets remain heuristic and
32-bit words are reported as raw values plus conservative representations.
"""
from __future__ import annotations

import argparse
import json
import math
import struct
from collections import Counter, defaultdict
from pathlib import Path

WINDOW_BYTES = 64
WORD_BYTES = 4


def classify_word(raw: bytes) -> dict:
    value = struct.unpack("<I", raw)[0]
    signed = struct.unpack("<i", raw)[0]
    floating = struct.unpack("<f", raw)[0]
    if value == 0:
        kind = "zero"
    elif all(0x20 <= byte <= 0x7E for byte in raw):
        kind = "printable_ascii"
    elif math.isfinite(floating) and abs(floating) <= 100000 and (
        floating == 0.0 or abs(floating) >= 1e-6
    ):
        kind = "float_candidate"
    elif value <= 255:
        kind = "small_integer"
    else:
        kind = "other"
    return {
        "u32le": value,
        "i32le": signed,
        "f32le": floating if math.isfinite(floating) else None,
        "kind": kind,
        "hex": raw.hex(),
    }


def build_report(inventory: dict, scene_root: Path, window_bytes: int = WINDOW_BYTES) -> dict:
    if window_bytes < WORD_BYTES or window_bytes > 256 or window_bytes % WORD_BYTES:
        raise ValueError("window_bytes must be a multiple of four from 4 to 256")
    scenes = inventory.get("scenes", [])
    if not scenes:
        raise ValueError("inventory contains no scenes")

    by_offset: dict[int, Counter] = defaultdict(Counter)
    class_counts: Counter = Counter()
    examples = []
    candidate_count = 0
    scene_count = 0

    for scene in scenes:
        path = scene_root / scene["file"]
        if not path.is_file():
            raise ValueError(f"missing scene file: {scene['file']}")
        data = path.read_bytes()
        if len(data) != scene.get("size"):
            raise ValueError(f"scene size mismatch: {scene['file']}")
        scene_count += 1
        for table_index, table in enumerate(scene.get("candidate_offset_tables", [])):
            for offset in table.get("offsets", [])[:-1]:
                if not isinstance(offset, int) or offset < 0 or offset + window_bytes > len(data):
                    raise ValueError(f"candidate window outside scene: {scene['file']}@{offset}")
                candidate_count += 1
                words = []
                for relative in range(0, window_bytes, WORD_BYTES):
                    raw = data[offset + relative:offset + relative + WORD_BYTES]
                    decoded = classify_word(raw)
                    by_offset[relative][decoded["kind"]] += 1
                    class_counts[decoded["kind"]] += 1
                    words.append(decoded)
                if len(examples) < 24:
                    examples.append({
                        "scene": scene["file"],
                        "table_index": table_index,
                        "candidate_offset": offset,
                        "first_16_bytes": data[offset:offset + 16].hex(),
                        "words": words[:4],
                    })

    offsets = []
    for relative in range(0, window_bytes, WORD_BYTES):
        counts = by_offset[relative]
        total = sum(counts.values())
        offsets.append({
            "relative_offset": relative,
            "sample_count": total,
            "kind_counts": dict(sorted(counts.items())),
            "dominant_kind": counts.most_common(1)[0][0] if counts else None,
        })

    return {
        "format": "RCCB candidate-start 32-bit word pattern survey v1",
        "scene_count": scene_count,
        "candidate_count": candidate_count,
        "window_bytes": window_bytes,
        "word_size": WORD_BYTES,
        "aggregate_word_kind_counts": dict(sorted(class_counts.items())),
        "relative_word_offsets": offsets,
        "examples": examples,
        "limitations": [
            "Candidate offsets are heuristic and are not proven record starts.",
            "A 32-bit word may have multiple valid interpretations; float/integer labels are clues only.",
            "No property names, value types, node ownership, or hierarchy are decoded.",
            "No source scene bytes are modified.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("inventory", type=Path)
    parser.add_argument("scene_root", type=Path)
    parser.add_argument("--window-bytes", type=int, default=WINDOW_BYTES)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    report = build_report(json.loads(args.inventory.read_text(encoding="utf-8")),
                          args.scene_root, args.window_bytes)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items()
                      if k not in ("relative_word_offsets", "examples")}, indent=2))


if __name__ == "__main__":
    main()
