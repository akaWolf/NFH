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
| a busy neighbour | `IsSleeping`, `IgnoreWoody`, the blocking-animation clause | the +0x78 byte is zero from the actor's constructor (fcn.00448320, 0x44848d) and changes only in the level's slot-49 handler (0x440c7f–0x440c87: `sete` — a toggle), which only the script interface's slot-207 stub (0x405f10 → 0x405f3d) reaches; no compiled code calls that slot (no `[vtable+0x33c]` call in game.exe), so the byte stays zero in every level and the catch on sight is never suspended | differs in kind: the PC neighbour has no busy or sleeping window — the mobile's `IgnoreWoody`/`IsSleeping` clauses are the remaster's; carried since 2026-09-17: `pcprofile.sees_while_busy` — the catch is the room and the hideout flag alone; 109's neighbour asleep in his `neighbor_hideout` bed sees a walking Woody (noise 1) and not a sneaking one |
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
| the action durations | the mobile clips (the neighbour's stations since 2026-09-17 at the PC station's ticks: `PCUseSeconds` in the overlays, `tools/pcref/pc_durations.py`) | objects.xml `time="N"` is N ticks of the 12 Hz level tick (the fiber countdown `dec [obj+0x28]` per tick, fcn.00474a20 / fcn.00475850 / fcn.00478120) and `time="auto"` the animation's frames, one a tick — a door 9–25 ticks is 0.75–2 s, the wash 59 ticks 4.9 s a visit; GFXEngine has no sprite timer of its own | read; `tools/pcref/canon.py` now prints the PC action seconds at 12 a second (it divided by 20 before, the tick's earlier misreading) |
| the walking speed | the mobile's `Speed` 1.25 u/s (Season 1), 1.0 (Season 2), `SpeedSneaking` 0.65 | objects.xml `<speed name=… speed=… start=… noise=…/>` per actor and gait animation (`SetSpeedMsg` → fcn.0044dd20: +8 speed, +0xc start, +0x10 noise); the walk fiber fcn.00475b30 waits one tick between steps (0x476148) and fcn.0047c7f0 moves the actor by the record of the facing animation (fcn.004459c0): `speed` px a tick plus `start` once when he leaves the standing animation `ms`, clamped at the target (0x47cc9f–0x47cd59) — the neighbour 8 px a tick along the floor, 3 up and down, running 18/9, Woody 17/6, sneaking 5/2, the dog 4; Season 2 the same for the neighbour, Olga and the mother (GameLogic.dll's walk step fcn.10009215, one axis a tick; the stair records 8/5 are never selected — nothing writes the gait 7) | differs: at the mobile scene's 96 px a unit (the house of 101: the living room's 586 px path ↔ the 6.8 u zone less the collider's margin, the hall 740 ↔ 8.4, the kitchen 412 ↔ 5.1; the neighbour's start 504 px ↔ −1.75 u within 9 px) the PC neighbour walks 1.00 u/s to the mobile's 1.25, Woody 2.1 to 1.25, sneaking 0.62 to 0.65; Season 2's scenes are 93–100 px a unit (208: the neighbour to Woody 338 px ↔ 3.69 u, the mother to Woody 446 ↔ 4.49; 201: the bridge to the right rail 1460 ↔ 14.5), so there the PC neighbour's 96 px/s is the mobile's 1.0 u/s — the remaster kept the Season 2 walk, sped Season 1's neighbour up by a quarter and halved Woody (2.0–2.1 u/s on PC in both seasons, 1.25 and 1.0 on the mobile) — carried since 2026-09-17: `pcprofile.walk_speed` moves every pawn at its floor record on a walk (whatever the direction — the mobile scene's depth offsets to its items are the remaster's; the axis-by-axis mix over them made the Season 2 laps 20-30 % longer than the PC video's) and at the vertical record on a door approach (the DOOR_CLIMB / DESCEND states, the PC's ~50 px climb to a back door), `tests/run_tricks.py` dodges by the same paces; the lap model below checks the climbs; since 2026-09-23 the Season 1 neighbour takes the gait the level class sets (+0x38, the index into the facing tables 0x51b5f0 / 0x51b648: 0 mg, 1 sn, 2 mr, 3 mrwc, 4 mgbowling1, 5 skate1, 6 piewalk — directly or through the step fcn.0045f6b0, run by 0x479660) before a GoTo and back to 0 at the next case: the run at mr1 18 / mr0 9 on every `noise` case (the pets' alarm, 107-114), the toilet and first-aid rushes (102, 103, 105, 106, 108's rinse), the antenna's shout (101, 102), the extinguisher's fetch and the way back to the barbecue (110), 113's runs to the main valve after the flood and to the heat valve after the hot heater and 112's way back in after the skate; the skate's slide at 18, the bowling ball's carry at 9 (`Routine._pc_runs`, `Pawn._pc_gait`, `pcprofile.GAIT_PX_PER_TICK`); the mobile's other urgents (111's vacuum and carpet) the PC walks, and the port shows the walk set on them; Season 2 (GameLogic.dll +0x3c, the level scripts' writes of 2 before a walk): 206's pillow errands, 210's run to the Mother, 211's phone and WC, 207's Olga to the sand castle carried, the rest open (docs/PC_FIDELITY.md, "Season 2's runs") |
| door transit | the pawns' door clips at 10 fps (Woody 16/13/10 frames out and 25/22/16 in by the left/right/back door, the neighbour 20/20/12 and 20/20/13); a flat door plays both at once, a walk-up door one after the other; the zone changes at the far clip's end | every Season 1 door is a `<door>` of the level's objects.xml with an `enter` action on the near door and a `leave` on the far one, `time` ticks each and the same on every door of a type in all 14 levels: the neighbour 19 + 19 (side), 11 + 22 (back), Woody 15 + 23 (right), 18 + 24 (left), 9 + 25 (back); game.exe composes the pair as one step list (fcn.00478030 over fcn.00477ed0, the near `enter` then the far `leave`), and the PC video of 110 puts the bedroom-to-living-room back door at ~3 s from the neighbour's arrival to his step out — the sum, not the longer clip; the actor is placed at the far door's hotspot for the `leave`, and the room pointer follows the placement (fcn.00448d70) | differed in three ways, all carried since 2026-09-17 (`pcprofile.door_ticks`, `doors_sequential`, `door_warp_early`): the two clips run one after the other through a flat door as well, each strip plays at the rate that lasts its PC ticks (the neighbour's far back-door strip has 13 frames for the PC's 23), and the pawn's zone flips at the far clip's start, where the PC's room pointer does — a pawn inside a door clip is caught, and catches, by that room (`World._detect_common`'s PC branch drops the door term). Season 2's 126 `<door>` objects carry hotspots (`<actor>`, `<actor>_in`, `<actor>_out` per actor) and 8 of them `enter`/`leave` actions (211's cabin, 212's and 213's topright/midright, 214's bridge): a pair is one step of GameLogic.dll (vtable 0x100ab1b8) — the walk to the near `<actor>_in`, then out of every room the movement straight to the far `<actor>_out` (or the enter, the placement, the leave), the far room set there and the run down to its floor (docs/PC_FIDELITY.md, "Season 2 walks") | differed: the mobile walks its transitions at the floor pace (a stair ~3 s where the PC's is 9-11 s for the neighbour); carried since 2026-09-23 (`PCPass`, tools/pcref/pc_walks_s2.py): the hop stands the `in` run, walks its complex steps for the straight movement's ticks (the zone flips at `<actor>_out`) and stands the `out` run; the back doors' climb, strips and descent last the `in` run, the two clips and the `out` run; since 2026-09-24 the `out` run is stood indeed (it had been lost with the step's hand-over), no floor record caps the pass, the floor between the stations and the doors lasts the PC's |dx| (PCPass `xi` / `xo`, PCApproach `x` and `tx`), and the pair is claimed as the step starts (flag 8 on both doors, 0x1000339d; freed at `<actor>_out`, fcn.10003454) — the next actor stands where it is |
| the lap's timing | the mobile clips and speeds through the port's routine engine | `tools/pcref/lap_model.py`: the walker's lap tokens (ICON / GOTO / ENTER / LEAVE / ACTION along the level class's cases, `LAPS=1 routine_order.py`) timed from the data — 8 px a tick along the floor and 3 px up and down the room to the objects' `neighbor` hotspots, the doors' standing points (the door type's hotspot + level.xml `position`) with their `enter` and `leave` ticks, the actions' `time` or animation frames — against the PC video's natural laps (docs/PC_LAPS.md): 101 34/32 s, 102 29/28, 105 44/40, 108 90/94, 109 104/113, 110 60/59, 112 143/155, 113 172/191, 114 147/168 — nine within ±12 %; 103 28/42, 106 60/108 and 107 37/54 fall short, where the neighbour waits on the object (the bath) or the video's lap carries a trick; 111 114/122 (the first lap — the 219 of 2026-09-06 paired the second, tricked lap; the washer and the drier are their three DoActions, no wait step) | the walk, the doors and the actions hold together as a model on ten laps; the three short ones are open |
| the Season 2 lap's timing | the mobile clips and walks; the PC videos' stays (span less the port's walk) since 2026-09-17 | `tools/pcref/lap_model_s2.py`: the level script's untricked lap (GameLogic.dll's step chain) timed from the data — the DoActions' `time` or clips, the hideouts, the bars' ticks, the GoTo's route (the Dijkstra of fcn.1000a421), the door passes and the station runs of the walk step — 203 105 s, 208 85.5, 209 104, 211 85, 212 124, 213 123, 214 90.3, 202 80.7 and the wait against the video's 84-112, 86, 97, 85, 113, 136, 91, 70-94 | carried 2026-09-23: the walk (the door passes, the station runs, the routes between stations: `PCPass` / `PCApproach`, tools/pcref/pc_walks_s2.py) and the code's stays on 203, 208, 209, 211, 212, 213 and since the same night 214 and 202 (210, 205, 207 and 204 since 2026-09-24, their laps from her `order`, from his play, from his dive and from the gong's leave) (pc_durations_s2.py CODE; 214 with its Mother's script and the pistol's poll, docs/PC_FIDELITY.md "214's handshake"; 202 per clip with his wait for Olga's sub and the shark paid at the sea's `enter`, "202's mat and swim"), the video's re-derived against the PC walk elsewhere; the port's idle legs within about a second of the model's (208's lap 82.5 s); since the same evening every walk's route is the path finder's (`world.pc_route` over the zones' PCRoom, from the station's hotspot or the pawn's x on the floor line — the 338 station pairs reproduced) and Woody's runs to his items' `woody` hotspots are carried (PCApproach `Woody`, 204 items); the idle laps under it (2026-09-24, the stays the walk writer had dropped since the routes restored): 203 99.5 s, 208 82.5, 209 100.8 (the model 105 with the fakir's `spit`), 211 80.8, 212 119.4, 213 126.6, 214 85.3 (the model 90.3), 202 81.7 (the model 80.7 and the wait), 210 98.7 call to call (its call by code since 2026-09-24: her naps and checks, his chair's bar and wakeup, the call, the run to her chair, the order and Fifi's tickle; ~101 with the PC's walks, the video's first lap 107), 205 101.6 (its table by code since 2026-09-24: the talk that calls Olga, the 72-tick wait, the play once she is there; the model 111.9, the video 102), 207 100.0 (its board by code: the dive once the Mother sits in her chair, she in it while he is in the pool room; the model 106, the video 107), 204 84.3 (its stays by code; the model 92.8, the video 81) — within 6 % of the model but 204 and 205, whose videos sit with the port (docs/PC_LAPS.md) |
| the S1 rage/bonus/hold | `pcprofile.s1_rage_*`, `Pawn.tick`, `play_angry` | fcn.00438a80, fcn.00438b90, fcn.0047bd00 | agrees (tests/test_hud_pc.py) |
| the S1 trick step's order (the action, the fire, the shout, the repair) and the shout's choice | `play_angry` (AngryHard 6.8 s after every trick, the mobile fix clips, the tricked clip paced to the normal stay) | fcn.0047bd00 as slot 2 of vtable 0x4e5944 (the OBJ2 step fcn.0047c290, the five-argument fcn.0047c320), the shout tables 0x51b584-0x51b5a4, fcn.0047ae70's repair, objects.xml's tricked actions | read 2026-09-22 in the code end to end (docs/PC_ROUTINES.md "The fire's tail"; the sites decoded by tools/pcref/fire_sites.py, the register-valued flags through the fibers' prologue constants): the order agrees except at the five-argument sites (the fire before the soap fall, the hair and the towel clips; the four-argument ones fire after their clip); the shout (7.67 s on a bonus, 2.1-3.75 cold, none at flags 2 or 3), the repair and the tricked action lengths differ — carried on every Season 1 level since 2026-09-22 (`World.s1_fire`, the routine's PCFireAt, the paced shout, fix and stand: docs/PC_FIDELITY.md "Season 1 reactions"; the stands read off the level classes' case chains by tools/pcref/trick_branches.py, the keys by tools/pcref/pc_reactions.py); the three engine-side steps of the reaction sequences (listener slot 26 = the GUI's face icons and a tick, slot 65 = the slip sound sfx_na_slip_up1.wav plus the soap's flag 0x20, the cactus clock's SwitchObjects job) are read in GFXEngine.dll and take no time |
| recipes, containers, rooms | the mobile data | objects.xml, level.xml | agrees where `canon.py` says "same"; the PC's extra `fro` room is the entrance hall |

### The routines and the scripts

The neighbour's day is compiled per level (fourteen classes, e.g. peep
fcn.00451f10 with 26 switch cases, sofa fcn.004545d0 with 25; the last case
is the beating). Each case yields through fcn.0045c600(next, current,
resume-after-interruption) — the third argument is the case to redo when
an urgent action interrupts a walk, not a catch hook. The order of the
GoTo / DoAction calls is in `tools/pcref/exe/nfh1_scripts.json`
(`tools/pcref/exe_scripts.py`). The walk itself is read from the code by
`tools/pcref/routine_order.py`: every case ends in a yield —
fcn.0045c600 / fcn.004706a0 / fcn.0045e640 (next, current,
resume-after-interruption) — so the lap is the chain of `next` values
from case 0, simulated with no trick fired (IFVARIANT, OBJ3, string
compares and the class's own helpers false, the engine's waits true, the
class's byte fields at their current value, a case that returns without
yielding treated as a poll that flips). The laps by code, against the
mobile routines the port carries:

| level | the lap by code (game.exe) | the mobile routine |
|---|---|---|
| 101 | sofa → binoculars → sofa | Sofa, Binoculars |
| 102 | sofa → beer → sofa; the toilet (case 7) only with the laxative flag `[this+0x1c]` after the beer counter `[this+0x14]` | Sofa, Beer |
| 103 | candle → cake → mailbox → candle; the first aid only after the mailbox trap (IFVARIANT anc/mailbox) | Candle, Cake, Cake, LetterBox |
| 104 | apple pie → microwave → whipped cream → basin, aftershave → apple pie | ApplePie, Microwave, WhippedCream, ApplePie, Deodrant, AfterShave, Sink… |
| 105 | piano (score) → football → flower → piano; the toilet only after the flower trick | Piano, Football, Window, PlantStink |
| 106 | photo album → candy → milk bottle → bath tub → album; the toilet through a class helper, the towel off the lap | PhotoAlbum, Candy, Pudding, BathTub ×2, Towel |
| 107 | painting → camera → magnesium → camera → potter's wheel → statue, footstool → painting | Drawing, Camera, Magnesium, Camera, DieselChair, Generator, FootStool |
| 108 | toothbrush → coffee → folding chair → ewer → flower → ewer → coffee … | ToothBrush, CoffeeMaker, Shezlong, WateringCan, Plant, WateringCan |
| 109 | teeth → bed, sleep → alarm clock → teeth → pig key → milk bottle → pig → milk bottle → cookies → parrot → pig key → teeth | Teeth, Bed, AlarmClock, Teeth, PigKeys, PigMilk, Pig, PigMilk, CornChips, Chili, PigKeys |
| 110 | meat bowl → beer → bbq → plant, spray → bbq → table → wine → meat bowl | SteakMeat, Beer, BBQ, Spray, BBQ, SteakChair, SteakWine |
| 111 | detergent → washing machine → tumble drier → ironing → laundry rack → aquarium → laundry rack → ironing → detergent | Detergent, WashingMachine ×3, Drier ×3, Iron, Airer, FishTank, Airer, Iron |
| 112 | book → aquarium → yoga mat → book → trampoline → home trainer → mixer → expander → barbell → skipping rope → book | YogaBook, FishTank, Yoga, YogaBook, Trampoline, Bicycle, Mixer ×2, ChestExpander, Weights, Rope |
| 113 | chair kit → power tool → valve → heater → basin → valve → fuse → ladder → fuse → chair kit | ChairAssembly, AngleGrinder, ValveMain, Radiator, Sink, ValveMain, FuseBox, Ladder, LadderDrill, FuseBox |
| 114 | polish → cups → polish → smoke → phonograph → records → phonograph → smoke → gun → hat → horn → polish (the phono chain on the record playing, OBJ3 lir/phono_play) | Polish, GoldCup, Polish, Pipe, Gramaphone, CDs, Gramaphone, Pipe, Gramaphone, Shotgun, Hat, MedalBox, Hat, Horn |

The same order on every level; the stations' durations are the PC data's
since 2026-09-17 (tools/pcref/pc_durations.py: every visit, a toggling
station's prime and unprime legs included; 111's machines their case's
three DoActions, one per leg, since 2026-09-23; the walker follows the
objects' presence — isObjectPresent, fcn.00479ff0, over level.xml and the
switches — so 111's second ironing irons the clothes case 8 gave the
board, 113's valve is switched off and on and 114 visits the phonograph a
third time to close it), and the video laps of docs/PC_LAPS.md are now
only the timing reference. Two data facts with no rating effect: the level
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
emitter is the gait itself: Woody's walking `<speed>` records `mg0`–`mg3`
carry `noise="1"` and his sneaking `sn0`–`sn3` `noise="0"` (generic/objects.xml;
every other actor's records are 0), so a walking Woody is a noise of 1 in
his room, a sneaking or standing one none — the pets' `wakeup` threshold
exactly, below the neighbour's alarm at 2. The port's rule for a sleeping
pet (moving and not sneaking, in its zone) is the same test; the reader of
the record's noise field (+0x10 in SetSpeedMsg's record) is not traced.

| rule | port (the mobile's, docs/GAMEPLAY.md §6) | binary / data | verdict |
|---|---|---|---|
| the pet sleeps until Woody moves in its zone, sneaking excepted | `Alerter.CanSeeWoody` + moving, `IsSneaking` | `wakeup` on a room noise ≥ 1; the briefings' walking-vs-sneaking rule; the emitter is the speed record's `noise` | agrees in kind; the PC pet also wakes on any noise-1 action in its room (the whistle, the saw); a walking Woody posts noise 1 to his room every tick of the walk (objects.xml `<speed name="mg…" noise="1"/>` on woody, 0 on his sneak `sn…` and on the neighbour's gaits; the walk step's tail 0x47ced5–0x47cf36 → fcn.004729c0, skipped under actor flag 0x100) |
| the awake pet barks at a visible Woody | the alert animations, `AlerterDelay` | state 4: bark while Woody is in the room and unhidden | agrees |
| the bark brings the neighbour | `Rottweiler.HearAlerter` → `SurpriseFar` | the bark's noise 2 → the house-wide `alarm`: the `noise` icon, the fast walk, `search` | agrees in kind |
| the whistle | `World.blow_whistle` wakes every alerter | the level script posts `whistle` to the dog: state 3 (from 2) or 4 | agrees for 114's one dog |
| the pet calms when the neighbour arrives | `OnRottweilerEnter` → "poor" | the `poor1`/`poor3`, `whine1`/`whine3` animations exist; the transition was not read | open |

## Season 2

Read earlier and carried (docs/PC_ROUTINES.md, the Season 2 sections): the
status struct (+0 coins, +8 mincoins, +0x14 lives, +0x18 respawn timer,
+0x1c rage, +0x24 ticks, +0x28 collapse), the trick accounting
fcn.1000140b, the gauge of 100 000, the decay of leveldata's `time` per
tick (the level update, 0x100447c4), the COLLAPSE! board fcn.10040226 / fcn.10040205, three
lives (the level update, 0x100445b7) and one taken per catch (fcn.10042471), the script
helpers. The level update is the GameLogic interface's slot 2 at 0x100442b3; the notes
before 2026-09-24 called it fcn.10044234, the name the radare2 dump of that day gives the
actors' job pass the update calls at 0x100445f8.

| rule | port | binary / data | verdict |
|---|---|---|---|
| the level completes when every trick is done | `all_done` (completed == total) | fcn.10041086: status +0xc == +0x10 (done == `reachable`) → the actors are stopped (fcn.1004ba02 → fcn.100450bf), the board | agrees; `reachable` 4/5/5/6/5/6/7/7/7/8/8/9/9/6 is the port's `total` (data) |
| the pass mark | `won` at WinningTricksCount | leveldata `mincoins`, checked when a flagged request comes in (byte +0x6f, set by the virtual at 0x1004717f — the menu's exit-level path, `mm_exitlevel`; coins ≥ mincoins passes) | agrees in effect: `mincoins` equals the mobile's WinningTricksCount on 13 levels and the 211 overlay carries the PC's 5 (data); the PC lets a player leave a level early through the menu, the port's menus do not model that |
| the catch | `_catch`: fear, the beating, `_respawn` | the catch fiber (vtable 0x100ab258 slot 10, entry 0x100061dc): Woody's `fear1`/`fear3` facing the catcher (0x10006510), the catcher's `fight` action (objects.xml: `fight_woody` with `fly_away_neighbor` / `fly_away_mother` on Woody, who becomes invisible), then case 4 places Woody 900 px above the respawn spot (0x10006336: y = top − 900, x = the midpoint) and plays the `respawn` action (the fall), case 5 takes a life (fcn.10042471) | agrees: the spot is the level's start area on video (docs/PC_FIDELITY.md §2.5) and the port's entrance location |
| the respawn timer | Woody is controllable as soon as he reappears | the catch (fcn.10042471 at 0x100424b6) copies leveldata's `respawntime="60"` into status +0x18, the level update counts it down (0x10044725), and while it runs the action runner fcn.1003cc45 drops the actions whose actor is `woody` (0x1003ce61, 0x1003ceae: the timer read fcn.10040123) | read: 5 s without Woody's actions after the respawn; open whether a walk command is among them, so not carried |
| lives out | game over | fcn.10042471: lives − 1, below zero → the failed path (0x100424d8) | agrees |
| the gauge, the decay, the board, the clock | `pcprofile.s2_rage_tick`, `calculate_score` | the level update 0x100442b3 (its status tick 0x10044710-0x100447f1), fcn.10040226 | agrees (docs/PC_ROUTINES.md) |
| the reaction to a trick | `pcprofile.s2_reaction_seconds`, `World.play_angry`: the mobile's angry set paced to the SHOUT's action | fcn.1000f977: the step's last parameter picks [shout2_light] / [shout2, shout2] / [shout2_hard] x3 / [shout2_high] — the static initializers 0x1007b54b-0x1007b61d fill 0x100df45c / 0x100df434 / 0x100df450 / 0x100df41c — after a first pick of [freakout1, freakout2, freakout3] (0x100df43c), which the SHOUT element (vtable 0x100ab99c, update 0x1000d751) plays instead once the status byte +0x28 is set: the credit sets it as the rage reaches 100 000 (0x10001500) and nothing clears it; the actions' animations (generic/objects.xml, anims.xml) 26 / 26 / 85 / 26 frames, the freakouts 37 / 38 / 63 | **fixed 2026-09-24**: the tables had been read as mixed (1: shout2 or shout2_hard, 2: shout2_hard or shout2, 3: the freakouts) and the freakout after the overflow was missing (`Pawn.pc_rage_full`) |
| a tricked visit's credit | `Routine.pc_credit_timer` / `pc_credit2_timer`, `World.pc_s2_credit` / `pc_s2_linked_credit` | fcn.1000140b credits each named record of a playing action on the tick its `time` equals the action's count (0x10001455), from the action step's playing state (0x1000254d) and its end (0x100025bf): 202's rail over the eels' pond pays bridge_crash 8 ticks into the crash and bridge_electrify 5 into the electrify, 22 ticks apart | **carried 2026-09-24**: PCCreditAt / PCCreditAtLinked for the item's own record, PCLinkedPaysAt for the linked trick's (the ladder's linked arm paid apart, `_s2_credit(part=)`); the done count is the trick table's credited records (fcn.100522e6, fcn.1005225b), so the pair's completion is booked with its last record (`Item.pc_done_due`) |
| a tricked step with no SHOUT of its own | `code_stays_tricked` (`TRICKED_CONT` 'steps', `TRICKED_VIA`, `TRICKED_ROWS`), PCShout -1 | the step hands over to its continuation, which plays the SHOUT and the repair: 204's gong 0x10032f52 (SHOUT 3), 205's skis 0x10024fc2, 211's sweets 0x10030dc2 / 0x10030d0f / 0x10030b9d (the toilet run, wcright's `puke` 40 ticks), 214's wheel from the door 0x1003af18; 206's weights and dynamite at their rows; 210's dog basket alone plays none; 214's door is visited tricked in neither game (CaptainDoorBehavior's ExtraItem, Item.cs:2606-2623) | **carried 2026-09-24**: the stand to the continuation's SHOUT, its level and repair; -1 skips the reaction; 212's ledge (the aux script's parrot shit, fcn.10034e05) and 213's bull (the step's byte +0x28 through eax, 0x10038ab1) read to their records later the same day |
| the co-actor's hit | `World.pc_affect_early`, `Routine._hit_begin`, PCHitSeconds | the action's behavior (hurt_neighbor …) fires as it starts; Olga's / the Mother's script runs her to him (gait 2) and plays the generic `fight` (fcn.1000eb19: 42 / 39 ticks; olga_fight / mother_fight on him), his handler then sets the SHOUT step (204 0x10032b6f, 207 0x1001596a, 210 0x1001a379, 214 0x1003ba90 / 0x1003b677 / 0x1003b328) | **carried 2026-09-24**: she sets off as his tricked use starts and fights on arrival (DoAction's job goes on her queue alone, fcn.10049216; the queue fcn.100492a8 locks no other actor; the job posts its behavior in its state 0, fcn.100018a6), his SHOUT at his use's end or her fight's start, whichever is later, alongside the fight; `always` (Loader.dll's action record +0x24, default "true") is true on every action |
| 206's pad and harpoon | `Level206RoutineBehavior._pc_gate`, `Item.pc_masked`, PCTrickArm / PCTrickFire, PCExtraPaysAtLinked | the load step 0x1002e3df's IfVariant ramp / ramp_manip arms the shot after the take (0x1002e27f -> 0x1002df9b shootrabbit 81 / 0x1002e0fd rubberrabbit 73: records 40, 45, 50), the Mother's fight latch ([step+0x24], 0x1002de6a), SHOUT 1, the ramp's repair 19; the shoot step 0x1002d948 asks nothing; the take step's rubber branch 0x1002da29 (rubberbear 69, harpoon_rubber 40, SHOUT 1) goes on to the put 0x1002d578, which switches the harpoon back | **carried 2026-09-24**: the pad fires at the shoot after an armed load, else the shoot plain; the rubber on at the take fires through the pad's DependsOn at the shoot (the take marks GotTricked), a later one is dropped at the put; harpoonAux off; the ExtraCoin206 at its tick |
| 211's rush | the after-toilet angry of the rush's item, PCToiletPaysAt, PCHitSeconds | 0x10030dc2's puke at wcright (40 ticks, wcright at 27, behavior puke on Olga) -> her handler 0x100318ce: `mad` (34), her fight step 0x1003183a (42; olga_fight -> his latch +0xd, 0x100301fb) -> 0x10030d0f SHOUT 1 -> 0x10030b9d the sign's repair (walk 34, repair 24) | **carried 2026-09-24**: the angry after the wc (the mobile loses it, ActionManager.cs:597), the record in the puke, her hit 3.0 s after it; differs: the repair at the wc, the walk on from there |
| the camera and the pose elements | instant (`INSTANT`, E2f40 'instant') | Ef51a (fcn.1000f51a): flag 8 only for a nonzero last argument, then it waits while [level+0xc] != 0 (Woody's mini-game); the pose element fcn.10014c5c / fcn.1000de51 (vtable 0x100ab990, update 0x1000cfaa) returns 1 at once; Ef779 (0x1000ce9c) likewise | **carried 2026-09-24**: 207's sand castle over the hedgehog's towel runs its linked continuation (0x1001513f: Olga's `n_lift`, the billboard's `enter` 56 ticks, SHOUT 2) — PCHitSecondsLinked, PCResumeHeadSeconds, PCExtraCoinLinked |
| the result screen | `COLLAPSE!` on an overflow, else the mobile's EXCELLENT / GOOD / PASSED | GUIEngine 0x10001536–0x10001652 fills `dialogs/gameover.xml` (`rating`, `coinsscore`, `lifesscore`, `bonusscore`, `timescore`, `wholescore`) from the status struct (eleven dwords, `push 0xb` at 0x1000515f) and a failed flag: `failed` (FAILURE), else `bonus` (COLLAPSE!) on the collapse byte +0x28, else `perfect` (GOOD JOB!) when coins +0 equal the total +4, else `success` (SUCCESS!) — `generic/strings.xml` | **fixed 2026-09-16**: `pcprofile.s2_result` under the profile; the rows were already the board's |
| the trick amounts | nine PC values in `levels/pc/*.overlay.json`, the rest the mobile's | tricks.xml `coins` / `rage` | agrees (data, the overlays' sources) |
| the routines | the mobile ActionManager orders | `tools/pcref/routine_order_s2.py`: each level script is a chain of step functions handing over through `[obj+8]`; followed with no trick fired, the laps by code are 201 rail → water puddle → captain's cap → buffet → water puddle (mobile: CaptainHat, Buffet, WaterPuddle, DeckRail, WaterPuddle), 203 bike → stage → image → toilet → melons (Microphone, ToiletPaper, ToiletFlush, Watermelon, Bicycle), 205 sand lion → mat → ping-pong → water skis → chef → tyre → firework, rocket → sand lion (OlgaMatBeach, TableTennis, WaterSkiis, Chef, Rockets, SandSculpture), 206 Fifi → blanket → Fifi → ramp → harpoon → dumbbell → Fifi → dynamite bag (DogFifi, DeckChair, Pillows, LaunchPad, Harpoon, Weights, Fifi, Dynamite…), 208 statue → platform → shoe cleaner → elephant (IndianPlatform, ShoeMachine, AngryElephant, ArmsBowl), 211 diving → dish → rod → boat → life vest (Sweets, FishingRod, LifeBoat, LifeJacket, DivingGear), 209 cow → ride → fakir → shoe mat → coal → trough → fuel (FireFakir, HotShoe, TadjMahal, HotShoe, Coal, IceCream, Cow), 212 cliff → parrot → boat → hands → whip → cigars → bank → bull ride (PreAztecThrone, AztecThrone, Whip, CigarBox, SleepBench, MechanicalBull, PreParrotLedge, ParrotLedge), 213 limber wall → carnivore → tortilla → piñata → bull-ride controls → washing tub (LiveBull, PlantCarnivore, Tortilla, BoatPicnic, Pinata, MechanicalBullControls, CementBath) | agrees in order on the nine laps that close; 202, 204, 207 and 214 end at a step that polls an action (202's `waitsea` swim, 0x10022534: the step stores no next and is re-entered until the level's event moves it on) or an event callback, 210 re-arms its deck-chair step — the order past those steps is open |
| the dexterity mini-games | `_dexterity_gate` + `DexterityState`: the remaster's lockpick game (fill 20 → 85 %) | objects.xml's `game` objects (one a level on 201-214, their Woody action's `time` 240-360, a `failed` action whose behaviour sends the neighbour running) and GameLogic's game object (vtable 0x100b1a7c, constructor fcn.100507f4, fcn.100508a1 once a level tick with the mouse): the first three ticks move the mouse onto the field's middle, then the rate 4/3/2/1/0 by the thumb's distance (under 200/400/600/800 in 1/10 px; -(progress x 4 / 10) in -40..-4 beyond it once the progress passed 10) and a push of three sinusoids (20/10/5, 0.0648/-0.1461/0.3696 rad a tick) times a factor from the combine.xml combination's startlevel to its endlevel with min(progress, 90)/90 (the object setter fcn.100452d7, the use_object step fcn.10004353 → fcn.10041735 → +0x40/+0x48); the DoAction step (fcn.10001b2c) adds the rate to the elapsed count clamped at `time`, the progress elapsed x 100 / time (fcn.100507dd), the win at `time`, the `failed` action below 0 — the earlier row's "no such code" was a search for the mobile's vocabulary | carried 2026-09-23: the PC's rates, counts, centring, push and alarm on the remaster's field, the thumb the mouse one to one (PCMinigameTicks / PCMinigameLevels, `DexterityState._pc_tick`, `pcprofile.s2_game_push`); a middle-held game lasts 3 + time/4 ticks; a lost game's neighbour runs onto the object (the `failed` behaviour `run`, registry 0x1003e278) or nobody comes (201's `aux`, 212, 213: PCMinigameFailed); the order in the level tick the PC's (2026-09-23): the DoAction step is Woody's job (fcn.10049246 pushes it on [actor+0x18], its first run only sets it up; fcn.100492a8 runs it from the actors' pass fcn.10044234, which the level update calls at 0x100445f8) and the game's update comes after it at 0x1004482b, the game made in that job pass (fcn.10041735) — a tick adds the rate the last update left, the first update at the game's start (`DexterityState._pc_update`); the field GFXEngine's since 2026-09-24 (the create message, slot 79 of the GFX visitor: the middle Woody's `minigame` hotspot, 0/-150, the camera scrolled onto it, 0x1000aa80 / 0x1000ab08; the draw fcn.1000fcf0: the textures at their own sizes, the icon centred, the thumb at (x + 1000) x (field - thumb) / 2000 of the state message's pair, fcn.1000fa00 — `hud._draw_pc_game`, `World.dexterity_focus`), measured on E04 759 s and E01 176 s (the middle at PC (400, 254)); a lost game's behaviour reaches its actor a level tick later and every tick after it until taken (the walker fcn.1003fc90 before the actors' pass, the votes of fcn.1004abcf: the level scripts' walks interruptible, their actions not — `DexterityState.pc_offer_tick`); open: the progress bar's front image (not in the data, the remaster's fill stands in) |
| detection ("sees Woody") | the mobile's predicate; since 2026-09-23 under the profile the PC's room trigger (`World._pc_s2_sees`) | the level update (at 0x100445f1) runs fcn.1003fc90 over a table of watch entries (an actor, a target, mode bits at +0x1c/+0x1d) and evaluates each with fcn.1003f573: the actor must carry flag 0x20, neither party flag 4 (the hideout flag — set on hiding, e.g. 0x100067e9, cleared by the `leave` action at 0x10006abc), the rooms compared through fcn.10040a7d (the record of the actor's +0x20 name), and in one mode a vertical distance below 15 (0x1003f7d0); a true entry fires an event object (fcn.1003f86d, fcn.1003f972, fcn.1003fa6b, fcn.1003fc6e — no strings); the table is filled from data and code: every action record carrying `behavior=`/`behavioractor=` (62 in the Season 2 objects.xml — the neighbour's `run` after a failed Woody action ×11, Olga's `kid_cry`, the mother's `crash`, …; parsed by fcn.1004fa5c/fcn.1004fbe7/fcn.10050c15 and flagged at +0x24, 0x1000a696), the engine's own per-action entries (fcn.1004008d from fcn.10001b2c at 0x10002478/0x100024af, mode 0) and the scripts' explicit ones (fcn.1004000a: the tutorials' and 201's `tutorial` entries, 213's `bull` and `boat`) | agrees in kind with the mobile's zone containment plus the hiding exemption. The mode bits are read (2026-09-17, fcn.1003f573 with the entry's +0x1c dword as its fourth argument): bit 1 — the two objects' rooms (fcn.10040a7d) are the same; bit 2 — the same room, the same floor record (fcn.1004c945 / fcn.10049006) and a vertical distance below 15 (0x1003f7d0); bit 4 — always true; no bit — never; and before any of them the second object must carry flag 0x20 and neither flag 4 (the hideout), with no sneaking, busy or animation term at all. The walker (fcn.1003fc90) tests an entry without a direct target against every other entry of the table whose ordinal (+0xc) reaches its threshold (+0x18), with the two modes ORed, and latches a hit in +0x1d bit 2. The engine's per-actor entries (fcn.1004008d from fcn.10001b2c) and the scripts' explicit ones (fcn.1004000a) are built with mode 0; the modes come from the parsed action records — `behavior=`/`behavioractor=` with `always="true"` (the 62 reactions: the neighbour's `run` after Woody's `failed`, `tongue`, `kid_cry`, `crash`, …) and the `room` keyword the level parsers compare (0x10070779 …). The catch itself (2026-09-17, later): fcn.1000eb19 (13 call sites, one per level class) runs the catcher's approach step fcn.1000e601 — the two rooms compared through fcn.10040a7d, a point beside the target at the fixed offset [0x100cc814], a path check (fcn.100072b1) and the move (fcn.10007d78) — and starts the `fight` action (the string global 0x100e1b50, fcn.10002cd5) once no step is left; the level classes call it with `neighbor` and a continuation from handlers they subscribe to engine events through fcn.1000e7f2 (18 subscriptions, e.g. event 0xf0 on `pool_deckchair` in the 207 class), and the data's `behavior="run" behavioractor="neighbor"` on Woody's `failed` action is the reaction after it. The per-actor watch entries carry mode 0 (fcn.10001b2c) or 0x100 (fcn.10008b74 — the lookup selector byte), the room bits come from the outer, data-side entries ORed in by the walker. The 13 sites are steps of the per-level actor scripts — fcn.10011655, run from the level constructors (fcn.10044bb5 / fcn.10044ce6), fills the level's table of actor → script (blocks of `woody`/`neighbor`/`mother`/`olga`/`fifi`/`bar_keeper`, one function per level and actor, Woody's the same fcn.100138d6 everywhere; the step chains tools/pcref/routine_order_s2.py reads) — and the step that calls fcn.1000eb19 is entered when fcn.100585c0(`crash`) holds (0x1001462e: `mov [edi+8], 0x1001452c`), i.e. it is the scripted fight with a co-actor after a crash reaction (the `m_hurt_n`, `olga_fight`, `mother_fight` scenes), not the catch of Woody. The catch objects themselves (the fear/fight fiber, vtable 0x100ab258 / 0x100ab278 with fcn.100061dc) are created by fcn.1003c4e3 — one level's `olga` script entry — and by the unheadered fcn.1003f086, which resolves an actor by name and tests its +0x14 flags 2 and 0x50 (the flag helpers fcn.100450bf / fcn.100450dc) and has no code reference at all: it is slot 2 of the vtables 0x100b0ff8 / 0x100b100c (radare2 `/x`), the event objects the level tick itself creates every tick while `[level+0x44]` is empty (the level update at 0x10044386 → fcn.10040f38 → fcn.100403d8 → fcn.100461eb, which resolves an actor by name and sets its flag 0x100000 → fcn.1003f431 → fcn.1003f3df, `new` of 0x18 bytes with four arguments). Those objects are the watch entries themselves: fcn.1003f4d9, which the walker's fire path fcn.1003f86d calls, is their equality (four string fields through the strcmp wrapper fcn.100585c0), fcn.1003f4b8 the list push, and slot 2 the entry's action when it fires — for this class the catch: resolve the actor in the level, test its +0x14 flags 2 / 0x50, start the fiber. The predicate fcn.1003f573 (reread the same day) returns false when the entry's mode byte carries none of 1 / 2 / 4, so a catch entry must be registered with a mode; the per-tick object the tick builds at 0x10044386 is the probe the walker compares the table against. The entries the tick's probe is matched against are the script steps' own: the `use_object` step's start method (0x100469c3, in the step-class vtables 0x100b1328 / 0x100b19c8) registers (`use_object`, the object, …) through fcn.1003f431 — the string global 0x100e1b74 is `use_object`, one of the engine's step kinds next to `goto_pos`, `combine`, `stop`, `crash`, `olga_fight`, `mother_fight` — and the data's `behavior=` records on that object's actions bring the modes (`room`, `always`); a matched pair fires slot 2, which resolves the behaviour's actor, tests its flags and starts the behaviour fiber (fcn.10005b94: the `run` that plays fear, `fight` and the respawn). That is the reaction path — the neighbour's `run` after Woody's failed minigame, Olga's shout — read end to end; a catch on Woody merely walking into the room does not pass through it (no data record names a walk), and where the PC's Season 2 tests that is what remains unread, so the profile's Season 2 keeps the mobile predicates. Read on 2026-09-23 — the walk-in catch is data after all: generic/trigger.xml gives the neighbour and the Mother a `fight` behaviour on Woody, `<trigger object="woody" position="room" type="always"/>` (and Woody a `die` one on either; Olga and the other actors have none), Loader.dll's trigger parser (0x1000a869-0x1000a936) makes `position` room / nearobj / house the mode bits 1 / 2 / 4 and `type` once / always 0x1000 / 0x2000 of the AddObjectTriggerMsg `flag`, and GameLogic's handler (fcn.1004fa5c: actor, actionactor, behavior, flag, object — the message registry binds it at 0x100505a3) files it in the watch table; so the catch is mode 1: both room pointers set and equal, the target placed (0x20), neither party's flag 4. Flag 4 is set by the enter step (vtable 0x100ab2ec, 0x100067d4-0x100067e9) when the entered object carries hideout or neighbor_hideout (0x140), cleared when the leave step's `leave` has played (0x10006ab7), and set or cleared by nine level steps (the complete list of the setter's mask-4 calls: 202's sea and beer, 206's, 210's and 214's Mother asleep and awake, 209's shoe mat — tools/pcref/pc_catch_s2.py) | differed in kind: the mobile's catch had IgnoreWoody, the blocking animations, IsSleeping, PassingComplexMove and DonePassingToOtherZone, its sleep windows the ProgressBars' sequence spans on the same stations; carried since 2026-09-23 (`pcprofile.s2_sight`, `World._pc_s2_sees`, `_pc_flag4_tick`, `Pawn.pc_room`, PCHideout): the room pointer — none on a hop's steps up to the transfer, less the `out` run stood before one, and inside a back door's clips — Woody's hiding through his hideout's leave clip, the catchers' flag 4 at their neighbor_hideout stations with the level steps' clears; the crossing check reads the same predicate |

## Not verified

- The frame pacer: the timer at `[app+0x50]` (fcn.00402cc0, fcn.00402d30)
  is an fps counter over 0.5 s windows, the only `Sleep` is the loading
  screen's, no `SetTimer`/`timeSetEvent`; the one 83 ms constant in the
  binaries (GFXEngine fcn.10003420, `GetTickCount`) is a button widget's
  auto-repeat interval, its 1000 ms the hold timer, and fcn.100092a0's
  167 ms the caret blink — what makes the level tick 12 Hz is not
  located. The 12 Hz itself stands on the clock, the GUI's
  divisions by 12 and the mercury (docs/PC_ROUTINES.md). Read further on
  2026-09-17: the app's timer is built for 60 (`push 0x3c` at 0x0040eed2
  into fcn.00402cc0; fcn.00402da0 is QueryPerformanceCounter with a
  timeGetTime fallback, in seconds since start), the level's update
  fcn.0043ab40 drains its message queue and then, while `[+0x54]` is set,
  runs the coroutines (fcn.00472390), the per-tick rules (fcn.00439cd0,
  which holds the anger rule fcn.00436bb0) and the clock (fcn.00438a80);
  the one fixed-step scheduler with a catch-up in game.exe — fcn.004237b0,
  an interval of `1000 / rate` ms (0x00423ca6) and `n = elapsed /
  interval` steps — belongs to the Video for Windows player (its
  constructor fcn.00423860 asks MSVFW32 for its version; the rate is the
  clip's), not to the level. The gate between the 60 Hz timer and the
  update is what remains unread; the port keeps its own 12 Hz accumulator. GFXEngine.dll (radare2, the same day) calls `Sleep` once — a 200 ms / 250 ms throttle of its present loop behind a flag (0x1002c1dd–0x1002c20c, the inactive-window pace) — and its GetTickCount/QueryPerformanceCounter pair is the CRT's cookie seed; the renderer has no frame limiter of its own. The frame function fcn.00410070 (called from fcn.00411d40's pump) runs one `[vtable+0x3c]` (slot 15) on the object at app+0x20 per frame, between two fps-timer updates and the render slot `+0x60`; the level's update fcn.0043ab40 counts its calls at +0x54 and runs the tick body — the coroutines, the rules, the clock — on every call while the byte at +0x88 is set (no divider there), and reaches it through fcn.00449f80 from the unheadered fcn.0044ae60 (slot 14 of the classes at vtables 0x4e19d0/0x4e19e8, radare2 `av` + the PE's own tables); which class sits at app+0x20 and how its slot 15 spaces the calls to 12 Hz is the one link still unread. Reread on 2026-09-23: fcn.00449f80 and the slot-14 method fcn.0044ae60 hold no timing at all (they walk the scene's objects and a script step — the chain named above is a step class, not the pacer); no binary of the Season 1 set carries 1/12 as a float or a double, nor 83.3; the one 83 in GFXEngine.dll's code is a sprite's default frame interval in ms (the constructor fcn.10001340 stores 0x53 at +0x3c, and the frame advance at 0x100016c0 steps the frame once `now` passes +0x40 + that interval) — the 12-a-second sheets, not the level tick. Season 2 (2026-09-24): NFH2's game.exe runs its frame
  in fcn.0040382d (the fps timer fcn.00402678 over 0.5 s windows, the object at app+0x20 by its slot
  15) and holds GameLogic.dll's level at [+0x30] (fcn.004064cf); the level's update is the interface's
  slot 2, 0x100442b3 — its message list, `inc [ebx+0x64]`, the watch walker, the actors' jobs (fcn.10044234), the game and the status tick on every call —
  and the caller that spaces those calls is not located either; the 12 Hz stands on the same evidence
  (the HUD clock's division of the tick count by 12, the videos' clips at 12 a second). Read further the
  same night: NFH2's main loop (fcn.0040f1f0) pumps the window messages (fcn.0040f120,
  PeekMessage / DispatchMessage) and calls the application's frame callback (vtable 0x454160,
  slot 3 = 0x40ac8f -> fcn.0040382d) back to back, waiting (WaitMessage) only when the callback
  declines; GameLogic calls no clock at all (its GetTickCount seeds random generators: the
  level constructor fcn.10044bb5, the mini-game's fcn.100507f4); so the spacing sits in the
  object the frame drives at app+0x20 (its slot 15) or below it, still unread.
- Season 1, settled on 2026-09-18: the catch's busy byte (+0x78) is
  toggled by one message only — the level's slot 49 (fcn.00440c10,
  `sete` on the byte of the actor named in the event, reached through
  the event class 0x4e7984 built by the script command `pause_neighbor`
  (fcn.00408210) and by PauseActorMsg (fcn.004509e0)) — and no Season 1
  level file uses either, so the neighbour is never busy during play: no
  busy window, as carried. The position object is the room for every
  room but the hall: the level files give each room one walkable
  `<floor>` (the rest are `wall="true"` strips) except `anc`, which has
  two or three side by side — where the port's one zone may be coarser
  than the PC's strips (open, and not where 106, 110 and 111 lose
  their tricks: those rooms have one floor).
- Season 2: what the respawn timer gates.
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
- Documented, not carried: the walking speeds (the `<speed>` records and
  the walk step, the row above; carried later that day) and the walk noise
  (the gait records' `noise` — the port's sleeping-pet test already matches); the Season 2 lap tool
  reads radare2's `fcn.` spelling of a next-step store too (nine laps
  close).
- Documented, not carried: the neighbour's blind byte (never set on PC),
  the door transit rates, the Season 2 watch table's sources (the
  `behavior` actions).
- Carried on 2026-09-17 (`runtime/pcprofile.py`, `runtime/world.py`,
  `tests/run_tricks.py`): the walking speeds (`walk_speed`), the door
  clips' pace (`clip_fps`) and the catch on sight without the busy
  windows (`sees_while_busy`); `NFH_PC_RULES=walk,doors,sight` keeps a
  subset of the three for bisecting a plan.
- Carried on 2026-09-17 (the Season 2 stations): PCUseSeconds on the
  routine items of 210-213 from the PC videos' bubble spans less the walk
  (tools/pcref/pc_durations_s2.py; docs/PC_FIDELITY.md "Season 2 station
  durations").
- Carried on 2026-09-18 (the other actors): the PC data's explicit
  action times (ticks / 12) as the stands of 212's Mother
  (PCUseSecondsRole, tools/pcref/pc_durations_others.py — 212 rates 100
  under them); 213's are within 3 s of the mobile's and stay; the loops
  without a time in the data keep the mobile clips.
- Carried on 2026-09-18: the Season 2 station stays on every episode
  (PCUseSeconds in levels/pc, tools/pcref/pc_durations_s2.py) except 214's, whose lap is a
  neighbour-Mother handshake (mother_sleep from his pistol sequence,
  mother_sit releasing his WaitWatch — the Level214 behaviour cs:62-65,
  130-147): under the PC stays the two waited for each other for good;
  a coin credit due past the use's end is paid by the tantrum once
  (World.play_angry drops the pending credit). Read and carried on
  2026-09-23: the PC's Mother script (the awake, sleep and reling steps,
  her handler of the pistol's `standup`) and his pistol step's poll of
  her (curaction and flag 4, 0x1003abc9-0x1003ad7d) — the stays of 214
  are the code's with them (docs/PC_FIDELITY.md "214's handshake").
- Read on 2026-09-18 (Loader.dll, fcn.10008b6f): the `<flag name=…>`
  table — container 0x10, hideout 0x40, singleuse 0x80, neighbor_hideout
  0x100, doorup 0x200, doordown 0x400, doorleft 0x800, doorright 0x1000,
  then 0x2000, autotake 0x4000, 0x8000 and game 0x20000 — the mask the
  loader sends as SetFlagMsg for each flag of an object. No data flag
  is 1, 2, 4 or 8, and no code in the three binaries stores those into a
  message or record with an immediate: the actor's bit 2 that the tick
  and the watch handler test, and the object bits 4 and 0x20 the watch
  predicate tests, are runtime states — set through the generic setter
  with a register or record mask by a sender this reading has not
  reached (game.exe builds messages too: its `createMsgList` and a
  "mask" field of its own). The predicate's hideout tests are therefore
  states (4, 0x20), not the data's hideout flags (0x40, 0x100).
- Read on 2026-09-18, the catch trigger's plumbing (GameLogic.dll):
  every GL object (actors and items alike) keeps a flag word at +0x14,
  read by fcn.100450dc (`flags & mask`) and written only by
  fcn.100450bf (`set(mask, bool)`); the immediates set through it are
  4, 8, 0x20, 0x10000, 0x40000, 0x80000, 0x100000 (states of the scenes'
  fibers), never 2 — bit 2 arrives as data: the message registry
  fcn.100500e6 (CreateGLObjMsg, AddObjectMsg, CreateRoomMsg, BeginRoomMsg,
  EndRoomMsg, SetPosMsg, AddNeighborMsg, AddHotSpotMsg, EndGLObjMsg,
  SetSpeedMsg, AddActionMsg, AddContentMsg, SetFlagMsg, CreateInvObjMsg,
  EndInvObjMsg, AddInvObjImgMsg, CreateCombinationMsg, AddIngredientMsg,
  EndCombinationMsg, CombineMsg, AddObjectTriggerMsg, AddNoiseTriggerMsg,
  SetStdActionMsg, SetLevelSizeMsg, SetAnimMsg, StopJobMsg, PauseActorMsg,
  AddIconMsg, StartLevelMsg, ActivateAnimMsg, GoToPosMsg, UseObjectMsg)
  binds SetFlagMsg to fcn.1004e78c, which parses the message's `mask`
  as a number and its `value` against "true" into a record the step
  class applies to the named object (vtable slot +0x7c, fcn.1004670e,
  through the visitor fcn.1004d0c9). The data's flag names (`<flag
  name=…>`: container, remove, doorleft/right/up/down, hideout,
  neighbor_hideout, autotake, game, singleuse, bad) exist as static
  string globals in GameLogic, Loader.dll and game.exe but no code maps
  them to bits by name — the mask is numbered upstream (the level
  compiler or game.exe's message builder, `createMsgList`), so which
  name is bit 2 stays unread. What bit 2 does is read: the actor tick
  fcn.10004f3d (from fcn.10005370) tests 0x40, 0x10 and 2 on the actor;
  under 2 it resolves a name (fcn.1003cc45 → fcn.10040a7d), finds the
  entry of that name in a list (fcn.1004ca80, strcmp) and starts a
  behaviour object of class 0x100ab1a0 (fcn.10003d50 → fcn.10003d01 →
  new(0x30) + fcn.1000340b) — the on-sight reaction, keyed by the
  actor's current room or target. The watch predicate fcn.1003f573 tests
  the entry's own mode bits 1/2/4 (same room / same room and floor /
  always) and two object flags, 0x20 and 4 (the hideout pair by their
  use in the data: Woody's hideout, the neighbour's neighbor_hideout
  station); the watch entries themselves are created by the use_object
  step (fcn.1003f431 keys them "use_object") and their class chain is
  fcn.1003f322 (vtable 0x100b0ff8) → fcn.1003f390 (0x100b100c) →
  fcn.1003f3df. The step kinds are goto_pos, combine, stop, crash,
  olga_fight, mother_fight and use_object (the static-init pool at
  0x1008ca42; run, won and mg0 beside them are states); the level
  scripts build them in code (fcn.10040f38 from the level classes).
- Read on 2026-09-18, the last candidate for the Season 2 catch trigger:
  slot 4 of the level classes' vtables (0x100b1548 the base, written by
  the constructor at 0x100430bf and used by the level constructors
  fcn.10044bb5/fcn.10044ce6; 0x100b1628 the derived, at 0x10044e94) is
  fcn.10043253(nameA, nameB, key): it resolves A and B in the level's
  object table (+0x10, fcn.1004ba02/fcn.1004bb0d), requires A's +0x14
  flags & 2 (fcn.100450dc is `flags & arg`), lists B's entries
  (fcn.1004ccdb) and calls virtual slot 1 of the entry whose +0xc name
  equals `key` (fcn.100585c0) — a by-name dispatch gated on the mode
  bit, not the watch objects' creation (fcn.1003cc45 on the match is an
  accessor). What sets flag 2 on an actor and what creates the watch
  entries remain unread; the profile's Season 2 keeps the mobile
  predicates.
- `tests/run_tricks.py` (2026-09-18): `whenin <Role> <ZoneName>` waits
  for a pawn to stand in a zone (213's Mother in Zone02); the PC dodge
  trusts the gate on a walk into the leg's own zone (212's cigar box) —
  both mobile-guarded, the regression byte-identical.
- Carried on 2026-09-18 (the reactions): the PC neighbour's reaction to
  a trick is one clip picked by the record's laugh level and a seeded
  random (GameLogic.dll 0x1000f9b5: the four clip tables), 2-7 s for the
  mobile's ~7.6-s angry set — PCLaugh per item (tools/pcref/coins.py
  --write-laugh), pcprofile.s2_reaction_seconds, the angry sequence
  paced in World.play_angry and the pace restored at its end.
- Withdrawn on 2026-09-18 (the coin ticks of 2026-09-17): a record's
  `time` is a frame of its own action, not the credit's moment — the PC's
  bar jumps 4-12 s before the neighbour leaves a tricked station, at the
  reaction's start (amounts.py against the bubble spans), which is the
  mobile's moment too; the coin is credited as the action completes
  (`_s2_credit` from `play_angry`), PCCoinTicks and `World.pc_credits`
  are gone.
- Carried on 2026-09-17 (the compound coins): the Season 2 ladder's
  hard-coded extras take the PC record's rage under the profile
  (`Item.pc_extra_coin` / `pc_extra_coin_206` from the overlays'
  PCExtraCoin / PCExtraCoin206, `World._pc_extra`), and the base amounts
  of 213's Tortilla and PlantCarnivore and 211's OlgaChild are the PC's —
  the accounting is fcn.1000140b per `<trick>` record, once per record
  (docs/PC_FIDELITY.md "Season 2 compound coins"; tools/pcref/coins.py).
- `tests/run_tricks.py` (2026-09-17, the chain pass): `Name@ZoneName:N`
  names the N-th twin of one zone (113's two hall marbles spots); the
  `await` timeout is 240 s under the profile (a PC lap runs to 180 s on
  113, and a trick armed a lap ahead pays a lap later); `whenanim <Role>
  <Anim>` waits for a pawn's animation (210's Mother naps on her own
  clock); an `await` parks
  a hidden Woody where he is, so a plan whose neighbour makes an urgent
  trip off his routine (113's hot-valve grab into the basement) ends in
  the wardrobe.
- `tests/run_tricks.py` (the same day): the harness dodges by the PC
  paces — a catcher's arrival is his climb to a back door plus the Enter
  clip, Woody's exit adds his own climb; the sleeper's and the ignorer's
  windows read the season from Woody. The Season 1 plans that stood on
  the mobile's busy windows or paces are re-timed from the idle runs under
  the profile (`tests/plans/pc/s1`: 102, 105-110, 114); Level114's overlay
  drops the remaster's priming from the pipe and the phonograph, as
  level_hunter's objects.xml has them.
- `runtime/pcprofile.py`, `runtime/world.py`, `tests/run_tricks.py` (the same
  day): the door pass as the PC's — the near `enter` then the far `leave`
  through every door, each strip lasting its `time` ticks, the zone flipped
  at the far clip's start (the row "door transit"; the PC video of 110
  measures the back door at ~3 s, the sum of 11 + 22 ticks).
- `levels/pc/Level202.overlay.json` (2026-09-17, later): two coin patches
  had missed their items — the rake's component is the `Rake` subclass,
  the shark's 35 000 is read from the Swimming item, not the Submarine
  that arms it; the mat's 20 000 was missing (cn_b1/tricks.xml). The
  run's rating.json now lists every payment (`pays`: time, item, points,
  hot) under the profile — the Season 1 chains and the Season 2 gauge are
  tuned from it.
- `tests/run_tricks.py` (the same day): the driver reads the profile's
  rules — a catcher's zone is his room pointer door clips included
  (`eta_to_zone`), Woody is out of a room at his far clip's start
  (`_out_of_zone_delay`), a station's length is its `PCUseSeconds` per
  visit (`use_len`), the back-door climb and descent are the measured 0.35
  and 0.23 u; and two habits of a human player — a click dropped by the
  Hide_In dive is repeated, the exit door's dialog is answered No.
- `tools/pcref/pc_durations.py`, `runtime/scene.py`, `runtime/world.py`
  (the same day): the neighbour's stations last the PC's ticks — each
  Season 1 overlay carries `PCUseSeconds` per routine item (the level
  class's DoActions of that station at 12 a second, from the lap model,
  one value per visit), and `RoutineAction._pc_use_seconds` plays the
  mobile use clips at the pace that lasts them (`AnimPlayer.time_scale`)
  or holds a walk-by stand for them (the Duration branch); 106's bath and
  104's shaving chain keep the mobile's (111's machines since 2026-09-23:
  the give, the wash or dry and the take, one per leg).
- `runtime/pcprofile.py` / `runtime/world.py` (the same day, later): the
  Season 2 captions FAILURE / COLLAPSE! / GOOD JOB! / SUCCESS! from
  GUIEngine's fill (`s2_result`).
- `docs/PC_ROUTINES.md`: the level-end paragraph rewritten to the state
  machine (the earlier "0 = caught, 1 = failed, 2–3 = success" was the
  jingle table read as the level state).
- `runtime/pcprofile.py`, `runtime/world.py` (2026-09-24): the Season 2
  SHOUT as the binary's tables — shout2 at levels 0, 1 and 3, shout2_hard
  at 2, a freakout once the gauge has overflowed (`s2_reaction_seconds`,
  `Pawn.pc_rage_full`; the row "the reaction to a trick").
- `tools/pcref/lap_model_s2.py`, `runtime/scene.py`, `runtime/world.py`
  (2026-09-24): the linked trick's variant of a tricked visit — the step
  with both tricks in the scene (202's rail, 204's jade, 210's dog basket,
  212's parrot ledge): its stand, SHOUT and repair (PCUseSecondsLinked,
  PCShoutLinked, PCFixSecondsLinked) and each record's credit at its own
  tick (PCCreditAtLinked, PCLinkedPaysAt); the message elements Ef82b and
  Efac4 are instant (their updates return 1 at once: 0x1000cf2a,
  0x1000d037), which times 205's tricked rockets.
- `tools/pcref/lap_model_s2.py`, `tools/pcref/pc_durations_s2.py`,
  `runtime/scene.py`, `runtime/world.py`, `tests/run_tricks.py`
  (2026-09-24, later): the tricked steps with no SHOUT of their own (the
  continuations, the co-actor's hit, the flows with none: the three rows
  above), the tricked run from the lap's scene at its row (`lap_state`:
  209's hot shoe), the camera, the pose and the show elements instant,
  207's castle's linked continuation and a two-way station's per-visit
  tricked move (201's puddle, `txt` [200, -100]); 207's plan awaits the
  extra coin (the count 7). runs/sw13s2 all 14 at 100, S1 and the mobile
  regression unchanged.
- `tools/pcref/lap_model_s2.py`, `runtime/scene.py`, `runtime/world.py`,
  `runtime/behaviors.py` (2026-09-24, later): 213's bull and 212's ledge
  read to their records (the step's byte through eax, the aux script's
  parrot); 206's pad and harpoon by the PC's steps (the row "206's pad and
  harpoon"); 214's door is visited tricked in neither game. 206's plan
  awaits the count 6. runs/sw14s2 all 14 at 100, S1 and the mobile
  regression unchanged.
- `tools/pcref/lap_model_s2.py`, `runtime/scene.py`, `runtime/world.py`
  (2026-09-24, later): 211's rush (the row "211's rush"). runs/sw15s2 all
  14 at 100 (211 at 262.0 s), S1 and the mobile regression unchanged.
- `runtime/world.py`, `runtime/behaviors.py`, `runtime/scene.py`,
  `tools/pcref/lap_model_s2.py` (2026-09-24, late): the co-actor's fight
  on arrival and his SHOUT from its start (the row "the co-actor's hit");
  206's rubber through the pad's DependsOn; the repair's walk to another
  object (211's sign, 203's generator: PCFixDepart); 214's Olga pose
  release kept for her pose after the hit.
- `tools/pcref/lap_model_s2.py`, `tools/pcref/pc_walks_s2.py` (2026-09-24,
  late): 203's microphone tricked through the generator's tights (the PC's
  only stage trick: 13.25/1/1.58/6.92); a SHOUT with no repair in a step
  that hands over off the lap takes the next step's repair (203's
  generator, 212's bench, 213's washing tub: 1.58); Woody's own action
  translation as his PCApproach `tx` (208's chalk, -45). 203 at 201.8 s,
  208 at 279.0, 212 at 875.2, 213 at 400.3 — all 100.
- `runtime/world.py`, `runtime/hud.py`, `runtime/pcprofile.py`,
  `runtime/viewer.py`, `runtime/record.py`, `runtime/app.py`,
  `tests/run_tricks.py` (2026-09-24, night): the mini-game's field as
  GFXEngine draws it (the row "the dexterity mini-games"): the middle
  Woody's `minigame` hotspot with the camera held on it, the textures at
  their own sizes in the level's px, the thumb at the setter's offset for
  the state message's pair; the mouse measured in level px. runs/sw19s2
  byte-identical to sw18s2 (all 14 at 100).
- `runtime/world.py` (2026-09-24, night): the lost game's run a level
  tick after the loss and every tick after it until his walk (the row
  "the dexterity mini-games"; docs/PC_FIDELITY.md 2.6 "the lost game's
  run", which corrects the same night's first reading: the use_object
  job that sets its +4 is Woody's, the neighbour's script actions carry
  0); 203's Olga shouts on that tick. runs/sw20s2 byte-identical to
  sw19s2 (no game is lost in the plans); the plans run with
  NFH_DEX_LOSE start his run 0-0.1 s later on the twelve levels whose
  lost game sends him.
