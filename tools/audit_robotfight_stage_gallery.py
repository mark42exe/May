#!/usr/bin/env python3
"""Validate the six recovered arena preview assets used by the reconstructed stage gallery."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from PIL import Image

STAGES = (
    ("scene_11", "TRAINING", "scene_thumbnail_11.png"),
    ("scene_0", "SCRAP YARD", "scene_thumbnail_0.png"),
    ("scene_1", "FACTORY", "scene_thumbnail_1.png"),
    ("scene_3", "ROOFTOPS", "scene_thumbnail_3.png"),
    ("scene_13", "CORE DROP", "scene_thumbnail_13.png"),
    ("scene_19", "FINAL PIT", "scene_thumbnail_19.png"),
)

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("resource_root", type=Path, help="Imported original/ resource directory")
    parser.add_argument("--out", type=Path, required=True, help="JSON audit output")
    args = parser.parse_args()

    root = args.resource_root
    records = []
    errors = []
    for stage_id, title, filename in STAGES:
        path = root / filename
        record = {"id": stage_id, "title": title, "thumbnail": filename, "exists": path.is_file()}
        if not path.is_file():
            errors.append(f"Missing arena thumbnail: {filename}")
        else:
            try:
                with Image.open(path) as image:
                    image.verify()
                with Image.open(path) as image:
                    width, height = image.size
                    record.update(width=width, height=height, format=image.format)
                    if width < 160 or height < 90:
                        errors.append(f"Arena thumbnail is unexpectedly small: {filename} ({width}x{height})")
            except Exception as exc:
                errors.append(f"Unreadable arena thumbnail {filename}: {exc}")
        records.append(record)

    required_scenes = ("RFBattleLayer.ccb", "RFMainLayer.ccb", "RFEditorLayer.ccb")
    scenes = {name: (root / name).is_file() for name in required_scenes}
    for name, present in scenes.items():
        if not present:
            errors.append(f"Missing required original scene: {name}")

    report = {
        "stage_count": len(records),
        "stages": records,
        "required_scene_files": scenes,
        "passed": not errors,
        "errors": errors,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Stage gallery assets: {len(records)} checked")
    for stage in records:
        dims = f"{stage.get('width', 0)}x{stage.get('height', 0)}"
        print(f"  {'OK' if stage['exists'] else 'MISSING'} {stage['id']}: {stage['title']} ({dims})")
    if errors:
        raise SystemExit("\n".join(errors))
    print("Stage gallery asset audit passed.")

if __name__ == "__main__":
    main()
