# NFH

Reverse engineering the Android build of *Neighbours from Hell: Season 1*
(`com.nordigames.nfh` 1.5.5, Unity 5.3.4f1, Mono) with a view to reimplementing
the game engine.

## Layout

| path | what |
|---|---|
| `tools/` | extraction pipeline — plain Python 3, no dependencies |
| `levels/` | all 20 scenes exported to JSON (22 MB) |
| `src/` | 33 867 lines of C# decompiled from the game assemblies |
| `docs/GAMEPLAY.md` | behavioural spec of the game, cited to source lines |
| `docs/BUILDS.md` | which build is which, and why 1.5.5 is the one to use |
| `*.apk` `*.obb` `*.xapk` | the shipped artifacts (see `docs/BUILDS.md`) |

The unpacked game data (~900 MB) deliberately lives outside the repo. Point
`NFH_DATA` at wherever `tools/extract.sh` wrote it.

## Reproducing

```sh
export NFH_DATA=/tmp/nfh-data
tools/extract.sh "$NFH_DATA"      # unpack APK + OBB, rejoin split .assets
python3 tools/validate_all.py     # self-test the readers
tools/decompile.sh                # ILSpy -> src/  (needs ~/.dotnet, no root)
python3 tools/export_level.py "$NFH_DATA/obb/assets/bin/Data/level5" levels/Level101.json
python3 tools/summary.py levels/Level101.json
python3 tools/zonegraph.py levels/Level101.json
```

## State

Done:

- **Data readable.** Every object in every scene deserializes with a byte-exact
  size match — 5774 / 5774 across 20 scenes, 85 component types. The schema is
  recovered from CIL metadata rather than guessed; see `tools/README.md` for the
  Unity serialization rules that mattered.
- **Code readable.** Mono assemblies decompile cleanly, no failures.
- **Mechanics specified.** `docs/GAMEPLAY.md` covers the routine engine, trick
  state machine, detection and catching, alerters, anger and scoring, zone
  navigation, and the rendering model — with 39 line-level citations.
- **Zone graph solved.** Not serialized, but rebuildable offline from door links
  plus the transform hierarchy (`tools/zonegraph.py`). All 17 playable levels
  come out connected.

Not started:

- **Assets.** 1431 textures (1085 uncompressed, 346 ETC — a decoder is needed),
  309 audio clips.
- **Runtime.** Sprite-sheet renderer, zone pathfinding, animation sequencer,
  `ActionManager`, alerter FSM, inventory, HUD.

Open questions are listed at the end of `docs/GAMEPLAY.md`.

## What makes this tractable

1.5.5 ships **Mono**, so `Assembly-CSharp.dll` is ordinary CIL with full
metadata. That single fact gives both the game logic *and* the schema for the
serialized level data — without it the MonoBehaviour blobs are unreadable, since
the build has its type tree stripped. Version 1.5.14 switched to IL2CPP and loses
this entirely.
