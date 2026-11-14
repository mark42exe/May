#!/usr/bin/env python3
"""Structural inventory for Robot Fight's proprietary RCCB scene files.

This is deliberately a diagnostic parser, not a CCBI decoder. It preserves byte
offsets and extracts printable UTF-8/ASCII runs so field boundaries can be
correlated across scenes without pretending the proprietary record grammar is
known.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import struct
from collections import Counter
from pathlib import Path

PRINTABLE = re.compile(rb"[\x20-\x7e]{4,}")
PRINTABLE_UTF16LE = re.compile(rb"(?:[\x20-\x7e]\x00){4,}")
NODE_TYPES = {
    "CCNode", "CCSprite", "CCSprite9Slice", "CCLabelTTF", "CCLabelBMFont",
    "CCButton", "DCNode", "DCLabel", "DCLabelTTF", "DCSprite",
    "DCUIButton", "DCUIControl",
}



def find_offset_tables(data: bytes) -> list[dict]:
    """Find candidate descending offset arrays without assigning field semantics.

    RCCB samples contain aligned u32 arrays whose entries point into scene
    records. A candidate is reported only when the complete array is in bounds
    and offsets are strictly descending. This is not a complete scene decoder.
    """
    candidates = []
    for pos in range(0x50, len(data) - 16, 4):
        count = struct.unpack_from("<I", data, pos)[0]
        if not 3 <= count <= 256:
            continue
        end = pos + 4 + count * 4
        if end > len(data):
            continue
        offsets = list(struct.unpack_from(f"<{count}I", data, pos + 4))
        if offsets[-1] not in (4, 20, 28):
            continue
        if offsets[0] <= end or any(value >= len(data) for value in offsets[:-1]):
            continue
        if not all(offsets[i] > offsets[i + 1] for i in range(count - 1)):
            continue
        targets = []
        for offset in offsets[:-1]:
            sample = data[offset:offset + 96]
            strings = [
                match.group().decode("ascii", "replace")
                for match in PRINTABLE.finditer(sample)
            ]
            targets.append({"offset": offset, "strings_near_target": strings[:4]})
        candidates.append({
            "table_offset": pos,
            "entry_count": count,
            "sentinel": offsets[-1],
            "offsets": offsets,
            "targets": targets,
        })
    return candidates


def inspect(path: Path) -> dict:
    data = path.read_bytes()
    strings = []
    for match in PRINTABLE.finditer(data):
        value = match.group().decode("ascii", "replace")
        strings.append({"offset": match.start(), "value": value, "encoding": "ascii"})
    # RCCB resources can store Cocos strings as narrow ASCII or UTF-16LE.
    # Preserve byte offsets so strings can be correlated with binary records.
    for match in PRINTABLE_UTF16LE.finditer(data):
        value = match.group().decode("utf-16le", "replace")
        strings.append({"offset": match.start(), "value": value, "encoding": "utf-16le"})
    strings.sort(key=lambda item: (item["offset"], item["encoding"]))
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
        "relative_path": str(path),
        "size": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
        "magic": data[4:8].decode("ascii", "replace") if len(data) >= 8 else "",
        "prefix_u32": struct.unpack_from("<I", data, 0)[0] if len(data) >= 4 else None,
        "header_u16": list(struct.unpack_from("<6H", data, 8)) if len(data) >= 20 else [],
        # Preserve the fixed prefix as raw values only. These words are
        # cross-scene invariants, not assigned version/property semantics.
        "header_prefix_words_u32": list(struct.unpack_from("<4I", data, 0)) if len(data) >= 16 else [],
        "header_prefix_words_u16_offset8": list(struct.unpack_from("<6H", data, 8)) if len(data) >= 20 else [],
        "header_prefix_words_u32_offset20": list(struct.unpack_from("<4I", data, 20)) if len(data) >= 36 else [],
        "node_type_counts": dict(Counter(types)),
        "resource_references": resources,
        "identifier_candidates": names,
        "strings": strings,
        "string_encoding_counts": dict(Counter(item["encoding"] for item in strings)),
        "candidate_offset_tables": find_offset_tables(data),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("root", type=Path, help="directory containing .ccb files")
    ap.add_argument("--output", type=Path, help="write JSON report (default: stdout)")
    args = ap.parse_args()
    files = sorted(args.root.rglob("*.ccb"))
    scenes = [inspect(p) for p in files]
    resource_usage = Counter(
        resource for scene in scenes for resource in scene["resource_references"]
    )
    node_type_totals = Counter()
    for scene in scenes:
        node_type_totals.update(scene["node_type_counts"])
    duplicate_hashes = {}
    for scene in scenes:
        duplicate_hashes.setdefault(scene["sha256"], []).append(scene["file"])
    duplicate_hashes = {
        digest: names for digest, names in duplicate_hashes.items() if len(names) > 1
    }
    # Cross-scene indexes expose reusable original resources and identifiers.
    # These relationships help map scene families without guessing the binary schema.
    resource_to_scenes = {}
    identifier_to_scenes = {}
    for scene in scenes:
        for resource in set(scene["resource_references"]):
            resource_to_scenes.setdefault(resource, []).append(scene["file"])
        # Candidates are structured records, not hashable strings.
        # Index semantic value + encoding; ignore repeated offsets within a scene.
        identifiers = set()
        for candidate in scene["identifier_candidates"]:
            if isinstance(candidate, dict):
                value = candidate.get("value")
                encoding = candidate.get("encoding", "unknown")
                if isinstance(value, str) and value:
                    identifiers.add(f"{encoding}:{value}")
            elif isinstance(candidate, str) and candidate:
                identifiers.add(candidate)
        for identifier in identifiers:
            identifier_to_scenes.setdefault(identifier, []).append(scene["file"])
    shared_resources = {
        key: value for key, value in sorted(resource_to_scenes.items())
        if len(value) > 1
    }
    shared_identifiers = {
        key: value for key, value in sorted(identifier_to_scenes.items())
        if len(value) > 1
    }
    report = {
        "format": "RCCB diagnostic inventory with cross-scene index; not a decoded scene graph",
        "scene_count": len(scenes),
        "unique_resource_reference_count": len(resource_to_scenes),
        "shared_resource_references": shared_resources,
        "shared_identifier_candidates": shared_identifiers,
        "total_scene_bytes": sum(scene["size"] for scene in scenes),
        "magic_counts": dict(Counter(s["magic"] for s in scenes)),
        "aggregate_node_type_counts": dict(node_type_totals.most_common()),
        "most_referenced_resources": [
            {"resource": name, "scene_reference_count": count}
            for name, count in resource_usage.most_common(200)
        ],
        "duplicate_scene_contents": duplicate_hashes,
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
