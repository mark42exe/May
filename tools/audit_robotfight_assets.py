#!/usr/bin/env python3
"""Inventory recovered Robot Fight / Toy Attack resources for native Cocos import."""
from pathlib import Path
import argparse, json, plistlib, struct, collections

def image_info(path):
    b = path.read_bytes()[:32]
    if b[:4] == b"RIFF" and b[8:12] == b"WEBP":
        kind = b[12:16]
        if kind == b"VP8X" and len(b) >= 30:
            w = 1 + int.from_bytes(b[24:27], "little")
            h = 1 + int.from_bytes(b[27:30], "little")
            return {"format":"webp","width":w,"height":h,"encoding":kind.decode("ascii")}
        return {"format":"webp","encoding":kind.decode("ascii", "replace")}
    if b[:8] == b"\x89PNG\r\n\x1a\n" and len(b) >= 24:
        return {"format":"png","width":struct.unpack(">I",b[16:20])[0],"height":struct.unpack(">I",b[20:24])[0]}
    return {}

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("root", type=Path)
    ap.add_argument("--out", type=Path, default=None)
    a=ap.parse_args()
    root=a.root
    files=[p for p in root.rglob("*") if p.is_file() and p.name != "_archive_manifest.json"]
    counts=collections.Counter()
    records=[]
    ccb=collections.Counter()
    plist_ok=0
    json_ok=0
    atlas_refs=set()
    for p in sorted(files):
        rel=p.relative_to(root).as_posix()
        ext=p.suffix.lower() or "<none>"
        counts[ext]+=1
        rec={"path":rel,"bytes":p.stat().st_size,"type":ext}
        if ext in (".webp",".png"):
            rec.update(image_info(p))
        if ext in (".plist",".ccb"):
            try:
                obj=plistlib.loads(p.read_bytes())
                plist_ok+=1
                if isinstance(obj,dict):
                    rec["plist_root_keys"]=sorted(str(k) for k in obj.keys())[:80]
                    if ext==".ccb":
                        rec["ccb_file_type"]=obj.get("fileType")
                        rec["ccb_file_version"]=obj.get("fileVersion")
                        rec["ccb_stage"]=[obj.get("stageWidth"),obj.get("stageHeight")]
                        rec["ccb_export_plugin"]=obj.get("exportPlugIn")
                        ccb[str(obj.get("fileType","untyped"))]+=1
            except Exception as e:
                rec["plist_parse_error"]=str(e)[:180]
        if ext==".json":
            try:
                obj=json.loads(p.read_text(encoding="utf-8"))
                json_ok+=1
                rec["json_root_type"]=type(obj).__name__
                if isinstance(obj,dict):
                    rec["json_root_keys"]=sorted(str(k) for k in obj.keys())[:80]
            except Exception as e:
                rec["json_parse_error"]=str(e)[:180]
        records.append(rec)
    archive={}
    mf=root/"_archive_manifest.json"
    if mf.exists():
        try:
            archive=json.loads(mf.read_text(encoding="utf-8"))
        except Exception:
            pass
    report={
        "resource_root":str(root),
        "total_files":len(files),
        "extension_counts":dict(sorted(counts.items())),
        "parsed_plist_files":plist_ok,
        "parsed_json_files":json_ok,
        "ccb_file_type_counts":dict(ccb),
        "archive_manifest_count":archive.get("count"),
        "files":records
    }
    out=a.out or root.parent/"robotfight_asset_inventory.json"
    out.write_text(json.dumps(report,indent=2),encoding="utf-8")
    print("Resource files:",len(files))
    print("Extensions:",dict(counts))
    print("Parsed plist/CCB:",plist_ok,"Parsed JSON:",json_ok)
    print("CCB fileType values:",dict(ccb))
    print("Inventory:",out)
if __name__=="__main__":
    main()
