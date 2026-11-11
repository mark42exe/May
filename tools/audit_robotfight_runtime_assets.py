#!/usr/bin/env python3
"""Validate recovered assets referenced directly by the reconstructed Cocos UI."""
from pathlib import Path
import argparse
import json
import plistlib

STAGES = ("11", "0", "1", "3", "13", "19")
REQUIRED_PLISTS = ("RFPartsData.plist", "RFQuestData.plist", "SoundEvents.plist")
OPTIONAL_ROBOT_ART = (
    "base_2_0.png", "core_1_0.png", "head_3_5.png",
    "arm_f_0_0.png", "arm_b_0_3.png", "battery_1_0.png",
)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()
    root = args.root
    required = list(REQUIRED_PLISTS) + [f"scene_thumbnail_{stage}.png" for stage in STAGES]
    missing_required = [name for name in required if not (root / name).is_file()]
    plist_results = {}
    for name in REQUIRED_PLISTS:
        path = root / name
        if not path.is_file():
            plist_results[name] = "missing"
            continue
        try:
            plistlib.loads(path.read_bytes())
            plist_results[name] = "valid"
        except Exception as exc:
            plist_results[name] = f"invalid: {exc}"
    invalid_plists = [name for name, result in plist_results.items() if result != "valid"]
    missing_optional = [name for name in OPTIONAL_ROBOT_ART if not (root / name).is_file()]
    report = {
        "resource_root": str(root),
        "required_runtime_assets": required,
        "missing_required_assets": missing_required,
        "plist_validation": plist_results,
        "optional_robot_art_present": [name for name in OPTIONAL_ROBOT_ART if (root / name).is_file()],
        "optional_robot_art_missing": missing_optional,
        "result": "failed" if missing_required or invalid_plists else "passed",
    }
    out = args.out or root.parent / "robotfight_runtime_asset_audit.json"
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print("Runtime asset audit:", report["result"].upper())
    print("Required assets:", len(required) - len(missing_required), "/", len(required))
    print("Valid required plists:", sum(v == "valid" for v in plist_results.values()), "/", len(REQUIRED_PLISTS))
    print("Optional robot art missing:", missing_optional)
    print("Report:", out)
    if missing_required:
        raise SystemExit("Missing required runtime assets: " + ", ".join(missing_required))
    if invalid_plists:
        raise SystemExit("Invalid runtime plist files: " + ", ".join(invalid_plists))

if __name__ == "__main__":
    main()
