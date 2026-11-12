#!/usr/bin/env python3
"""Extract bounded, byte-preserving RCCB candidate record samples.

The output is forensic evidence for format research, not a decoded scene graph.
No field is assigned semantic meaning by this tool.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import struct
from collections import Counter
from pathlib import Path

PRINTABLE = re.compile(rb"[ -~]{4,}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("scene_root", type=Path)
    ap.add_argument("inventory", type=Path)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--window", type=int, default=96)
    args = ap.parse_args()
    if not 16 <= args.window <= 256:
        raise SystemExit("window must be between 16 and 256 bytes")

    inventory = json.loads(args.inventory.read_text(encoding="utf-8"))
    samples = []
    missing_scenes = []
    for scene in inventory.get("scenes", []):
        path = args.scene_root / scene["file"]
        if not path.is_file():
            missing_scenes.append(scene["file"])
            continue
        raw = path.read_bytes()
        if len(raw) != scene.get("size") or hashlib.sha256(raw).hexdigest() != scene.get("sha256"):
            raise SystemExit(f"Scene changed since inventory: {scene['file']}")
        for table_index, table in enumerate(scene.get("candidate_offset_tables", [])):
            for target_index, target in enumerate(table.get("targets", [])):
                offset = target.get("offset")
                if not isinstance(offset, int) or offset < 0 or offset >= len(raw):
                    raise SystemExit(f"Out-of-range candidate offset in {scene['file']}")
                chunk = raw[offset:min(len(raw), offset + args.window)]
                strings = [m.group().decode("ascii", "replace") for m in PRINTABLE.finditer(chunk)]
                words = [struct.unpack_from("<I", chunk, pos)[0]
                         for pos in range(0, len(chunk) - 3, 4)]
                samples.append({
                    "scene": scene["file"],
                    "table_index": table_index,
                    "target_index": target_index,
                    "table_offset": table.get("table_offset"),
                    "record_offset": offset,
                    "sample_length": len(chunk),
                    "sample_hex": chunk.hex(),
                    "sample_sha256": hashlib.sha256(chunk).hexdigest(),
                    "ascii_runs": strings,
                    "u32_le_words": words,
                })

    if missing_scenes:
        raise SystemExit("Missing scene files: " + ", ".join(missing_scenes))
    if not samples:
        raise SystemExit("No candidate records were sampled")

    hashes = Counter(item["sample_sha256"] for item in samples)
    report = {
        "format": "RCCB bounded candidate record samples; no semantic decoding",
        "scene_count": len(inventory.get("scenes", [])),
        "sample_count": len(samples),
        "window_bytes": args.window,
        "unique_sample_hashes": len(hashes),
        "repeated_sample_hashes": sum(1 for count in hashes.values() if count > 1),
        "samples": samples,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "samples"}, indent=2))


if __name__ == "__main__":
    main()
