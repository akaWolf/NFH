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
VIEWER RATING: and TRICKS:). The jingles (read 2026-09-25): the handler
fcn.00437de0 posts a message (vtable 0x4e09d4) on every change of the
state to 2..5 (the tick, 0x439dd6-0x439df3: not for 0 and 1) and the
level classes' slot 43 (0x440d40, vtables 0x4e07b8 / 0x4e1638) plays the
jingle of the table at 0x440fbc indexed by the state less 2
(0x440f23-0x440f34): 2 and 4 `jingle_failed`, 3 `jingle_caught`, 5
`jingle_success_normal`; `jingle_success_perfect` is in the string tables
and never played by the code. A catch plays two: the caught one on state
3, then the failed or the success one when the beating's state 1 turns 2
or 5.

| rule | port | binary | verdict |
|---|---|---|---|
| the level ends when every trick has fired | `GameState.all_done` (completed == total) | state 5 on fired == `reachable` | agrees; `reachable` equals the port's `total` on all 14 levels (data) |
| the level ends when the rating reaches 100 | not modelled | state 5 on score ≥ 100 after the reaction | equivalent on every level: the sum of the trick scores is 76–91, so 100 needs the last trick and the ticks together (data, docs/PC_LAPS.md) |
| time's up: success at or above minquota | `calculate_score`: won = rating ≥ `pc_min_rating` | state 5 / 4 by `minquota` | agrees |
| a catch with the quota reached is still a success | `_catch` → `_finish_game` → `calculate_score` (won by the quota) | state 5 from state 1 when score ≥ minquota | agrees |
| the jingles | the mobile's: caught at a catch and nothing after, success or perfect by the rating, perfect for all the tricks | the table by the state less 2 (above): caught on the catch's state 3, then failed or success on 2 / 5; failed on time's up; success (never perfect) on 5 | **fixed 2026-09-25**: `pcprofile.S1_JINGLES` under the profile (`_after_hit`, `finish_game_on_hud_click`, `_win`) |
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
| detection is zone containment, no line of sight | `CanRottweilerSeeWoody`: same Zone | same position object | agrees: the object is the room — it is set by name (fcn.00437970 → fcn.00448d70 → fcn.00444b30) and the walk compares it with its route's next room by name (0x475ebb-0x475f00), while level.xml's `<floor>` strips carry no name; the hall's (`anc`) two or three strips are one room, the port's one zone |
| a hidden Woody is safe | `Hiding` | flag 4 | agrees |
| a busy neighbour | `IsSleeping`, `IgnoreWoody`, the blocking-animation clause | the +0x78 byte is zero from the actor's constructor (fcn.00448320, 0x44848d) and changes only in the level's slot-49 handler (0x440c7f–0x440c87: `sete` — a toggle), which only the script interface's slot-207 stub (0x405f10 → 0x405f3d) reaches; no compiled code calls that slot (no `[vtable+0x33c]` call in game.exe), so the byte stays zero in every level and the catch on sight is never suspended | differs in kind: the PC neighbour has no busy or sleeping window — the mobile's `IgnoreWoody`/`IsSleeping` clauses are the remaster's; carried since 2026-09-17: `pcprofile.sees_while_busy` — the catch is the room and the hideout flag alone; 109's neighbour in his `neighbor_hideout` bed catches no one, and a walking Woody's noise 1 wakes him out of it (the row "the Bed special case") |
| doorways are safe transit | `IsPassingDoor`, `IsMovingToAdjacentZone` | no: the room pointer follows the far door's placement for its `leave` (fcn.00448d70), so a pawn inside a door clip is caught, and catches, by the room it is placed in — the row "door transit" | carried since 2026-09-17 (`pcprofile.door_warp_early`, `World._detect_common`'s PC branch without the door terms) |
| the Bed special case | movement is fatal while he is in bed | 109's bed is the Season 1 set's one `neighbor_hideout` (level_pig's objects.xml): its enter sets flag 4 (fcn.004737a0, 0x473965), so the catch rule's flag test (fcn.0043c2b0) keeps the sleeper out of it until the leave (fcn.00473a60); level_pig's trigger.xml gives him a `wakeup` on a noise of 1 in his room, which a walking Woody makes on every tick of the walk (a sneaking one's gait records carry 0), and the pig class ("Level05::handleTrigger", vtable 0x4e4694) takes it in the bed's cases 7 and 8 only (fcn.00468580 from the accept slot 0x468650): the sleep's job stopped and a new list (fcn.00476770): the LEAVE of bed/bed_sleep (fcn.00473ea0 at 0x468aff — its `leave` action, the object's 17-frame oneshot, 16 ticks by the Loader) and the switch back to bed/bed (fcn.00468700, a SwitchObjectsJobCallback — the object swap, instant), then case 10 (fcn.0045c600(10), 0x468beb) — past the alarm clock's case 9 | differed: the port's profile caught a walking Woody at once from the bed, and spared a standing or sneaking one during the walk to it; carried since 2026-09-25 (`Pawn.pc_bed`, `World._pc_bed_noise`, `RoutineState.pc_wake_from_bed`): no catch from the bed, a walking Woody in the bedroom wakes him, the remaster's BedOut plays at the pace of the `leave`'s 16 ticks (PCLeaveSeconds, since 2026-09-26; a frame a tick, 17, before), the alarm clock's action is skipped, and the catch is the room's again once he is out |
| the beating, then the level ends | `_catch`: the fear pose, `_finish_game`, the caught jingle (and under the profile the outcome's after the beating) | fcn.00474510, state 1, then state 5 or 2 by the quota | agrees |

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
| the action durations | the mobile clips (the neighbour's stations since 2026-09-17 at the PC station's ticks: `PCUseSeconds` in the overlays, `tools/pcref/pc_durations.py`) | objects.xml `time="N"` is N ticks of the 12 Hz level tick (counted by the ACTION step, read 2026-09-26: the step's update fcn.004772f0 — slot 2 of vtable 0x4e546c, which the actor's tick 0x444db0 calls on the front job every tick, popping a done one and updating the next within the tick (0x444e05-0x444e7c) — starts it on its first call, makes a timer job of the longest time (fcn.0047e520 / fcn.0047f660, vtable 0x4e5bcc), pushes it on the actor with the run-now flag 0 (fcn.00444d30) and returns not done (0x477ad6); the timer's update 0x47e500 counts the time down and is done on its (time + 1)th call, the first on the tick after; the step's next update, in that tick, ends it (the started flag +0x24, the stop fcn.00476da0, done at 0x477b3b), and the sequence (vtable 0x4e5430, update 0x476530) or the level class — itself the job under them, slot 2 of its vtable (0x461940 for level_pie) — pushes the next step with the run-now flag 0 (0x4765d4, the cases' pushes) and returns not done, so the next step starts on the tick after: an action lasts its time + 2 ticks, two when the longest time is 0 and no timer is made (0x477975) — NFH2's DoActions job, the time + 2, is the same count; a sequence's own first update puts one tick before its first step; the `dec [obj+0x28]` once read as the countdown, fcn.00474ab0 / fcn.00475900 / fcn.00478210, is the step objects' reference count — their Release, slot 1 — and fcn.00474a20 / fcn.00475850 / fcn.00478120 the factories that build those steps, corrected 2026-09-25) and `time="auto"` as NFH1's Loader.dll stores it (0x1000a865-0x1000aa05, the rule of NFH2's Loader): the longer of the actor's and the object's oneshot animation less one, at least 0 — `inv` not asked, a loop or a missing animation -1 (107's doors, the only `auto` ones, 20 frames → 19, the other levels' explicit times) — a door 9–25 ticks is 0.75–2 s, the wash 59 ticks 4.9 s a visit; GFXEngine has no sprite timer of its own | read; the lap model and the trick tool counted an `auto` action's frames (one tick more, a looping actor animation's frames instead of the object's oneshot) until 2026-09-25; `tools/pcref/canon.py` now prints the PC action seconds at 12 a second (it divided by 20 before, the tick's earlier misreading); the step's + 2 carried since 2026-09-26 wherever the profile times a Season 1 action — the stations' PCUseSeconds, the tricked stands, the doors, the shouts, the pets' clips, Woody's tricks, containers and hideouts, the alerters' leave (`tools/pcref/lap_model.py` `job_ticks`; read and carried as + 1 earlier that day, the step's own first tick missed) |
| Woody's trick actions | the remaster's use clip at its own pace (MakeTrick 12 frames at 10 a second, 1.2 s; TakeGround 0.57 s; 102's SawSofa 4.8 s) | a trick is a combination of combine.xml (the object and the inventory item it takes; the tricked object its name), and Woody plays it as the object's action named after the item (lir/sofa's `fartbag`, kit/binoculars' `superglue`) or `use` where it takes none, at the record's time as the Loader stores it — 23 ticks (1.92 s) on most, 11 (0.92 s) on a quarter, 16 on 103's mousetrap and 109's pig key, 180 (15 s, Woody `inv`) on 102's saw; a trick on a room's floor (kit/groundbanana ← kit + banana, the soap, the marbles) is Woody's own `laydown` (generic/objects.xml, the ACTION step at 0x44b109-0x44b141), 3 ticks; the action's next animation (`smile`) is an idle, no time; a container's take is his `take` of the object (its `open` and `close` are 0 ticks for him — a one-frame oneshot of his, none of the object's): take0/1/3 18 ticks on 73 containers (the remaster's TakeInventory, 1.5 s), take_low0 11 on 18 (the rubbish bins), take_high 14 on 10 (the first aid); a hideout's `enter` and `leave` of his — the wardrobe 19 and 19 ticks, the bed 4 and 4, where the remaster's Hide_In and its leave clip take 2.0 s each — the LEAVE step clearing flag 4 once its `leave` has played (game.exe: its update 0x473ae0 frees the object and pushes the `leave` ACTION with the run-now flag 1, and its next update, in the tick that ACTION ends, finds nothing occupied and clears flag 4 — the branch 0x473b2b → 0x473ccc; read so on 2026-09-27, the earlier reading had put the clear at the step's start): the Season 1 catch reads him from the clip's end, as the Season 2 one does (`Pawn.pc_leaving_hideout`, since 2026-09-27; the port had caught him from the clip's start); Season 2's hideouts' `enter` and `leave` jobs 8-13 ticks each (the pipe, the beach chair, the baskets, the deck chairs, the lorry, the statue), carried the same way, its flag 4 cleared once the `leave` has played (the port keeps him hidden through the clip) | differed; carried since 2026-09-26 (`tools/pcref/pc_woody.py` → PCWoodySeconds by the inventory type Woody holds, `World.woody_use`: the remaster's clips at the pace that lasts it via `AnimPlayer.clip_pace`), each an ACTION step of its time + 2 (the row "the action durations": 25 ticks, 2.08 s, on most tricks, the laydown 5, the takes 20, 13 and 16, the wardrobe 21 and 21, the bed 6 and 6); the remaster's TrickLaugh after it stays, a click leaves it at once as on the mobile. Season 2 plays the same records as a DoActions job on Woody's queue, the Loader's time + 2: 13 ticks (1.08 s) on most tricks (uselow/usemid), 10-15 on the rest, 208's safety line 25, 209's drain 19, 210's pylon 29 — carried the same way on the tricks paired by the inventory the mobile item takes (a combination with a mini-game left to the game; the tricks that take no item keep the remaster's clip); its containers' `take` is a 16-tick job (1.33 s) where the remaster's search is a one-frame pick-up, ItemFound and TakeLow or TakeHigh, 1.9-2.9 s — paced as a whole to it (the level's mini-game item left to the game) |
| the walking speed | the mobile's `Speed` 1.25 u/s (Season 1), 1.0 (Season 2), `SpeedSneaking` 0.65 | objects.xml `<speed name=… speed=… start=… noise=…/>` per actor and gait animation (`SetSpeedMsg` → fcn.0044dd20: +8 speed, +0xc start, +0x10 noise); the walk fiber fcn.00475b30 waits one tick between steps (0x476148) and fcn.0047c7f0 moves the actor by the record of the facing animation (fcn.004459c0): `speed` px a tick plus `start` once when he leaves the standing animation `ms`, clamped at the target (0x47cc9f–0x47cd59) — the neighbour 8 px a tick along the floor, 3 up and down, running 18/9, Woody 17/6, sneaking 5/2, the dog 4; Season 2 the same for the neighbour, Olga and the mother (GameLogic.dll's walk step fcn.10009215, one axis a tick; the stair records 8/5 are never selected — nothing writes the gait 7) | differs: at the mobile scene's 96 px a unit (the house of 101: the living room's 586 px path ↔ the 6.8 u zone less the collider's margin, the hall 740 ↔ 8.4, the kitchen 412 ↔ 5.1; the neighbour's start 504 px ↔ −1.75 u within 9 px) the PC neighbour walks 1.00 u/s to the mobile's 1.25, Woody 2.1 to 1.25, sneaking 0.62 to 0.65; Season 2's scenes are 93–100 px a unit (208: the neighbour to Woody 338 px ↔ 3.69 u, the mother to Woody 446 ↔ 4.49; 201: the bridge to the right rail 1460 ↔ 14.5), so there the PC neighbour's 96 px/s is the mobile's 1.0 u/s — the remaster kept the Season 2 walk, sped Season 1's neighbour up by a quarter and halved Woody (2.0–2.1 u/s on PC in both seasons, 1.25 and 1.0 on the mobile) — carried since 2026-09-17 (and since 2026-09-26 the Season 1 neighbour's walk on the PC's legs, since 2026-09-27 Woody's: the movers' ticks between the door types' standing points and the stations' hotspots — while x is off the target's, y to the room's floor line first (the room's point, fcn.0044bac0; 0x47cbc6–0x47cc9d, read 2026-09-27), then x, then y to the target's — docs/PC_FIDELITY.md "Season 1 walks"): `pcprofile.walk_speed` moves every pawn at its floor record on a walk (whatever the direction — the mobile scene's depth offsets to its items are the remaster's; the axis-by-axis mix over them made the Season 2 laps 20-30 % longer than the PC video's) and at the vertical record on a door approach (the DOOR_CLIMB / DESCEND states, the PC's ~50 px climb to a back door), `tests/run_tricks.py` dodges by the same paces; the lap model below checks the climbs; since 2026-09-23 the Season 1 neighbour takes the gait the level class sets (+0x38, the index into the facing tables 0x51b5f0 / 0x51b648: 0 mg, 1 sn, 2 mr, 3 mrwc, 4 mgbowling1, 5 skate1, 6 piewalk — directly or through the step fcn.0045f6b0, run by 0x479660) before a GoTo and back to 0 at the next case: the run at mr1 18 / mr0 9 on every `noise` case (the pets' alarm, 107-114), the toilet and first-aid rushes (102, 103, 105, 106, 108's rinse), the antenna's shout (101, 102), the extinguisher's fetch and the way back to the barbecue (110), 113's runs to the main valve after the flood and to the heat valve after the hot heater and 112's way back in after the skate; the skate's slide at 18, the bowling ball's carry at 9 (`Routine._pc_runs`, `Pawn._pc_gait`, `pcprofile.GAIT_PX_PER_TICK`); the mobile's other urgents (111's vacuum and carpet) the PC walks, and the port shows the walk set on them; Season 2 (GameLogic.dll +0x3c, the level scripts' writes of 2 before a walk): 206's pillow errands, 210's run to the Mother, 211's phone and WC, 207's Olga to the sand castle carried, the rest open (docs/PC_FIDELITY.md, "Season 2's runs") |
| door transit | the pawns' door clips at 10 fps (Woody 16/13/10 frames out and 25/22/16 in by the left/right/back door, the neighbour 20/20/12 and 20/20/13); a flat door plays both at once, a walk-up door one after the other; the zone changes at the far clip's end | every Season 1 door is a `<door>` of the level's objects.xml with an `enter` action on the near door and a `leave` on the far one, `time` ticks each and the same on every inner door of a type in all 14 levels: the neighbour 19 + 19 (side), 11 + 22 (back), Woody 15 + 23 (right), 18 + 24 (left), 9 + 25 (back), each clip an ACTION step of its time + 2 (the row "the action durations"; `pcprofile.DOOR_TICKS` 21 + 21, 13 + 24, 17 + 25, 20 + 26, 11 + 27 since 2026-09-26) — 107's doors are `auto`, which the Loader stores as the same figures (the animations' frames less one); the front door pair differs for Woody (anc/fro, a right door, `enter` 18 where the type has 15; fro/anc, a left one, `leave` 23 on 101-107 and 109, 25 on 108, 110, 111, 113 and 114, where the type has 24; 112's anc/fro 15 + 23 like the type): his way in from the porch (fro/anc's `enter` 18, anc/fro's `leave` 23) is the type's, his way out to it is not — the port's table gives that pass 15 + 24 against the PC's 18 + 23 or 18 + 25: the exit door's pass, after its confirmation, ends the level as it finishes (World.finish_game_on_hud_click) and a Season 1 score carries no time, so the 0.25 s moves nothing but the end screen's moment — kept at the type's figures; game.exe's door step (vtable 0x4e5370, update 0x474590 → fcn.004741e0) claims the pair, places the actor at the far door's hotspot — the room pointer follows the placement (fcn.00448d70) — and pushes one ACTION step (fcn.00478030 over fcn.00477ed0, vtable 0x4e546c) with two entries, the near door's `enter` and the far door's `leave`; the ACTION update starts every entry in one pass over its list (0x477391-0x47793c) and times the step by the longest entry (the running max at 0x477785-0x4777ab, less the step's +0x20, which the door step sets from its own +0x20, 0 from its constructor 0x474109): the two clips run together and the pass lasts the far `leave`'s time + 2 on every door (the neighbour 21 through a side door, 24 through a back door; Woody 25, 26, 27). Read 2026-09-26: E14's frames at 12 a second, the camera on the neighbour (192-212 s), put the kitchen's side door at 17-18 ticks from his arrival to his step out, the living room's back door at ~23 and the bedroom's side door at ~18, the far door opening a tick or two after the near one, and his walk between them at the movers' ticks (41, 38, 25) — the kitchen polish to the cups 16.7 s against the concurrent model's 17.6 and the sequential one's 22.2; the "~3 s" read on E10's back door in 2026-09-17 (and taken for the sum) is the climb to the door's hotspot, 50 px at 3 a tick, and the pass | differed in three ways, carried since 2026-09-17 (`pcprofile.door_ticks`, `door_warp_early`): each strip plays at the rate that lasts its PC ticks (the neighbour's far back-door strip has 13 frames for the PC's 24), and the pawn's zone flips as the pass starts, where the PC's room pointer does — a pawn inside a door clip is caught, and catches, by that room (`World._detect_common`'s PC branch drops the door term); the two strips ran one after the other through every door on the 2026-09-17 reading of the video, and since 2026-09-26 they run together (`doors_concurrent`), the walk-up door's too, where the mobile runs those one after the other. Season 2's 126 `<door>` objects carry hotspots (`<actor>`, `<actor>_in`, `<actor>_out` per actor) and 8 of them `enter`/`leave` actions (211's cabin, 212's and 213's topright/midright, 214's bridge): a pair is one step of GameLogic.dll (vtable 0x100ab1b8) — the walk to the near `<actor>_in`, then out of every room the movement straight to the far `<actor>_out` (or the enter, the placement, the leave), the far room set there and the run down to its floor (docs/PC_FIDELITY.md, "Season 2 walks") | differed: the mobile walks its transitions at the floor pace (a stair ~3 s where the PC's is 9-11 s for the neighbour); carried since 2026-09-23 (`PCPass`, tools/pcref/pc_walks_s2.py): the hop stands the `in` run, walks its complex steps for the straight movement's ticks (the zone flips at `<actor>_out`) and stands the `out` run; the back doors' climb, strips and descent last the `in` run, the two clips and the `out` run; since 2026-09-24 the `out` run is stood indeed (it had been lost with the step's hand-over), no floor record caps the pass, the floor between the stations and the doors lasts the PC's |dx| (PCPass `xi` / `xo`, PCApproach `x` and `tx`), and the pair is claimed as the step starts (flag 8 on both doors, 0x1000339d; freed at `<actor>_out`, fcn.10003454) — the next actor stands where it is |
| the lap's timing | the mobile clips and speeds through the port's routine engine | `tools/pcref/lap_model.py`: the walker's lap tokens (ICON / GOTO / ENTER / LEAVE / ACTION along the level class's cases, `LAPS=1 routine_order.py`) timed from the data — 8 px a tick along the floor and 3 px up and down the room to the objects' `neighbor` hotspots, the doors' standing points (the door type's hotspot + level.xml `position`) with their `enter` and `leave` ticks, the actions' `time` or animation frames — against the PC video's natural laps (docs/PC_LAPS.md): 101 33.5/32 s, 102 28.2/28, 105 45.8/40, 108 90.4/94, 109 112.1/113, 110 60.8/59, 111 113.6/122 (the first lap — the 219 of 2026-09-06 paired the second, tricked lap; the washer and the drier are their three DoActions, no wait step), 112 147.3/155, 113 167.2/191, 114 168.9/168; 106 a two-lap cycle since 2026-09-25 (Level_Bath::isBathFilled: the fill, then the bath and the towel) 59.8 + 65.0 against the video's 57 + 60; no unknown step left (the actors' own records, the actor targets, the action's name by its record); 103 28/42 and 107 37/54 fall short, the video's lap carrying a trick | the walk, the doors and the actions hold together as a model on twelve laps; 103 and 107 are open |
| the Season 2 lap's timing | the mobile clips and walks; the PC videos' stays (span less the port's walk) since 2026-09-17 | `tools/pcref/lap_model_s2.py`: the level script's untricked lap (GameLogic.dll's step chain) timed from the data — the DoActions' `time` or clips, the hideouts, the bars' ticks, the GoTo's route (the Dijkstra of fcn.1000a421), the door passes and the station runs of the walk step — 203 105 s, 208 85.5, 209 104, 211 85, 212 124, 213 123, 214 90.3, 202 80.7 and the wait against the video's 84-112, 86, 97, 85, 113, 136, 91, 70-94 | carried 2026-09-23: the walk (the door passes, the station runs, the routes between stations: `PCPass` / `PCApproach`, tools/pcref/pc_walks_s2.py) and the code's stays on 203, 208, 209, 211, 212, 213 and since the same night 214 and 202 (210, 205, 207 and 204 since 2026-09-24, their laps from her `order`, from his play, from his dive and from the gong's leave) (pc_durations_s2.py CODE; 214 with its Mother's script and the pistol's poll, docs/PC_FIDELITY.md "214's handshake"; 202 per clip with his wait for Olga's sub and the shark paid at the sea's `enter`, "202's mat and swim"), the video's re-derived against the PC walk elsewhere; the port's idle legs within about a second of the model's (208's lap 82.5 s); since the same evening every walk's route is the path finder's (`world.pc_route` over the zones' PCRoom, from the station's hotspot or the pawn's x on the floor line — the 338 station pairs reproduced) and Woody's runs to his items' `woody` hotspots are carried (PCApproach `Woody`, 204 items); the idle laps under it (2026-09-24, the stays the walk writer had dropped since the routes restored): 203 99.5 s, 208 82.5, 209 100.8 (the model 105 with the fakir's `spit`), 211 80.8, 212 119.4, 213 126.6, 214 85.3 (the model 90.3), 202 81.7 (the model 80.7 and the wait), 210 98.7 call to call (its call by code since 2026-09-24: her naps and checks, his chair's bar and wakeup, the call, the run to her chair, the order and Fifi's tickle; ~101 with the PC's walks, the video's first lap 107), 205 101.6 (its table by code since 2026-09-24: the talk that calls Olga, the 72-tick wait, the play once she is there; the model 111.9, the video 102), 207 100.0 (its board by code: the dive once the Mother sits in her chair, she in it while he is in the pool room; the model 106, the video 107), 204 84.3 (its stays by code; the model 92.8, the video 81) — within 6 % of the model but 204 and 205, whose videos sit with the port (docs/PC_LAPS.md) |
| the S1 rage/bonus/hold | `pcprofile.s1_rage_*`, `Pawn.tick`, `play_angry` | fcn.00438a80, fcn.00438b90, fcn.0047bd00 | agrees (tests/test_hud_pc.py) |
| the S1 trick step's order (the action, the fire, the shout, the repair) and the shout's choice | `play_angry` (AngryHard 6.8 s after every trick, the mobile fix clips, the tricked clip paced to the normal stay) | fcn.0047bd00 as slot 2 of vtable 0x4e5944 (the OBJ2 step fcn.0047c290, the five-argument fcn.0047c320), the shout tables 0x51b584-0x51b5a4, fcn.0047ae70's repair, objects.xml's tricked actions | read 2026-09-22 in the code end to end (docs/PC_ROUTINES.md "The fire's tail"; the sites decoded by tools/pcref/fire_sites.py, the register-valued flags through the fibers' prologue constants): the order agrees except at the five-argument sites (the fire before the soap fall, the hair and the towel clips; the four-argument ones fire after their clip); the shout (7.58 s on a bonus, 2.0-3.67 cold — the Loader's times since 2026-09-25, 7.67 and 2.1-3.75 by the frames before — none at flags 2 or 3), the repair and the tricked action lengths differ — carried on every Season 1 level since 2026-09-22 (`World.s1_fire`, the routine's PCFireAt, the paced shout, fix and stand: docs/PC_FIDELITY.md "Season 1 reactions"; the stands read off the level classes' case chains by tools/pcref/trick_branches.py, the keys by tools/pcref/pc_reactions.py); the three engine-side steps of the reaction sequences (listener slot 26 = the GUI's face icons and a tick, slot 65 = the slip sound sfx_na_slip_up1.wav plus the soap's flag 0x20, the cactus clock's SwitchObjects job) are read in GFXEngine.dll and take no time |
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
| 106 | photo album → candy → milk bottle → bath tub (the fill) → album → candy → milk bottle → bath tub (the bath: the shower's enter, cases 14-15 the towel) → album — Level_Bath::isBathFilled (fcn.0046bc90) alternates the laps; the toilet through a class helper | PhotoAlbum, Candy, Pudding, BathTub, PhotoAlbum, Candy, Pudding, BathTub, Towel |
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
the states' meaning read on 2026-09-25 (the pet class's tick
fcn.0045bfa0: 1 falling asleep, 2 asleep, 3 waking, 4 awake — the rows
under "The alerters").

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
| the bark brings the neighbour | `Rottweiler.HearAlerter` → `SurpriseFar` | the bark's noise 2 → the house-wide `alarm`: the `noise` icon, the fast walk, `search`; the first bark comes as the `wakeup` action ends (state 3 pushes it; `auto` over a oneshot of 8 frames the dog, 11 the parrot, which the Loader stores as 7 and 10 ticks) and posts `startle_woody` with it; every bark is an action of its own (generic/objects.xml bark1/bark3: 35 ticks the dog, 22 the parrot, noise 2), so each posts the alarm again while Woody stays | agrees in kind; the timing carried since 2026-09-25 (`pcprofile.S1_PET_WAKEUP_TICKS`, `S1_PET_BARK`; each clip an ACTION step of its time + 2 since 2026-09-26 — the wake-up 9 and 12 ticks, the barks 37 and 24, the whines 25 and 31): the neighbour hears, and Woody flinches, at the wake-up's end instead of AlerterDelay's 0.5 s, at once for a pet already awake; each bark the remaster's alert clips at its ticks (the dog's pair — bark1 runs its 18-frame bark twice — the parrot's one scream) and a hearing at its start; the alarm itself is the level class's `noise` case — the `noise` icon, the run (gait 2) and a GOTO2 to the pet's room — then the next case's `search` (fcn.0047a690: the ACTION `search` on the neighbour, 24 ticks; 112's cases 21 and 22 at 0x46504a-0x465120), carried since 2026-09-26 as the remaster's Search at that pace (the Alerter's PCSurpriseSeconds 2.0 s, the remaster 2.5) |
| the whistle | `World.blow_whistle` wakes every alerter | the level script posts `whistle` to the dog: state 3 (from 2) or 4 | agrees for 114's one dog |
| the pet calms when the neighbour arrives | `OnRottweilerEnter` → "poor" | the class's tick (fcn.0045bfa0, read 2026-09-25) compares the rooms of `woody` and `neighbor` with its own every tick; awake (state 4) it barks while Woody is in the room unhidden (bark1/bark3 by its facing, `startle_woody` posted once per entry, latch +0x1c), else barks once for a pending whistle (latch +0x1d), else — the neighbour in the room — faces him and whines (`whine1`/`whine3`: poor1/poor3, 23 ticks the dog, 29 the parrot), else idles (ms1/ms3) and counts its timer down; asleep (state 2) it has no branch for the neighbour, and his gaits carry no noise; a bark or a whine is an action on the pet's queue that holds the class's step, so state 4 decides again only as it ends | differed: the port's pet woke for the neighbour and whined only when he answered its alarm; carried since 2026-09-25 (`AlerterFSM` under `pcprofile.s1_pets`): an awake pet with no Woody to bark at whines whenever the neighbour is in its room — one whine the remaster's PoorSequence clips at its ticks (`S1_PET_WHINE`: the dog's two 12-frame clips, poor1 running its whine twice; the parrot's one), Woody's arrival and the neighbour's leaving waiting for its end — an asleep one sleeps on |
| the pet falls asleep again | the WakeSequence's length after the alert (the dog's 65 frames at 8 a second, 8.1 s; the parrot's 23, 2.9 s) | state 3 (a noise of 1 or the whistle while asleep) plays `wakeup` and sets the timer to 72 ticks (0x45c153); state 4 counts it only in the idle branch — the bark and the whine are actions on the pet's queue, which hold the class's step — and at 0 it goes to state 1, `fallasleep` then `sleep` (0x45c45a-0x45c46f) | differed; carried since 2026-09-25 (`AlerterFSM.pc_timer`, `pcprofile.S1_PET_AWAKE_TICKS`): 6 s of idle in the room without Woody or the neighbour before the pet sleeps, its idle the remaster's WakeSequence — it falls asleep the tick the timer ends, not at the idle clip's end, and a bark or a whine in hand stops the count |

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
| the catch | `_catch`: fear, the beating, `_respawn` | the catch fiber (vtable 0x100ab258 slot 10, entry 0x100061dc) on Woody's queue: Woody's `fear1`/`fear3` facing the catcher (0x10006510), the catcher's `fight` action (generic/objects.xml: `fight_woody` with `fly_away_neighbor` / `fly_away_mother` on Woody — invisible, then 900 px up over the action's ticks 36-44 / 41-49, its `<translation>` — and `inv` after it), then case 4 (0x100062cc) picks the room, fcn.10005f58: every room of the level in its map's order (the names': the iterator fcn.1004018d, the UTF-16 compare fcn.10058390) scores 50 with more than one `<neighbor>` record and 0 with one (0x1000610c), 101 more with an object flagged `hideout` in it (0x100060b7), 50 less with a `bad` actor in it in his hideout (flag 4, 0x100060a0) and 10000 less with one out of it (0x10006139) — an actor counts in the room its pointer names (fcn.10040a7d) — and the first room above 0 and above every earlier one is taken (0x1000613f; none: the assert "Kein leerer Raum!!!"); Woody goes 900 px above the middle of its path (0x10006330-0x1000634a: x the two ends' mean, y path1's less 900; fcn.10041ad0 the room, fcn.100418f6 the point) and his `respawn` action goes in front of the fiber (fcn.10049246 without a first run): the fall back over its ticks 0-5 (translation 0/900) and the landing (generic/anims.xml `respawn`, 38 frames: 37 by the Loader's rule, a job of 39 ticks); case 5 (0x10006274), the job done, clears the catch's flag 0x10000 off Woody and takes the life (fcn.10042471) | carried since 2026-09-25 (`World._pc_respawn_zone`, `_respawn`, `_pc_respawn_landed`; PCRoom `hideout` from tools/pcref/pc_walks_s2.py): the room, Woody on the middle of its floor, his input held from the catch to case 5 (the fiber heads his queue; a click then is kept: the GoToPos handler, slot 71 of the level's message class 0x100b18b0 at 0x10046adc, offers the command to the queue's jobs, fcn.1004b27f → fcn.1004abcf asking each job's slot 5, and when the queue refuses it the handler keeps it in [level+0x60], which the level update re-offers on every tick, 0x100443ea — the port's StoreBlockedInput, replayed when the lock lifts); since 2026-09-25 (later) the landing itself (`World._pc_landing_tick`, levels/pc/Season2.overlay.json from tools/pcref/pc_respawn_s2.py): the remaster ships the fifteen images unused as W_Landing.png, played as the PC's 38 frames with their sounds, registered by gfxdata.xml's offsets against W_Stand, unseen on case 4's tick and falling 180 px a tick over the job's counts 1-5 (fcn.100015c4); and the fight at the PC's pace — the remaster's FightWoody / MotherHitWoody are fight_woody frame for frame and sound for sound, slowed to 8 / 9 frames a second, played a frame a tick with the respawn at the `fight` job's 45th / 51st tick (`pcprofile.S2_FIGHT_TICKS`). Not in the remaster: fly_away.tga (Woody kicked 900 px up over the fight's last ticks — the port keeps him hidden). The fear is the PC's (case 1: fear1 for a catcher on the right, else fear3; six frames, then the loop until the fight) over W_Fear, whose halves hold fear3_0000-0009 and fear1_0000-0009 (`PCFear1`/`PCFear3`, tools/pcref/pc_respawn_s2.py) — at the remaster's own placement, its halves cropped apart and the loop frames 6 px off. Before, the level entrance; the let's play's respawns (5:04, 6:05) land in the beach's left room — by Olga's mat, then at the foot of the gate's stairs, x 360 of its path 100-620 — the first room of that map, not Woody's start (the shop) |
| the respawn timer | none: a catch could follow at once | case 5 (fcn.10042471 at 0x100424b6) sets status +0x18 to leveldata.xml's `respawntime="60"`, the level update counts it down after its watch walker (0x10044725 past 0x100445f1), and while it runs the `fight` and `die` behaviours of generic/trigger.xml refuse Woody: their predicates (slot 4 of the vtables 0x100b0eec / 0x100b0e8c, fcn.1003d526 / fcn.1003cd8e) read it with Woody either party (0x1003d5f9, 0x1003d646 / 0x1003ce61, 0x1003ceae — fcn.1003cc45 there is the actor's name, not an action runner), beside the catch's flag 0x10000 on the behaviour's actor (set by both behaviours' starts, 0x1003d4bf / 0x1003cd27; refused at 0x1003d6b5 / 0x1003cf1d) and the scenes' flag 0x100000 on either (fcn.1000885f); the same span GFXEngine outlines Woody (the message of vtable 0x100b145c from 0x10042515 on / 0x10044765 off, visitor slot 80 0x1000ac00 → his sprite's +0x39, which draw slot 10 at 0x10011c50 turns into the frame in black at x±1 and y±1 under it; ship1's tutorial: "As long as Woody's image flashes, the neighbour is unable to see him") | carried since 2026-09-25 (`World._pc_catch_barred`, `pc_outlined`, render.draw_sprite's `outline`): no catch from the catch through the landing and 60 ticks (5 s) after it, the outline one PC px wide |
| lives out | game over | fcn.10042471 on the last life — status +0x14 at 1 before the decrement (fcn.1004012a, 0x10042483) — ends the level (slot 13 with 0, 0x100424d8-0x100424dc), case 4 having skipped the fall (0x1000634d): three attempts, x3, x2, x1 | differed: the port respawned on the last life as well, a fourth attempt; carried since 2026-09-25 (`_catch`: a respawn above one life) |
| the gauge, the decay, the board, the clock | `pcprofile.s2_rage_tick`, `calculate_score` | the level update 0x100442b3 (its status tick 0x10044710-0x100447f1), fcn.10040226 | agrees (docs/PC_ROUTINES.md) |
| the reaction to a trick | `pcprofile.s2_reaction_seconds`, `World.play_angry`: the mobile's angry set paced to the SHOUT's action | fcn.1000f977: the step's last parameter picks [shout2_light] / [shout2, shout2] / [shout2_hard] x3 / [shout2_high] — the static initializers 0x1007b54b-0x1007b61d fill 0x100df45c / 0x100df434 / 0x100df450 / 0x100df41c — after a first pick of [freakout1, freakout2, freakout3] (0x100df43c), which the SHOUT element (vtable 0x100ab99c, update 0x1000d751) plays instead once the status byte +0x28 is set: the credit sets it as the rage reaches 100 000 (0x10001500) and nothing clears it; the actions' animations (generic/objects.xml, anims.xml) 26 / 26 / 85 / 26 frames, the freakouts 37 / 38 / 63 — the Loader's times one less; the element's first update pushes the action's DoActions job in front of itself (fcn.10049216) and returns 0 (0x1000d8a2), the job runs its time + 2 from the tick after, the element's next update returns 1 (0x1000d8a6): time + 4 ticks, shout2 29, shout2_hard 88, the freakouts 40 / 41 / 66 | **fixed 2026-09-24**: the tables had been read as mixed (1: shout2 or shout2_hard, 2: shout2_hard or shout2, 3: the freakouts) and the freakout after the overflow was missing (`Pawn.pc_rage_full`); **2026-09-25**: the lengths the element's ticks (`S2_SHOUT_TICKS`, the frames before) |
| a tricked visit's credit | `Routine.pc_credit_timer` / `pc_credit2_timer`, `World.pc_s2_credit` / `pc_s2_linked_credit` | fcn.1000140b credits each named record of a playing action on the tick its `time` equals the action's count (0x10001455), from the action step's playing state (0x1000254d) and its end (0x100025bf): 202's rail over the eels' pond pays bridge_crash 8 ticks into the crash and bridge_electrify 5 into the electrify, 22 ticks apart | **carried 2026-09-24**: PCCreditAt / PCCreditAtLinked for the item's own record, PCLinkedPaysAt for the linked trick's (the ladder's linked arm paid apart, `_s2_credit(part=)`); the done count is the trick table's credited records (fcn.100522e6, fcn.1005225b), so the pair's completion is booked with its last record (`Item.pc_done_due`) |
| a tricked step with no SHOUT of its own | `code_stays_tricked` (`TRICKED_CONT` 'steps', `TRICKED_VIA`, `TRICKED_ROWS`), PCShout -1 | the step hands over to its continuation, which plays the SHOUT and the repair: 204's gong 0x10032f52 (SHOUT 3), 205's skis 0x10024fc2, 211's sweets 0x10030dc2 / 0x10030d0f / 0x10030b9d (the toilet run, wcright's `puke` 40 ticks), 214's wheel from the door 0x1003af18; 206's weights and dynamite at their rows; 210's dog basket alone plays none; 214's door is visited tricked in neither game (CaptainDoorBehavior's ExtraItem, Item.cs:2606-2623) | **carried 2026-09-24**: the stand to the continuation's SHOUT, its level and repair; -1 skips the reaction; 212's ledge (the aux script's parrot shit, fcn.10034e05) and 213's bull (the step's byte +0x28 through eax, 0x10038ab1) read to their records later the same day |
| an action's behaviour | the mobile's hand-offs at the use's end (play_angry's affect, PawnToAbortMutexOnFinish, the once-loop flags) | the DoActions job (update 0x100020c0): state 0 sets the participants' animations and sends the start message (fcn.100018a6: the job's +0x14 / +0x18, a text the GFX shows — "string" / "alreadyininv" of fcn.10002d71's callers — slot 48 of the GFX visitor, 0x1000a220), state 1 counts +0x28 past +0x24 (fcn.100011f2), state 2 sets the next animations and posts the action record's behavior (+0x1c) to its behavioractor (+0x20) with fcn.1004000a (0x10002708) and ends the job; the abort slot (0x10001d1b) posts it too when the record's `always` byte (+0x24) is set (0x10002009-0x1000203f); Loader.dll's time="auto" is the longer of the actor's and the object's oneshot animation less one (a loop or "inv" not counted, 0x10009704-0x10009842) — the post the Loader's time + 2 ticks after the job's first update, the offer on the tick after | **fixed 2026-09-25**: the 2026-09-24 reading (the behaviour posted at the job's start) is withdrawn with its carries — the lost game's run (13 ticks after the loss), 203's shout (his run 71 ticks after hers begins), the co-actor's fight (below), 205's talk (0.33 s into his mat, PCBehaviourAt) and play (her table mutex at his use's end), 210's call (his chair 1.83 s after her call begins) and order (his stands there 1.58 s), 211's puke (below), 213's bull (Olga's ride on the `bull` his step posts as he arrives, his wait on its `leave`: PCBehaviourAt, PCBehaviourAtEnd), 214's pistol (her `standup` at his play's end); `lap_model_s2.Data.loader_time` / `job_ticks` |
| the co-actor's hit | `Routine._hit_begin` / `_hit_pawn_done`, play_angry's affect, PCHitSeconds | the action's behavior (hurt_neighbor …) is posted as its job ends; Olga's / the Mother's script runs her to him (gait 2) and plays the generic `fight` (fcn.1000eb19: 42 / 39 ticks; its object is he: `inv` in its state 0, `ms2` in its state 2; olga_fight / mother_fight on him as it ends), his handler then sets the SHOUT step (204 0x10032b6f, 207 0x1001596a, 210 0x1001a379, 214 0x1003ba90 / 0x1003b677 / 0x1003b328) | **fixed 2026-09-25**: she sets off as his tricked use ends, her hit hides him for the fight's ticks and his SHOUT follows it — the mobile's order (the early set-off of 2026-09-24, `World.pc_affect_early`, is gone); DoAction's job goes on her queue alone (fcn.10049216; the queue fcn.100492a8 locks no other actor) |
| 206's pad and harpoon | `Level206RoutineBehavior._pc_gate`, `Item.pc_masked`, PCTrickArm / PCTrickFire, PCExtraPaysAtLinked | the load step 0x1002e3df's IfVariant ramp / ramp_manip arms the shot after the take (0x1002e27f -> 0x1002df9b shootrabbit 81 / 0x1002e0fd rubberrabbit 73: records 40, 45, 50), the Mother's fight latch ([step+0x24], 0x1002de6a), SHOUT 1, the ramp's repair 19; the shoot step 0x1002d948 asks nothing; the take step's rubber branch 0x1002da29 (rubberbear 69, harpoon_rubber 40, SHOUT 1) goes on to the put 0x1002d578, which switches the harpoon back | **carried 2026-09-24**: the pad fires at the shoot after an armed load, else the shoot plain; the rubber on at the take fires through the pad's DependsOn at the shoot (the take marks GotTricked), a later one is dropped at the put; harpoonAux off; the ExtraCoin206 at its tick |
| 211's rush | the after-toilet angry of the rush's item, PCToiletPaysAt, PCHitSeconds | 0x10030dc2's puke at wcright (40 ticks, wcright at 27, behavior puke on Olga, posted as its job ends) -> her handler 0x100318ce: `mad` (34), her fight step 0x1003183a (42; olga_fight -> his latch +0xd, 0x100301fb) -> 0x10030d0f SHOUT 1 -> 0x10030b9d the sign's repair (walk 34, repair 24) | **carried 2026-09-24**: the angry after the wc (the mobile loses it, ActionManager.cs:597), the record in the puke; her hit her mad and fight after the puke, 6.33 s (**fixed 2026-09-25**: 3.0, the two less the puke under the start reading); differs: the repair at the wc, the walk on from there |
| the camera and the pose elements | instant (`INSTANT`, E2f40 'instant') | Ef51a (fcn.1000f51a): flag 8 only for a nonzero last argument, then it waits while [level+0xc] != 0 (Woody's mini-game); the pose element fcn.10014c5c / fcn.1000de51 (vtable 0x100ab990, update 0x1000cfaa) returns 1 at once; Ef779 (0x1000ce9c) likewise | **carried 2026-09-24**: 207's sand castle over the hedgehog's towel runs its linked continuation (0x1001513f: Olga's `n_lift`, the billboard's `enter` 56 ticks, SHOUT 2) — PCHitSecondsLinked, PCResumeHeadSeconds, PCExtraCoinLinked |
| the result screen | `COLLAPSE!` on an overflow, else the mobile's EXCELLENT / GOOD / PASSED | GUIEngine 0x10001536–0x10001652 fills `dialogs/gameover.xml` (`rating`, `coinsscore`, `lifesscore`, `bonusscore`, `timescore`, `wholescore`) from the status struct (eleven dwords, `push 0xb` at 0x1000515f) and a failed flag: `failed` (FAILURE), else `bonus` (COLLAPSE!) on the collapse byte +0x28, else `perfect` (GOOD JOB!) when coins +0 equal the total +4, else `success` (SUCCESS!) — `generic/strings.xml` | **fixed 2026-09-16**: `pcprofile.s2_result` under the profile; the rows were already the board's |
| the trick amounts | nine PC values in `levels/pc/*.overlay.json`, the rest the mobile's | tricks.xml `coins` / `rage` | agrees (data, the overlays' sources) |
| the routines | the mobile ActionManager orders | `tools/pcref/routine_order_s2.py`: each level script is a chain of step functions handing over through `[obj+8]`; followed with no trick fired, the laps by code are 201 rail → water puddle → captain's cap → buffet → water puddle (mobile: CaptainHat, Buffet, WaterPuddle, DeckRail, WaterPuddle), 203 bike → stage → image → toilet → melons (Microphone, ToiletPaper, ToiletFlush, Watermelon, Bicycle), 205 sand lion → mat → ping-pong → water skis → chef → tyre → firework, rocket → sand lion (OlgaMatBeach, TableTennis, WaterSkiis, Chef, Rockets, SandSculpture), 206 Fifi → blanket → Fifi → ramp → harpoon → dumbbell → Fifi → dynamite bag (DogFifi, DeckChair, Pillows, LaunchPad, Harpoon, Weights, Fifi, Dynamite…), 208 statue → platform → shoe cleaner → elephant (IndianPlatform, ShoeMachine, AngryElephant, ArmsBowl), 211 diving → dish → rod → boat → life vest (Sweets, FishingRod, LifeBoat, LifeJacket, DivingGear), 209 cow → ride → fakir → shoe mat → coal → trough → fuel (FireFakir, HotShoe, TadjMahal, HotShoe, Coal, IceCream, Cow), 212 cliff → parrot → boat → hands → whip → cigars → bank → bull ride (PreAztecThrone, AztecThrone, Whip, CigarBox, SleepBench, MechanicalBull, PreParrotLedge, ParrotLedge), 213 limber wall → carnivore → tortilla → piñata → bull-ride controls → washing tub (LiveBull, PlantCarnivore, Tortilla, BoatPicnic, Pinata, MechanicalBullControls, CementBath) | agrees in order on the nine laps that close; 202, 204, 207 and 214 end at a step that polls an action (202's `waitsea` swim, 0x10022534: the step stores no next and is re-entered until the level's event moves it on) or an event callback, 210 re-arms its deck-chair step — the order past those steps is open |
| the dexterity mini-games | `_dexterity_gate` + `DexterityState`: the remaster's lockpick game (fill 20 → 85 %) | objects.xml's `game` objects (one a level on 201-214, their Woody action's `time` 240-360, a `failed` action whose behaviour sends the neighbour running) and GameLogic's game object (vtable 0x100b1a7c, constructor fcn.100507f4, fcn.100508a1 once a level tick with the mouse): the first three ticks move the mouse onto the field's middle, then the rate 4/3/2/1/0 by the thumb's distance (under 200/400/600/800 in 1/10 px; -(progress x 4 / 10) in -40..-4 beyond it once the progress passed 10) and a push of three sinusoids (20/10/5, 0.0648/-0.1461/0.3696 rad a tick) times a factor from the combine.xml combination's startlevel to its endlevel with min(progress, 90)/90 (the object setter fcn.100452d7, the use_object step fcn.10004353 → fcn.10041735 → +0x40/+0x48); the DoAction step (fcn.10001b2c) adds the rate to the elapsed count clamped at `time`, the progress elapsed x 100 / time (fcn.100507dd), the win at `time`, the `failed` action below 0 — the earlier row's "no such code" was a search for the mobile's vocabulary | carried 2026-09-23: the PC's rates, counts, centring, push and alarm on the remaster's field, the thumb the mouse one to one (PCMinigameTicks / PCMinigameLevels, `DexterityState._pc_tick`, `pcprofile.s2_game_push`); a middle-held game lasts 3 + time/4 ticks; a lost game's neighbour runs onto the object (the `failed` behaviour `run`, registry 0x1003e278 — offered thirteen level ticks after the loss since 2026-09-25: the game's job ends on the next tick, the use_object step pushes the `failed` job in front of itself, which posts the behaviour 10 ticks after its first update, PCMinigameFailedTicks) or nobody comes (201's `aux`, 212, 213: PCMinigameFailed); the order in the level tick the PC's (2026-09-23): the DoAction step is Woody's job (fcn.10049246 pushes it on [actor+0x18], its first run only sets it up; fcn.100492a8 runs it from the actors' pass fcn.10044234, which the level update calls at 0x100445f8) and the game's update comes after it at 0x1004482b, the game made in that job pass (fcn.10041735) — a tick adds the rate the last update left, the first update at the game's start (`DexterityState._pc_update`); the field GFXEngine's since 2026-09-24 (the create message, slot 79 of the GFX visitor: the middle Woody's `minigame` hotspot, 0/-150, above his place for the game — the object's `woody` hotspot, off the room's floor line on thirteen levels (PCMinigameLift: 204 +24, 211 -92) — the camera scrolled onto it, 0x1000aa80 / 0x1000ab08; the draw fcn.1000fcf0: the textures at their own sizes, the icon centred, the thumb at (x + 1000) x (field - thumb) / 2000 of the state message's pair, fcn.1000fa00 — `hud._draw_pc_game`, `World.dexterity_focus`; the vertical progress bar 28 px in, the field's disk inside its ring, since 2026-09-25 — `Hud._draw_pc_game_bar`; its rows floor(progress x height / 100) as GFXEngine's progress widget draws them, vtable 0x100422b8 slot 9 0x10010e90, since 2026-09-26), measured on E04 759 s and E01 176 s (the middle at PC (400, 254)); a lost game's behaviour reaches its actor a level tick later and every tick after it until taken (the walker fcn.1003fc90 before the actors' pass, the votes of fcn.1004abcf: the level scripts' walks interruptible, their actions not — `DexterityState.pc_offer_tick`); open: the progress bar's front image (not in the data, the remaster's fill stands in) |
| detection ("sees Woody") | the mobile's predicate; since 2026-09-23 under the profile the PC's room trigger (`World._pc_s2_sees`) | the level update (at 0x100445f1) runs fcn.1003fc90 over a table of watch entries (an actor, a target, mode bits at +0x1c/+0x1d) and evaluates each with fcn.1003f573: the actor must carry flag 0x20, neither party flag 4 (the hideout flag — set on hiding, e.g. 0x100067e9, cleared by the `leave` action at 0x10006abc), the rooms compared through fcn.10040a7d (the record of the actor's +0x20 name), and in one mode a vertical distance below 15 (0x1003f7d0); a true entry fires an event object (fcn.1003f86d, fcn.1003f972, fcn.1003fa6b, fcn.1003fc6e — no strings); the table is filled from data and code: every action record carrying `behavior=`/`behavioractor=` (62 in the Season 2 objects.xml — the neighbour's `run` after a failed Woody action ×11, Olga's `kid_cry`, the mother's `crash`, …; parsed by fcn.1004fa5c/fcn.1004fbe7/fcn.10050c15 and flagged at +0x24, 0x1000a696), the engine's own per-action entries (fcn.1004008d from the DoActions job's state 0 for an action whose `noise` is above 0, 0x10002478/0x100024af, mode 0) and the scripts' explicit ones (fcn.1004000a: the tutorials' and 201's `tutorial` entries, 213's `bull` and `boat`) | agrees in kind with the mobile's zone containment plus the hiding exemption. The mode bits are read (2026-09-17, fcn.1003f573 with the entry's +0x1c dword as its fourth argument): bit 1 — the two objects' rooms (fcn.10040a7d) are the same; bit 2 — the same room, the same floor record (fcn.1004c945 / fcn.10049006) and a vertical distance below 15 (0x1003f7d0); bit 4 — always true; no bit — never; and before any of them the second object must carry flag 0x20 and neither flag 4 (the hideout), with no sneaking, busy or animation term at all. The walker (fcn.1003fc90) tests an entry without a direct target against every other entry of the table whose ordinal (+0xc) reaches its threshold (+0x18), with the two modes ORed, and latches a hit in +0x1d bit 2. The engine's per-action entries (fcn.1004008d from the DoActions job's state 0, an action's `noise`) and the posted behaviours (fcn.1004000a: the scripts' explicit ones and the actions' own, from the job's state 2) are built with mode 0; the modes come from the parsed action records — `behavior=`/`behavioractor=` with `always="true"` (the 62 reactions: the neighbour's `run` after Woody's `failed`, `tongue`, `kid_cry`, `crash`, …) and the `room` keyword the level parsers compare (0x10070779 …). The catch itself (2026-09-17, later): fcn.1000eb19 (13 call sites, one per level class) runs the catcher's approach step fcn.1000e601 — the two rooms compared through fcn.10040a7d, a point beside the target at the fixed offset [0x100cc814], a path check (fcn.100072b1) and the move (fcn.10007d78) — and starts the `fight` action (the string global 0x100e1b50, fcn.10002cd5) once no step is left; the level classes call it with `neighbor` and a continuation from handlers they subscribe to engine events through fcn.1000e7f2 (18 subscriptions, e.g. event 0xf0 on `pool_deckchair` in the 207 class), and the data's `behavior="run" behavioractor="neighbor"` on Woody's `failed` action is the reaction after it. The per-actor watch entries carry mode 0 (fcn.10001b2c) or 0x100 (fcn.10008b74 — the lookup selector byte), the room bits come from the outer, data-side entries ORed in by the walker. The 13 sites are steps of the per-level actor scripts — fcn.10011655, run from the level constructors (fcn.10044bb5 / fcn.10044ce6), fills the level's table of actor → script (blocks of `woody`/`neighbor`/`mother`/`olga`/`fifi`/`bar_keeper`, one function per level and actor, Woody's the same fcn.100138d6 everywhere; the step chains tools/pcref/routine_order_s2.py reads) — and the step that calls fcn.1000eb19 is entered when fcn.100585c0(`crash`) holds (0x1001462e: `mov [edi+8], 0x1001452c`), i.e. it is the scripted fight with a co-actor after a crash reaction (the `m_hurt_n`, `olga_fight`, `mother_fight` scenes), not the catch of Woody. The catch objects themselves (the fear/fight fiber, vtable 0x100ab258 / 0x100ab278 with fcn.100061dc) are created by fcn.1003c4e3 — one level's `olga` script entry — and by the unheadered fcn.1003f086, which resolves an actor by name and tests its +0x14 flags 2 and 0x50 (the flag helpers fcn.100450bf / fcn.100450dc) and has no code reference at all: it is slot 2 of the vtables 0x100b0ff8 / 0x100b100c (radare2 `/x`), the event objects the level tick itself creates every tick while `[level+0x44]` is empty (the level update at 0x10044386 → fcn.10040f38 → fcn.100403d8 → fcn.100461eb, which resolves an actor by name and sets its flag 0x100000 → fcn.1003f431 → fcn.1003f3df, `new` of 0x18 bytes with four arguments). Those objects are the watch entries themselves: fcn.1003f4d9, which the walker's fire path fcn.1003f86d calls, is their equality (four string fields through the strcmp wrapper fcn.100585c0), fcn.1003f4b8 the list push, and slot 2 the entry's action when it fires — for this class the catch: resolve the actor in the level, test its +0x14 flags 2 / 0x50, start the fiber. The predicate fcn.1003f573 (reread the same day) returns false when the entry's mode byte carries none of 1 / 2 / 4, so a catch entry must be registered with a mode; the per-tick object the tick builds at 0x10044386 is the probe the walker compares the table against. The entries the tick's probe is matched against are the script steps' own: the `use_object` step's start method (0x100469c3, in the step-class vtables 0x100b1328 / 0x100b19c8) registers (`use_object`, the object, …) through fcn.1003f431 — the string global 0x100e1b74 is `use_object`, one of the engine's step kinds next to `goto_pos`, `combine`, `stop`, `crash`, `olga_fight`, `mother_fight` — and the data's `behavior=` records on that object's actions bring the modes (`room`, `always`); a matched pair fires slot 2, which resolves the behaviour's actor, tests its flags and starts the behaviour fiber (fcn.10005b94: the `run` that plays fear, `fight` and the respawn). That is the reaction path — the neighbour's `run` after Woody's failed minigame, Olga's shout — read end to end; a catch on Woody merely walking into the room does not pass through it (no data record names a walk), and where the PC's Season 2 tests that is what remains unread, so the profile's Season 2 keeps the mobile predicates. Read on 2026-09-23 — the walk-in catch is data after all: generic/trigger.xml gives the neighbour and the Mother a `fight` behaviour on Woody, `<trigger object="woody" position="room" type="always"/>` (and Woody a `die` one on either; Olga and the other actors have none), Loader.dll's trigger parser (0x1000a869-0x1000a936) makes `position` room / nearobj / house the mode bits 1 / 2 / 4 and `type` once / always 0x1000 / 0x2000 of the AddObjectTriggerMsg `flag`, and GameLogic's handler (fcn.1004fa5c: actor, actionactor, behavior, flag, object — the message registry binds it at 0x100505a3) files it in the watch table; so the catch is mode 1: both room pointers set and equal, the target placed (0x20), neither party's flag 4. Flag 4 is set by the enter step (vtable 0x100ab2ec, 0x100067d4-0x100067e9) when the entered object carries hideout or neighbor_hideout (0x140), cleared when the leave step's `leave` has played (0x10006ab7), and set or cleared by nine level steps (the complete list of the setter's mask-4 calls: 202's sea and beer, 206's, 210's and 214's Mother asleep and awake, 209's shoe mat — tools/pcref/pc_catch_s2.py) | differed in kind: the mobile's catch had IgnoreWoody, the blocking animations, IsSleeping, PassingComplexMove and DonePassingToOtherZone, its sleep windows the ProgressBars' sequence spans on the same stations; carried since 2026-09-23 (`pcprofile.s2_sight`, `World._pc_s2_sees`, `_pc_flag4_tick`, `Pawn.pc_room`, PCHideout): the room pointer — none on a hop's steps up to the transfer, less the `out` run stood before one, and inside a back door's clips — Woody's hiding through his hideout's leave clip, the catchers' flag 4 at their neighbor_hideout stations with the level steps' clears; the crossing check reads the same predicate |

