#!/usr/bin/env python3
"""Stage the separately recovered RCCB scene bundle into the imported runtime resources."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path


REQUIRED = ("RFBattleLayer.ccb", "RFMainLayer.ccb", "RFEditorLayer.ccb")


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("scene_root", type=Path, help="Root containing the extracted verified scene bundle")
    parser.add_argument("resource_root", type=Path, help="Imported Resources/original destination")
    parser.add_argument("--expected-count", type=int, default=138)
    args = parser.parse_args()

    scene_root = args.scene_root.resolve()
    resource_root = args.resource_root.resolve()
    if not scene_root.is_dir() or not resource_root.is_dir():
        raise SystemExit("Scene source and imported resource destination must both exist")

    candidates = []
    for path in scene_root.rglob("*.ccb"):
        resolved = path.resolve()
        if resolved == resource_root or resource_root in resolved.parents:
            continue
        if path.is_file() and path.stat().st_size:
            candidates.append(path)

    # The workflow also places a root-level convenience copy of RFBattleLayer.ccb.
    # Deduplicate identical copies by filename; reject conflicting same-name scenes.
    by_name: dict[str, Path] = {}
    for path in sorted(candidates):
        previous = by_name.get(path.name)
        if previous is None:
            by_name[path.name] = path
        elif digest(previous) != digest(path):
            raise SystemExit(f"Conflicting recovered scene files share the name {path.name}")

    names = set(by_name)
    missing = [name for name in REQUIRED if name not in names]
    if missing:
        raise SystemExit("Recovered scene bundle is missing required scenes: " + ", ".join(missing))
    if len(by_name) != args.expected_count:
        raise SystemExit(
            f"Recovered scene bundle has {len(by_name)} unique scenes; expected {args.expected_count}"
        )

    copied = []
    for name, source in sorted(by_name.items()):
        target = resource_root / name
        if source.resolve() != target.resolve():
            shutil.copy2(source, target)
        if not target.is_file() or digest(source) != digest(target):
            raise SystemExit(f"Scene staging verification failed: {name}")
        copied.append({"name": name, "bytes": target.stat().st_size, "sha256": digest(target)})

    report = {
        "expected_count": args.expected_count,
        "unique_scene_count": len(copied),
        "required_scenes": list(REQUIRED),
        "passed": True,
        "scenes": copied,
    }
    report_path = resource_root / "recovered_scene_staging_report.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "scenes"}, indent=2))
    print("Recovered scene files staged and SHA-256 verified.")


if __name__ == "__main__":
    main()
