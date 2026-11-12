#!/usr/bin/env python3
"""Measure RCCB candidate offsets against validated string-token boundaries.

This reports byte-position relationships only. It does not infer property types
or claim that a candidate offset is a real node-record boundary.
"""
from __future__ import annotations
import argparse
import collections
import json
from pathlib import Path


def analyze(samples: dict, strings: dict) -> dict:
    if samples.get("scene_count") != strings.get("scene_count"):
        raise ValueError("scene inventory mismatch")
    by_scene = {s["file"]: s["tokens"] for s in strings.get("scenes", [])}
    records = []
    distributions = collections.defaultdict(collections.Counter)
    for sample in samples.get("samples", []):
        start = sample["record_offset"]
        end = start + sample["sample_length"]
        tokens = by_scene.get(sample["scene"])
        if tokens is None:
            raise ValueError("sample scene missing from string layer: " + sample["scene"])
        contained = [t for t in tokens if start <= t["length_offset"] and t["payload_offset"] < end]
        offsets = []
        for token in contained:
            rel_len = token["length_offset"] - start
            rel_payload = token["payload_offset"] - start
            relation = "prefix_at_candidate" if rel_len == 0 else "prefix_inside_window"
            offsets.append({
                "value": token["value"], "relative_length_offset": rel_len,
                "relative_payload_offset": rel_payload,
                "byte_length": token["byte_length"], "relation": relation,
            })
            distributions[(sample["table_index"], sample.get("marker", "unclassified"))][rel_len] += 1
        records.append({
            "scene": sample["scene"], "table_index": sample["table_index"],
            "record_offset": start, "marker": sample.get("marker", "unclassified"),
            "token_count": len(offsets), "tokens": offsets,
            "candidate_starts_with_string_length_prefix": any(x["relative_length_offset"] == 0 for x in offsets),
        })
    summary = []
    for (table, marker), counts in sorted(distributions.items()):
        summary.append({
            "table_index": table, "marker": marker,
            "token_prefix_relative_offsets": [
                {"offset": offset, "occurrences": count}
                for offset, count in sorted(counts.items())
            ],
        })
    return {
        "format": "RCCB candidate-to-string-boundary correlation v1",
        "scene_count": samples["scene_count"], "sample_count": len(records),
        "records_with_tokens": sum(bool(r["token_count"]) for r in records),
        "records_starting_at_string_length_prefix": sum(r["candidate_starts_with_string_length_prefix"] for r in records),
        "summary": summary, "records": records,
        "limitations": [
            "Candidate record offsets remain heuristic.",
            "String-token boundary alignment does not establish a property field.",
            "No node class, property value, ownership, or parent-child relationship is decoded.",
        ],
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("samples", type=Path)
    ap.add_argument("strings", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    report = analyze(json.loads(args.samples.read_text()), json.loads(args.strings.read_text()))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "records"}, indent=2))


if __name__ == "__main__":
    main()
