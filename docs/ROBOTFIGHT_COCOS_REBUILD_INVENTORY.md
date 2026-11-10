# Robot Fight offline ARM64 rebuild — engine and asset inventory

## Confirmed project state

- Repository: `mark42exe/May`, branch `main`.
- Existing workflow: `.github/workflows/robotfight-arm64.yml`.
- Latest verified workflow run at the time of this note: `42780687384` (success).
- Output artifact: `RobotFight-ARM64-debug`, 68,579,607 bytes, SHA-256 `e9b07873d8de56743157bf5047ce177b08d3cd58e99cdc953b01be6f24fc44be`.
- Existing workflow builds a WebView wrapper around `robotfight/android/index.html`; it does not currently compile Cocos2d-x or execute the original game code.
- The DCA extraction script verifies each payload CRC and extracted 3,232 resources in the prior verified run.

## Engine research

- Official Cocos2d-x download archive lists 3.16 (2017) and 3.17.2 (2019).
- Official 3.16 release notes explicitly document Android ARM64 third-party libraries and the `cocos run -p android --app-abi arm64-v8a` target.
- 3.17.2 documentation records Android testing with NDK r19c and Python 2.7.5+, which makes it a less convenient first candidate for a modern GitHub Actions image.
- The original APK's `libcocos2dcpp.so` was inspected and its strings identify **Cocos2d-x 3.15.1**. Treat 3.15.1 as the compatibility target, not v4 or 3.16.
- Cocos2d-x 3.13 introduced Android `arm64-v8a` support; the official Cocos release history documents that 64-bit third-party libraries were provided from that line onward. Therefore 3.15.1 is already from a 64-bit-capable engine line. Rebuild the matching engine and its third-party dependencies for ARM64, then port the game's custom native layer.
- The current workflow's Cocos2d-x v4 download is a temporary test scaffold and is not the correct engine target. Do not treat its output as a port of the original game.

## Recovered game data

- DCA archive inventory from the prior extraction: 3,232 resources, CRC-verified.
- Approximate types recorded: 2,805 WebP, 25 PNG, 178 JSON, 138 CCB, 68 plist, plus other files.
- Local data files identified: tutor bot roster, AI chip definitions, stage definitions, and robot parts catalog.
- The current WebView prototype uses recovered part sprites, but assembles them with approximate placement; it does not yet reproduce the original Cocos scene graph, animation timelines, or combat logic.
- The CCB files must be inspected to establish whether they are CocosBuilder source files, compiled CCBI, or a game-specific variation. Do not assume they can be loaded directly without the matching reader and node-loader classes.

## Required next engineering stages

1. Extract and catalogue every DCA path, dimensions, plist frame references, atlas image references, CCB header/format, and JSON/plist schema.
2. Pin and fetch Cocos2d-x 3.15.1 source in CI; verify the Android ARM64 engine and third-party dependencies compile from source with a compatible NDK/toolchain.
3. Recreate the original Android project around Cocos2d-x 3.15.1 and target `arm64-v8a`; preserve the original engine API and binary/resource expectations rather than using v4 or relabelling ARM32 libraries.
4. Reconstruct the original screens using recovered atlas frames, plist metadata, fonts, and CCB scene data wherever compatible.
5. Reimplement offline bot selection, combat state, progression, local profile persistence, and the victory-only +2,000 coin reward.
6. Add automated checks for ARM64 ELF libraries, asset manifest completeness, offline/no-network behavior, save persistence, and reward idempotency.
7. Keep the current WebView APK as a playable reference build until the native Cocos version passes device testing.

## Important constraints

- The original proprietary C++ game source has not been recovered. The original engine version is identified as Cocos2d-x 3.15.1, but the game-specific native code still has to be reconstructed or reimplemented.
- Original ARM32 shared libraries cannot be made ARM64 by renaming or changing APK metadata.
- The current APK is a prototype/reference, not a complete restoration.
- Preserve the recovered source assets and document their original paths; do not replace them with generated placeholder art.


## Video reference review (2026-11-10)

The three supplied links identify the game publicly as **Toy Attack** by Animoca Brands, consistent with the Animoca package namespace in the supplied original APK.

- `PV3FgGDyjic`: “Toy Attack - Gameplay Trailer (iOS,Android)” by TanJinGames, 20:02. The page has no captions; the browser could not expose playable frames, so this is not yet a frame-by-frame reference.
- `Hx9fxdv422w`: “Toy Attack - Coding Robot - Demo 2” by Animoca Brands, 0:40. The available thumbnail shows the block-based robot programming interface: Variable, Operator, Value, and Action categories, with IF/THEN logic and rotate-arm actions. Captions are unavailable.
- `z_Zuu0kzk9s`: “Toy Attack - Android Gameplay HD” by OGLPLAYS Android iOS Gameplays, 23:57. The available thumbnail shows an arena fight, PLAYER/OPPONENT labels, health indicators, pause control, and a “HEAD DESTROYED” result banner. Captions are unavailable.

The first link is a broad gameplay trailer, not a separate game called Robot Fight. The latter two provide useful reference clues for Toy Attack's coding UI and arena HUD. Only thumbnails/page metadata were inspectable in this browser session; do not claim full-motion animation timing or exact screen transitions were observed.

## Current CI asset-audit stage

The workflow now runs `tools/audit_robotfight_assets.py` immediately after extracting the DCA archive. It inventories extensions, image dimensions where available, plist/JSON parseability, and CCB root metadata, then uploads `RobotFight-Recovered-Asset-Inventory` as a separate artifact. This is an import-preparation step, not yet a Cocos runtime integration.

## Native engine import gate

Before wiring scenes into Cocos, use the generated inventory to establish whether the `.ccb` resources are CocosBuilder XML/binary plists, published `.ccbi`, or a game-specific format. CocosBuilder's documented editable `.ccb` format is plist-based, while runtime `.ccbi` is a compact binary format; the matching CCBReader/NodeLoader support and custom node classes must be confirmed against the actual files. The original CocosBuilder format documentation describes this distinction: https://github.com/cocos2d/CocosBuilder/blob/v3.5.0/Documentation/X3.%20CCB%20File%20Format.md and https://github.com/cocos2d/CocosBuilder/blob/v3.5.0/Documentation/4c.%20Connecting%20with%20cocos2d-x.md.

Next gate: build a minimal Cocos2d-x 3.16 arm64-v8a native scene in CI, then load a representative atlas/sprite and one compatible scene resource before porting full UI/gameplay. Do not replace the current reference APK until this native smoke test passes.
