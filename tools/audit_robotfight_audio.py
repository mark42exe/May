#!/usr/bin/env python3
"""Audit every audio file referenced by the recovered Toy Attack SoundEvents plist."""
from __future__ import annotations

import argparse
import json
import plistlib
from pathlib import Path, PurePosixPath


ALLOWED_AUDIO = {".ogg", ".wav", ".mp3", ".m4a"}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path, help="Imported Resources/original directory")
    parser.add_argument("--out", type=Path, help="Optional JSON report path")
    args = parser.parse_args()

    root = args.root.resolve()
    plist_path = root / "SoundEvents.plist"
    problems: list[str] = []
    if not plist_path.is_file():
        raise SystemExit(f"Sound event plist not found: {plist_path}")

    try:
        with plist_path.open("rb") as stream:
            data = plistlib.load(stream)
    except Exception as exc:
        raise SystemExit(f"Cannot parse SoundEvents.plist: {exc}") from exc

    if not isinstance(data, dict):
        raise SystemExit("SoundEvents.plist root must be a dictionary")
    events = data.get("events")
    if not isinstance(events, dict) or not events:
        raise SystemExit("SoundEvents.plist has no event dictionary")

    checked: list[dict[str, object]] = []
    for event_name, config in events.items():
        if not isinstance(event_name, str) or not isinstance(config, dict):
            problems.append(f"Invalid event entry: {event_name!r}")
            continue
        tracks = config.get("localTracks", [])
        if not isinstance(tracks, list):
            problems.append(f"{event_name}: localTracks must be an array")
            continue
        for track in tracks:
            if not isinstance(track, str) or not track:
                problems.append(f"{event_name}: audio track name is empty or not a string")
                continue
            relative = PurePosixPath(track.replace("\\", "/"))
            if relative.is_absolute() or ".." in relative.parts or relative.suffix.lower() not in ALLOWED_AUDIO:
                problems.append(f"{event_name}: unsafe or unsupported audio path {track!r}")
                continue
            target = (root / Path(*relative.parts)).resolve()
            if root not in target.parents or not target.is_file() or target.stat().st_size == 0:
                problems.append(f"{event_name}: referenced audio file is missing or empty: {track}")
                continue
            checked.append({
                "event": event_name,
                "track": relative.as_posix(),
                "bytes": target.stat().st_size,
            })

    report = {
        "event_count": len(events),
        "track_reference_count": len(checked),
        "unique_track_count": len({item["track"] for item in checked}),
        "passed": not problems and bool(checked),
        "problems": problems,
        "tracks": checked,
    }
    rendered = json.dumps(report, indent=2)
    print(rendered)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(rendered + "\n", encoding="utf-8")
    if problems or not checked:
        raise SystemExit("AUDIO EVENT AUDIT FAILED")


if __name__ == "__main__":
    main()
