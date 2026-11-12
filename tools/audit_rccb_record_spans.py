#!/usr/bin/env python3
"""Audit candidate RCCB record spans against independently decoded string tokens.

Offset tables provide candidate record starts, not proven object boundaries.
This tool derives non-overlapping intervals within each table only and reports
which verified string tokens fall wholly inside each interval. It does not
assign node/property semantics or construct a scene graph.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

NODE_TYPES = {
    "CCNode", "CCSprite", "CCSprite9Slice", "CCLabelTTF", "CCLabelBMFont",
    "CCButton", "DCNode", "DCLabel", "DCLabelTTF", "DCSprite",
    "DCUIButton", "DCUIControl",
}
RESOURCE_SUFFIXES = (".webp", ".png", ".jpg", ".jpeg", ".ttf", ".fnt", ".plist", ".json")


def build_report(inventory: dict, string_layer: dict) -> dict:
    if inventory.get("scene_count") != string_layer.get("scene_count"):
        raise ValueError("scene counts differ between inventory and string layer")

    strings_by_scene = {scene["file"]: scene for scene in string_layer.get("scenes", [])}
    records = []
    scene_summaries = []
    total_tables = 0

    for scene in inventory.get("scenes", []):
        name = scene["file"]
        decoded = strings_by_scene.get(name)
        if decoded is None:
            raise ValueError(f"missing decoded string inventory for {name}")
        tokens = decoded.get("tokens", [])
        token_endpoints = []
        for token in tokens:
            start = token.get("length_offset")
            length = token.get("byte_length")
            if not isinstance(start, int) or not isinstance(length, int) or length < 0:
                raise ValueError(f"invalid token offsets in {name}")
            end = start + 4 + length + (1 if token.get("nul_terminated") else 0)
            if end > scene["size"] or start < 0:
                raise ValueError(f"token outside scene bounds in {name}")
            token_endpoints.append((start, end, token))

        scene_record_count = 0
        for table_index, table in enumerate(scene.get("candidate_offset_tables", [])):
            total_tables += 1
            offsets = sorted({
                item["offset"] for item in table.get("targets", [])
                if isinstance(item.get("offset"), int)
            }, reverse=True)
            if not offsets:
                continue
            if any(offset < 16 or offset >= scene["size"] for offset in offsets):
                raise ValueError(f"candidate record start outside bounds in {name}")
            for index, start in enumerate(offsets):
                end = offsets[index - 1] if index else scene["size"]
                if end <= start:
                    raise ValueError(f"invalid candidate span in {name}")
                contained = [
                    token for token_start, token_end, token in token_endpoints
                    if start <= token_start and token_end <= end
                ]
                values = [token["value"] for token in contained]
                classes = sorted(set(values) & NODE_TYPES)
                resources = sorted({
                    value for value in values
                    if value.lower().endswith(RESOURCE_SUFFIXES)
                })
                record = {
                    "scene": name,
                    "table_index": table_index,
                    "table_offset": table.get("table_offset"),
                    "candidate_start": start,
                    "candidate_end_exclusive": end,
                    "span_bytes": end - start,
                    "contained_token_count": len(contained),
                    "node_class_tokens": classes,
                    "resource_tokens": resources,
                    "all_tokens": values,
                    "boundary_confidence": "candidate-only; derived from adjacent offsets in this table",
                }
                records.append(record)
                scene_record_count += 1
        scene_summaries.append({
            "scene": name,
            "candidate_table_count": len(scene.get("candidate_offset_tables", [])),
            "candidate_span_count": scene_record_count,
        })

    class_counts = Counter(
        class_name for record in records for class_name in record["node_class_tokens"]
    )
    return {
        "format": "RCCB candidate record span/token containment audit v1",
        "scene_count": len(inventory.get("scenes", [])),
        "candidate_table_count": total_tables,
        "candidate_span_count": len(records),
        "span_boundary_note": "Adjacent candidate offsets define analysis intervals only; they are not proven RCCB record boundaries.",
        "node_class_token_record_counts": dict(sorted(class_counts.items())),
        "scenes": scene_summaries,
        "records": records,
        "limitations": [
            "Offset arrays are heuristic candidates, not a decoded RCCB grammar.",
            "Intervals may overlap across different candidate tables.",
            "Contained strings do not establish property ownership or node hierarchy.",
            "No source bytes are changed and no scene graph is emitted.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("inventory", type=Path)
    parser.add_argument("string_layer", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    report = build_report(
        json.loads(args.inventory.read_text(encoding="utf-8")),
        json.loads(args.string_layer.read_text(encoding="utf-8")),
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n",
                        encoding="utf-8")
    print(json.dumps({key: value for key, value in report.items()
                      if key not in ("records", "scenes")}, indent=2))


if __name__ == "__main__":
    main()
