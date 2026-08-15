# NFH

Reverse engineering the Android builds of *Neighbours from Hell* seasons 1 and 2
(`com.nordigames.nfh` 1.5.5 and `com.nordigames.nfh2` 3.2.5 — both Unity 5.3.4f1,
Mono) with a view to reimplementing the game engine.

Both seasons ship the *same* `Assembly-CSharp.dll` source tree, so one decompile
and one spec cover both. See `docs/BUILDS.md`.

## Layout

| path | what |
|---|---|
| `tools/` | extraction pipeline — plain Python 3, no dependencies |
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

Not started:

- **Assets.** 1431 textures (1085 uncompressed, 346 ETC — a decoder is needed),
  309 audio clips.
- **Runtime.** Sprite-sheet renderer, zone pathfinding, animation sequencer,
  `ActionManager`, alerter FSM, inventory, HUD.

Open questions are listed at the end of `docs/GAMEPLAY.md`.

## What makes this tractable

1.5.5 and 3.2.5 ship **Mono**, so `Assembly-CSharp.dll` is ordinary CIL with full
metadata. That single fact gives both the game logic *and* the schema for the
serialized level data — without it the MonoBehaviour blobs are unreadable, since
the builds have their type tree stripped. The successors (1.5.14, 3.2.13)
switched to IL2CPP and lose this entirely.
