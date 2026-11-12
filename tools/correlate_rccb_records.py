#!/usr/bin/env python3
"""Correlate RCCB candidate records without assigning field semantics."""
from __future__ import annotations
import argparse
import collections
import json
import math
import re
from pathlib import Path

CLASS_RE = re.compile(r"^(?:CC|DC)[A-Za-z0-9_]+$")


def entropy(values: list[int]) -> float:
    counts = collections.Counter(values)
    total = len(values)
    return round(-sum((n / total) * math.log2(n / total) for n in counts.values()), 4)


def marker(sample: dict) -> str:
    for value in sample.get("ascii_runs", []):
        if CLASS_RE.fullmatch(value):
            return value
    for value in sample.get("ascii_runs", []):
        if value.lower().endswith((".webp", ".png", ".jpg", ".ttf", ".fnt", ".plist")):
            return "resource:" + value
    return "unclassified"


def summarize(records: list[dict], window: int, threshold: float) -> dict:
    count = len(records)
    chunks = [bytes.fromhex(r["sample_hex"])[:window] for r in records]
    byte_columns = list(zip(*chunks))
    stable_bytes = []
    for offset, column in enumerate(byte_columns):
        freq = collections.Counter(column)
        value, occurrences = freq.most_common(1)[0]
        if occurrences / count >= threshold:
            stable_bytes.append({"offset": offset, "value_hex": f"{value:02x}",
                "support": occurrences, "ratio": round(occurrences / count, 4),
                "distinct_values": len(freq), "entropy_bits": entropy(list(column))})
    stable_words = []
    words_per_record = min(len(chunk) // 4 for chunk in chunks)
    for word_index in range(words_per_record):
        values = [int.from_bytes(chunk[word_index*4:word_index*4+4], "little") for chunk in chunks]
        freq = collections.Counter(values)
        value, occurrences = freq.most_common(1)[0]
        if occurrences / count >= threshold:
            stable_words.append({"byte_offset": word_index * 4, "common_u32_le": value,
                "support": occurrences, "ratio": round(occurrences / count, 4),
                "distinct_values": len(freq), "entropy_bits": entropy(values)})
    return {"sample_count": count, "unique_sample_hashes": len({r["sample_sha256"] for r in records}),
            "stable_byte_positions": stable_bytes, "stable_u32_positions": stable_words}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("samples", type=Path)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--min-group", type=int, default=3)
    ap.add_argument("--stability", type=float, default=0.8)
    args = ap.parse_args()
    if args.min_group < 2 or not 0.5 <= args.stability <= 1.0:
        raise SystemExit("min-group must be >=2 and stability must be 0.5..1.0")
    source = json.loads(args.samples.read_text(encoding="utf-8"))
    samples = source.get("samples", [])
    groups = collections.defaultdict(list)
    for item in samples:
        if len(bytes.fromhex(item["sample_hex"])) != item["sample_length"]:
            raise SystemExit(f"Invalid sample length: {item.get('scene')} offset {item.get('record_offset')}")
        groups[(item["table_index"], marker(item))].append(item)
    results = []
    for (table_index, marker_name), records in sorted(groups.items()):
        if len(records) < args.min_group:
            continue
        summary = summarize(records, source.get("window_bytes", 96), args.stability)
        if not summary["stable_u32_positions"] and not summary["stable_byte_positions"]:
            continue
        results.append({"table_index": table_index, "marker": marker_name,
            "scene_count": len({r["scene"] for r in records}), **summary})
    report = {"format": "RCCB cross-record correlation; no field semantics inferred",
        "input_scene_count": source.get("scene_count"), "input_sample_count": len(samples),
        "group_count": len(results),
        "method": {"group_keys": ["table_index", "visible class/resource marker"],
            "minimum_group_size": args.min_group, "stable_position_threshold": args.stability,
            "note": "Offsets are relative to candidate record starts; table ordinals and markers are correlation keys only."},
        "groups": results}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k:v for k,v in report.items() if k != "groups"}, indent=2))


if __name__ == "__main__":
    main()
