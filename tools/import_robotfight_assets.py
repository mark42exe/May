#!/usr/bin/env python3
"""Import Toy Attack's named DCA resources or original APK into Cocos Resources.

WebP files are converted to PNG for predictable Cocos2d-x image decoding.
Proprietary RCCB scenes are preserved as data; this tool does not claim to decode them.
"""
from __future__ import annotations
import argparse, json, os, pathlib, shutil, struct, tempfile, zipfile, zlib
from PIL import Image

def safe_target(root: pathlib.Path, name: str) -> pathlib.Path:
    name = name.replace("\\", "/")
    parts = [p for p in name.split("/") if p not in ("", ".")]
    if not parts or name.startswith("/") or ".." in parts:
        raise ValueError(f"Unsafe archive path: {name!r}")
    target = root.joinpath(*parts)
    target.parent.mkdir(parents=True, exist_ok=True)
    return target

def extract_dca(data: bytes, out: pathlib.Path) -> int:
    if data[:4] != b"DCA\0":
        raise ValueError("Input is not a DCA archive")
    version, flags, records_offset, records_bytes, strings_offset, strings_bytes = struct.unpack_from("<6I", data, 4)
    if records_bytes % 8 or strings_offset + strings_bytes > len(data):
        raise ValueError("Invalid DCA directory bounds")
    table = data[strings_offset:strings_offset + strings_bytes]
    names, pos = {}, 0
    for raw in table.split(b"\0"):
        names[pos] = raw.decode("utf-8", "replace")
        pos += len(raw) + 1
    manifest = []
    for i in range(records_bytes // 8):
        name_offset, file_offset = struct.unpack_from("<II", data, records_offset + i * 8)
        if file_offset + 12 > len(data):
            raise ValueError(f"Invalid DCA file offset at record {i}")
        name = names.get(name_offset)
        if name is None:
            raise ValueError(f"Unknown DCA name offset at record {i}")
        crc, codec, size = struct.unpack_from("<III", data, file_offset)
        payload = data[file_offset + 12:file_offset + 12 + size]
        if len(payload) != size or (zlib.crc32(payload) & 0xffffffff) != crc:
            raise ValueError(f"DCA CRC/length mismatch: {name}")
        safe_target(out, name).write_bytes(payload)
        manifest.append({"name": name, "codec": codec, "bytes": size, "crc32": f"{crc:08x}"})
    (out / "_archive_manifest.json").write_text(json.dumps({
        "version": version, "flags": flags, "count": len(manifest), "files": manifest
    }, indent=2), encoding="utf-8")
    return len(manifest)

def unpack_input(path: pathlib.Path, temp: pathlib.Path) -> pathlib.Path:
    data = path.read_bytes()
    source = temp / "source"
    source.mkdir(parents=True, exist_ok=True)
    if data[:4] == b"DCA\0":
        extract_dca(data, source)
        return source
    if not zipfile.is_zipfile(path):
        raise ValueError("Input must be a Toy Attack APK, DCA archive, or named-assets ZIP")
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        if "assets/gamedata.dca" in names:
            extract_dca(archive.read("assets/gamedata.dca"), source)
            return source
        # Named asset bundle: flatten its single enclosing folder but keep subdirectories.
        for info in archive.infolist():
            if info.is_dir():
                continue
            name = info.filename.replace("\\", "/")
            if "/" in name:
                name = name.split("/", 1)[1]
            if not name:
                continue
            safe_target(source, name).write_bytes(archive.read(info))
    return source

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, type=pathlib.Path,
                    help="original APK, gamedata.dca, or RobotFight_full_named_assets.zip")
    ap.add_argument("--output", required=True, type=pathlib.Path)
    args = ap.parse_args()
    if not args.input.is_file():
        raise SystemExit(f"Input asset archive not found: {args.input}")
    args.output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="toy-attack-assets-") as td:
        source = unpack_input(args.input, pathlib.Path(td))
        counts = {"images_png": 0, "images_webp_converted": 0, "data_files": 0, "excluded_weapon_files": 0}
        imported = []
        for item in sorted(source.rglob("*")):
            if not item.is_file() or item.name == "_archive_manifest.json":
                continue
            rel = item.relative_to(source)
            if "weapon" in item.stem.lower():
                counts["excluded_weapon_files"] += 1
                continue
            suffix = item.suffix.lower()
            dest_rel = rel.with_suffix(".png") if suffix == ".webp" else rel
            dest = args.output / dest_rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            if suffix == ".webp":
                with Image.open(item) as im:
                    im.convert("RGBA").save(dest, format="PNG", optimize=True)
                counts["images_webp_converted"] += 1
            else:
                shutil.copy2(item, dest)
                if suffix == ".png":
                    counts["images_png"] += 1
                else:
                    counts["data_files"] += 1
            imported.append(dest_rel.as_posix())
        manifest = {"source": args.input.name, "imported_files": len(imported),
                    "counts": counts, "files": imported}
        (args.output / "original_asset_manifest.json").write_text(
            json.dumps(manifest, indent=2), encoding="utf-8")
        print(json.dumps({"imported_files": len(imported), **counts}, indent=2))
        if not imported:
            raise SystemExit("No original resources were imported")

if __name__ == "__main__":
    main()
