#!/usr/bin/env python3
"""Fail-fast preflight for imported and packaged Toy Attack assets."""
from __future__ import annotations

import argparse
import hashlib
import json
import plistlib
import struct
from pathlib import Path, PurePosixPath
from zipfile import BadZipFile, ZipFile

from PIL import Image

REQUIRED = (
    "RFBattleLayer.ccb", "RFMainLayer.ccb", "RFEditorLayer.ccb",
    "RFPartsData.plist", "RFQuestData.plist", "SoundEvents.plist",
    "Normal1.ogg", "bgm_scene_battleFight.wav", "sfx_btn_press.ogg",
)
STAGE_THUMBNAILS = (
    "scene_thumbnail_11.png", "scene_thumbnail_0.png",
    "scene_thumbnail_1.png", "scene_thumbnail_3.png",
    "scene_thumbnail_13.png", "scene_thumbnail_19.png",
)
NATIVE_LIBRARY = "lib/arm64-v8a/libMyGame.so"


def valid_relative_path(value: object) -> bool:
    if not isinstance(value, str) or not value or "\\" in value:
        return False
    parts = value.split("/")
    if any(part in ("", ".", "..") for part in parts):
        return False
    path = PurePosixPath(value)
    return not path.is_absolute() and ":" not in parts[0]


def sha256_stream(stream) -> str:
    digest = hashlib.sha256()
    while True:
        chunk = stream.read(1024 * 1024)
        if not chunk:
            break
        digest.update(chunk)
    return digest.hexdigest()


