# The port against the PC binaries — rule by rule

The PC originals on hand (`docs/PC_FIDELITY.md` §6: Season 1's `game.exe`
and `GFXEngine.dll`, Season 2's `game.exe`, `GameLogic.dll`, `GUIEngine.dll`,
both `gamedata.bnd` archives unpacked) are the canon of the PC profile. This
document lists what the profile claims, where the port implements it, the
function of the binary that decides it, and whether the two agree. "Read"
means the rule was taken from the disassembly (radare2 over the binaries,
addresses given); "data" means it was checked against the unpacked XML
(`tools/pcref/canon.py` lays the PC level next to the mobile's); "open" means
the binary has not been read far enough to say. Nothing here comes from a
video except where the video is named.

The mobile runtime (`--profile=mobile`) is not the subject: it is verified
against the mobile game's own bytecode and Frida traces
(`tools/livediff/README.md`, `tools/csdiff/`). Every difference below is
between the PC binaries and the PC profile.

## Season 1

### The level's end

The level state lives in one object (`game.exe`, constructor fcn.0043b9b0:
+0x54 tick count, +0x58 elapsed, +0x5c limit, +0x60 score, +0x64 bonus count,
+0x70/+0x74 rage current and max, +0x78 hold, +0x80 state, +0x84 level
angrytime, +0x8a "check the quota" flag). Every tick fcn.00439cd0 runs the
scripts and then fcn.00436bb0, which returns the new state:

| state | meaning | how it is reached (fcn.00436bb0) |
|---|---|---|
| 0 | running | nothing below applies |
| 5 | success | the flag +0x8a is set (fcn.0047bc90, called at the end of every trick's reaction fiber fcn.0045b470 right after the score is added at 0x45bb25) and the score is 100 or more, or the fired-trick count (fcn.00416690) equals leveldata's `reachable`; or the clock ran out with a score at or above `minquota` (record +0x1c) |
| 4 | time's up | the clock ran out (elapsed > limit, +0x58 / +0x5c) with a score below `minquota` |
| 2 | caught | the level class's last switch case set state 1 (the beating's end, e.g. peep 0x452008, sofa 0x454eaa — every level class has one) and the quota check with `minquota` as the threshold did not pass |
| 3 | caught on sight | Woody and the neighbour hold the same position object (`[actor+0x1c]`, fcn.00444b00), the byte +0x78 of the second actor is clear, and neither actor carries flag 4 in its flag word (fcn.0043c2b0) — see "The catch" |

The order in the function is 3, then 5, then 4, then 2. The level-changed
handler fcn.00437de0 tells the GUI two booleans, success = (state == 5) and
time's up = (state == 4) (fcn.00478870 at 0x47890c–0x478926), and writes the
episode's map state: 4 when the score is 90 or more (0x437ebe, `cmp eax,
0x5a`), 3 when it is at or above `minquota` — leveldata's `perfect` and
`finished` strings (the wide strings at 0x4e727c / 0x4e7268).

The game-over dialog is captioned in `GFXEngine.dll` (0x1000e0f9–0x1000e2b1):
the success flag picks `perfect` when the viewer rating (`[esp+0x70]`) is at
least 90 (0x1000e201) and `success` below, the time's-up flag picks
`timeover`, everything else `failed`; `generic/strings.xml` spells them
BRILLIANT!, SUCCESS!, TIME'S UP!, FAILED! (category `gameover`, with
VIEWER RATING: and TRICKS:). The jingle table at 0x440f2f (0 and 2
`jingle_failed`, 1 `jingle_caught`, 3 `jingle_success_normal`) is indexed
by the dialog's outcome; `jingle_success_perfect` is in the string tables
and never played by the code.

| rule | port | binary | verdict |
|---|---|---|---|
| the level ends when every trick has fired | `GameState.all_done` (completed == total) | state 5 on fired == `reachable` | agrees; `reachable` equals the port's `total` on all 14 levels (data) |
| the level ends when the rating reaches 100 | not modelled | state 5 on score ≥ 100 after the reaction | equivalent on every level: the sum of the trick scores is 76–91, so 100 needs the last trick and the ticks together (data, docs/PC_LAPS.md) |
| time's up: success at or above minquota | `calculate_score`: won = rating ≥ `pc_min_rating` | state 5 / 4 by `minquota` | agrees |
| a catch with the quota reached is still a success | `_catch` → `_finish_game` → `calculate_score` (won by the quota) | state 5 from state 1 when score ≥ minquota | agrees (the port's caught jingle plays either way, as the PC's index-1 jingle does) |
| the result captions | the mobile's EXCELLENT / GOOD / PASSED / FAILED / TIME UP | BRILLIANT! from 90, SUCCESS!, TIME'S UP!, FAILED! | **fixed 2026-09-16**: `pcprofile.s1_result` under the profile |
| the map's perfect episode | rating ≥ 100 | rating ≥ 90 (leveldata state 4) | **fixed 2026-09-16**: `pcprofile.s1_perfect` under the profile (`app.py`'s score save) |
| the minimum ratings | `pcprofile.S1_MIN_RATING` | leveldata.xml `minquota` 50/55/60/65/70/75, 60/65/70/75, 60/65/70/75 | agrees (data) |
| the time limits | the mobile's TimeMinutes | leveldata.xml `time` 3600/4320/5040/7200 ticks at 12 Hz = 5:00, 6:00, 7:00, 10:00 | agrees on all 14 levels (data) |
| the clock | 12 Hz ticks, the HUD's minutes | fcn.00438a80: elapsed++ per tick, clamped at the limit; the GUI divides by 12 | agrees (docs/PC_ROUTINES.md) |

### The catch

The per-tick rule is the one in fcn.00436bb0 above: fcn.00448bf0 looks up
`woody` and `neighbor`, fcn.00444b00 returns each actor's position object
(`[actor+0x1c]`; set by fcn.00444b30 from a level entity looked up by name,
fcn.00448d70 — the walk step at 0x475ef1 compares the same field with the
name-looked-up target to decide whether the actor is there yet), and the
catch needs the two to be equal, the byte +0x78 of the actor looked up
second to be zero (written only by the level's event handler at 0x440c87
from an event's boolean; the handler is slot 49 of the level state's
vtables 0x4e07b8 / 0x4e1638, reached through the level's script
interface — vtable 0x4e7650, slot 207, the stub at 0x405f10 — whose
callers the dump does not show as direct calls), and flag 4 clear on
both. Flag 4 is set by fcn.004737a0 (SetFlag 4 at 0x473965, then the
actor's +0x30 hideout pointer and an action) and cleared by fcn.00473a60 —
Woody in a hideout (the `hideout` flag of `objects.xml`). State 3 starts
the beating: the event handler at 0x43f5b0 consumes the pending catcher,
tests the catcher's type flags (0x10 → fcn.004753e0, 2 → fcn.00474a20) and
runs the cutscene fiber fcn.00474510, which ends by writing state 1 at
0x474981 and clearing flag 8 on both actors. The same fiber is started by
the neighbour's walk step (fcn.00475b30 region, 0x476057) when his
coordinates (fcn.00444690: +0x28/+0x2c) meet Woody's — the chase's arrival.

| rule | port (the mobile's, docs/GAMEPLAY.md §2) | binary | verdict |
|---|---|---|---|
| detection is zone containment, no line of sight | `CanRottweilerSeeWoody`: same Zone | same position object | agrees in kind; whether the PC's object is the room or the floor strip is open — the walk code treats it as the walk target's identity |
| a hidden Woody is safe | `Hiding` | flag 4 | agrees |
| a busy neighbour | `IsSleeping`, `IgnoreWoody`, the blocking-animation clause | the +0x78 byte, set per script event | agrees in kind; which actions set it is open (the sender of the event was not traced) |
| doorways are safe transit | `IsPassingDoor`, `IsMovingToAdjacentZone` | not read | open |
| the Bed special case | movement is fatal while he is in bed | not read | open |
| the beating, then the level ends | `_catch`: the fear pose, `_finish_game`, the caught jingle | fcn.00474510, state 1, then state 5 or 2 by the quota | agrees |

### The anger, the score, the tricks

Read earlier and carried (docs/PC_ROUTINES.md "The anger and the bonus",
docs/PC_FIDELITY.md §7): the 12 Hz tick, the rage current/hold rule
(fcn.00438b90, fcn.00438a80), the +3 bonus while the current is above zero
(fcn.0047bd00, fcn.004357e0), the score clamp at 100 (fcn.00438070), the
face icon (fcn.00438550), the once-only quotas.

| rule | port | binary / data | verdict |
|---|---|---|---|
| trick scores | the mobile's TrickScore, six PC values patched (`levels/pc/*.overlay.json`) | tricks.xml `quota1` | agrees per level (`canon.py`'s named lists; the multiset line counts every mobile object with a TrickScore, so read the names) |
| angrytime per level and per trick | `PCAngryTime` overlays | level.xml `angrytime`, tricks.xml `angrytime` | agrees (data) |
| the S1 rage/bonus/hold | `pcprofile.s1_rage_*`, `Pawn.tick`, `play_angry` | fcn.00438a80, fcn.00438b90, fcn.0047bd00 | agrees (tests/test_hud_pc.py) |
| recipes, containers, rooms | the mobile data | objects.xml, level.xml | agrees where `canon.py` says "same"; the PC's extra `fro` room is the entrance hall |

### The routines and the scripts

The neighbour's day is compiled per level (fourteen classes, e.g. peep
fcn.00451f10 with 26 switch cases, sofa fcn.004545d0 with 25; the last case
is the beating). Each case yields through fcn.0045c600(next, current,
resume-after-interruption) — the third argument is the case to redo when
an urgent action interrupts a walk, not a catch hook. The order of the
GoTo / DoAction calls is in `tools/pcref/exe/nfh1_scripts.json`
(`tools/pcref/exe_scripts.py`). The stations the classes visit (their
`ICON`/`GOTO` names — sofa, binoculars; beer, sofa, toilet; detergent,
washing machine, drier, iron, rack, aquarium, vacuum; polish, cups, pipe,
phonograph, records, gun, hat, horn; ...) are the mobile routines' items
on all fourteen levels; the order of the switch cases is not the order of
the walk (112 lists the trampoline last and 113 starts at the valve where
the video and the mobile start at the chair), so the lap order stands on
the video (docs/PC_LAPS.md, the same order everywhere) and the durations
are the mobile data's (the open ceilings of 103–114 in
docs/PC_FIDELITY.md §7). Two data facts with no rating effect: the level
`trigger.xml` marks four object triggers `always` (105 mum_smeared and
phoneringing, 111 ironingboard_burn and dirtycarpet — the neighbour
reacts every pass) where every other is `once`, and `objects.xml` flags
fourteen objects `singleuse`; the mobile's ReuseAfterFix (102 sofa, 104
microwave, 105 piano, 108 sunbed and brush, 109 bed, 110 chair, 113
ladder) is a different notion (re-tricking after the fix) and neither
pays twice — both games' tricks pay once (fcn.0047bd00 skips a fired
trick; the mobile's OnTrickDone counts it once). The hunter
level's dog (fcn.0045bcb0) is an event-driven state machine: `whistle`
moves it to state 3 (from state 2) or 4, `wakeup`, `pause`, `resume` are
the other events; the port's whistle wakes the level's alerters
(`World.blow_whistle`), which is the same effect on the one dog of 114 —
the states' meaning is open.

### The alerters

The PC's pets are data plus one class. `generic/trigger.xml` gives every
level's `dog` and `chili` a `wakeup` behaviour on a noise of 1 or more in
their room and the neighbour an `alarm` on a noise of 2 anywhere in the
house (the pig level adds a `wakeup` for the sleeping neighbour himself);
the level files' `trigger.xml` hold the tricks' `nearobj` triggers (a
behaviour such as `banana_on_floor` or `dirty_microwave` once the
neighbour is near the tricked object). The noise sources in `objects.xml`
are the pets' barks (`bark1`/`bark3`, noise 2), the dog whistle (noise 1,
114) and the saw (noise 1, 102); every other action carries `noise="0"`
and animations have no noise attribute. The registrations reach the game
logic as `AddNoiseTriggerMsg` / `AddObjectTriggerMsg` (the loader at
0x43d90a, the receiver fcn.004509e0 → fcn.00450410) and the pet's class
(fcn.0045bcb0, shared by the dog and the parrot) is a five-state machine:
0 init → 1 `fallasleep` → 2 `sleep`, the `wakeup` event (or the whistle)
→ 3 `wakeup` with a 72-tick timer → 4 awake; every tick it compares the
rooms of `woody`, `neighbor` and itself (fcn.00444b00) and Woody's hideout
flag 4, and in state 4 barks (`bark1`/`bark3` by facing, then
`startle_woody`) while Woody is in its room and unhidden; the sleeping
state itself never looks. The neighbour's `alarm` is a switch case of the
level class (peep case 22: the `noise` icon, `fast` gait, a walk to the
noise, then the resume case 24) plus the engine's chain fcn.0047a690 (the
`search` action, the `dog_shout` icon). The level scripts also drive the
pets directly — `wakeup`, `pause`, `resume` and `whistle` events posted to
`chili`/`dog` at fixed steps (fcn.00468840, fcn.00459220). The briefings
say a walking Woody is noticed in the pet's room and sneaking is not
(`level_laundry`, `tutorial_3`: the right mouse button sneaks; the
`ChangeMoveTypeMsg` handler fcn.0044efc0 reads `sneaking="true"`); the
emitter that turns a non-sneaking walk into a room noise was not located
(the walk fiber and step helpers fcn.00475b30 / fcn.00444d30 / fcn.0047d030
post nothing).

| rule | port (the mobile's, docs/GAMEPLAY.md §6) | binary / data | verdict |
|---|---|---|---|
| the pet sleeps until Woody moves in its zone, sneaking excepted | `Alerter.CanSeeWoody` + moving, `IsSneaking` | `wakeup` on a room noise ≥ 1; the briefings' walking-vs-sneaking rule; the emitter open | agrees in kind; the PC pet also wakes on any noise-1 action in its room (the whistle, the saw) |
| the awake pet barks at a visible Woody | the alert animations, `AlerterDelay` | state 4: bark while Woody is in the room and unhidden | agrees |
| the bark brings the neighbour | `Rottweiler.HearAlerter` → `SurpriseFar` | the bark's noise 2 → the house-wide `alarm`: the `noise` icon, the fast walk, `search` | agrees in kind |
| the whistle | `World.blow_whistle` wakes every alerter | the level script posts `whistle` to the dog: state 3 (from 2) or 4 | agrees for 114's one dog |
| the pet calms when the neighbour arrives | `OnRottweilerEnter` → "poor" | the `poor1`/`poor3`, `whine1`/`whine3` animations exist; the transition was not read | open |

## Season 2

Read earlier and carried (docs/PC_ROUTINES.md, the Season 2 sections): the
status struct (+0 coins, +8 mincoins, +0x14 lives, +0x18 respawn timer,
+0x1c rage, +0x24 ticks, +0x28 collapse), the trick accounting
fcn.1000140b, the gauge of 100 000, the decay of leveldata's `time` per
tick (fcn.10044234), the COLLAPSE! board fcn.10040226 / fcn.10040205, three
lives (fcn.10044234) and one taken per catch (fcn.10042471), the script
helpers.

| rule | port | binary / data | verdict |
|---|---|---|---|
| the level completes when every trick is done | `all_done` (completed == total) | fcn.10041086: status +0xc == +0x10 (done == `reachable`) → the actors are stopped (fcn.1004ba02 → fcn.100450bf), the board | agrees; `reachable` 4/5/5/6/5/6/7/7/7/8/8/9/9/6 is the port's `total` (data) |
| the pass mark | `won` at WinningTricksCount | leveldata `mincoins`, checked when a flagged request comes in (byte +0x6f, set by the virtual at 0x1004717f — the menu's exit-level path, `mm_exitlevel`; coins ≥ mincoins passes) | agrees in effect: `mincoins` equals the mobile's WinningTricksCount on 13 levels and the 211 overlay carries the PC's 5 (data); the PC lets a player leave a level early through the menu, the port's menus do not model that |
| the catch | `_catch`: fear, the beating, `_respawn` | the catch fiber (vtable 0x100ab258 slot 10, entry 0x100061dc): Woody's `fear1`/`fear3` facing the catcher (0x10006510), the catcher's `fight` action (objects.xml: `fight_woody` with `fly_away_neighbor` / `fly_away_mother` on Woody, who becomes invisible), then case 4 places Woody 900 px above the respawn spot (0x10006336: y = top − 900, x = the midpoint) and plays the `respawn` action (the fall), case 5 takes a life (fcn.10042471) | agrees: the spot is the level's start area on video (docs/PC_FIDELITY.md §2.5) and the port's entrance location |
| the respawn timer | Woody is controllable as soon as he reappears | the catch (fcn.10042471 at 0x100424b6) copies leveldata's `respawntime="60"` into status +0x18, the tick counts it down (fcn.10044234 at 0x10044725), and while it runs the action runner fcn.1003cc45 drops the actions whose actor is `woody` (0x1003ce61, 0x1003ceae: the timer read fcn.10040123) | read: 5 s without Woody's actions after the respawn; open whether a walk command is among them, so not carried |
| lives out | game over | fcn.10042471: lives − 1, below zero → the failed path (0x100424d8) | agrees |
| the gauge, the decay, the board, the clock | `pcprofile.s2_rage_tick`, `calculate_score` | fcn.10044234, fcn.10040226 | agrees (docs/PC_ROUTINES.md) |
| the trick amounts | nine PC values in `levels/pc/*.overlay.json`, the rest the mobile's | tricks.xml `coins` / `rage` | agrees (data, the overlays' sources) |
| detection ("sees Woody") | the mobile's predicate | the level tick (fcn.10044234 at 0x100445f1) runs fcn.1003fc90 over a table of watch entries (an actor, a target, mode bits at +0x1c/+0x1d) and evaluates each with fcn.1003f573: the actor must carry flag 0x20, neither party flag 4 (the hideout flag — set on hiding, e.g. 0x100067e9, cleared by the `leave` action at 0x10006abc), the rooms compared through fcn.10040a7d (the record of the actor's +0x20 name), and in one mode a vertical distance below 15 (0x1003f7d0); a true entry fires an event object (fcn.1003f86d, fcn.1003f972, fcn.1003fa6b, fcn.1003fc6e — no strings) | agrees in kind with the mobile's zone containment plus the hiding exemption; open: which entries the levels register (scripts or engine) and what the reactions do — the catch itself is the catcher's `fight` action, issued by the level class's own method (the `fight` string sites, one per level, e.g. 0x100149dc) |

## Not verified

- The frame pacer: the timer at `[app+0x50]` (fcn.00402cc0, fcn.00402d30)
  is an fps counter over 0.5 s windows, the only `Sleep` is the loading
  screen's, no `SetTimer`/`timeSetEvent`; the one 83 ms constant in the
  binaries (GFXEngine fcn.10003420, `GetTickCount`) is a button widget's
  auto-repeat interval, its 1000 ms the hold timer, and fcn.100092a0's
  167 ms the caret blink — what makes the level tick 12 Hz is not
  located. The 12 Hz itself stands on the clock, the GUI's
  divisions by 12 and the mercury (docs/PC_ROUTINES.md).
- Season 1: which neighbour actions clear or set the +0x78 byte (the
  script event's sender); whether the position object of the catch is
  the room or the floor strip; door transit; the noise a walking Woody
  makes for the pets' `wakeup` trigger (the briefings state the rule,
  the emitter was not found).
- Season 2: which watch entries the levels register with the trigger
  evaluator fcn.1003f573 and what its reactions run; what the respawn
  timer gates.
- The jingle table's index (0..3) is the dialog's outcome, not the level
  state; which outcome maps to which index was not traced beyond the
  table itself.

## What this pass changed

- `runtime/pcprofile.py`: `S1_PERFECT_RATING = 90`, `s1_perfect`,
  `s1_result` — the PC's captions and threshold, with the addresses.
- `runtime/world.py`: `calculate_score` captions a Season 1 level under
  the profile with `s1_result` (BRILLIANT!, SUCCESS!, TIME'S UP!,
  FAILED!) after the mobile band.
- `runtime/app.py`: the saved `perfect` flag of a Season 1 level uses the
  90 mark under the profile.
- `tests/test_hud_pc.py`: the captions and the threshold.
- `docs/PC_ROUTINES.md`: the level-end paragraph rewritten to the state
  machine (the earlier "0 = caught, 1 = failed, 2–3 = success" was the
  jingle table read as the level state).
