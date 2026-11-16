#!/usr/bin/env python3
"""Audit exact and near RCCB candidate-offset coincidences with decoded strings.

This is a positional audit only. A matching string boundary does not prove
that a candidate offset is a node record, field pointer, or object boundary.
"""
from __future__ import annotations
import argparse
import collections
import json
from pathlib import Path

NODE_CLASSES = {
    "CCNode", "CCSprite", "CCSprite9Slice", "CCLabelTTF", "CCLabelBMFont",
    "CCButton", "DCNode", "DCLabel", "DCLabelTTF", "DCSprite",
    "DCUIButton", "DCUIControl", "DCUICollectionNodeCell",
}
RESOURCE_SUFFIXES = (".webp", ".png", ".jpg", ".jpeg", ".ttf", ".fnt", ".plist", ".json")


def token_kind(value: str) -> str:
    if value in NODE_CLASSES:
        return "node_class"
    if any(value.lower().endswith(s) and len(value) > len(s) for s in RESOURCE_SUFFIXES):
        return "resource"
    return "other"


def analyze(samples: dict, strings: dict, radius: int = 16) -> dict:
    if samples.get("scene_count") != strings.get("scene_count"):
        raise ValueError("scene inventory mismatch")
    if radius < 0:
        raise ValueError("radius must be non-negative")
    by_scene = {scene["file"]: scene["tokens"] for scene in strings.get("scenes", [])}
    matches = []
    deltas = {
        "length_prefix": collections.Counter(),
        "payload_start": collections.Counter(),
    }
    exact = {
        "length_prefix": collections.Counter(),
        "payload_start": collections.Counter(),
    }
    for sample in samples.get("samples", []):
        scene = sample["scene"]
        if scene not in by_scene:
            raise ValueError("sample scene missing from string layer: " + scene)
        candidate = sample["record_offset"]
        for token in by_scene[scene]:
            for anchor, field in (("length_prefix", "length_offset"), ("payload_start", "payload_offset")):
                delta = token[field] - candidate
                if abs(delta) <= radius:
                    kind = token_kind(token["value"])
                    deltas[anchor][delta] += 1
                    if delta == 0:
                        exact[anchor][kind] += 1
                        matches.append({
                            "scene": scene,
                            "table_index": sample["table_index"],
                            "candidate_offset": candidate,
                            "anchor": anchor,
                            "token_kind": kind,
                            "token": token["value"],
                            "length_offset": token["length_offset"],
                            "payload_offset": token["payload_offset"],
                        })
    return {
        "format": "RCCB candidate-token-anchor audit v1",
        "scene_count": samples["scene_count"],
        "sample_count": len(samples.get("samples", [])),
        "radius_bytes": radius,
        "exact_length_prefix_matches": sum(exact["length_prefix"].values()),
        "exact_payload_start_matches": sum(exact["payload_start"].values()),
        "exact_matches_by_anchor_and_kind": {
            anchor: dict(sorted(counts.items()))
            for anchor, counts in exact.items()
        },
        "nearby_delta_histograms": {
            anchor: [{"delta_bytes": delta, "occurrences": count}
                     for delta, count in sorted(counts.items())]
            for anchor, counts in deltas.items()
        },
        "exact_matches": matches,
        "limitations": [
            "Candidate offsets are heuristic and are not proven record starts.",
            "Exact coincidence with a string prefix or payload is positional evidence only.",
            "No field type, object ownership, hierarchy, or scene graph is inferred.",
            "Nearby token positions do not establish pointer direction or serialization layout.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("samples", type=Path)
    parser.add_argument("strings", type=Path)
    parser.add_argument("--radius", type=int, default=16)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    report = analyze(json.loads(args.samples.read_text()), json.loads(args.strings.read_text()), args.radius)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k not in ("exact_matches", "nearby_delta_histograms")}, indent=2))


if __name__ == "__main__":
    main()
