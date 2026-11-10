#!/usr/bin/env python3
"""Inventory recovered Robot Fight / Toy Attack resources for native Cocos import."""
from pathlib import Path
import argparse, json, plistlib, struct, collections

def image_info(path):
    data = path.read_bytes()
    b = data[:32]
    if b[:4] == b"RIFF" and b[8:12] == b"WEBP":
        kind = b[12:16]
        result = {"format": "webp", "encoding": kind.decode("ascii", "replace")}
        # VP8X stores 24-bit minus-one dimensions at fixed offsets.
        if kind == b"VP8X" and len(b) >= 30:
            result.update(width=1 + int.from_bytes(b[24:27], "little"),
                          height=1 + int.from_bytes(b[27:30], "little"))
        # VP8L stores dimensions in the packed 4-byte image header.
        elif kind == b"VP8L" and len(data) >= 25 and data[20] == 0x2f:
            bits = int.from_bytes(data[21:25], "little")
            result.update(width=(bits & 0x3fff) + 1,
                          height=((bits >> 14) & 0x3fff) + 1)
        # Lossy VP8 frame header contains a start code and 14-bit dimensions.
        elif kind == b"VP8 " and len(data) >= 30 and data[23:26] == b"\x9d\x01\x2a":
            result.update(width=int.from_bytes(data[26:28], "little") & 0x3fff,
                          height=int.from_bytes(data[28:30], "little") & 0x3fff)
        return result
    if b[:8] == b"\x89PNG\r\n\x1a\n" and len(b) >= 24:
        return {"format": "png", "width": struct.unpack(">I", b[16:20])[0],
                "height": struct.unpack(">I", b[20:24])[0]}
    return {}

def ccb_info(path):
    data = path.read_bytes()
    result = {"ccb_signature_hex": data[:8].hex()}
    if data.startswith(b"ccbi"):
        result["ccb_container"] = "CCBI"
        if len(data) > 4:
            result["ccb_version_byte"] = data[4]
    elif data.startswith(b"bplist00"):
        result["ccb_container"] = "binary-plist"
    elif data.lstrip().startswith(b"<?xml"):
        result["ccb_container"] = "xml-plist"
    else:
        result["ccb_container"] = "unknown-binary-or-custom"
    return result

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("root", type=Path)
    ap.add_argument("--out", type=Path, default=None)
    a = ap.parse_args()
    root = a.root
    files = [p for p in root.rglob("*") if p.is_file() and p.name != "_archive_manifest.json"]
    counts = collections.Counter()
    records = []
    ccb = collections.Counter()
    plist_ok = json_ok = 0
    for p in sorted(files):
        rel = p.relative_to(root).as_posix()
        ext = p.suffix.lower() or "<none>"
        counts[ext] += 1
        rec = {"path": rel, "bytes": p.stat().st_size, "type": ext}
        if ext in (".webp", ".png"):
            rec.update(image_info(p))
        if ext == ".ccb":
            rec.update(ccb_info(p))
            ccb[rec["ccb_container"]] += 1
        if ext == ".plist":
            try:
                obj = plistlib.loads(p.read_bytes())
                plist_ok += 1
                if isinstance(obj, dict):
                    rec["plist_root_keys"] = sorted(str(k) for k in obj.keys())[:80]
            except Exception as e:
                rec["plist_parse_error"] = str(e)[:180]
        if ext == ".json":
            try:
                obj = json.loads(p.read_text(encoding="utf-8"))
                json_ok += 1
                rec["json_root_type"] = type(obj).__name__
                if isinstance(obj, dict):
                    rec["json_root_keys"] = sorted(str(k) for k in obj.keys())[:80]
            except Exception as e:
                rec["json_parse_error"] = str(e)[:180]
        records.append(rec)
    archive = {}
    mf = root / "_archive_manifest.json"
    if mf.exists():
        try:
            archive = json.loads(mf.read_text(encoding="utf-8"))
        except Exception:
            pass
    report = {
        "resource_root": str(root),
        "total_files": len(files),
        "extension_counts": dict(sorted(counts.items())),
        "parsed_plist_files": plist_ok,
        "parsed_json_files": json_ok,
        "ccb_container_counts": dict(ccb),
        "archive_manifest_count": archive.get("count"),
        "files": records,
    }
    out = a.out or root.parent / "robotfight_asset_inventory.json"
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print("Resource files:", len(files))
    print("Extensions:", dict(counts))
    print("Parsed plist:", plist_ok, "Parsed JSON:", json_ok)
    print("CCB containers:", dict(ccb))
    print("Inventory:", out)

if __name__ == "__main__":
    main()