## Not verified

- The Season 1 step boundaries around other steps: an ACTION lasts its
  time + 2 ticks (carried since 2026-09-26 — "the action durations"), a
  sequence's first update puts a tick before its first step, and the
  GOTO's walk is read and carried (the same evening, docs/PC_FIDELITY.md
  "Season 1 walks"): the GOTO step (vtable 0x4e19e8, update 0x44a7b0)
  pushes its walk job (vtable 0x4e53d0, update 0x475c80: a LEAVE of the
  occupied object first, 0x475ce6, the door steps fcn.00474a20, the
  movers fcn.0047d030) and the walk job its movers with the run-now flag
  1 (the pushes at 0x44a9e6 and 0x4760ad — the first reading of that
  evening had them at 0 and a two-tick stand before every walk), so the
  first move falls in the GOTO's first tick and a leg after a door in
  the far door's last tick; the GOTO's next update ends it a tick after
  the last move, three ticks with no move (tools/pcref/lap_model.py,
  `Pawn._pc1_close`). ENTER and LEAVE of an object, read 2026-09-27: the
  ENTER step (fcn.00473e20 -> vtable 0x4e531c, update 0x473830) sets the
  actor's flag 4 where the object carries the hideout flags 0x140, marks
  the object occupied (fcn.00444a70) and pushes the object's `enter` as an
  ACTION with the run-now flag 1, and its next update — in the tick that
  ACTION ends, the actor's tick updating the next job once one is popped —
  finds the object occupied and ends; the LEAVE step (fcn.00473ea0 ->
  vtable 0x4e5334, update 0x473ae0) frees the object, places the actor,
  pushes the `leave` likewise, and its next update finds nothing occupied,
  clears flag 4 (0x473ccc) and ends. Each is so its ACTION's time + 2, two
  ticks without a record, as the lap model counts them.
