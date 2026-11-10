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
- Use Cocos2d-x 3.16 as the first engine integration candidate, pinned to a known commit/tag. Do not assume this proves the original game used exactly 3.16; the original binary's exact engine version remains unconfirmed.
- Keep 3.17.2 as a fallback if the recovered resource format or engine API points to it.

## Recovered game data

- DCA archive inventory from the prior extraction: 3,232 resources, CRC-verified.
- Approximate types recorded: 2,805 WebP, 25 PNG, 178 JSON, 138 CCB, 68 plist, plus other files.
- Local data files identified: tutor bot roster, AI chip definitions, stage definitions, and robot parts catalog.
- The current WebView prototype uses recovered part sprites, but assembles them with approximate placement; it does not yet reproduce the original Cocos scene graph, animation timelines, or combat logic.
- The CCB files must be inspected to establish whether they are CocosBuilder source files, compiled CCBI, or a game-specific variation. Do not assume they can be loaded directly without the matching reader and node-loader classes.

## Required next engineering stages

1. Extract and catalogue every DCA path, dimensions, plist frame references, atlas image references, CCB header/format, and JSON/plist schema.
2. Pin and fetch Cocos2d-x 3.16 source in CI; verify its Android ARM64 toolchain with a minimal native scene before replacing the current app shell.
3. Build a Cocos2d-x Android project targeting only `arm64-v8a`; modernize build scripts as needed rather than relabelling the original ARM32 libraries.
4. Reconstruct the original screens using recovered atlas frames, plist metadata, fonts, and CCB scene data wherever compatible.
5. Reimplement offline bot selection, combat state, progression, local profile persistence, and the victory-only +2,000 coin reward.
6. Add automated checks for ARM64 ELF libraries, asset manifest completeness, offline/no-network behavior, save persistence, and reward idempotency.
7. Keep the current WebView APK as a playable reference build until the native Cocos version passes device testing.

## Important constraints

- The original proprietary C++ game source has not been recovered.
- Original ARM32 shared libraries cannot be made ARM64 by renaming or changing APK metadata.
- The current APK is a prototype/reference, not a complete restoration.
- Preserve the recovered source assets and document their original paths; do not replace them with generated placeholder art.