def verify_manifest_records(records: object, read_asset, label: str,
                            problems: list[str]) -> tuple[int, int]:
    if not isinstance(records, list):
        problems.append(f"{label}: manifest files is not a list")
        return 0, 0
    seen: set[str] = set()
    verified = total_bytes = 0
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            problems.append(f"{label}: malformed manifest record #{index}")
            continue
        rel = record.get("path")
        if not valid_relative_path(rel) or rel in seen:
            problems.append(f"{label}: unsafe or duplicate manifest path: {rel!r}")
            continue
        seen.add(rel)
        try:
            data_size, digest = read_asset(rel)
        except (FileNotFoundError, KeyError, OSError, BadZipFile) as exc:
            problems.append(f"{label}: missing/unreadable asset {rel}: {exc}")
            continue
        if data_size != record.get("bytes") or digest != record.get("sha256"):
            problems.append(f"{label}: integrity mismatch: {rel}")
            continue
        verified += 1
        total_bytes += data_size
    return verified, total_bytes


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    parser.add_argument("--minimum-files", type=int, default=3000)
    parser.add_argument("--apk", type=Path, help="also verify every manifest asset inside this APK")
    args = parser.parse_args()
    root = args.root
    problems: list[str] = []
    if not root.is_dir():
        raise SystemExit(f"Imported resource directory does not exist: {root}")

    manifest_path = root / "original_asset_manifest.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception as exc:
        manifest = {}
        problems.append(f"Asset manifest cannot be parsed: {exc}")
    if not isinstance(manifest, dict):
        manifest = {}
        problems.append("Asset manifest root is not an object")

    files = [p for p in root.rglob("*") if p.is_file()]
    if len(files) < args.minimum_files:
        problems.append(f"Only {len(files)} files imported; expected at least {args.minimum_files}")
    for name in REQUIRED + STAGE_THUMBNAILS:
        path = root / name
        if not path.is_file() or path.stat().st_size == 0:
            problems.append(f"Required original asset missing or empty: {name}")

    records = manifest.get("files", [])
    if not isinstance(records, list) or len(records) != manifest.get("imported_files"):
        problems.append("Asset manifest file list/count is inconsistent")

    def read_local(rel: str) -> tuple[int, str]:
        path = root.joinpath(*PurePosixPath(rel).parts)
        if path.is_symlink() or not path.is_file():
            raise FileNotFoundError(rel)
        return path.stat().st_size, sha256_stream(path.open("rb"))

    local_verified, local_bytes = verify_manifest_records(
        records, read_local, "local", problems
    )

    image_count = 0
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in (".png", ".webp"):
            continue
        image_count += 1
        try:
            with Image.open(path) as image:
                image.verify()
        except Exception as exc:
            problems.append(f"Unreadable image {path.relative_to(root)}: {exc}")

    plist_count = 0
    for name in ("RFPartsData.plist", "RFQuestData.plist", "SoundEvents.plist"):
        path = root / name
        if not path.is_file():
            continue
        try:
            with path.open("rb") as stream:
                value = plistlib.load(stream)
            if not isinstance(value, dict) or not value:
                problems.append(f"{name} has an empty or non-dictionary root")
            else:
                plist_count += 1
        except Exception as exc:
            problems.append(f"{name} cannot be parsed: {exc}")

    audio_checked = 0
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in (".ogg", ".wav", ".mp3", ".m4a"):
            continue
        with path.open("rb") as stream:
            data = stream.read(16)
        suffix = path.suffix.lower()
        valid = (
            (suffix == ".ogg" and data.startswith(b"OggS")) or
            (suffix == ".wav" and len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WAVE") or
            (suffix == ".mp3" and (data.startswith(b"ID3") or (len(data) >= 2 and data[0] == 0xFF and (data[1] & 0xE0) == 0xE0))) or
            (suffix == ".m4a" and len(data) >= 8 and data[4:8] == b"ftyp")
        )
        if not valid:
            problems.append(f"Audio file signature mismatch: {path.relative_to(root)}")
        else:
            audio_checked += 1

    packaged_verified = packaged_bytes = 0
    if args.apk:
        try:
            with ZipFile(args.apk) as apk:
                bad_member = apk.testzip()
                if bad_member:
                    problems.append(f"APK ZIP CRC failure: {bad_member}")
                package_manifest_name = "assets/original/original_asset_manifest.json"
                package_manifest = json.loads(apk.read(package_manifest_name))
                if package_manifest != manifest:
                    problems.append("Packaged asset manifest differs from preflight manifest")

                def read_packaged(rel: str) -> tuple[int, str]:
                    with apk.open("assets/original/" + rel) as stream:
                        size = 0
                        digest = hashlib.sha256()
                        while True:
                            chunk = stream.read(1024 * 1024)
                            if not chunk:
                                break
                            size += len(chunk)
                            digest.update(chunk)
                        return size, digest.hexdigest()

                packaged_verified, packaged_bytes = verify_manifest_records(
                    records, read_packaged, "APK", problems
                )
                native = apk.read(NATIVE_LIBRARY)
                if native[:4] != b"\x7fELF" or native[4] != 2 or native[5] != 1:
                    problems.append("APK native library is not ELF64 little-endian")
                elif struct.unpack_from("<H", native, 18)[0] != 183:
                    problems.append("APK native library is not AArch64")
                if "assets/original/RFBattleLayer.ccb" not in apk.namelist():
                    problems.append("APK is missing original RFBattleLayer.ccb")
        except Exception as exc:
            problems.append(f"APK package audit failed: {exc}")

    report = {
        "file_count": len(files),
        "manifest_imported_files": manifest.get("imported_files"),
        "manifest_entries_verified": local_verified,
        "manifest_bytes_verified": local_bytes,
        "packaged_manifest_entries_verified": packaged_verified,
        "packaged_bytes_verified": packaged_bytes,
        "audio_files_checked": audio_checked,
        "image_count_checked": image_count,
        "critical_plists_parsed": plist_count,
        "apk_checked": bool(args.apk),
        "passed": not problems,
        "problems": problems,
    }
    print(json.dumps(report, indent=2))
    if problems:
        raise SystemExit("IMPORTED RESOURCE PREFLIGHT FAILED")


if __name__ == "__main__":
    main()
