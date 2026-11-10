# Toy Attack original asset integration

## Verified source archive

The recovered named asset archive contains 3,232 entries:
- 2,805 WebP images
- 25 PNG images
- 179 JSON files
- 138 proprietary RCCB scene files
- 68 plist files
- 10 skeleton/animation files, 3 bitmap fonts, 2 TrueType fonts, and other data

The native Cocos project does not yet contain this 33 MB archive. The importer is committed at `tools/import_robotfight_assets.py` and supports:
- the original Toy Attack APK (reads `assets/gamedata.dca`)
- a standalone `gamedata.dca`
- `RobotFight_full_named_assets.zip`

It converts WebP images to PNG for predictable Cocos image loading, preserves JSON/plist/CCB/animation/font data, writes an import manifest, and rejects unsafe archive paths or invalid DCA CRCs. Files whose names identify weapon assets are excluded from this import path.

## CI import location

Place one source file at one of these paths:
- `robotfight/original_assets/RobotFight_full_named_assets.zip`
- `robotfight/original_assets/toy_attack.apk`
- `robotfight/original_assets/gamedata.dca`

The ARM64 workflow automatically imports it into the generated Cocos `Resources/original/` directory. The source archive is deliberately not duplicated into Git history by this code change.

## Current renderer integration

The native arena scene now attempts to load original robot component images:
- `original/base_2_0.png`
- `original/core_1_0.png`
- `original/head_0_0.png`
- `original/arm_b_0_3.png`
- `original/arm_f_0_0.png`

When all five are present, the scene composes a temporary robot preview from original artwork. If any is missing, it falls back to the diagnostic silhouette. This is a component-art proof, not the original animated robot rig; the original JSON animation and RCCB node hierarchy still need reconstruction.

## Scene-format limitation

The 138 CCB files use the game-specific `RCCB` header, not standard CCBI. They remain preserved as data and must not be passed to stock Cocos `CCBReader` until a decoder has been validated against multiple scenes.
