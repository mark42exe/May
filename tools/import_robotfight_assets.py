#!/usr/bin/env python3
"""Import Toy Attack's named DCA resources or original APK into Cocos Resources.

WebP files are converted to PNG for predictable Cocos2d-x image decoding.
Proprietary RCCB scenes are preserved as data; this tool does not claim to decode them.
"""
from __future__ import annotations
import argparse, hashlib, json, os, pathlib, shutil, struct, tempfile, zipfile, zlib
from PIL import Image

def safe_target(root: pathlib.Path, name: str) -> pathlib.Path:
    name = name.replace("\\", "/")
    parts = [p for p in name.split("/") if p not in ("", ".")]
    if not parts or name.startswith("/") or ".." in parts:
        raise ValueError(f"Unsafe archive path: {name!r}")
    target = root.joinpath(*parts)
    target.parent.mkdir(parents=True, exist_ok=True)
    return target

def write_unique(root: pathlib.Path, name: str, payload: bytes) -> pathlib.Path:
    target = safe_target(root, name)
    if target.exists():
        raise ValueError(f"Duplicate archive path: {name!r}")
    target.write_bytes(payload)
    return target


def is_junk_metadata(rel: pathlib.Path) -> bool:
    ignored = {".DS_Store", "Thumbs.db", "desktop.ini"}
    return any(part in ignored or part == "__MACOSX" or part.startswith("._")
               for part in rel.parts)

def extract_dca(data: bytes, out: pathlib.Path) -> int:
    if data[:4] != b"DCA\0":
        raise ValueError("Input is not a DCA archive")
    if len(data) < 28:
        raise ValueError("Truncated DCA header")
    version, flags, records_offset, records_bytes, strings_offset, strings_bytes = struct.unpack_from("<6I", data, 4)
    records_end = records_offset + records_bytes
    strings_end = strings_offset + strings_bytes
    if (records_offset < 28 or strings_offset < 28 or records_bytes % 8 or
            records_end < records_offset or records_end > len(data) or
            strings_end < strings_offset or strings_end > len(data)):
        raise ValueError("Invalid DCA directory bounds")
    if records_offset < strings_end and strings_offset < records_end:
        raise ValueError("DCA record and string tables overlap")
    table = data[strings_offset:strings_offset + strings_bytes]
    names, pos = {}, 0
    for raw in table.split(b"\0"):
        names[pos] = raw.decode("utf-8", "replace")
        pos += len(raw) + 1
    manifest = []
    for i in range(records_bytes // 8):
        name_offset, file_offset = struct.unpack_from("<II", data, records_offset + i * 8)
        if file_offset < 28 or file_offset + 12 > len(data):
            raise ValueError(f"Invalid DCA file offset at record {i}")
        name = names.get(name_offset)
        if name is None:
            raise ValueError(f"Unknown DCA name offset at record {i}")
        crc, codec, size = struct.unpack_from("<III", data, file_offset)
        payload_end = file_offset + 12 + size
        if payload_end < file_offset + 12 or payload_end > len(data):
            raise ValueError(f"DCA payload exceeds archive bounds: {name}")
        payload = data[file_offset + 12:payload_end]
        if len(payload) != size or (zlib.crc32(payload) & 0xffffffff) != crc:
            raise ValueError(f"DCA CRC/length mismatch: {name}")
        write_unique(out, name, payload)
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
        dca_name = next((name for name in (
            "assets/gamedata.dca",
            "assets/robotfight_original/gamedata.dca",
        ) if name in names), None)
        if dca_name:
            extract_dca(archive.read(dca_name), source)
            # SoundEvents.plist references audio stored beside the DCA, not inside it.
            # Preserve these original audio/font payloads so the native port can play them.
            prefix = "assets/robotfight_original/"
            for info in archive.infolist():
                if info.is_dir() or not info.filename.startswith(prefix):
                    continue
                relative = info.filename[len(prefix):]
                suffix = pathlib.PurePosixPath(relative).suffix.lower()
                if "/" in relative or suffix not in {".ogg", ".wav", ".m4a", ".mp3", ".ttf"}:
                    continue
                write_unique(source, relative, archive.read(info))
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
            write_unique(source, name, archive.read(info))
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
        counts = {"images_png": 0, "images_webp_converted": 0, "data_files": 0}
        imported = []
        for item in sorted(source.rglob("*")):
            if not item.is_file() or item.name == "_archive_manifest.json":
                continue
            rel = item.relative_to(source)
            if is_junk_metadata(rel):
                continue
            suffix = item.suffix.lower()
            dest_rel = rel.with_suffix(".png") if suffix == ".webp" else rel
            dest = args.output / dest_rel
            # Some original archives contain both foo.png and foo.webp. Keep the
            # PNG at the canonical Cocos path and preserve the converted WebP
            # separately instead of silently overwriting one original asset.
            if dest.exists():
                if suffix == ".webp":
                    dest_rel = dest_rel.with_name(dest_rel.stem + "__from_webp.png")
                    dest = args.output / dest_rel
                    if dest.exists():
                        raise ValueError(f"Repeated converted-image destination: {dest_rel}")
                else:
                    raise ValueError(f"Duplicate imported asset destination: {dest_rel}")
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
            imported.append({
                "path": dest_rel.as_posix(),
                "bytes": dest.stat().st_size,
                "sha256": hashlib.sha256(dest.read_bytes()).hexdigest(),
            })
        manifest = {"source": args.input.name, "imported_files": len(imported),
                    "counts": counts, "files": imported}
        (args.output / "original_asset_manifest.json").write_text(
            json.dumps(manifest, indent=2), encoding="utf-8")
        print(json.dumps({"imported_files": len(imported), **counts}, indent=2))
        if not imported:
            raise SystemExit("No original resources were imported")

if __name__ == "__main__":
    main()