- Woody's Season 1 walk, carried 2026-09-27: his clicks reach the same
  GOTO as the neighbour's steps (the level's command handlers at 0x440088
  / 0x44014f / 0x4401fd call fcn.004364f0 / fcn.004368d0, which build it
  through fcn.0044ad10 -> fcn.0044abe0, vtable 0x4e19e8), so his walk is
  the walk job's legs at his records — mg1 / mg3 17 px a tick with `start`
  12, mg0 / mg2 6, sneaking sn1 / sn3 5 with 2, sn0 / sn2 2 — between the
  door types' `woody` / `woody_out` hotspots and the `woody` hotspot of
  the object his action takes place at (tools/pcref/pc_walks_s1.py
  `woody_targets`, pc_woody.py's pairing: the trick combination's base
  object, the one container holding the item's inventory, the hideout), a
  floor click's point mapped into its room; the far door places him at its
  own exit offset. Which object of the room the handlers target on a click
  (the object's `woody` hotspot or the clicked point) is not read
  instruction by instruction: the port takes the hotspot for an item and
  the point for the floor. The neighbour's walk is the PC's since
  2026-09-26 (docs/PC_FIDELITY.md "Season 1 walks": the idle laps within
  1.4 s of tools/pcref/lap_model.py on every level, docs/PC_LAPS.md),
  where the mobile's paths had put the idle laps 0.3-7.7 s off the model
  and single legs 1-3 s (113's angle grinder to the main valve 30.0
  against 26.6); the model's stations sit on the videos' bubbles within
  about a second on E08, E09, E13 and E14 with the door pass as one step
  of its two clips (the row "door transit") and the mover down to the
  floor line and up again between raised points (docs/PC_FIDELITY.md
  "Season 1 walks", "The walker's arguments"; docs/PC_LAPS.md).
- The Season 2 pawns and the Season 1 door rules: `pcprofile.door_warp_early`
  takes the pawn's NFH2Path, which only Woody carries in Season 2 (the
  neighbour, Olga and the Mother have it false — read 2026-09-26 on 211 and
  213), so their walk-up doors (the eight with `enter`/`leave` actions:
  211's cabin, 212's and 213's topright/midright, 214's bridge) have placed
  them at the far door as its clip starts since 2026-09-17, the Season 1
  rule; GameLogic plays those doors as the near door's `enter`, the
  placement at the far door's `<actor>_out` — where the far room is set
  (fcn.10003647, fcn.10003236, fcn.10003454; the row "door transit") — and
  the far door's `leave`, the same order, and the catch reads that room
  (`Pawn.pc_room`), not the zone. The concurrent pass of 2026-09-26 keys on
  the level's season (`doors_concurrent`), and the Season 2 sweep is
  byte-identical under it.
- The Season 1 chains against Badinfos' runs (2026-09-26, remeasured
  2026-09-27): E04 pays its seven 18.2, 12.6, 22.3, 12.2, 19.0 and 26.8 s
  apart, the port's plan 18.2, 12.5, 22.1, 11.8, 19.2 and 26.5 since the
  reaction walks (runs/look_s1; 18.2, 11.9, 21.1, 11.8, 19.0 and 24.6 with
  the door pass and the floor line alone, runs/floor2s1; 18.6, 11.7, 19.0,
  11.8, 18.9 and 22.1 before those). The picture to the oven had been
  split on E04's frames: from the fire (199.9) to case 1's pie icon 11.0 s
  against the port's 9.95 — the shout (93 ticks), then the repair's walk
  from the floor line up to anc/mum_smeared's hotspot (435/390, 30 px: 11
  ticks, fcn.0047ae70 over isActorAtObject) and the clean (25) —, and the
  walk to the kitchen's back door 5.8 s against 4.6, the first 10 ticks of
  it the way down from that hotspot to the floor line; from the pass to
  the oven's fire 10.0 s against 10.05, the pie's own stand about 1.75 s
  against 1.5. Against the thermometers of every Season 1 episode
  (tools/pcref/thermo_jumps.py; a jump within a few seconds of another can
  merge, so the docs' careful readings take precedence — E06's): E03 16.6,
  16.0, 12.7, 14.1 and 12.0 s against 16.4, 16.9, 13.4, 14.6 and 12.5 (the
  letter box's shout and first-aid run, the cake's prime split), E06
  within 0.9 s of its reading, E09 10.3, 37.7, 15.9, 22.4 and 39.2 against
  11.2, 38.3, 15.7, 23.2 and 38.0 (the key board's re-run), E10 within 1.4
  s, E12 within 0.8 s (the skates' wheeze and shout2), E07 within 1.0 s
  once the potter's wheel walks to its tricked hotspot before its repair
  (the generator to the statue 20.7 against 21.2, 17.8 before; the drawing
  and the dove merge in the thermometer); E08 and E13, read off the HUD's
  counter in the frames after each jump, pay other orders than the port's
  plans, and their comparable pairs agree — E08 the deck chair to the
  lotion 12.8 against 13.4, the coffee to the toothbrush 12.9 against
  13.3; E13 the chair to the marbles 16.3 against 17.2, the marbles to the
  grinder 26.5 against 26.5, the ladder to the fuse 13.4 against 13.9; E01
  (microwave > binoculars > TV > sofa), E02 (the laxative beer, then the
  missing paper after his 8-s read on the rush's toilet — the port's plan
  stuffs the toilet before the rush, which fires as he comes in) and E05
  (the bowling ball first) pay other orders too; the S2 sweep of
  2026-09-27 (runs/sun_s2) is byte-identical to runs/floor2s2. E11's chain
  (runs/clean_s1) 23.7, 15.5, 25.3, 26.8, 28.6, 22.0 and 20.4 s against
  Badinfos' 23.7, 16.0, 26.3, 27.6, 29.4, 22.5 and 20.9 (the marbles'
  clean carried), E14's last three 33.2, 8.1 and 19.4 against 33.7, ~8.1
  and ~20.4 (the hat stand's visits, runs/hat114). E11's living room after
  the dog's alarm, read 2026-09-27: a room trigger fires on every tick its
  two rooms match, into a pending list (fcn.00472390, the check
  fcn.00471bc0), and a pending behaviour is offered down the actor's queue
  (fcn.00448180 → fcn.00447d90): the job that takes it — the level class,
  slot 5 (Level_Laundry's 0x454a90 refuses the carpet only in its own
  cases 20-23) — gets it when every job above has its +4 set, which are
  aborted (slot 3) before the class's slot 4 (0x454600: case 20); one
  above with +4 clear keeps it pending. The door step and its ACTION carry
  0 (0x474075, 0x4743de), the walk job 1 (0x4755ff), a GOTO its caller's
  flag (fcn.0044a710; the cases' GoTos pass 1), the cases' lists 0
  (Level_Laundry's eight fcn.00476770 calls) and the pet alarm's list 1
  (fcn.0047a690). So in E11 the carpet waits through the living-room door,
  the alarm's walk to the room ends, case 18 shows `dog_shout` and pushes
  its list, the carpet aborts it and case 20 plays the `search` (the
  bubble: `?!` to 212.25, `dog_shout` 212.5-214.5, the vacuum from
  214.75). The port plays that search since (runs/search111: the entry
  315.8, the search 317.8-320.0, the fire 326.0 — 10.2 s against the PC's
  11.3, 8.0 before); the other 1.1 s lie in the vacuum's case 22 (E11: the
  take ends ~217.1 and the vacuum clip starts ~218.8, where the port walks
  the 70 px between the two hotspots in 0.8 s — not read further). A
  carpet met during a case's list (+4 clear) would wait for the list's end
  on the PC; no plan meets it, and the port takes it at the door.
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
  busy window, as carried. The position object is the room, the hall
  too (settled 2026-09-25: set by name through fcn.00448d70 and compared
  with the walk route's rooms by name, 0x475ebb-0x475f00; `anc`'s two or
  three walkable `<floor>` strips carry no name), as the port's zone.

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
  name is bit 2 stays unread (reread on 2026-09-25: Loader.dll's
  `<flag>` parser, 0x10009c80-0x1000a04d, compares the name with its
  wide-string globals and stores the mask — container 0x10, hideout
  0x40, singleuse 0x80, neighbor_hideout 0x100, doorup 0x200, doordown
  0x400, doorleft 0x800, doorright 0x1000, remove 0x2000, autotake
  0x4000, bad 0x8000, game 0x20000; none is 2, bit 2 is a state). What
  bit 2 does is read: the actor tick
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
  or holds a walk-by stand for them (the Duration branch); 111's machines
  since 2026-09-23 (the give, the wash or dry and the take, one per leg);
  106's bath and towel, 104's shaving chain, 107's drawing, 113's ladder
  drill and 114's medal box since 2026-09-25 (below).
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
- `tools/pcref/pc_minigames.py`, `levels/pc/*.overlay.json`,
  `runtime/scene.py`, `runtime/world.py` (2026-09-24, later): the
  mini-game's middle from Woody's place for the game — the object's
  `woody` hotspot, PCMinigameLift px above the room's floor line (201 55,
  202 -7, 203 60, 204 24, 205 13, 206 38, 207 -2, 208 76, 209 0, 210 11,
  211 -92, 212 20, 213 -79, 214 84) — taken from the walking line: 204's
  field 150 px above the drawn shoes as on E04 (127 before). runs/sw21s2
  byte-identical to sw20s2, S1 and the mobile regression unchanged.
- `runtime/world.py`, `runtime/scene.py`, `runtime/behaviors.py`,
  `tools/pcref/lap_model_s2.py`, `tools/pcref/pc_minigames.py`,
  `tools/pcref/pc_durations_s2.py`, `tools/pcref/pc_durations_others.py`,
  `levels/pc/Level2*.overlay.json`, `tests/plans/pc/s2/Level210.txt`,
  `Level211.txt` (2026-09-25): an action's behaviour is posted as its
  DoActions job ends (the row "an action's behaviour": state 2,
  fcn.1004000a at 0x10002708; the start's fcn.100018a6 carries a text) —
  the reading of 2026-09-24 and its carries withdrawn: the lost game's
  run offered 13 ticks after the loss (PCMinigameFailedTicks 10 on all
  fourteen), 203's his 71 ticks after her shout begins; the co-actor's
  fight in the mobile's order (his action's end, her hit hiding him, his
  SHOUT after it; `World.pc_affect_early` gone); 205's talk cutting her
  mat's loop 0.33 s into his stay (PCBehaviourAt) and her table mutex at
  his play's end; 210's chair 1.83 s after her call begins (PCWaitFor
  `then`) and his stands at hers her order's 1.58 s (Stand_Left); 211's
  puke hit 6.33 s (her mad and fight); 213's bull by code (the controls
  0.92 and 0.08, no wait stay, her ride 6.75, her loop cut on `bull` 0.08 s
  into his controls, his on `leave` 0.17 s after her ride: his bull span
  11.75 s against the video's 12.0, 17.2 before); 214's `standup` at his
  play's end. 210 re-planned (v25: the net on her first nap, 100 at
  296.0 s), 211 (the child and the phone after her lap-3 visit, the
  overflow at 259.6 s); runs/end2s2 all 14 at 100, S1 (end1s1) and the
  mobile regression (end1mob) byte-identical.
- `tools/pcref/lap_model_s2.py`, `tools/pcref/pc_durations_s2.py`,
  `levels/pc/Level202/205/207/210.overlay.json`,
  `tests/plans/pc/s2/Level202.txt` (2026-09-25, later): the lap model's
  action ticks by Loader.dll's time="auto" rule (the longer oneshot of the
  actor's and the object's animation, a loop not counted: 205's chef 4.58
  s and rocket 2.5, 207's bartender 7.83, 210's tricked basket 1.75 s
  longer by the bone's 40-frame bark); 202's kid dives on his own queue
  (the dive step pushes the dive, the switch and the run ashore onto the
  kid, 0x100220a1-0x100221e3, and goes on to the sea step): the swim holds
  WaitSea only until Olga's sub is in the sea (the 10.33 s after it
  withdrawn), his lap ~77 s; 202 v7 (the same chain, 100 at 307.6 s).
  The elements' own ticks, open that evening, carried in the next entry.
  `pc_durations_s2.py --code-keys` writes the code's stays too
  (`write_code_stays`: code_stays, STAYS_CODE, RUSH). runs/end4s2.
