# Robot Fight RCCB scene format notes

## Verified inventory

The original scene bundle contains **138 `.ccb` files**, totaling **952,552 bytes** in the extracted scene set. Every file begins with the same 8-byte signature:

```text
10 00 00 00 52 43 43 42
```

Interpretation that is safe to make:
- bytes 0–3: little-endian integer 16 (meaning not yet established)
- bytes 4–7: ASCII `RCCB`
- bytes 8–15: repeated 16-bit values `08 00 0c 00 04 00 08 00`

This is **not** the standard CCBI magic/header. The meaning of the first integer and the remaining header fields has not been proven. Do not strip the first eight bytes and feed the remainder to Cocos2d-x's stock `CCBReader` without a format-level test.

## Strings and node-class inventory

A diagnostic scan of printable ASCII strings found these occurrences across all 138 files:

| Node class | Occurrences |
|---|---:|
| CCSprite | 837 |
| CCNode | 580 |
| CCLabelTTF | 447 |
| DCSprite | 333 |
| DCNode | 282 |
| CCButton | 246 |
| CCSprite9Slice | 216 |
| DCLabel | 142 |
| DCUIButton | 135 |
| DCLabelTTF | 99 |
| DCUIControl | 5 |
| CCLabelBMFont | 2 |

The scan found 2,346 resource-reference occurrences spanning 450 unique resource names. These are string-level counts, not decoded object counts: the same resource or class may occur in property metadata and should not be treated as proof of one instantiated node per string.

## Battle scene evidence

`RFBattleLayer.ccb` is 55,708 bytes and contains 187 resource-reference strings. Its string table includes:
- two player-side HUD/code areas and player/opponent labels
- timer and result/pause UI
- heat/overheat meter and 42 indexed heat-bar names (0–41)
- left/right boost controls and directional controls
- AI-chip containers and cooldown nodes
- player/opponent battery meters
- robot HP components named Base, Core, Head, FrontArm, and BackArm

This is enough to establish that the recovered file retains substantial original battle-scene metadata and resource links. It is not yet enough to reconstruct exact parent-child relationships, property types, animation timelines, or runtime callbacks.

## Tooling added

- `tools/inspect_rccb.py` emits a JSON inventory with string offsets, candidate identifiers, resource references, node-class counts, and header values.
- `.github/workflows/rccb-inspect.yml` runs the inventory against the verified original-scene artifact and publishes `RobotFight-RCCB-Structure-Report`.

Latest verified inspector run:
- Run ID: 42790626495
- Result: success
- Recovered scene count: 138
- Magic counts: `RCCB: 138`

## Next engineering gate

Before using these files in a Cocos runtime, determine the binary record grammar:
1. correlate offsets and lengths across small scenes and `RFBattleLayer.ccb`;
2. identify string, scalar, node-class, property, child-node, and timeline records;
3. validate any candidate decoder against multiple independent scenes;
4. only then implement a reader/adapter and render a native Cocos smoke-test scene.

The existing ARM64 WebView APK is not evidence that this Cocos scene reader or native game port is complete.


## New offset-table evidence (2026-11-10)

The inspector now scans aligned 32-bit words for complete, in-bounds,
strictly-descending offset arrays. It does **not** label their payloads as
decoded nodes. The updated report was generated successfully from the recovered
138-scene archive (Actions run 4).

Verified observations from that report:

- 105 of 138 scenes contain at least one candidate array under this conservative
  rule; 152 candidate arrays were found.
- In `RFBattleLayer.ccb`, the array at byte offset `0xD8` has 16 entries and
  points to records containing stage/background resources such as
  `background_3_2.webp`, `stage_0_ground_b_1.webp`, and
  `stage_0_foreground.webp`.
- Additional arrays in that same scene point into records containing font
  references and indexed heat-bar names (including `heatBar40` and
  `heatBar41`).
- The final small values (commonly 4, and sometimes 20 or 28) behave as
  sentinels in these candidate arrays. Their exact meaning remains unknown.

This establishes that RCCB contains navigable offset-indexed regions and gives
repeatable entry points for the next parser stage. It does **not** yet establish
the binary grammar for each record, the node parent/child graph, property types,
or animation timelines. Runtime scene reconstruction is still blocked on those
decoders.


## Validated string-layer decoder (2026-11-12)

A separate decoder now tests the repeated RCCB string token pattern across the
entire recovered scene set. The observed token layout is:

- 4-byte little-endian byte length;
- exactly that many printable ASCII bytes;
- a NUL terminator immediately after the payload.

The decoder verifies each scene's byte length and SHA-256 against the structural
inventory before scanning. On the recovered 138-scene bundle it found 8,565
candidate tokens. Of these, 8,372 exactly match an ASCII string and byte offset
already reported independently by the original inspector. It also found 193
short or previously unindexed strings. Another 665 inspector strings do not
match this exact token layout and are intentionally left unresolved.

This validates one reusable layer of the RCCB encoding. It does not decode
node records, property types, parent-child relationships, timelines, or runtime
callbacks. The output preserves byte offsets and raw string values so later
record decoding can use them without guessing.
