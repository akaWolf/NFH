# NFH

Reverse engineering the Android builds of *Neighbours from Hell* seasons 1 and 2
(`com.nordigames.nfh` 1.5.5 and `com.nordigames.nfh2` 3.2.5 — both Unity 5.3.4f1,
Mono) with a view to reimplementing the game engine.

Both seasons ship the *same* `Assembly-CSharp.dll` source tree, so one decompile
and one spec cover both. See `docs/BUILDS.md`.

## Layout

| path | what |
|---|---|
| `tools/` | extraction pipeline — plain Python 3, numpy only for textures |
| `runtime/` | reimplemented renderer — Python + PySDL2 |
| `levels/s1/`, `levels/s2/` | all 37 scenes of both seasons as JSON (41 MB) |
| `src/` | 33 867 lines of C# decompiled from the game assemblies |
| `docs/GAMEPLAY.md` | behavioural spec of the game, cited to source lines |
| `docs/BUILDS.md` | which build is which, and why 1.5.5 is the one to use |
| `*.apk` `*.obb` `*.xapk` | the shipped artifacts (see `docs/BUILDS.md`) |

The unpacked game data (~900 MB per season) deliberately lives outside the repo.
Point `NFH_DATA` at wherever `tools/extract.sh` wrote it; every tool reads that
one variable, so switching seasons means pointing it at the other extraction —
nothing else changes.

## Reproducing

```sh
export NFH_DATA=/tmp/nfh-data
tools/extract.sh "$NFH_DATA"      # unpack APK + OBB, rejoin split .assets
python3 tools/validate_all.py     # self-test the readers
tools/decompile.sh                # ILSpy -> src/  (needs ~/.dotnet, no root)
python3 tools/export_level.py "$NFH_DATA/obb/assets/bin/Data/level5" levels/s1/Level101.json
python3 tools/summary.py levels/s1/Level101.json
python3 tools/zonegraph.py levels/s1/Level101.json
python3 tools/extract_textures.py textures   # 4013 PNGs, ~10 min for both seasons
python3 tools/extract_audio.py audio         # 923 WAV + 41 raw .fsb
python3 tools/extract_gui.py textures/s1 textures/gui/ textures/bubbles/ inventory/
python3 tools/extract_strings.py strings/s1 fonts/s1   # localization + TTFs
NFH_TEXTURES=textures python3 runtime/viewer.py levels/s1/Level101.json
```

## State

Done:

- **Data readable.** Every object in every scene deserializes with a byte-exact
  size match — 5774 / 5774 across Season 1's 20 scenes and 4726 / 4726 across
  Season 2's 17, with no code changes between them. The schema is recovered from
  CIL metadata rather than guessed; see `tools/README.md` for the Unity
  serialization rules that mattered.
- **Code readable.** Mono assemblies decompile cleanly, no failures.
- **Mechanics specified.** `docs/GAMEPLAY.md` covers the routine engine, trick
  state machine, detection and catching, alerters, anger and scoring, zone
  navigation, and the rendering model — with 39 line-level citations.
- **Zone graph solved.** Not serialized, but rebuildable offline from door links
  plus the transform hierarchy (`tools/zonegraph.py`). All 31 playable levels
  across both seasons come out connected.

- **Assets extracted.** All 4013 textures decode to PNG — ETC1, ETC2 and EAC
  implemented from scratch, since 9.9% of blocks use ETC2-only modes. Of 964
  audio clips, 923 unwrap from their FMOD FSB5 containers to WAV; the 41
  FMOD-Vorbis music tracks are kept as raw `.fsb`.

- **Rendering reimplemented.** `runtime/` draws any level from the exported JSON
  and the extracted PNGs, reproducing both passes the game used: world-space
  quads for the backdrop, then screen-space sheet blits ordered by `GUIDepth`.
  All 28 playable levels render with every sprite placed and no missing sheet.

- **Woody walks.** Click-to-move with BFS over the door graph, and door transits
  animated the way the game does them — the pawn hides and the door plays the
  sheet that contains him. Every zone of all 28 playable levels is reachable.

- **The neighbour keeps his routine.** `ActionManager` walks his cyclic action
  list, crossing zones and playing each item's use sequence. Season 1 runs
  clean on all 14 levels; Season 2 needs the Olga/Mother/`NFH2Path` branches.

Not started:

- **Gameplay.** Trick state machine, inventory, detection and catching,
  alerters, anger and scoring, HUD — `docs/GAMEPLAY.md` §5–§7.

Open questions are listed at the end of `docs/GAMEPLAY.md`.

## What makes this tractable

1.5.5 and 3.2.5 ship **Mono**, so `Assembly-CSharp.dll` is ordinary CIL with full
metadata. That single fact gives both the game logic *and* the schema for the
serialized level data — without it the MonoBehaviour blobs are unreadable, since
the builds have their type tree stripped. The successors (1.5.14, 3.2.13)
switched to IL2CPP and lose this entirely.