- `tools/pcref/lap_model_s2.py`, `levels/pc/Level2*.overlay.json`,
  `runtime/hud.py`, `runtime/pcprofile.py`, `tests/plans/pc/s2/Level208.txt`,
  `Level211.txt` (2026-09-25, night): the elements' own ticks in the lap
  model — an action its whole job (the Loader's time + 2), an element
  done on its first update a tick (the sequence 0x1000ad52 pushes it with
  a first run and returns 0), a step a tick and a walking step three (the
  script's job runs the step and returns 0; the GoTo's first tick before
  the walk and its done tick after the arrival, 0x10007670 / 0x10007409;
  `step_ticks`); every Season 2 writer re-run (the stays, clips, tricked
  keys, the co-actors' clips and bars, the door passes' enter/leave, 201's
  rail repair, 205's pant): the stays 0.1-0.5 s longer, the laps 0.9-2.4 s;
  207's linked lift keeps its resume (the record pays within the lift).
  The mini-game's progress bar from the minigame xml (vertical, 28/28):
  the field's disk inside its ring from the remaster's full field, rows
  from the bottom up. 208 (`park!` through Zone05 after the rat) and 211
  (the Mother's sleep before her lap-3 visit) re-timed: runs/end6s2 all 14
  at 100; S1 end6s1 and the mobile regression end6mob byte-identical.
- `runtime/world.py`, `runtime/pcprofile.py`, `runtime/render.py`,
  `runtime/viewer.py`, `tools/pcref/pc_walks_s2.py`,
  `levels/pc/Level2*.overlay.json` (2026-09-25, night): the Season 2
  respawn by the catch fiber — the room of fcn.10005f58 (PCRoom
  `hideout`, the names' order, the `bad` actors' rooms and flag 4),
  Woody on the middle of its floor, held through the `respawn` action's
  39 ticks, the life taken at its end, then the respawn timer's 60 ticks
  without a catch (both behaviours' predicates) and the outline; the
  last life ends the level (a fourth attempt before). Loader.dll's flag
  names read (0x10009c80-0x1000a04d): container 0x10, hideout 0x40,
  singleuse 0x80, neighbor_hideout 0x100, doorup 0x200, doordown 0x400,
  doorleft 0x800, doorright 0x1000, remove 0x2000, autotake 0x4000, bad
  0x8000, game 0x20000. The row's misreading withdrawn: fcn.1003cc45 is
  the actor's name, the timer is read by the behaviours' predicates.
- `runtime/pcprofile.py`, `runtime/world.py` (2026-09-25, night): the
  Season 1 jingles by the level state less 2 (game.exe 0x440f23-0x440f34,
  the message fcn.00437de0 posts on each change to 2..5): under the
  profile a catch's beating ends on the failed or the success jingle by
  the quota, time's up plays failed or success, every success the normal
  one (`S1_JINGLES`, `s1_jingles`). The hall's position object settled
  as the room (the `<floor>` strips have no name; the walk compares its
  route's rooms by name).
- `runtime/world.py`, `runtime/pcprofile.py` (2026-09-25, later still):
  109's bed as the PC's hideout (flag 4 from the enter, the noise wake,
  BedOut, the alarm clock skipped); the Season 1 pets' awake timer, their
  whine at the neighbour and their first bark (the `wakeup` action's 8 / 11
  ticks) for the neighbour's hearing and Woody's startle; the Season 2
  catch's click read (kept pending, re-offered each tick).
- `runtime/world.py`, `runtime/pcprofile.py`, `tools/pcref/pc_respawn_s2.py`,
  `levels/pc/Season2.overlay.json` (2026-09-25, later): the respawn's
  landing from the remaster's unused W_Landing.png as the PC's `respawn`
  (38 frames, the sounds, the gfxdata registration, the 900 px fall by
  the translation), and the catch fight a frame a tick with the respawn
  at the `fight` job's end (45 / 51 ticks); `apply_overlay` matches by a
  component's fields and takes the Season 2 file first. The row "doorways
  are safe transit" settled by the door transit reading of 2026-09-17.
- `tools/pcref/lap_model.py`, `tools/pcref/routine_order.py`,
  `tools/pcref/pc_durations.py`, `levels/pc/Level1*.overlay.json`
  (2026-09-25, later still): every Season 1 routine item has its PC
  seconds — the actors' own action records read (objects.xml `<actor>`
  blocks), an action's name the string that names a record, an actor's
  hotspot at its level.xml position plus the offset (fcn.00445aa0), the
  bath's two-lap cycle (fcn.0046bc90), the walk's leave closing the
  station it leaves; the pairs split by action names ('+' sums): 104's
  shaving chain and second pie visit, 106's fill, bath and towel, 107's
  drawing, 113's Ladder / LadderDrill, 114's Hat / MedalBox / Hat, 112's
  mixer. runs/dur1s1 all 14 at 100.
- `runtime/world.py`, `runtime/scene.py`, `tools/pcref/lap_model.py`,
  `levels/pc/Level107.overlay.json` (the same night): a visit the PC
  plays no action at — 107's ENTER of the stool, whose `enter` the
  object has no record of (the ACTION step's start fcn.004772f0 pushes
  no job) — is PCUseSeconds [0.0]: no pose, no clip, the stand ends at
  once (`RoutineAction.pc_zero_visit`); the mobile's DieselStart (0.4 s)
  is gone from the lap.
- `tools/pcref/lap_model.py`, `tools/pcref/trick_branches.py`,
  `levels/pc/Level1*.overlay.json` (the same night, later): `time="auto"`
  as NFH1's Loader.dll stores it (0x1000a865-0x1000aa05: the longer of the
  actor's and the object's oneshot animation less one, at least 0, a loop
  or a missing one -1, `inv` not asked — NFH2's rule): every `auto` action
  a tick shorter, 107's doors 19/19 and 11/22 like the other levels'
  explicit times (0 in the model before), 114's tricked phonograph its
  `play` (the object's 15-frame oneshot, not the neighbour's looping
  `ms0`); the actors' records of generic/objects.xml in the model's
  lookup; the lap model's 107 48.4 s (video 54). The Season 1 pets under
  the profile (`runtime/world.py` AlerterFSM, `pcprofile.S1_PET_BARK` /
  `S1_PET_WHINE`): a bark or a whine is an action that holds the class's
  step — the remaster's clips at its ticks, every bark's noise 2 heard
  again, Woody noticed and the neighbour's leaving taken as it ends, the
  pet asleep the tick its timer ends in the idle.
- `runtime/pcprofile.py` (the same night): the pets' `wakeup` by the
  Loader's rule — 7 ticks the dog, 10 the parrot (8 and 11, the frames,
  before): the first bark, the neighbour's hearing and Woody's flinch a
  tick earlier.
- `runtime/pcprofile.py` (the same night, later): the shouts' lengths —
  Season 1's fire plays its shout as an ACTION step (0x47bf7d over
  fcn.00477f60), so it lasts the record's time as the Loader stores it,
  the oneshot's frames less one (`S1_SHOUT_TICKS`: shout2_extra 91,
  shout0_light 24, shout0_medium 44, shout0 and shout2 25); Season 2's
  SHOUT element lasts its DoActions job and its own two updates, the
  Loader's time + 4 (`S2_SHOUT_TICKS`: 29, 88, 29; the freakouts 40, 41,
  66) — the frames before.
