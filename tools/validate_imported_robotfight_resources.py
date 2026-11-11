#!/usr/bin/env python3
"""Fail-fast preflight for imported Toy Attack assets before expensive native builds."""
from __future__ import annotations

import argparse
import hashlib
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
        except Exception as exc:
            manifest = {}
            problems.append(f"Asset manifest cannot be parsed: {exc}")

    files = [p for p in root.rglob("*") if p.is_file()]
    if len(files) < args.minimum_files:
        problems.append(f"Only {len(files)} files imported; expected at least {args.minimum_files}")
    for name in REQUIRED + STAGE_THUMBNAILS:
        path = root / name
        if not path.is_file() or path.stat().st_size == 0:
            problems.append(f"Required original asset missing or empty: {name}")

    # Verify every imported original asset against the import-time manifest.
    manifest_files = manifest.get("files", [])
    if manifest_files and isinstance(manifest_files[0], str):
        problems.append("Legacy asset manifest has no per-file hashes; re-import original assets")
    elif not isinstance(manifest_files, list) or len(manifest_files) != manifest.get("imported_files"):
        problems.append("Asset manifest file list/count is inconsistent")
    else:
        seen = set()
        for record in manifest_files:
            rel = record.get("path", "")
            candidate = Path(rel)
            if not rel or candidate.is_absolute() or ".." in candidate.parts or rel in seen:
                problems.append(f"Unsafe or duplicate manifest path: {rel!r}")
                continue
            seen.add(rel)
            path = root / candidate
            if not path.is_file():
                problems.append(f"Manifest asset missing: {rel}")
                continue
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            if path.stat().st_size != record.get("bytes") or digest != record.get("sha256"):
                problems.append(f"Asset integrity mismatch: {rel}")

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

    audio_checked = 0
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in (".ogg", ".wav", ".mp3", ".m4a"):
            continue
        data = path.read_bytes()[:16]
        suffix = path.suffix.lower()
        valid = (
            (suffix == ".ogg" and data.startswith(b"OggS")) or
            (suffix == ".wav" and len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WAVE") or
            (suffix == ".mp3" and (data.startswith(b"ID3") or (len(data) >= 2 and data[0] == 0xFF and (data[1] & 0xE0) == 0xE0))) or
            (suffix == ".m4a" and len(data) >= 8 and data[4:8] == b"ftyp")
        )
        if not valid:
            problems.append(f"Audio file signature mismatch: {path.relative_to(root)}")
        else:
            audio_checked += 1

    report = {
        "file_count": len(files),
        "manifest_entries_verified": len(manifest_files) if isinstance(manifest_files, list) else 0,
        "audio_files_checked": audio_checked,
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
