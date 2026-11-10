#!/usr/bin/env python3
"""Validate recovered Toy Attack part geometry and its flattened image resources.

Missing JSON for some catalog entries is reported as metadata coverage, not treated
as corruption: several tutor/special parts are represented by alternate resources.
Every JSON file that is present must be internally consistent and reference files
that were actually imported.
"""
from __future__ import annotations

import argparse
import json
import plistlib
from collections import Counter
from pathlib import Path

CATEGORIES = {
    "Base": "base",
    "Core": "core",
    "Head": "head",
    "FrontArm": "arm_f",
    "BackArm": "arm_b",
}


def fail(message: str) -> None:
    raise SystemExit("PART GEOMETRY AUDIT FAILED: " + message)


def audit(root: Path) -> dict:
    catalog_path = root / "RFPartsData.plist"
    if not catalog_path.is_file():
        fail(f"missing {catalog_path.name}")
    with catalog_path.open("rb") as stream:
        catalog = plistlib.load(stream)

    report = {"catalog_entries": {}, "geometry_files": 0,
              "image_references": 0, "fixtures": 0, "special_entries_without_json": {}}
    for category, prefix in CATEGORIES.items():
        entries = catalog.get(category)
        if not isinstance(entries, dict):
            fail(f"catalog category {category} is missing or malformed")
        present = 0
        missing = []
        for part_id in entries:
            if part_id == "dummy":
                continue
            json_path = root / f"{prefix}_{part_id}.json"
            if not json_path.is_file():
                missing.append(part_id)
                continue
            try:
                data = json.loads(json_path.read_text(encoding="utf-8"))
            except Exception as exc:
                fail(f"cannot parse {json_path.name}: {exc}")
            bodies = data.get("body")
            images = data.get("image")
            if not isinstance(bodies, list) or not bodies:
                fail(f"{json_path.name} has no body records")
            if not isinstance(images, list) or not images:
                fail(f"{json_path.name} has no image records")
            for index, body in enumerate(bodies):
                position = body.get("position")
                if position is not None and not all(
                    isinstance(position.get(axis), (int, float)) for axis in ("x", "y")
                ):
                    fail(f"{json_path.name} body {index} has invalid position")
                for fixture in body.get("fixture", []):
                    report["fixtures"] += 1
                    polygon = fixture.get("polygon")
                    if polygon:
                        vertices = polygon.get("vertices", {})
                        xs, ys = vertices.get("x", []), vertices.get("y", [])
                        if len(xs) != len(ys) or len(xs) < 3:
                            fail(f"{json_path.name} body {index} has malformed polygon")
            for image in images:
                report["image_references"] += 1
                body_index = image.get("body")
                if not isinstance(body_index, int) or not 0 <= body_index < len(bodies):
                    fail(f"{json_path.name} has image with invalid body index {body_index}")
                source_name = Path(image.get("file", "")).name
                if not source_name or not (root / source_name).is_file():
                    fail(f"{json_path.name} references missing image {source_name!r}")
            present += 1
            report["geometry_files"] += 1
        if present < 20:
            fail(f"{category} geometry coverage unexpectedly low: {present}")
        report["catalog_entries"][category] = {
            "catalog": len(entries) - (1 if "dummy" in entries else 0),
            "geometry_json": present,
        }
        report["special_entries_without_json"][category] = missing

    batteries = catalog.get("Battery")
    if not isinstance(batteries, dict) or len(batteries) < 3:
        fail("battery catalog is incomplete")
    for battery_id in batteries:
        image_id = battery_id.split("_")[-1]
        image_name = f"battery_1_{image_id}.png"
        if not (root / image_name).is_file():
            fail(f"battery {battery_id} references missing image {image_name}")
    report["battery_entries"] = len(batteries)
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path, help="imported original resource directory")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    report = audit(args.root)
    rendered = json.dumps(report, indent=2, sort_keys=True)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    print("PART GEOMETRY AUDIT PASSED")


if __name__ == "__main__":
    main()