- `runtime/world.py`, `runtime/scene.py`, `tools/pcref/pc_durations.py`,
  `levels/pc/Level109.overlay.json` (2026-09-26): 109's noise wake reread
  — the pig class pushes the LEAVE of bed/bed_sleep (0x468aff) and then
  the SwitchObjects callback (fcn.00468700, instant): BedOut at the
  `leave`'s 16 ticks (PCLeaveSeconds, pc_durations.py LEAVES). A clip
  the profile paces (a time_scale, or a door strip at clip_fps) starts
  with its first frame's time in the accumulator (`AnimPlayer._set_start`):
  the mobile's Refresh advances on its first call, which left every paced
  clip one frame time short of its PC action less an app frame (BedOut
  1.27 s for 1.33) — stations, stands, repairs, shouts, the pets' barks
  and the door strips last their ticks now.
- `tools/pcref/pc_woody.py`, `runtime/world.py`, `runtime/scene.py`,
  `levels/pc/Level1*.overlay.json` (2026-09-26): Woody's trick actions —
  the object's action named after the inventory item (or `use`), a
  floor's `laydown` — at the Loader's times under the profile
  (PCWoodySeconds): 1.92 s or 0.92 s where the remaster plays 1.2, 0.25
  s for a floor drop where it plays 0.57, 15 s for 102's saw.
