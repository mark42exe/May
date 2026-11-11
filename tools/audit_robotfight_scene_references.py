#!/usr/bin/env python3
"""Inventory file dependencies embedded as printable strings in recovered RCCB scenes.

RCCB is the game's proprietary scene format, not standard CocosBuilder CCBI.
This conservative audit does not claim to decode the scene graph; it records
asset references and custom node-class names for targeted recovery work.
"""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path, PurePosixPath

ASSET_SUFFIXES = {".webp", ".png", ".jpg", ".jpeg", ".plist", ".ccb", ".ttf", ".fnt", ".ogg", ".wav", ".mp3", ".m4a"}
KNOWN_CLASSES = {
    "CCSprite", "CCNode", "CCLabelTTF", "DCSprite", "DCNode", "CCButton",
    "CCSprite9Slice", "DCLabel", "DCUIButton", "DCLabelTTF", "CCBFile",
    "CCParticleSystem", "DCUITableNode", "DCUITableNodeCell", "DCUIEditBox",
    "CCTextField", "DCUIControl", "CCScrollView", "DCClippingNode",
    "CCLabelBMFont", "DCLabelBMF", "DCUICollectionNodeCell",
    "DCUICollectionNode", "CCNodeColor", "DCParticleSystemQuad",
}


def printable_strings(data: bytes):
    for match in re.finditer(rb"[\x20-\x7e]{4,}", data):
        yield match.group().decode("ascii", "ignore")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path, help="Imported Resources/original directory containing RCCB scenes")
    parser.add_argument("--out", type=Path, help="Optional JSON report path")
    parser.add_argument("--strict", action="store_true", help="Return failure when any scene reference is missing")
    args = parser.parse_args()

    root = args.root.resolve()
    scenes = sorted(root.rglob("*.ccb"))
    if not scenes:
        raise SystemExit(f"No recovered RCCB scenes found under {root}")

    class_counts = Counter()
    reference_scenes: dict[str, set[str]] = defaultdict(set)
    invalid_references: list[dict[str, str]] = []
    scene_details = []

    for scene in scenes:
        data = scene.read_bytes()
        if len(data) < 8 or data[4:8] != b"RCCB":
            invalid_references.append({
                "scene": scene.relative_to(root).as_posix(),
                "reference": "<scene-header>",
                "reason": "missing RCCB magic at byte offset 4",
            })
        strings = list(printable_strings(data))
        classes = sorted({value for value in strings if value in KNOWN_CLASSES})
        class_counts.update(classes)
        refs = set()
        for value in strings:
            suffix = PurePosixPath(value).suffix.lower()
            if suffix not in ASSET_SUFFIXES:
                continue
            rel = PurePosixPath(value.replace("\\", "/"))
            if rel.is_absolute() or ".." in rel.parts:
                invalid_references.append({
                    "scene": scene.relative_to(root).as_posix(),
                    "reference": value,
                    "reason": "absolute or traversal path",
                })
                continue
            refs.add(rel.as_posix())
            reference_scenes[rel.as_posix()].add(scene.relative_to(root).as_posix())
        scene_details.append({
            "scene": scene.relative_to(root).as_posix(),
            "bytes": len(data),
            "magic": data[4:8].decode("ascii", "replace") if len(data) >= 8 else "",
            "class_names": classes,
            "asset_reference_count": len(refs),
        })

    found = []
    missing = []
    for reference, used_by in sorted(reference_scenes.items()):
        rel = PurePosixPath(reference)
        candidates = [root.joinpath(*rel.parts)]
        if rel.suffix.lower() == ".webp":
            candidates.append(root.joinpath(*rel.with_suffix(".png").parts))
        target = next((path for path in candidates if path.is_file() and path.stat().st_size > 0), None)
        record = {
            "reference": reference,
            "scene_count": len(used_by),
            "scenes": sorted(used_by),
        }
        if target:
            record["resolved_as"] = target.relative_to(root).as_posix()
            found.append(record)
        else:
            missing.append(record)

    report = {
        "scene_count": len(scenes),
        "rccb_header_valid_count": sum(item["magic"] == "RCCB" for item in scene_details),
        "unique_asset_reference_count": len(reference_scenes),
        "resolved_reference_count": len(found),
        "missing_reference_count": len(missing),
        "invalid_reference_count": len(invalid_references),
        "node_class_scene_counts": dict(class_counts.most_common()),
        "missing_references": missing,
        "invalid_references": invalid_references,
        "scenes": scene_details,
    }
    rendered = json.dumps(report, indent=2)
    print(rendered)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(rendered + "\n", encoding="utf-8")
    if args.strict and (missing or invalid_references):
        raise SystemExit("RCCB SCENE DEPENDENCY AUDIT FAILED")


if __name__ == "__main__":
    main()
