# NFH level data extraction

Reads the level data out of the Android builds of *Neighbours from Hell* seasons
1 and 2 (1.5.5 and 3.2.5 — both Unity 5.3.4f1, Mono backend). Plain Python 3, with two
exceptions: texture decoding wants numpy (the ETC block decode is vectorised),
and decompiling to C# needs .NET + ILSpy. Both install without root — see
`decompile.sh`.

## Why this works

The game ships a Mono `Assembly-CSharp.dll`, so the full .NET metadata survives:
class names, field names, field types, declaration order. Unity serialized every
`MonoBehaviour` in the scenes using exactly that field layout, and it stripped the
type tree from the build to save space. So the DLL *is* the schema for the level
data — recover the layout from the metadata and the scene blobs become readable.

## Pipeline

| file | does |
|---|---|
| `paths.py` | where the unpacked data lives (`NFH_DATA` overrides) |
| `extract.sh` | unpacks APK + OBB, rejoins the split `sharedassets*.assets` |
| `unityser.py` | Unity SerializedFile v15 reader: object table, `MonoScript` names |
| `cli_meta.py` | ECMA-335 metadata reader: types, fields, enums, generic bases |
| `monodeser.py` | Unity serialization rules → deserializes `MonoBehaviour` payloads |
| `scene.py` | whole scene: `GameObject` / `Transform` / `BoxCollider` + scripts |
| `export_level.py` | one scene → JSON, enums as names, pointers as object names; `PatternFile` TextAssets parsed into each animation's `Pattern` + `Sounds` (`AnimationInstance.SetupPattern`) — Season 2 keeps 3917 animations' frames and sound keys there |
| `summary.py` | human-readable digest of an exported level |
| `zonegraph.py` | rebuilds the runtime zone graph from static data |
| `texture.py` | Texture2D reader plus ETC1/ETC2/EAC and linear decoders, PNG out |
| `extract_textures.py` | every Texture2D → PNG |
| `audio.py` | AudioClip reader, FSB5 container walk, WAV out |
| `extract_audio.py` | every AudioClip → WAV (or raw `.fsb`) |
| `validate_all.py` | self-test (see below) |
| `assets.py` | cross-file PPtr resolution: renderer → material → texture |
| `decompile.sh` | ILSpy → `src/` (33.9k lines of C# across 241 files) |

## Usage

```sh
tools/extract.sh                       # -> ./data (about 900 MB)
python3 tools/validate_all.py
python3 tools/export_level.py data/obb/assets/bin/Data/level5 levels/s1/Level101.json
python3 tools/summary.py levels/s1/Level101.json
```

`levels/s1/` and `levels/s2/` already hold every scene of both seasons exported
as JSON, so `extract.sh` is only needed to regenerate them or to reach the
textures and audio.

The same pipeline reads both seasons unchanged — set `NFH_DATA` to whichever
extraction you want. Season 2 uses `Transition` (a `Door` subclass) for nearly
all of its zone links, which `zonegraph.py` accounts for.

## Self-test

Every object is read against its declared `byte_size` in the serialized file. If
the recovered layout were wrong by even one field, the byte count would not land
on the boundary. `validate_all.py` reports:

```
exact 5774 / 5774 objects across 20 scenes     # season 1
exact 4726 / 4726 objects across 17 scenes     # season 2, same code
types covered: 85 and 106
```

Season 1 alone is 2008 `MonoBehaviour` instances across 82 script classes.

## Serialization rules that mattered

- Fields serialize in declaration order, **base class first**.
- Skipped: `static`, `const`, `readonly`, `[NonSerialized]`, and non-public
  fields without `[SerializeField]`. Also skipped: delegates, `Dictionary`,
  interfaces — Unity cannot serialize them, so they occupy no bytes.
- `[Serializable]` is emitted as `TypeAttributes.Serializable` (`0x2000`), **not**
  as a custom attribute. Looking for an attribute finds nothing.
- Primitives smaller than 4 bytes are padded to a 4-byte boundary individually.
  Strings and arrays are padded after the whole value.
- Generic bases must be resolved through the `TypeSpec` signature, substituting
  the type arguments: `ItemAnimationController : AnimationControllerBase<ItemAnimationState>`
  keeps all its data in the base class.
- `UnityEngine.GUIStyle` is inline, not a pointer: 348 bytes, and it uses the
  native convention of padding after a *run* of small fields rather than after
  each one.
- `Transform` in this build has no `m_RootOrder` and no `m_LocalEulerAnglesHint`.
- The backdrop quads reference Unity's built-in meshes: pathID 10209 is 'Plane'
  (AABB 10x10 in XZ) and 10202 is 'Cube' (1x1x1) — verified against the
  `unity default resources` file shipped in the APK, not assumed.
- Composing the hierarchy needs the rotation, not just position and scale. 216
  transforms carry the quaternion that lays an object into the view plane, and
  28 of their children sit at a non-zero local offset — one 28.7 units along
  local z, which that rotation turns into world y.
- `GameObject`'s trailing `m_IsActive` is not padded — `byte_size` excludes the
  inter-object padding.

## Assets

```sh
NFH_DATA=... python3 tools/extract_textures.py textures
NFH_DATA=... python3 tools/extract_audio.py   audio
```

Textures come out as RGBA PNG, row-flipped (Unity stores them bottom-up). Every
one decodes; nothing in either season is streamed, so the pixel data always sits
inline in the serialized file.

| | Season 1 | Season 2 |
|---|---|---|
| textures | 1578 (272 Mpx) | 2435 (599 Mpx) |
| audio | 300 WAV + 13 `.fsb` | 623 WAV + 28 `.fsb` |
| runtime | 25.7 min | 45.9 min |

Texture formats are ARGB32, RGBA32, RGB24, RGBA4444, RGB565, ETC_RGB4 and
ETC2_RGBA8. The ETC path needed all of ETC2, not just ETC1: **9.9% of blocks use
the T, H and Planar modes** that ETC2 adds, and decoding those as plain ETC1
corrupts them visibly. The tell is a differential block whose 5-bit channel sum
overflows — the first overflowing channel picks the mode.

Audio is wrapped by Unity in FMOD FSB5 containers inside `.resource` files.
Almost all of it is PCM16 mono at 44.1 kHz, which unwraps straight to WAV. The
music tracks are FMOD Vorbis, whose setup headers FMOD strips; those are written
out as raw `.fsb` for a real FSB5 decoder to deal with later.

### A trap worth knowing

Anything over ~1 MB is stored as `.splitN` parts — not only
`sharedassets*.assets` but also the `.resource` files holding the music. Joining
only the former silently loses 7 audio clips and 143 textures, with no error:
the objects parse fine, their payload just isn't there. `extract.sh` joins every
split set.

Resources are also referenced across the APK/OBB boundary, so a `.resource` named
by a file in one tree may live in the other. The extractors search both.

## What is in the data, and what is not

Serialized: the object tree, transforms, colliders, and every script field —
trick definitions, their required inventory, score, animation states, dependency
links, localization keys, door links, Woody's movement constants.

Not serialized: the **zone adjacency graph**. `Zone` stores only flags and
strings; the extent comes from the GameObject's `BoxCollider`, and the neighbour
list is built at runtime by `ZoneController.Start()`:

```csharp
foreach (Door d in zone.GetComponentsInChildren<Door>())
    if ((!d.Locked || d.TemporalLock) && d.LinkTo != null)
        zone.AddNeighbor(d.LinkTo.transform.parent.GetComponent<Zone>());
```

Every input to that rule *is* serialized — doors sit in the zone's transform
subtree and `LinkTo` is a stored pointer — so `zonegraph.py` reconstructs the
graph offline. Every playable level of both seasons comes out fully connected —
17 in Season 1, 14 in Season 2. Season 1 has `Zone01` as the hub in all of them;
Season 2's topologies vary. `Helpers.GetShortestPath` is Dijkstra with a uniform
cost of 1.0 per hop, so shortest paths are plain BFS over that graph.

`GetComponentsInChildren<Door>()` also matches `Transition`, the one `Door`
subclass, which is how Season 2 links almost all of its zones — `zonegraph.py`
matches both.