- `tools/pcref/pc_woody.py`, `levels/pc/Level2*.overlay.json` (the same
  night): Season 2's Woody tricks at the DoActions job's ticks (the
  Loader's time + 2), paired by the inventory the mobile item takes.
- `tools/pcref/pc_woody.py`, `levels/pc/Level1*.overlay.json`,
  `runtime/world.py`, `tests/run_tricks.py` (the same night): the Season 1
  containers — Woody's `take` of the PC object whose contents are the
  SearchItem's inventory (PCWoodySeconds `use`), the remaster's whole
  search paced to it: its one-frame pick-up and the take sequence after
  it (TakeInventory and WoodyPickUpHigh, 1.52 s together) — 1.5 s on most,
  as before, 0.92 s at the rubbish bins, 1.17 s at the first aid (pacing
  the pick-up alone had put 1.4 s on every search and lost six plans).
  The harness's `use_time` reads PCWoodySeconds.
- `tools/pcref/pc_woody.py`, `levels/pc/Level2*.overlay.json` (the same
  night): Season 2's containers — Woody's `take` as a 16-tick job, the
  remaster's 1.9-2.9-s search paced to it; the mini-game items
  (PCMinigameTicks) left out.
- `tools/pcref/pc_woody.py`, `runtime/world.py`, `levels/pc/Level1*.overlay.json`
  (the same night): Woody's hideouts under the profile — the hide clip and
  the leave clip at the PC `enter` and `leave` (PCWoodySeconds `enter` /
  `leave`: the wardrobe 1.58 s each, the bed 0.33 where the remaster
  plays 2.0); the S1 LEAVE step clears flag 4 at its start (0x473ccc) —
  corrected 2026-09-27: at its end, once the `leave` ACTION has played
  (the Woody row above).
- `tools/pcref/pc_woody.py`, `levels/pc/Level2*.overlay.json` (the same
  night): Season 2's hideouts — Woody's `enter` and `leave` jobs, the
  HideItem paired with the level's hideout object (one of each, else by
  a shared word: the lorry, the statue).
