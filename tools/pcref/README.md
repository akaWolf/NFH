# PC reference measurements

The PC games' neighbour routine, read off the 100 % walkthrough videos
without touching the game: the PC HUD's top-left thought bubble shows the
neighbour's CURRENT activity (coffee cup, deck chair, watering can …), so
its icon per second is his action sequence — camera-independent, unlike
tracking his sprite (the PC view pans and he is often off-screen).

- `bubble.py <video> <start> <dur> <x0> <y0> <w> <h> <out_prefix> [fps] [T]`
  crops the bubble per frame, clusters the crops greedily (24×24 RGB, L2
  threshold T≈900), writes `<prefix>.json` (t, cluster), `<prefix>_icons.png`
  (one exemplar per cluster) and prints the run-length sequence. Crops used:
  Badinfos 720p Season 1 `10 568 120 70`, Badinfos 720p NFH2 `15 548 150 65`.
- `episodes_s1.json`, `episodes_nfh2.json`: episode start/end in the two
  Badinfos videos (from ffmpeg scene cuts + the episode-selection cards).
- `laps_table.py`: the cluster→activity labels (read by eye from the icon
  sheets), the PC sequences, the lap periods, and the mobile side from the
  port's recordings (`tests/run_tricks.py` state.jsonl: the neighbour's
  `using` items) — writes the detail file behind `docs/PC_LAPS_DETAIL.md`.

Videos live outside the repo in `~/nfh-bench/pcref` (see its README.txt;
`yt-dlp -4` from pcnew). Results: `docs/PC_LAPS.md`.
- `laps_natural.py [--plans <dir>] [--idle <dir>] [level ...]`: the neighbour's
  natural lap (no trick fired) — writes 28 wait-only plans for the harness,
  then pairs the idle recordings' actions with PC_LAPS_DETAIL's bubble spans
  by name (docs/PC_LAPS.md, "Natural laps").
- `amounts.py <video> [episode ...]`: the NFH2 trick amounts — the gauge's
  jumps per second, each labelled with the bubble activity of that second
  (PC_LAPS_DETAIL.md) and scaled to the full bar, beside the level's mobile
  AngerAmounts (the overlays in levels/pc).
- `gauge.py <video> <start> <dur>`: the PC NFH2 anger gauge (the bar at the
  left of the 720p frame) as fill % per second — its jumps are the tricks'
  amounts, its plateaus the decay (~0.4 %/s).
- `lives2.py <video> <start> <dur> <x0> <y0> <w> <h> <prefix> [T] [white|red]`: the
  PC NFH2 lives counter (top right) binarized and clustered per second — a
  cluster change is a lost life; used to find the catches in a let's play.
- `thermo.py [video]`: the Season 1 thermometer (the neighbour's anger meter,
  bottom-left): the mercury column at 10 Hz per episode, its full holds and
  full-to-empty durations — of the red part of the column only: the white-hot
  top is not red, so its "full" outlives the true one by ~2 s and its drains
  are short. `thermo_rows.py <episode>…` reads the first non-blue row instead
  and prints, per trick, the seconds the fill stays at 97 %+ and the fall in
  %/s — the 60-tick hold at 12 Hz (5 s) and 0.7 × the level's `angrytime`
  ticks over the visible tube (docs/PC_ROUTINES.md); the PC overlays carry
  the angrytime in ticks as PCAngryTime, and the profile runs the PC rule on
  it (docs/PC_FIDELITY.md §7).
- `thermo_jumps.py <episode>…`: the thermometer's jumps per episode — the second
  of every trick of Badinfos' run (game.exe fires the trick before its
  animation), the fill just before each jump and the gap to the previous one:
  the PC's own chain of a level (E06 in docs/PC_LAPS_DETAIL.md — nine tricks,
  eight bonuses). A jump within ~4 s of the tube's emptying can still be a
  bonus (the bulb holds the bar's bottom ~30 %); the HUD's bonus counter in
  a frame settles it, and in the frames Woody is the blond in blue, the
  neighbour the man in the vest.
- `pc_tricked_actions.py`: the Season 1 TRICKED objects' neighbour actions in
  seconds next to the normal object's, paired by the scripts' `If <tricked>
  of <normal>` steps (docs/PC_ROUTINES.md) — the PC plays the tricked
  object's own action (106's make_foampudding 3.17 s, not make_pudding's
  8.00) where the port stretches the tricked clip to the normal stay
  (docs/PC_FIDELITY.md, the 106 paragraph).
