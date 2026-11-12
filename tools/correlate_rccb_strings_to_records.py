#!/usr/bin/env python3
"""Correlate decoded RCCB string tokens with candidate record-relative offsets."""
from __future__ import annotations
import argparse
import collections
import json
import re
from pathlib import Path

CLASS_RE = re.compile(r"^(?:CC|DC)[A-Za-z0-9_]+$")


def record_marker(sample: dict) -> str:
    for value in sample.get("ascii_runs", []):
        if CLASS_RE.fullmatch(value):
            return value
    for value in sample.get("ascii_runs", []):
        if value.lower().endswith((".webp", ".png", ".jpg", ".ttf", ".fnt", ".plist")):
            return "resource:" + value
    return "unclassified"


def collect_record_tokens(samples: dict, strings: dict) -> list[dict]:
    by_scene = {scene["file"]: scene["tokens"] for scene in strings.get("scenes", [])}
    joined = []
    for record in samples.get("samples", []):
        start = record["record_offset"]
        end = start + record["sample_length"]
        tokens = [
            {"relative_payload_offset": token["payload_offset"] - start,
             "value": token["value"], "byte_length": token["byte_length"]}
            for token in by_scene.get(record["scene"], [])
            if start <= token["payload_offset"] < end
        ]
        joined.append({
            "scene": record["scene"], "table_index": record["table_index"],
            "record_offset": start, "marker": record_marker(record), "tokens": tokens,
        })
    return joined


def summarize(joined: list[dict], min_group: int = 3, min_support: float = 0.5) -> dict:
    groups = collections.defaultdict(list)
    for item in joined:
        groups[(item["table_index"], item["marker"])].append(item)
    results = []
    for (table_index, marker), records in sorted(groups.items()):
        if len(records) < min_group:
            continue
        occurrences = collections.Counter()
        for record in records:
            # Count each (offset, value) at most once per record.
            occurrences.update(set((t["relative_payload_offset"], t["value"]) for t in record["tokens"]))
        frequent = [
            {"relative_payload_offset": offset, "value": value, "record_count": count,
             "support": round(count / len(records), 4)}
            for (offset, value), count in occurrences.items()
            if count / len(records) >= min_support
        ]
        frequent.sort(key=lambda x: (-x["record_count"], x["relative_payload_offset"], x["value"]))
        results.append({
            "table_index": table_index, "marker": marker,
            "record_count": len(records),
            "scene_count": len({r["scene"] for r in records}),
            "records_with_tokens": sum(bool(r["tokens"]) for r in records),
            "frequent_relative_tokens": frequent,
        })
    return {"record_count": len(joined), "group_count": len(results), "groups": results}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("samples", type=Path)
    ap.add_argument("strings", type=Path)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--min-group", type=int, default=3)
    ap.add_argument("--min-support", type=float, default=0.5)
    args = ap.parse_args()
    if args.min_group < 2 or not 0.0 < args.min_support <= 1.0:
        raise SystemExit("min-group must be >=2 and min-support must be 0..1")
    sample_report = json.loads(args.samples.read_text(encoding="utf-8"))
    string_report = json.loads(args.strings.read_text(encoding="utf-8"))
    sample_scenes = sample_report.get("scene_count")
    string_scenes = string_report.get("scene_count")
    if sample_scenes != string_scenes:
        raise SystemExit(f"Scene inventory mismatch: samples={sample_scenes}, strings={string_scenes}")
    joined = collect_record_tokens(sample_report, string_report)
    result = summarize(joined, args.min_group, args.min_support)
    report = {
        "format": "RCCB record-relative string correlation; no field semantics inferred",
        "scene_count": sample_scenes, "sample_count": len(joined),
        "string_token_count": string_report.get("token_count"),
        "method": {
            "join": "scene filename + decoded token payload offset inside bounded candidate record window",
            "group_keys": ["candidate table ordinal", "first visible node-class/resource marker"],
            "minimum_group_size": args.min_group, "minimum_support": args.min_support,
            "warning": "Relative offsets are observations, not decoded field boundaries or property meanings."
        },
        **result,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "groups"}, indent=2))


if __name__ == "__main__":
    main()
