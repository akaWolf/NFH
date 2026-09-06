# NFH

A source port of *Neighbours from Hell* seasons 1 and 2 — the Android
remasters (`com.nordigames.nfh` 1.5.5 and `com.nordigames.nfh2` 3.2.5, both
Unity 5.3.4f1, Mono) — rebuilt in Python from the game's own decompiled code
and its exported level data. Both seasons play from the splash to the credits;
every line of the runtime cites the method of `Assembly-CSharp` it reproduces.

Two runtimes live in one tree:

- the **mobile-parity runtime** (`--profile=mobile`), checked against the
  original running under Frida, frame by frame;
- the **PC-experience profile** (the default): the same runtime with the
  2003 PC game's rules and constants restored where the remaster changed
  them, measured off the PC original's video — the rating is 100 % on
  every level, as it is on PC.

Both seasons ship the *same* `Assembly-CSharp.dll` source tree, so one
decompile and one spec cover both. See `docs/BUILDS.md`.

## Layout

| path | what |
|---|---|
| `runtime/` | the game: renderer, world, routine engine, tricks, HUD, menus, tutorial (`runtime/README.md`) |
| `runtime/pcprofile.py`, `levels/pc/` | the PC-experience profile: the rule switches and one data overlay per level, each with its source |
| `levels/s1/`, `levels/s2/` | all 37 scenes of both seasons as JSON (41 MB) |
| `tests/` | the suites: the trick matrix (`run_tricks.py` + `plans/`), moments, menus, tutorials, the input monkey, invariants, the bytecode diff |
| `tools/` | the extraction pipeline — plain Python 3, numpy only for textures (`tools/README.md`) |
| `tools/livediff/` | the bench: the original game in an Android-x86 VM / emulator, its state read out under Frida, plans replayed on both sides |
| `tools/csdiff/` | the game's own bytecode run against the port one method at a time |
| `tools/pcref/` | measurements off the PC original's videos (laps, amounts, the thermometer, the lives) and a reader for its data archive (`gamedata.py`) |
| `src/` | the decompiled game assemblies — generated, not stored (`src/README.md`) |
| `docs/GAMEPLAY.md` | the behavioural spec, cited to source lines |
| `docs/PC_FIDELITY.md`, `docs/PC_VS_MOBILE.md`, `docs/PC_LAPS.md` | what the PC original does differently, what the profile carries, the numbers |
| `docs/BUILDS.md`, `docs/BUNDLE.md` | which build is which; the desktop bundles |
| `*.apk` `*.obb` `*.xapk` | the shipped artifacts (see `docs/BUILDS.md`) |

The unpacked game data (~900 MB per season) deliberately lives outside the
repo. Point `NFH_DATA` at wherever `tools/extract.sh` wrote it; every tool
reads that one variable, so switching seasons means pointing it at the other
extraction — nothing else changes.

## Playing

```sh
./run.sh                          # the full game: splash, menus, levels
                                  # (extracts the assets from the apk/obb on first run)
./run.sh Level108                 # the full flow, straight into a level
./run.sh --profile=mobile         # the mobile-parity runtime instead of the PC profile
./run.sh levels/s2/Level208.json  # the bare level viewer
```

Standalone Linux/Windows bundles build in CI (`.github/workflows/bundles.yml`,
PyInstaller over `nfh.spec`); a bundle extracts the assets from the user's own
apk/obb next to the executable on first start — see `docs/BUNDLE.md`.

## Verifying

The trick matrix drives every trick of every level from a plan file to the
end screen on the real 60 Hz loop, with the dodging a player does by hand:

```sh
python3 tests/run_tricks.py tests/plans/pc/s1/Level106.txt        # one plan, the PC profile
python3 tests/run_tricks.py --all --profile=mobile --jobs=4 --out=$HOME/nfh-bench/runs/mob
NFH_SEED=1 NFH_SHOT_FPS=1 python3 tests/run_tricks.py tests/plans/s2/Level210.txt --out=$HOME/nfh-bench/runs/l210
```