- `fire_sites.py [--fibers]`: every trick-fire step site of game.exe (the
  three-, four- and five-argument steps whose run is fcn.0047bd00) decoded off
  the listing by a stack emulation — name, index, flags, animation, actor —
  and, with `--fibers`, a register-valued index or flags resolved through
  radare2's analysis of the level fiber (the prologue constant of the class's
  `run`): the shout choice and the pay-before-clip sites of docs/PC_ROUTINES.md
  "The fire's tail".
- `gamedata.py <gamedata.bnd> list|cat|grep|tags …`: the PC original's data archive
  (a plain ZIP of XML and TGA: per level `level.xml`, `objects.xml`,
  `tricks.xml`, `anims.xml`, `trigger.xml`; copies in ~/nfh-bench/pcref/pc) —
  the PC side as data. It settled what the videos could only estimate
  (docs/PC_FIDELITY.md §7, "The PC's own data"): Season 1 `quota1` per trick
  = the mobile TrickScore but on 109/111/112; `angrytime` per level = the
  thermometer's drain in 1/20 s; Season 2 `rage` per trick = the mobile
  AngerAmount but on eight items, and the gauge is 80 000 rage long. The
  amounts.py readings (all 1.25× the data) are superseded by it.
- `pc_durations_s2.py [--write] <level ...>`: the Season 2 neighbour's station stays from the PC videos' bubble spans (docs/PC_LAPS_DETAIL.md, the first lap) less the walk the profile's neighbour takes to each station (runs/idlepc2s2), into the overlays as PCUseSeconds per visit. Written for every Season 2 level (2026-09-18); the aliases pair PC bubble names with the port's uses in order, a port visit the PC never makes (209's first shoe: the PC does the Taj before the shoes) keeps the mobile length as a leading 0, and a level whose lap is a two-actor handshake (214: the Mother's sit releases his pistol wait) is skipped whole.
- `pc_durations_others.py [--write] <level ...>`: the other actors' stands (the Mother, Olga …) from the PC data's `time` ticks of their actions, paired per level with the idle runs' stands (NFH_SCRATCH/s2_idle_others.json) in ALIAS, into the overlays as PCUseSecondsRole.
- `coins.py <level ...>`: the Season 2 coin tricks of the profile's plan against the PC combinations' `<trick>` records — the rage each pays and the records a compound fires (the amounts of the PCExtraCoin overlays); a record's `time` is a frame of its action, not the credit's moment (the `--write-ticks` carry is withdrawn); `--write-laugh` writes PCLaugh, the records' `laugh` level that picks the PC neighbour's reaction clip (the level's commonest level for an item the pairing does not reach).
- `canon.py <level ...>`: the PC canon per level next to the mobile's data —
  tricks and values, recipes, containers, walk-by triggers, rooms, the
  neighbour's action lengths — with the multiset diffs (docs/PC_FIDELITY.md §7,
  "The canon audit").

- `routine_order.py` — the neighbour's lap of every Season 1 level read from game.exe's compiled level classes (the yield chain of each class's switch, simulated with no trick fired); prints the laps beside the mobile routines. Needs the radare2 listing of game.exe (`~/nfh-bench/pcref/r2/nfh1_game_text.txt`) and `exe/nfh1_globals.json`.
- `routine_order_s2.py` — the Season 2 counterpart: the chain of step functions of each GameLogic.dll level script followed with no trick fired; nine laps close (201, 203, 205, 206, 208, 209, 211, 212, 213), the polling steps of 202/204/207/214 and 210's deck chair stop the rest (`TAILS=1` shows the branches). Needs `~/nfh-bench/pcref/r2/nfh2_gamelogic_text.txt`.

- `lap_model.py` — the Season 1 lap by code and data: `LAPS=1 routine_order.py`'s ICON / GOTO / ENTER / LEAVE / ACTION tokens of each level class, walked at the neighbour's `<speed>` records between the objects' hotspots through the doors (standing points, `enter`/`leave` ticks), the actions at their `time` or frames; against the PC video's natural laps (docs/PC_LAPS.md). The door sum (the near `enter` plus the far `leave`) is the engine's: game.exe composes the pair as one step list (fcn.00478030) and the 110 video measures a back door at ~3 s. `-v` lists the legs; `LAP_TOKENS=<file>` caches the walker's output.
- `routine_order.py` `LAPS=1` — prints each level's lap as tokens (`LAP <level> <n>: ICON x | GOTO obj | ACTION act + obj …`), the helpers of the class (the sofa's sit picker) descended into, the compound GoTo/DoAction helpers labelled (fcn.00479f10 GoTo+enter, fcn.0044ac80 GoTo with leave, fcn.00473e20/ea0 enter/leave, fcn.00479c70 DoAction+wait).