- `runtime/hud.py` (the same night): the mini-game's progress bar rows
  read — GFXEngine's progress widget (vtable 0x100422b8, made by
  fcn.100103f0 into the game's +4, maximum 100; the draw 0x10010e90)
  fills from the bottom by value x height / maximum in unsigned integers;
  the port computes the rows so (it multiplied a float before).
- `tools/pcref/pc_durations.py`, `runtime/world.py`,
  `levels/pc/Level1*.overlay.json` (the same night): the pets' alarm read
  — the `noise` case runs him to the pet's room, the next case plays his
  `search` (fcn.0047a690, 24 ticks): the remaster's Search at the
  alerter at that pace (PCSurpriseSeconds 2.0 s on the Alerter,
  pc_durations.py ALERTERS).
- `tools/pcref/lap_model.py`, `tools/pcref/trick_branches.py`,
  `tools/pcref/pc_durations.py`, `tools/pcref/pc_woody.py`,
  `runtime/pcprofile.py`, `levels/pc/Level1*.overlay.json` (2026-09-26,
  later): the Season 1 action's job — the ACTION step's timer is done on
  its (time + 1)th update, the first a tick after the push, so every
  action the profile times was carried at its time + 1 ticks: the stations
  and the tricked stands, the doors (`DOOR_TICKS`), the shouts
  (`S1_SHOUT_TICKS`), the pets' clips, Woody's actions and the alerters'
  leave (docs/PC_LAPS.md). The
  Woody writer sets PCWoodySeconds in place: the patches pc_reactions.py
  merges its keys into had kept a stale copy beside the new one.
