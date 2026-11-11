#!/usr/bin/env python3
"""Fail-fast preflight for imported Toy Attack assets before expensive native builds."""
from __future__ import annotations

import argparse
import json
import plistlib
from pathlib import Path
from PIL import Image

REQUIRED = (
    "RFBattleLayer.ccb", "RFMainLayer.ccb", "RFEditorLayer.ccb",
    "RFPartsData.plist", "RFQuestData.plist", "SoundEvents.plist",
    "Normal1.ogg", "bgm_scene_battleFight.wav", "sfx_btn_press.ogg",
)
STAGE_THUMBNAILS = (
    "scene_thumbnail_11.png", "scene_thumbnail_0.png",
    "scene_thumbnail_1.png", "scene_thumbnail_3.png",
    "scene_thumbnail_13.png", "scene_thumbnail_19.png",
)

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    parser.add_argument("--minimum-files", type=int, default=3000)
    args = parser.parse_args()
    root = args.root
    problems: list[str] = []
    if not root.is_dir():
        raise SystemExit(f"Imported resource directory does not exist: {root}")

    manifest_path = root / "original_asset_manifest.json"
    if not manifest_path.is_file():
        problems.append("original_asset_manifest.json is missing")
        manifest = {}
    else:
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            if not isinstance(manifest, dict):
                raise ValueError("manifest root must be a JSON object")
            listed = manifest.get("files")
            if not isinstance(listed, list) or not all(isinstance(item, str) for item in listed):
                raise ValueError("manifest 'files' must be a list of paths")
            if manifest.get("imported_files") != len(listed):
                raise ValueError("manifest imported_files count does not match its file list")
            if len(set(listed)) != len(listed):
                raise ValueError("manifest contains duplicate resource paths")
            for relative in listed:
                candidate = Path(relative)
                if candidate.is_absolute() or ".." in candidate.parts:
                    problems.append(f"Unsafe path in asset manifest: {relative}")
                    continue
                if not (root / candidate).is_file():
                    problems.append(f"Manifest resource was not imported: {relative}")
        except Exception as exc:
            manifest = {}
            problems.append(f"Asset manifest is invalid: {exc}")

    files = [p for p in root.rglob("*") if p.is_file()]
    if len(files) < args.minimum_files:
        problems.append(f"Only {len(files)} files imported; expected at least {args.minimum_files}")
    for name in REQUIRED + STAGE_THUMBNAILS:
        path = root / name
        if not path.is_file() or path.stat().st_size == 0:
            problems.append(f"Required original asset missing or empty: {name}")

    image_count = 0
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in (".png", ".webp"):
            continue
        image_count += 1
        try:
            with Image.open(path) as image:
                image.verify()
        except Exception as exc:
            problems.append(f"Unreadable image {path.relative_to(root)}: {exc}")

    plist_count = 0
    for name in ("RFPartsData.plist", "RFQuestData.plist", "SoundEvents.plist"):
        path = root / name
        if not path.is_file():
            continue
        try:
            with path.open("rb") as stream:
                value = plistlib.load(stream)
            if not isinstance(value, dict) or not value:
                problems.append(f"{name} has an empty or non-dictionary root")
            else:
                plist_count += 1
        except Exception as exc:
            problems.append(f"{name} cannot be parsed: {exc}")

    report = {
        "file_count": len(files),
        "manifest_imported_files": manifest.get("imported_files"),
        "image_count_checked": image_count,
        "critical_plists_parsed": plist_count,
        "required_assets": list(REQUIRED + STAGE_THUMBNAILS),
        "passed": not problems,
        "problems": problems,
    }
    print(json.dumps(report, indent=2))
    if problems:
        raise SystemExit("IMPORTED RESOURCE PREFLIGHT FAILED")

if __name__ == "__main__":
    main()
