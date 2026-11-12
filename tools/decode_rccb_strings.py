#!/usr/bin/env python3
"""Recover length-prefixed ASCII string tokens from RCCB scene binaries.

This is a validated string-layer decoder only. It does not decode node graphs,
property types, timelines, or runtime callbacks.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import struct
from pathlib import Path

MAX_STRING_BYTES = 512


def decode(path: Path) -> list[dict]:
    data = path.read_bytes()
    found = []
    # Verified across independent scenes: u32le byte length, exact printable
    # ASCII payload, and a NUL terminator.
    for payload in range(4, len(data) - 1):
        length = struct.unpack_from("<I", data, payload - 4)[0]
        if not 1 <= length <= MAX_STRING_BYTES:
            continue
        end = payload + length
        if end >= len(data) or data[end] != 0:
            continue
        raw = data[payload:end]
        if any(byte < 0x20 or byte > 0x7e for byte in raw):
            continue
        found.append({
            "length_offset": payload - 4,
            "payload_offset": payload,
            "byte_length": length,
            "value": raw.decode("ascii"),
            "nul_terminated": True,
        })
    return found


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("scene_root", type=Path)
    ap.add_argument("inventory", type=Path)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    inventory = json.loads(args.inventory.read_text(encoding="utf-8"))
    scenes, missing = [], []
    for entry in inventory.get("scenes", []):
        path = args.scene_root / entry["file"]
        if not path.is_file():
            missing.append(entry["file"])
            continue
        raw = path.read_bytes()
        if len(raw) != entry.get("size") or hashlib.sha256(raw).hexdigest() != entry.get("sha256"):
            raise SystemExit(f"Scene differs from verified inventory: {entry['file']}")
        tokens = decode(path)
        inventory_strings = {
            (item.get("offset"), item.get("value"))
            for item in entry.get("strings", [])
            if item.get("encoding") == "ascii"
        }
        decoded_strings = {(item["payload_offset"], item["value"]) for item in tokens}
        scenes.append({
            "file": entry["file"],
            "sha256": entry["sha256"],
            "token_count": len(tokens),
            "matched_inventory_strings": len(inventory_strings & decoded_strings),
            "unmatched_inventory_strings": len(inventory_strings - decoded_strings),
            "additional_decoded_strings": len(decoded_strings - inventory_strings),
            "tokens": tokens,
        })
    if missing:
        raise SystemExit("Missing scene files: " + ", ".join(missing))
    token_count = sum(scene["token_count"] for scene in scenes)
    matched = sum(scene["matched_inventory_strings"] for scene in scenes)
    unmatched = sum(scene["unmatched_inventory_strings"] for scene in scenes)
    additional = sum(scene["additional_decoded_strings"] for scene in scenes)
    report = {
        "format": "RCCB validated length-prefixed ASCII string layer",
        "encoding_rule": "u32le byte length + printable ASCII bytes + NUL",
        "scene_count": len(scenes),
        "token_count": token_count,
        "inventory_ascii_string_match_count": matched,
        "inventory_ascii_string_unmatched_count": unmatched,
        "additional_short_or_unindexed_string_count": additional,
        "max_string_bytes": MAX_STRING_BYTES,
        "scenes": scenes,
        "limitations": [
            "No node graph decoding",
            "No property type decoding",
            "No timeline decoding",
            "No runtime callback decoding",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({
        "scene_count": len(scenes),
        "token_count": token_count,
        "inventory_ascii_string_match_count": matched,
        "inventory_ascii_string_unmatched_count": unmatched,
        "additional_short_or_unindexed_string_count": additional,
        "max_string_bytes": MAX_STRING_BYTES,
    }, indent=2))


if __name__ == "__main__":
    main()
