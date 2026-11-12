#!/usr/bin/env python3
"""Group unresolved RCCB references with exact numbered asset-family siblings.

This is an evidence report only. A sibling is not treated as an interchangeable
replacement: no files are copied, renamed, or rewritten.
"""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path, PurePosixPath

TOKEN_RE = re.compile(r"[a-z]+|[0-9]+", re.IGNORECASE)


def family_key(name: str) -> tuple[str, ...]:
    """Return the filename tokens before an optional trailing numeric variant."""
    stem = PurePosixPath(name).stem
    tokens = tuple(token.casefold() for token in TOKEN_RE.findall(stem))
    if tokens and tokens[-1].isdigit():
        tokens = tokens[:-1]
    return tokens


def index_asset_families(root: Path) -> dict[tuple[str, ...], list[str]]:
    families: dict[tuple[str, ...], list[str]] = defaultdict(list)
    for path in sorted(root.rglob("*")):
        if path.is_file() and not path.is_symlink():
            key = family_key(path.name)
            if key:
                families[key].append(path.relative_to(root).as_posix())
    return dict(families)


def build_report(root: Path, audit: dict) -> dict:
    missing = audit.get("missing_references")
    if not isinstance(missing, list):
        raise ValueError("Scene audit must contain a missing_references list")
    families = index_asset_families(root)
    records = []
    family_counts: Counter[str] = Counter()
    for item in missing:
        reference = item.get("reference")
        if not isinstance(reference, str) or not reference:
            continue
        key = family_key(reference)
        siblings = [
            candidate for candidate in families.get(key, [])
            if PurePosixPath(candidate).name.casefold() != PurePosixPath(reference).name.casefold()
        ]
        family_label = "_".join(key)
        if siblings:
            family_counts[family_label] += 1
        records.append({
            "reference": reference,
            "scene_count": item.get("scene_count", 0),
            "family_key": family_label,
            "existing_family_siblings": siblings,
            "sibling_count": len(siblings),
            "replacement_selected": False,
            "manual_visual_validation_required": bool(siblings),
        })
    return {
        "format": "RCCB missing asset exact numbered-family sibling audit",
        "missing_reference_count": len(records),
        "references_with_existing_family_siblings": sum(r["sibling_count"] > 0 for r in records),
        "references_without_existing_family_siblings": sum(r["sibling_count"] == 0 for r in records),
        "automatic_repairs": 0,
        "family_groups": [
            {"family_key": key, "missing_reference_count": count}
            for key, count in sorted(family_counts.items())
        ],
        "records": records,
        "warning": "Filename-family siblings are recovery clues, not approved replacements.",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("asset_root", type=Path)
    parser.add_argument("scene_audit", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if not args.asset_root.is_dir():
        raise SystemExit(f"Asset root does not exist: {args.asset_root}")
    audit = json.loads(args.scene_audit.read_text(encoding="utf-8"))
    report = build_report(args.asset_root, audit)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2) + chr(10), encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "records"}, indent=2))


if __name__ == "__main__":
    main()
