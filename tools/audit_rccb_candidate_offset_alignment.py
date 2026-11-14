#!/usr/bin/env python3
"""Measure proximity between heuristic RCCB offsets and visible string tokens.

This is a forensic alignment report only. It does not promote candidate offsets
into record boundaries or assign meaning to any binary field.
"""
from __future__ import annotations

import argparse
import collections
import json
from pathlib import Path

NODE_CLASSES = {
    "CCNode", "CCSprite", "CCSprite9Slice", "CCLabelTTF", "CCLabelBMFont",
    "CCButton", "DCNode", "DCLabel", "DCLabelTTF", "DCSprite",
    "DCUIButton", "DCUIControl",
}
RESOURCE_SUFFIXES = (".webp", ".png", ".jpg", ".jpeg", ".ttf", ".fnt", ".plist", ".json")


def token_kind(value: str) -> str | None:
    if value in NODE_CLASSES:
        return "node_class"
    if value.lower().endswith(RESOURCE_SUFFIXES):
        return "resource"
    return None


def analyze(inventory: dict, scene_root: Path, max_distance: int = 256) -> dict:
    if max_distance < 0 or max_distance > 4096:
        raise ValueError("max_distance must be between 0 and 4096")
    scenes = inventory.get("scenes")
    if not isinstance(scenes, list) or not scenes:
        raise ValueError("inventory contains no scenes")

    candidate_count = 0
    with_class_count = 0
    with_resource_count = 0
    class_scenes = set()
    resource_scenes = set()
    exact_class = 0
    radius_counts = {radius: {"node_class": 0, "resource": 0}
                     for radius in (0, 4, 16, 32, 64, 96, 256) if radius <= max_distance}
    class_deltas = collections.defaultdict(collections.Counter)
    resource_deltas = collections.defaultdict(collections.Counter)
    nearest_examples = []
    table_summaries = []

    for scene in scenes:
        name = scene.get("file")
        if not isinstance(name, str) or not name:
            raise ValueError("scene filename missing")
        path = scene_root / name
        if not path.is_file():
            raise ValueError(f"missing scene file: {name}")
        data_size = path.stat().st_size
        if data_size != scene.get("size"):
            raise ValueError(f"scene size mismatch: {name}")

        tokens = []
        for item in scene.get("strings", []):
            value = item.get("value") if isinstance(item, dict) else None
            offset = item.get("offset") if isinstance(item, dict) else None
            kind = token_kind(value) if isinstance(value, str) else None
            if kind and isinstance(offset, int) and 0 <= offset < data_size:
                tokens.append({"value": value, "offset": offset, "kind": kind,
                               "encoding": item.get("encoding", "unknown")})
        tokens.sort(key=lambda item: item["offset"])

        for table_index, table in enumerate(scene.get("candidate_offset_tables", [])):
            table_offsets = table.get("offsets", [])
            table_class_hits = 0
            table_resource_hits = 0
            for candidate in table_offsets[:-1]:
                if not isinstance(candidate, int) or candidate < 0 or candidate >= data_size:
                    raise ValueError(f"candidate offset outside scene: {name}@{candidate}")
                candidate_count += 1
                nearby = [t for t in tokens if abs(t["offset"] - candidate) <= max_distance]
                classes = [t for t in nearby if t["kind"] == "node_class"]
                resources = [t for t in nearby if t["kind"] == "resource"]
                for radius in radius_counts:
                    if any(abs(t["offset"] - candidate) <= radius for t in tokens if t["kind"] == "node_class"):
                        radius_counts[radius]["node_class"] += 1
                    if any(abs(t["offset"] - candidate) <= radius for t in tokens if t["kind"] == "resource"):
                        radius_counts[radius]["resource"] += 1
                if classes:
                    nearest = min(classes, key=lambda t: (abs(t["offset"] - candidate), t["offset"]))
                    delta = nearest["offset"] - candidate
                    with_class_count += 1
                    class_scenes.add(name)
                    class_deltas[nearest["value"]][delta] += 1
                    table_class_hits += 1
                    exact_class += delta == 0
                if resources:
                    nearest_resource = min(resources, key=lambda t: (abs(t["offset"] - candidate), t["offset"]))
                    delta_resource = nearest_resource["offset"] - candidate
                    with_resource_count += 1
                    resource_scenes.add(name)
                    resource_deltas[nearest_resource["value"]][delta_resource] += 1
                    table_resource_hits += 1
                if len(nearest_examples) < 80 and (classes or resources):
                    chosen = min(nearby, key=lambda t: (abs(t["offset"] - candidate), t["offset"]))
                    nearest_examples.append({
                        "scene": name, "table_index": table_index,
                        "candidate_offset": candidate,
                        "nearest_token": chosen["value"],
                        "token_kind": chosen["kind"],
                        "signed_delta_token_minus_candidate": chosen["offset"] - candidate,
                    })
            table_summaries.append({
                "scene": name, "table_index": table_index,
                "candidate_count": len(table_offsets) - 1,
                "node_class_proximity_count": table_class_hits,
                "resource_proximity_count": table_resource_hits,
                "sentinel": table_offsets[-1] if table_offsets else None,
            })

    return {
        "format": "RCCB heuristic candidate-offset/token proximity audit v1",
        "scene_count": len(scenes),
        "candidate_offset_count": candidate_count,
        "maximum_absolute_distance_bytes": max_distance,
        "candidate_offsets_with_node_class_nearby": with_class_count,
        "candidate_offsets_with_node_class_nearby_scene_count": len(class_scenes),
        "candidate_offsets_with_resource_nearby": with_resource_count,
        "candidate_offsets_with_resource_nearby_scene_count": len(resource_scenes),
        "candidate_offsets_exactly_at_node_class_string": exact_class,
        "candidate_offsets_with_token_by_radius": [
            {"radius_bytes": radius, **counts} for radius, counts in sorted(radius_counts.items())
        ],
        "nearest_node_class_signed_delta_counts": {
            marker: [{"delta": delta, "count": count} for delta, count in sorted(counts.items())]
            for marker, counts in sorted(class_deltas.items())
        },
        "nearest_resource_signed_delta_counts": {
            marker: [{"delta": delta, "count": count} for delta, count in sorted(counts.items())]
            for marker, counts in sorted(resource_deltas.items())
        },
        "table_summaries": table_summaries,
        "nearest_examples": nearest_examples,
        "limitations": [
            "Candidate offsets remain heuristic and are not proven RCCB record starts.",
            "String proximity does not establish field boundaries, property types, ownership, or hierarchy.",
            "The report does not modify any original scene bytes.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("inventory", type=Path)
    parser.add_argument("scene_root", type=Path)
    parser.add_argument("--max-distance", type=int, default=256)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    report = analyze(json.loads(args.inventory.read_text(encoding="utf-8")),
                     args.scene_root, args.max_distance)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items()
                      if k not in ("table_summaries", "nearest_examples",
                                   "nearest_node_class_signed_delta_counts",
                                   "nearest_resource_signed_delta_counts")}, indent=2))


if __name__ == "__main__":
    main()
