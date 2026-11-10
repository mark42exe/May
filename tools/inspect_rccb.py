#!/usr/bin/env python3
"""Structural inventory for Robot Fight's proprietary RCCB scene files.

This is deliberately a diagnostic parser, not a CCBI decoder. It preserves byte
offsets and extracts printable UTF-8/ASCII runs so field boundaries can be
correlated across scenes without pretending the proprietary record grammar is
known.
"""
from __future__ import annotations

import argparse
import json
import re
import struct
from collections import Counter
from pathlib import Path

PRINTABLE = re.compile(rb"[\x20-\x7e]{4,}")
NODE_TYPES = {
    "CCNode", "CCSprite", "CCSprite9Slice", "CCLabelTTF", "CCLabelBMFont",
    "CCButton", "DCNode", "DCLabel", "DCLabelTTF", "DCSprite",
    "DCUIButton", "DCUIControl",
}


def inspect(path: Path) -> dict:
    data = path.read_bytes()
    strings = []
    for match in PRINTABLE.finditer(data):
        value = match.group().decode("ascii", "replace")
        strings.append({"offset": match.start(), "value": value})
    types = [s["value"] for s in strings if s["value"] in NODE_TYPES]
    resources = [s["value"] for s in strings if s["value"].lower().endswith(
        (".webp", ".png", ".jpg", ".jpeg", ".ttf", ".fnt", ".plist", ".json")
    )]
    names = [
        s for s in strings
        if s["value"] not in NODE_TYPES
        and not s["value"].lower().endswith((".webp", ".png", ".jpg", ".jpeg", ".ttf", ".fnt", ".plist", ".json"))
        and re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{2,}", s["value"])
    ]
    return {
        "file": path.name,
        "size": len(data),
        "magic": data[4:8].decode("ascii", "replace") if len(data) >= 8 else "",
        "prefix_u32": struct.unpack_from("<I", data, 0)[0] if len(data) >= 4 else None,
        "header_u16": list(struct.unpack_from("<4H", data, 8)) if len(data) >= 16 else [],
        "node_type_counts": dict(Counter(types)),
        "resource_references": resources,
        "identifier_candidates": names,
        "strings": strings,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("root", type=Path, help="directory containing .ccb files")
    ap.add_argument("--output", type=Path, help="write JSON report (default: stdout)")
    args = ap.parse_args()
    files = sorted(args.root.rglob("*.ccb"))
    scenes = [inspect(p) for p in files]
    report = {
        "format": "RCCB diagnostic inventory; not a decoded scene graph",
        "scene_count": len(scenes),
        "magic_counts": dict(Counter(s["magic"] for s in scenes)),
        "scenes": scenes,
    }
    rendered = json.dumps(report, indent=2, ensure_ascii=False)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)


if __name__ == "__main__":
    main()
