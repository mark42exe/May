#!/usr/bin/env python3
"""Create a deterministic integrity manifest for imported original game assets.

The manifest records exact relative paths, byte sizes and SHA-256 digests. It
never rewrites, renames, converts or substitutes source assets.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path


def build_manifest(root: Path, output: Path) -> dict:
    root = root.resolve()
    output = output.resolve()
    if not root.is_dir():
        raise ValueError(f"asset root is not a directory: {root}")

    entries = []
    folded_paths: dict[str, str] = {}
    extension_counts: Counter[str] = Counter()
    total_bytes = 0

    for path in sorted(root.rglob("*"), key=lambda item: item.as_posix().casefold()):
        if path.is_symlink():
            raise ValueError(f"symlink is not allowed in asset tree: {path}")
        if not path.is_file() or path.resolve() == output:
            continue
        relative = path.relative_to(root).as_posix()
        folded = relative.casefold()
        previous = folded_paths.get(folded)
        if previous is not None and previous != relative:
            raise ValueError(f"case-insensitive path collision: {previous} / {relative}")
        folded_paths[folded] = relative

        digest = hashlib.sha256()
        size = 0
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                size += len(chunk)
                digest.update(chunk)
        extension = path.suffix.lower() or "[no extension]"
        extension_counts[extension] += 1
        total_bytes += size
        entries.append({
            "path": relative,
            "size": size,
            "sha256": digest.hexdigest(),
        })

    return {
        "format": "toy-attack-original-assets-integrity-v1",
        "asset_root": ".",
        "file_count": len(entries),
        "total_bytes": total_bytes,
        "extension_counts": dict(sorted(extension_counts.items())),
        "files": entries,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("asset_root", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = build_manifest(args.asset_root, args.output)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n",
                           encoding="utf-8")
    print(json.dumps({key: value for key, value in report.items() if key != "files"},
                     indent=2))


if __name__ == "__main__":
    main()