- `levels/pc/Level104.overlay.json`, `runtime/pcprofile.py` (the same
  day): 104's lap is game.exe's — level_pie (class 46198c) runs the pie,
  the oven (put_apple_pie, cook, take_apple_pie, after the dirty oven's
  trick step as well: case 4, 0x461b61-0x461e5f), the cream and the eat,
  the basin: the mobile's order and its ReuseAfterFix. The overlay's
  reorder (the microwave after the eat, read off E04's thermometer as
  "the cream followed by the microwave at once") and its ReuseAfterFix
  off are gone, and the overlay ops that served them (`actions_by_index`,
  `actions`, the `owner` match). E04's frames pay the cream's eat 114.6 s
  (cold), the bathroom soap 132.8, the toilet 145.4, the aftershave 167.7,
  the deodorant 179.9, the picture 198.9 and the dirty oven 225.7 on his
  next oven visit — the plan's chain since (v8).
- `runtime/world.py` (the same day): a station the mobile makes a walk-by
  fires on his arrival — 111's rack, whose case 14 fires its OBJ2
  bal/clothes_food at once (PCFireAt 0), then the repair and the take;
  the port had played the remaster's FindLeft (1.6 s) first. Its surprise
  clip plays at the tricked stand's pace (the take, 0.33 s).
- `tests/plans/pc/s1/Level111.txt` (the same day, v18): E11's drier to
  vacuum is a run — the dog in the living room, woken by Woody walking
  through, barks while the drier's shout plays, and the `noise` alarm
  (E11's `?!` bubble from 205, 9.5 s after the fire) runs him up from the
  basement into the carpet's room; the frames also put the ironing board
  (278.8) before the fish tank (301.3), the order the plan pays.
- `tools/pcref/lap_model.py`, `tools/pcref/trick_branches.py`,
  `tools/pcref/pc_durations.py`, `runtime/pcprofile.py`,
  `levels/pc/Level1*.overlay.json`, `tests/test_hud_pc.py` (the same
  evening): the ACTION step is time + 2, not + 1 — its update starts it on
  the first call and returns not done (0x477ad6), ends it on the call in
  the timer's last tick (0x477b3b), and the sequence or the level class
  pushes the next step with the run-now flag 0, so it starts a tick later;
  no timer (the longest time 0) is two ticks. `DOOR_TICKS` 21 + 21,
  13 + 24, Woody 17 + 25, 20 + 26, 11 + 27; `S1_SHOUT_TICKS` 93, 26, 46,
  27, 27; the pets' wake-up 9 and 12, barks 37 and 24, whines 25 and 31;
  the overlays regenerated. The lap model's station pairing walks lap 1
  (`model(steady=False)`; the steady lap from the walker's wrap had left
  108's toothbrush and 113's chair kit without their actions), its
  stations put a steady lap's split first station first. All 28 plans at
  100; E04's chain now 18.6, 11.7, 19.0, 11.8, 18.9, 22.1 s against the
  video's 18.2, 12.6, 22.3, 12.2, 19.0, 26.8.
