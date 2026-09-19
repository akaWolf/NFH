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
| `tools/pcref/` | the PC original's data (`gamedata.py` reads its archive, `canon.py` lays each level's canon next to the mobile's) and measurements off its videos (laps, the thermometer, the lives) |
| `src/` | the decompiled game assemblies — generated, not stored (`src/README.md`) |
| `docs/GAMEPLAY.md` | the behavioural spec, cited to source lines |
| `docs/PC_FIDELITY.md`, `docs/PC_VS_MOBILE.md`, `docs/PC_LAPS.md` | what the PC original does differently, what the profile carries, the numbers |
| `docs/PC_VERIFICATION.md` | the profile against the PC binaries, rule by rule: the function that decides each rule, the verdict, what is still open |
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
original cannot produce; the moments are the mobile's and run under
`NFH_PROFILE=mobile`), `tests/run_csdiff.py` (the bytecode diff) and
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
- **The PC profile.** The PC's scoring (the S1 viewer rating, the S2
  COLLAPSE! board with the clock), its trick amounts, lap orders and
  scores where they differ, the whistle, three lives, the PC's own
  minigame (since 2026-09-23: GameLogic's game object, `docs/PC_FIDELITY.md`
  2.6), the
  rating's count-up and — since 2026-09-16, read from game.exe — the
  Season 1 anger itself (a trick sets the indicator to its `angrytime`,
  60 ticks of hold, one per tick at 12 Hz, +3 while above zero), and
  since 2026-09-17 the PC's walking speeds, door pass (both clips in
  turn, at the PC's ticks, the room changing at the far clip's start),
  catch on sight and the neighbour's station durations at the PC's ticks
  (docs/PC_VERIFICATION.md) — each
  deviation an overlay entry or an `is_pc()` branch with its source
  (`docs/PC_FIDELITY.md` §7). Under the four PC rules read from the
  binaries on 2026-09-17 — the walking speeds, the door pass, the catch
  on sight with no busy window, the stations' durations — the profile's
  idle laps sit within 10 % of the lap model on every level it covers
  (docs/PC_LAPS.md) and the plans were re-timed to them; since 2026-09-22
  the Season 1 reactions are the PC's too — the trick step's fire, its
  shout, its repair and the tricked stand, read off game.exe's level
  classes (`docs/PC_FIDELITY.md` "Season 1 reactions") — and since
  2026-09-23 every Season 1 level rates 100 in the PC's own chain orders
  (Badinfos' runs read off the HUD and the thermometer): a station tricked
  through its DependsOn plays the dependency's trick, a fixing tool its own
  case, a visit's prime leg its stay, 109's pig visit catches the pig and
  feeds it, 111's washer and drier are one station each and its ironing
  board burns between the give and the ironing (`docs/PC_FIDELITY.md` "The
  playing trick"); every Season 2 level rates 100 as well — the PC's
  station stays, compound coins and reaction clips are carried on every
  episode since 2026-09-18, and the Mother's PC stands on 212
  (`docs/PC_FIDELITY.md` "Season 2 station durations" / "compound coins"
  / "Season 2 reactions" / "The other actors' stands"); a coin is
  credited as its trick action completes, where the PC's bar jumps. Since
  2026-09-23 the Season 2 walk is GameLogic.dll's too — the door pair as
  one step (the walk to the near door's hotspot, the movement or the
  clips out of every room, the run down in the far room), the runs up
  and down to the stations' hotspots, the path finder's routes between
  stations — and the stays on the levels whose lap the code closes (six,
  214 the seventh since its handshake was read) are the code's
  (`docs/PC_FIDELITY.md` "Season 2 walks"); the plans of
  203, 206, 207, 208, 210-214 were re-timed to it (213's pile on his lap
  3, 212's on lap 5). Since 2026-09-23 the Season 2 catch is the PC's as
  well — generic/trigger.xml's room trigger for the neighbour and the
  Mother: the same room pointer (none mid-pass) and neither in a hideout,
  the catchers' being their neighbor_hideout stations and the level
  steps' sleeps (`docs/PC_FIDELITY.md` "The Season 2 catch") — and every
  Season 2 walk routes with the PC's path finder, Woody's to his items'
  PC hotspots included ("Season 2 routes and Woody's runs"); 207, 208,
  212 and 213 were re-timed to them (212's pile now on his lap 6), and
  all 28 levels rate 100 again. The mini-game's level tick is the PC's
  order too: Woody's DoAction step adds the rate the game's last update
  left, the update follows it (§2.6 of `docs/PC_FIDELITY.md`). And 214's
  neighbour-Mother handshake is the PC's script under the profile (it kept
  the mobile pace until 2026-09-23): his pistol's `standup` puts her to
  sleep in her chair for 600 ticks, she stands at the reling for 80 and
  sits awake until his next pistol, where he waits for her — his stays
  are the code's, and 214 was re-planned to it ("214's handshake"). So
  are 202's mat and swim: his mat's bar and beer at the code's ticks, the
  beer's `leave` waking Olga, his wait at the shore until she has put the
  kid's sub into the sea, the kid's dive and run ashore, the sea's bar,
  and the shark paid as the shark sea's `enter` ends (per clip:
  PCClipSeconds, PCWaitFor, PCCreditAfter; "202's mat and swim") — his
  lap is 82 s where the video's stays had made it 60; 202 was re-planned
  to it. And 210's call (2026-09-24): the Mother naps 240 ticks in her
  chair and at each nap's end looks for him in his — away, she stays
  awake 180 and naps again; in it, she gets up and calls once his sun
  bar and `wakeup` are over; the call gets him out of his chair and
  running to hers, where her order sends him to Fifi (her tickle, the
  take) — her chair, his chair and the handshake per clip at the code's
  ticks (PCClipSeconds, PCClipSecondsRole, PCWaitFor at the other's
  start, PCWaitForRole; "210's call"). His lap is 99 s call to call; the
  v23 plan still rates 100. The overlay writers of the walk and the catch
  had dropped the duration tools' keys sharing a patch since the routes
  of 2026-09-23 (207's bartender, 209's Taj, 212's throne look and
  ledge step, 213's control wait and the Mother's stands): they rewrite
  their keys in place now and the stays are back. And 205's table: his
  `talk` at Olga's mat calls her to the table and he waits 72 ticks, then
  plays once she is there, and her mat's wake-up and get-up and the table's
  play run at the code's ticks — a timed mutex for his mat, her mat's loop
  cut at his arrival, the mat's own clips at the PC's (PCItemClipSeconds),
  his play held for her and her release as it starts ("205's table"); his
  lap is 102 s, the video's 102, and the v3 plan still rates 100. And
  207's board: he dives only once the Mother sits in her deck chair, and
  she stays in it while he is in the pool room — her pool and chair and
  his board at the code's ticks, the rest of his stays the code's (the
  video's had his towel at 0.8 s; "207's board"); his lap is 100 s, the
  video's 107, and 207 was re-planned to it. 204's stays are the code's
  too (its gong sends him on by its own `gong`; "204's stays"), its lap
  84 s, the video's 81. The anims.xml reader of the lap model had given
  an empty animation's or object's successor to it (205's ski put, 204's
  gong and jade): it reads tag by tag now.
  The mobile numbers do not move: the regression under
  `--profile=mobile` is byte-identical.

Open: the frame pacer of game.exe (the level tick at 12 Hz is measured off
the HUD clock; the 60 Hz timer and the level's update are read, the gate
between them is not — no binary carries 1/12, GFXEngine's 83 ms is the
sprites' frame interval); two Season 2 runs whose scene the mobile plays
otherwise (201's tutorial runs him to the entry to shout after the soap
puddle, 205's back to the nailed water ski to pant and repair it; the
calls' runs of 208 and 210 are the Urgent ones, 210's Mother's to him on
Fifi's fall is carried; `docs/PC_FIDELITY.md` "Season 2's runs"); the PC's
field image (the data archive holds no TGA; the game's 100 px radius is
carried) and 203's Olga shout before the run (her `shout` has no clip in
the port); and the gap between the model's walks on the PC's rooms and
the port's on the mobile zones (204, 205: the model 10 % over the video
and the port). 111's machines are
the level class's DoActions (the washer's 24 s in the video is the walk
and give, wash, get_clothes; 47 s was a tricked lap), and the Season 1
neighbour runs where game.exe sets his gait. The Season 2 idle laps under
the profile (2026-09-24, the lap period on the neighbour's first station)
sit within 6 % of GameLogic's lap model on ten of the twelve levels it
times (203 99.5 s / 105, 208 82.5 / 85.5, 209 100.8 / 105, 211 80.8 / 85,
212 119.4 / 124, 213 126.6 / 123, 214 85.3 / 90.3 — the video's 91 shower
to shower — 202 81.7 / 80.7 plus his wait for Olga's sub, the video's 70
and 90-94, 210 98.7 / ~101 with its call, the video's first lap 107, and
207 100.0 / 106 with its board, the video's 107), 204 and 205 at −9 %
(84.3 / 92.8 and 101.6 / 111.9, the videos' 81 and 102: the model's walks
on the PC's rooms are the longer); 201 and 206 have no free lap; the
Season 2 gauge is 100 000 rage long and falls by
leveldata's `time` every 1/12 s (0.36 %/s), and the coins are the levels'
tricks.xml rage values. The Season 1 anger rule, the result captions and
the map's perfect mark are read from the binaries and carried
(`docs/PC_ROUTINES.md`, `docs/PC_VERIFICATION.md`). `docs/GAMEPLAY.md`
§10–§11 list what resists a clean reimplementation.

## What makes this tractable

1.5.5 and 3.2.5 ship **Mono**, so `Assembly-CSharp.dll` is ordinary CIL with
full metadata. That single fact gives both the game logic *and* the schema for
the serialized level data — without it the MonoBehaviour blobs are unreadable,
since the builds have their type tree stripped. The successors (1.5.14,
3.2.13) switched to IL2CPP and lose this entirely. And the apk carries an x86
build of the player, so the original runs natively on an x86_64 host, which is
what made diffing the port against it feasible at all.