Runs are seeded (`NFH_SEED`, default 0) and reproduce to the frame; the run
dir holds the state log, the results per leg and the rating. `NFH_GATE_LOG`,
`NFH_ROUTINE_LOG` and `NFH_SHOT_FPS` (PNG frames) are the diagnostics. The
other suites: `tests/run_moments.py` (scripted moments), `tests/run_menu.py`
and `tests/run_tutorial.py` (the flow and the five tutorials),
`tests/monkey.py` over `tests/invariants.py` (random input against states the
original cannot produce), `tests/run_csdiff.py` (the bytecode diff) and
`python3 -m unittest tests.test_hud_pc` (the profile's HUD arithmetic).
The bench that replays a plan on the original itself is described in
`tools/livediff/README.md`.

## Reproducing the data

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

- **Data readable.** Every object in every scene deserializes with a
  byte-exact size match — 5774 / 5774 across Season 1's 20 scenes and
  4726 / 4726 across Season 2's 17. The schema is recovered from CIL
  metadata rather than guessed (`tools/README.md`).
- **Code readable.** The Mono assemblies decompile cleanly; the spec in
  `docs/GAMEPLAY.md` covers the routine engine, the trick state machine,
  detection and catching, alerters, anger and scoring, zone navigation and
  the rendering model, cited to source lines.
- **Assets extracted.** All 4013 textures (ETC1/ETC2/EAC from scratch), 923
  of 964 audio clips to WAV, the 41 FMOD-Vorbis music tracks as raw `.fsb`.
- **The game runs.** Both draw passes of the original, the door-graph
  walking, the neighbour's cyclic routine with its urgent actions, every
  trick and its fix, the alerters, the catch, the anger meter and the
  rating, the HUD, the menus, the level flow, the five
  tutorials and the dexterity minigames — all 28 playable levels of both
  seasons, from the splash to the end screen.
- **Checked against the original three ways.** The invariants watch our
  own loop; `tools/csdiff` runs the game's bytecode against ours per
  method; `tools/livediff` replays a plan on the original running under
  Frida and diffs the two traces — the port's fixes are listed there,
  level by level.
- **The trick matrix.** 54 mobile plans (every level, and every level's
  tricks in a second order): all won, 33 PERFECT; the rest are the
  remaster's own ceilings — one anger overflow per Season 2 level and no
  whistle on Level114 — measured in `docs/PC_VS_MOBILE.md`.
- **The PC profile.** 28 of 28 levels at 100 %: the PC's scoring (the S1
  viewer rating, the S2 COLLAPSE! board with the clock), its trick
  amounts, lap orders and scores where they differ, the whistle, three
  lives, no minigames, the thermometer's drain and the rating's count-up
  — each deviation an overlay entry or an `is_pc()` branch with its
  source (`docs/PC_FIDELITY.md` §7). The mobile numbers do not move: the
  54-plan regression under `--profile=mobile` is byte-identical.

Open: three natural laps still differ from the PC's by more than 15 %
(111, 213, 210 — routine structure, not constants), and the PC's tick
window is bracketed at 18–25 s rather than measured (the data's 23.6 s
sits inside). `docs/GAMEPLAY.md` §10–§11 list what resists a clean
reimplementation.

## What makes this tractable

1.5.5 and 3.2.5 ship **Mono**, so `Assembly-CSharp.dll` is ordinary CIL with
full metadata. That single fact gives both the game logic *and* the schema for
the serialized level data — without it the MonoBehaviour blobs are unreadable,
since the builds have their type tree stripped. The successors (1.5.14,
3.2.13) switched to IL2CPP and lose this entirely. And the apk carries an x86
build of the player, so the original runs natively on an x86_64 host, which is
what made diffing the port against it feasible at all.
