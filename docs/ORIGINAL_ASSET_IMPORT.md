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

It converts WebP images to PNG for predictable Cocos image loading, preserves JSON/plist/CCB/animation/font data (including fictional weapon/equipment assets), writes an import manifest, and rejects unsafe archive paths or invalid DCA CRCs.

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


## Recovered game-data inventory

The verified resource payload contains 3,232 DCA directory records. The native build's converted resource tree currently contains 3,220 files:

| Resource type | Count |
|---|---:|
| PNG images (including converted WebP) | 2,819 |
| JSON part/stage/animation data | 179 |
| Proprietary RCCB scene files | 138 |
| Property lists | 68 |
| Skeletal animation files | 10 |
| Bitmap font descriptors | 3 |
| TrueType fonts | 2 |
| JPEG images | 1 |

The original part catalog contains 198 entries: 39 each for Head, Core, FrontArm, BackArm and Base, plus 3 batteries. Each robot-part JSON includes Box2D-style body fixtures and polygon vertices, as well as physical properties such as density and friction. The catalog includes part serials, star ratings, power points, attack/HP multipliers, thumbnails, and editor customization ranges.

Other recovered configuration:
- 6 stage definitions, including the versus-stage order and stage object/trap data.
- 13 named AI behaviour definitions.
- 40 condition chips and 56 action chips.
- 8 tutorial opponent robot builds.
- 148 quest identifiers plus quest definitions and achievement requirements.
- Loot-cycle, reward-pool, and loot-box configuration.
- Tutorial flow, language strings, colors, skins, preload lists, and sound-event mappings.
- 138 RCCB scene layouts, including battle HUD, main menu, editor, profile, stage selection, loot, tutorial, settings, and quest scenes.

## Restoration constraints

The RCCB files begin with a proprietary RCCB header and are not standard Cocos Creator/CCBReader files. They are retained intact as source references; the port must recreate their layouts and behaviour in native Cocos2d-x nodes.

The DCA resource archive does not include the OGG files named by SoundEvents.plist. Those sound references are catalogued, but the corresponding audio payloads still need to be recovered from an original package or separately supplied sound archive.

The recovered data is not the original proprietary C++ game source. Collision polygons, part stats, stage rules, AI chip definitions, and UI assets can be reused as data, but the runtime systems must be reimplemented and validated.
