#!/usr/bin/env python3
"""Strictly validate the RCCB inventory before it is used for format research.

This checks repeatable structural evidence only. It intentionally does not
interpret candidate offsets as decoded nodes or claim CCBI compatibility.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

EXPECTED_SCENES = 138
EXPECTED_MAGIC = "RCCB"
REQUIRED_BATTLE_EVIDENCE = {
    "background_3_2.webp",
    "heatBar40",
    "heatBar41",
    "RFBattleLayer.ccb",
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("report", type=Path)
    args = parser.parse_args()
    report = json.loads(args.report.read_text(encoding="utf-8"))
    scenes = report.get("scenes")
    if not isinstance(scenes, list) or len(scenes) != EXPECTED_SCENES:
        raise SystemExit(f"Expected {EXPECTED_SCENES} scene records")
    if report.get("scene_count") != EXPECTED_SCENES:
        raise SystemExit("Top-level scene_count disagrees with scene records")
    if report.get("magic_counts") != {EXPECTED_MAGIC: EXPECTED_SCENES}:
        raise SystemExit("Unexpected RCCB magic distribution")

    names = [scene.get("file") for scene in scenes]
    if len(set(names)) != EXPECTED_SCENES or any(not name for name in names):
        raise SystemExit("Scene filenames are missing or duplicated")

    total_bytes = 0
    candidate_count = 0
    battle = None
    for scene in scenes:
        size = scene.get("size")
        if not isinstance(size, int) or size <= 16:
            raise SystemExit(f"Invalid scene size: {scene.get('file')}")
        total_bytes += size
        if scene.get("magic") != EXPECTED_MAGIC:
            raise SystemExit(f"Unexpected magic in {scene.get('file')}")
        if not isinstance(scene.get("sha256"), str) or len(scene["sha256"]) != 64:
            raise SystemExit(f"Missing SHA-256 for {scene.get('file')}")
        if not isinstance(scene.get("resource_references"), list):
            raise SystemExit(f"Missing resource references for {scene.get('file')}")
        for table in scene.get("candidate_offset_tables", []):
            offsets = table.get("offsets", [])
            if len(offsets) != table.get("entry_count"):
                raise SystemExit(f"Malformed candidate offset table in {scene.get('file')}")
            if not all(isinstance(value, int) for value in offsets):
                raise SystemExit(f"Non-integer candidate offset in {scene.get('file')}")
            if not all(offsets[i] > offsets[i + 1] for i in range(len(offsets) - 1)):
                raise SystemExit(f"Candidate offsets are not descending in {scene.get('file')}")
            if any(value >= size for value in offsets[:-1]):
                raise SystemExit(f"Candidate offset escapes scene bounds in {scene.get('file')}")
            candidate_count += 1
        if scene.get("file") == "RFBattleLayer.ccb":
            battle = scene

    if report.get("total_scene_bytes") != total_bytes:
        raise SystemExit("Top-level byte total disagrees with scene records")
    if battle is None:
        raise SystemExit("RFBattleLayer.ccb is absent from inventory")

    # The inspector stores identifier candidates and strings as records with
    # offset/value/encoding fields, not as bare strings.
    battle_evidence = set(battle.get("resource_references", []))
    for field in ("identifier_candidates", "strings"):
        records = battle.get(field, [])
        if not isinstance(records, list):
            raise SystemExit(f"Malformed {field} in battle scene")
        for record in records:
            if isinstance(record, dict) and isinstance(record.get("value"), str):
                battle_evidence.add(record["value"])
    battle_evidence.add(battle["file"])
    missing = sorted(REQUIRED_BATTLE_EVIDENCE - battle_evidence)
    if missing:
        raise SystemExit("Battle-scene evidence missing: " + ", ".join(missing))

    print(json.dumps({
        "passed": True,
        "scene_count": EXPECTED_SCENES,
        "total_scene_bytes": total_bytes,
        "candidate_offset_table_count": candidate_count,
        "battle_scene_evidence": sorted(REQUIRED_BATTLE_EVIDENCE),
        "interpretation": "structural validation only; not a decoded scene graph",
    }, indent=2))


if __name__ == "__main__":
    main()
