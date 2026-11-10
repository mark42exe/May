#!/usr/bin/env python3
from pathlib import Path
import json, struct, sys, zlib
if len(sys.argv) != 3: raise SystemExit("usage: extract_robotfight_dca.py gamedata.dca output_dir")
src, out = Path(sys.argv[1]), Path(sys.argv[2])
data = src.read_bytes()
if data[:4] != b"DCA\0": raise SystemExit("invalid DCA magic: " + repr(data[:8]))
version, flags, records_offset, records_bytes, strings_offset, strings_bytes = struct.unpack_from("<6I", data, 4)
table = data[strings_offset:strings_offset + strings_bytes]
names, pos = {}, 0
for raw in table.split(b"\0"):
    names[pos] = raw.decode("utf-8", "replace")
    pos += len(raw) + 1
out.mkdir(parents=True, exist_ok=True)
manifest = []
for i in range(records_bytes // 8):
    name_offset, file_offset = struct.unpack_from("<II", data, records_offset + i * 8)
    name = names.get(name_offset)
    if name is None: raise ValueError("unknown DCA name offset")
    name = name.replace("\\", "/")
    parts = [p for p in name.split("/") if p not in ("", ".")]
    if not parts or name.startswith("/") or ".." in parts: raise ValueError("unsafe archive path")
    crc, codec, size = struct.unpack_from("<III", data, file_offset)
    payload = data[file_offset + 12:file_offset + 12 + size]
    if len(payload) != size or (zlib.crc32(payload) & 0xffffffff) != crc: raise ValueError("CRC mismatch: " + name)
    target = out.joinpath(*parts)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(payload)
    manifest.append({"name": name, "codec": codec, "bytes": size, "crc32": f"{crc:08x}"})
(out / "_archive_manifest.json").write_text(json.dumps({"version": version, "flags": flags, "count": len(manifest), "files": manifest}, indent=2))
print("Extracted and CRC-verified", len(manifest), "original resources")
