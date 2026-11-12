#!/usr/bin/env python3
"""Suggest exact-file candidates for unresolved RCCB scene references.

This is deliberately a report-only tool: a basename match is not proof that an
asset is interchangeable, so it never copies, renames, or silently resolves
missing dependencies. Review the generated candidates before changing assets.
"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path, PurePosixPath

IMAGE_FALLBACKS = {
    ".webp": (".png",),
    ".png": (".webp",),
}


def build_index(root: Path) -> dict[str, list[str]]:
    index: dict[str, list[str]] = defaultdict(list)
    for path in sorted(root.rglob("*")):
        if path.is_file() and not path.is_symlink():
            index[path.name.casefold()].append(path.relative_to(root).as_posix())
    return dict(index)


def candidates_for(reference: str, index: dict[str, list[str]]) -> list[str]:
    ref = PurePosixPath(reference)
    names = [ref.name]
    names.extend(ref.stem + suffix for suffix in IMAGE_FALLBACKS.get(ref.suffix.lower(), ()))
    matches: list[str] = []
    for name in names:
        matches.extend(index.get(name.casefold(), []))
    return sorted(set(matches))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("asset_root", type=Path)
    parser.add_argument("scene_audit", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--source-manifest", type=Path,
                        help="original DCA manifest from the source APK; distinguishes absent source assets from import losses")
    args = parser.parse_args()

    root = args.asset_root.resolve()
    if not root.is_dir():
        raise SystemExit(f"Asset root does not exist: {root}")
    audit = json.loads(args.scene_audit.read_text(encoding="utf-8"))
    missing = audit.get("missing_references")
    if not isinstance(missing, list):
        raise SystemExit("Scene audit has no missing_references list")

    index = build_index(root)
    source_names: set[str] | None = None
    if args.source_manifest:
        source_manifest = json.loads(args.source_manifest.read_text(encoding="utf-8"))
        source_files = source_manifest.get("files")
        if not isinstance(source_files, list):
            raise SystemExit("Source archive manifest has no files list")
        source_names = {
            PurePosixPath(record["name"]).name.casefold()
            for record in source_files
            if isinstance(record, dict) and isinstance(record.get("name"), str)
        }
    records = []
    for item in missing:
        reference = item.get("reference", "")
        if not isinstance(reference, str) or not reference:
            continue
        matches = candidates_for(reference, index)
        records.append({
            "reference": reference,
            "scene_count": item.get("scene_count", 0),
            "status": ("unique_basename_candidate" if len(matches) == 1 else
                       "ambiguous_basename_candidates" if matches else
                       "no_candidate_found"),
            "candidates": matches,
            "source_archive_present": (None if source_names is None else
                                       PurePosixPath(reference).name.casefold() in source_names),
            "requires_manual_validation": bool(matches),
        })

    report = {
        "asset_root": str(root),
        "missing_reference_count": len(records),
        "unique_candidate_count": sum(r["status"] == "unique_basename_candidate" for r in records),
        "ambiguous_candidate_count": sum(r["status"] == "ambiguous_basename_candidates" for r in records),
        "no_candidate_count": sum(r["status"] == "no_candidate_found" for r in records),
        "automatic_repairs": 0,
        "source_manifest_checked": source_names is not None,
        "source_archive_present_count": sum(r["source_archive_present"] is True for r in records),
        "source_archive_absent_count": sum(r["source_archive_present"] is False for r in records),
        "records": records,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2) + chr(10), encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "records"}, indent=2))


if __name__ == "__main__":
    main()
