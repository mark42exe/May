#!/usr/bin/env python3
"""Validate recovered sprite-animation definitions against their original atlases.

This is a resource-integrity audit only. It does not decode proprietary skeletons
or claim to recreate original runtime animation behavior.
"""
from __future__ import annotations
import argparse
import json
import plistlib
from pathlib import Path

def expected_frames(spec: str) -> list[str]:
    if "," not in spec:
        return [spec]
    pattern, first_text, last_text = spec.rsplit(",", 2)
    first, last = int(first_text), int(last_text)
    step = 1 if last >= first else -1
    if "%" not in pattern:
        raise ValueError(f"frame range has no printf placeholder: {spec}")
    return [pattern % index for index in range(first, last + step, step)]

def audit(root: Path) -> dict:
    records, problems = [], []
    total_frames = 0
    for config_path in sorted(root.rglob("*Anim.plist")):
        rel = config_path.relative_to(root).as_posix()
        try:
            config = plistlib.loads(config_path.read_bytes())
        except Exception as exc:
            problems.append(f"{rel}: cannot parse animation plist: {exc}")
            continue
        if not isinstance(config, dict):
            problems.append(f"{rel}: animation root is not a dictionary")
            continue
        fps, texture, animations = config.get("fps"), config.get("texture"), config.get("animations")
        if not isinstance(fps, (int, float)) or fps <= 0:
            problems.append(f"{rel}: missing or invalid fps")
        if not isinstance(texture, str) or not texture:
            problems.append(f"{rel}: missing texture atlas name")
            continue
        if not isinstance(animations, dict) or not animations:
            problems.append(f"{rel}: missing animation definitions")
            continue
        atlas_path = config_path.parent / texture
        if not atlas_path.is_file():
            problems.append(f"{rel}: atlas plist missing: {texture}")
            continue
        try:
            atlas = plistlib.loads(atlas_path.read_bytes())
            frames = atlas.get("frames", {}) if isinstance(atlas, dict) else {}
            if not isinstance(frames, dict):
                raise ValueError("atlas frames root is not a dictionary")
        except Exception as exc:
            problems.append(f"{rel}: cannot parse atlas {texture}: {exc}")
            continue
        target = atlas.get("metadata", {}).get("target", {})
        texture_base = target.get("textureFileName")
        texture_ext = target.get("textureFileExtension", ".png")
        texture_ok = bool(texture_base) and any(
            (config_path.parent / f"{texture_base}{ext}").is_file()
            for ext in dict.fromkeys((texture_ext, ".png", ".webp"))
        )
        if texture_base and not texture_ok:
            problems.append(f"{rel}: atlas image missing for {texture_base}")
        animation_count, frame_count, missing = 0, 0, []
        for animation_name, definition in animations.items():
            animation_count += 1
            if not isinstance(definition, dict) or not isinstance(definition.get("frames"), list):
                problems.append(f"{rel}: animation {animation_name} has no frame list")
                continue
            for spec in definition["frames"]:
                try:
                    expanded = expected_frames(str(spec))
                except Exception as exc:
                    problems.append(f"{rel}: invalid frame spec {spec!r}: {exc}")
                    continue
                for frame_name in expanded:
                    frame_count += 1
                    if frame_name not in frames:
                        missing.append(frame_name)
        total_frames += frame_count
        if missing:
            problems.append(f"{rel}: {len(missing)} frame references absent from {texture}: " + ", ".join(missing[:12]))
        records.append({
            "animation_config": rel, "atlas": atlas_path.relative_to(root).as_posix(),
            "fps": fps, "animation_count": animation_count,
            "frame_references_checked": frame_count, "atlas_frame_count": len(frames),
            "missing_frame_references": missing, "atlas_image_verified": texture_ok,
        })
    return {
        "animation_config_count": len(records), "frame_references_checked": total_frames,
        "passed": not problems and bool(records), "problems": problems, "animations": records,
    }

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()
    if not args.root.is_dir():
        raise SystemExit(f"Resource directory does not exist: {args.root}")
    report = audit(args.root)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\\n")
    print(json.dumps({
        "animation_config_count": report["animation_config_count"],
        "frame_references_checked": report["frame_references_checked"],
        "passed": report["passed"], "problems": report["problems"],
        "report": str(args.out) if args.out else None,
    }, indent=2))
    if not report["passed"]:
        raise SystemExit("ORIGINAL ANIMATION RESOURCE AUDIT FAILED")

if __name__ == "__main__":
    main()
