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
| the moment it ends | the mobile's WinGameOnCompleteAllTricks: GameEnding at the pay and PlayWinAnimations 2.5 s later | state 5 is tested when the flag +0x8a is set (fcn.00436bb0 reads and clears it each tick): the StopMsg closing the fire's list sets it (fcn.0047bc90, the StopMsg message's slot 2 0x47c4a0 calls it on the step's tick; 0x47bfdd) — after the trick's shout; until then the level runs on (the catch on sight tested first); E01: the TV's fire 350.0 (the tricks' counter), its shout2_extra (a bonus) to 358.0, Woody's win 358.5, the board 360.67; tutorial_3: the fire ≈209.75, the shout2 to 215.25, the win 215.5, the board 219.5 | **fixed 2026-10-03**: `World._pc_s1_success` under the profile (the win on the StopMsg's tick; tutorial_3 in the port: the win 5.50 s after the fire, the board 9.7 s, the video 5.5 and 9.75); a last trick without its StopMsg (flag 1, PCStopSkip: 102's beer, 105's plant, 106's towel, candy and tub, 110's barbecue, 112's skates, 114's medal box) ends by its level class's own StopMsgs (0x46076c, 0x463554, 0x465903, 0x46d06a, 0x46d1cf, 0x46eb76, 0x470241) — **carried 2026-10-04** (PCEndAfter, `World.pc_end_after`: the rush's toilet business, his next use of the towel or the hat, the skate's reaction, the sound extinguisher's shout at the burning barbecue — which the tool's tail now plays: PCToolShout, PCToolRepair) |
| the level ends when the rating reaches 100 | not modelled | state 5 on score ≥ 100 after the reaction | equivalent on every level: the sum of the trick scores is 76–91, so 100 needs the last trick and the ticks together (data, docs/PC_LAPS.md) |
| time's up: success at or above minquota | `calculate_score`: won = rating ≥ `pc_min_rating` | state 5 / 4 by `minquota` | agrees |
| a catch with the quota reached is still a success | `_catch` → `_finish_game` → `calculate_score` (won by the quota) | state 5 from state 1 when score ≥ minquota | agrees |
| the jingles | the mobile's: caught at a catch and nothing after, success or perfect by the rating, perfect for all the tricks | the table by the state less 2 (above): caught on the catch's state 3, then failed or success on 2 / 5; failed on time's up; success (never perfect) on 5 | **fixed 2026-09-25**: `pcprofile.S1_JINGLES` under the profile (`_after_hit`, `finish_game_on_hud_click`, `_win`) |
| the trick's jingle | none: MusicPlayer.PlayJokeMusic (the Joke clip, jingle_joke) has no caller | Season 1: the fire posts `music/jingle_joke.mp3` (0x51b570) through the same jingle message as the end's (fcn.00438690: vtable 0x4e0a1c, a listener's slot 41; at 0x47be4f, after the face 0x47be39) when it scores — a fire of no points leaves at 0x47bdcf first —, with no music stop before it (the end's jingles stop the music first, the level's slot 10, 0x440f20). Season 2: an action's record list plays it on the tick of each `<trick>` record with jingle="true", named or not, credited or not (fcn.1000140b: the credit block, then the flag +0xc at 0x10001528 -> fcn.10041ffb); Loader.dll reads each record's attributes by name (0x10009b8f-0x10009c9f: jingle a bool, false unless set) — 87 of the 175 records carry it, most on the tick of the record they sit by, some on the action's tick 0 before it (201's cap and buffet, 202's rail and rake, 208's tap). SFXEngine.dll plays a jingle as an intermezzo (`InterMezzo playMusic`, `Callback::InterMezzoStreamEnd`): its start closes the other streams with their places kept (0x10003d70: the position saved, AIL_close_stream), its end callback reopens them there (`restoreVolumes`, 0x10002e10), and one while another plays is refused (`intermezzo Rejected Slot Playing`, 0x10002fa4) | **carried 2026-10-04** (`World.pc_trick_jingle`, `SoundBank.play_intermezzo` on a channel of its own, the level track paused under it and resumed): Season 1 in `s1_fire` when it pays (101: the four fires, the four jingles); Season 2 on the read flows' clock — PCJingleAt / PCJingleAtLinked, the jingle records of the tricked flow (lap_model_s2._step_jingles, PCCreditAt's clock; `Routine.pc_jingles`) and 207's lift from its start (PCHitJinglesLinked) —, on the stand-ins' credit where their record carries the jingle on its own tick (PCJingle, tools/pcref/coins.py STAND_IN: 9 items; 205's chef, 208's elephant line and platform, 209's fakir and coals, 211's boat and 213's piñata read as tricked flows since, PCJingleAt, and 202's weeded rake and 208's tap, whose jingle is the action's tick 0); 202's plan: the beer mat's and the shark's with their credits (251.28, 271.65), the weeded rake's 0.33 s before rake_ground (260.40), the linked rail's 0.67 s and 0.42 s before bridge_crash and bridge_electrify (307.23, 309.42); 211's kid in the cabin phone's linked `crash` since (PCJingleAtLinked) (docs/PC_FIDELITY.md, "The trick's jingle"; 204's vase, 209's trough, 210's diving board and 212's second throne pay in their partner's linked flows, PCJingleAtLinked); the reference holds the track 2.4-2.6 s a jingle (E02's five, tools/pcref/music_tracks.py) where the remaster's clip lasts 3.68 s (1.58 s of it silence) — the PC's jingle_joke.mp3 is not in the copy |
| the level's music | LevelSounds[1] (MusicPlayer.GetLevelMusic), one track, from 15 s in | game.exe keeps two names on the level state: its mood +0x3c (`normal` at the level's start, 0x43bafd, and again as the start job ends, fcn.00471570; `slow` as a sneaking walk starts — the step at 0x472e90 sets the actor's gait 1 and the mood, 0x472ef2 —, `normal` as it stops, 0x472d8c) and an override +0x40 (`fast` from the pet alarm's noise case on, set by ten level classes with the noise icon — 0x454253, 0x4563c6, 0x458e5c, 0x459b9d, 0x45e430, 0x461597, 0x46507f, 0x468334, 0x46b4f8, 0x46ece3 —, cleared by the alarm's list as the search comes, fcn.0047a690 at 0x47a6d5, and at 0x46ed53); every 12 ticks the level update posts the override, else the mood, with a fade of 500 ms (fcn.00438280, the message 0x4e0a10 to a listener's slot 45; SFXEngine's crossFade::playMusic); its first update stops the music and plays jingle_levelstart (0x43b245-0x43b259); each level draws its set at random, ingame1 or ingame2 (fcn.0040eef0(2) on the app's Mersenne Twister, fcn.0040ef50: `normal`, `fast`, `slow` to music/ingame<k>_*.mp3) — the remaster's scenes ship both sets (LevelSounds ingame1_*, AlternateLevelSounds ingame2_*); the options carry `dynamicmusic` (options +0x12, 0 in their constructor 0x40a8f0, the config's value loaded at 0x40a494) whose effect is not located; Season 2's leveldata.xml names one track a level | **carried 2026-10-04** (`World._pc_music_tick`, `SoundBank.pc_track` / `play_intermezzo`): the clap is the level's first-update jingle, an intermezzo (`World.play_clap`); the level draws its set on a generator of its own; every 12 ticks it posts the override (`fast` from the neighbour's run to a pet — the `noise` case — to his arrival, the next case: `World.pc_music_override` from `Routine.start_urgent` / `_urgent_arrived`), else the mood (`slow` while Woody's walk sneaks, else `normal`); SFXEngine's crossFade (fcn.10002e90): the same clip plays on, another fades in over 500 ms on the free slot at the playing one's place (fcn.100041d0 -> fcn.100041a0) while the old fades out, the first from its top without a fade (0x1000344f), and under an intermezzo the slot takes the new clip closed and opens it at the kept place as the intermezzo ends (0x10003129 -> playMusic; restoreVolumes, fcn.10004400 -> fcn.10003d70(1)). The reference (tools/pcref/music_tracks.py over the fourteen episodes): each plays one set (ingame1 six, ingame2 eight), slow at the normal clip's place in E08-E14's sneaking walks, fast in E11 and E13's alarms, the track from its top as the clap's 15.0 s end (E09-E11, E13: 14.87-15.04 s), each trick jingle holding it 2.4-2.6 s (its intermezzo: the PC's jingle_joke.mp3 is not in the copy, the remaster's is 3.68 s with 1.58 s of silence at its end); the dynamicmusic option's reader is not located and the reference plays the moods. Open: E02 opened its clip 5.6 s in at the clap's end (a slot's stale place, fcn.10003d70(1) sets the kept +0x40; not carried) |
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
| the instant steps and the fire step | the stands counted the ACTION steps alone (their time + 2): a list's own first update, its message steps and StopMsgs, the fire step's own ticks around the shout and a reaction handler's list went uncounted — the trick's shout started with the fire, the next step with the shout's end | a case pushes its list (fcn.00476770) with the run-now flag 0 (Level_Laundry's tail 0x456da4-0x456dbf; 106 of the level classes' job pushes carry a literal 0, 5 in the GOTO code 1) and the list's update (0x476530) pushes one element a call, with the run-now flag 0, returning not done until its count is out: the list's first update is a tick before its first element; a message step (fcn.0047c640: vtable 0x4e59b8, update 0x47c550 calls the message's slot 2 and returns done — the SWITCH, OBJ1, the switch back after a take, a gait) and a StopMsg (fcn.0047c6c0, fcn.0047c480's message in the same wrapper) are a tick each — the level classes post 279 ACTIONs, 138 message steps and 92 StopMsgs into their lists. The fire (fcn.0047c290 / fcn.0047c320 / fcn.0047c3b0, vtable 0x4e5944, update 0x47bd00) is a step of its own: its first update fires — the score, the rage, the face, the jingle (0x51b570) — and pushes a list (0x47be5b; 0x47c015-0x47c031, the run-now flag 0) of the step's own clip (+0x18: the five- and four-argument steps' fall, shock or explode), unless flag 2 the `shout` message (fcn.004618b0 over 0x51b580) and the shout ACTION, unless flag 1 a StopMsg whose callback fcn.0047bc90 sets the actor's +0x8a (the level's end check), and returns not done; its second update, as that list ends, ends it: flags 0 and no clip of its own, the shout starts three ticks after the fire and the stand's next step four ticks after the shout's end (the shout's time + 6 where the port had + 2); a fire that scores nothing pushes no list (two ticks); the S1 sites' flags are 0, 2 (109's cactus clock, 108's coffee, 102's sofa and paper) or 3. The repair helper fcn.0047ae70 posts its GoTo (when he stands off the object), the repair or clean ACTION and a message step (fcn.0047add0, the object switched back). A reaction handler (the looks fcn.0047d520 / fcn.0047d780 / fcn.0047d9e0 and 111's board in Level_Laundry, the slips fcn.0047b6a0 / fcn.0047d0e0 / fcn.0047ddc0, the trap fcn.0047b470) builds a list [StopMsg, …] and pushes it with the run-now flag 0 as the trigger pass delivers the behaviour (fcn.00448180 at 0x472620, inside fcn.00472390, which the level's update runs at 0x43b2ee before the rules fcn.00439cd0 and the actors' ticks at 0x439d91): the list's first update falls in that tick's actors' pass, the StopMsg on the next, the handler's first element two ticks after the trigger; a slip's list ends with the floor object's removal (fcn.0047b610 in the same wrapper) | differed; carried since 2026-09-27: the fire step's ticks in World.play_angry (`_s1_fire_stands`: pcprofile.S1_FIRE_LEAD_TICKS 2, S1_FIRE_ICON_TICKS 1, S1_FIRE_STOP_TICKS 1; PCStopSkip = flag 1; PCFireLead where an early fire's paced span carries the lead — the use past PCFireAt, the fall, the shock, FIRE_LEAD added to it); the handlers' PCReactLead 2 stood in Routine._on_surprise_near before the fire or the GoToObjX, PCReactTail 1 after the repair or the removal; the instant steps a tick each in tools/pcref/lap_model.py (routine_order.py's INSTANT labels) → the stations' PCUseSeconds (pc_durations.py: with the action they precede), and in trick_branches.summarise → the tricked stands (with the action they precede, `pre_fire` right before the fire); the idle laps then match the lap model within 1.6 s a lap on all 14 (runs/idlejt). Against Badinfos' thermometers (tools: scratchpad chaincmp over thermo_jumps, the order-comparable pairs of 103, 104, 109, 110, 111, 112 and 114, n = 45) the port's gaps had run 0.40 s short of the PC's on average; with the fire step's ticks −0.06, with every instant +0.18, and with the walk's boundaries read on the same day (a GOTO ends in its last move's tick, a door's pass starts in it: the row "the walking speed") the 45 pairs average −0.03 s, their mean distance 0.38 s against 0.52 (runs/fin_s1); the idle laps match tools/pcref/lap_model.py within 1.3 s a lap on all 14 (runs/idlewalk4). The profile's waits and paced clips end on the frame their whole ticks are reached (pcprofile.TIMER_EPS: k/12 s counted down in 1/60 s steps had cost one frame more on 50 of the first 60 k). The skate's list (Level_Fitness 0x46303e-0x46355a: its start, a StopMsg, two message steps and a StopMsg before the slide, a 12-tick wait (fcn.0047e520) and a StopMsg before the fire, the gait messages around the walk back in, a StopMsg after the shout2) is the RollerSkater's own sequence, carried on 2026-09-27 (45946e0: PCReactLead 6 — the slide's first move six ticks after the trigger —, PCSlideTo at the skate gait, PCFallSeconds with the timer and the StopMsg, a tick for each gait message, `wheeze`, the explicit `shout2` and the tick after it in `RollerSkaterBehavior`); the pet alarm's list (fcn.0047a690: pushed with the run-now flag 0, no StopMsg) likewise (5b8cac2: its first update a tick before the `search`, then `shout0_light` at the pet — tools/pcref/pc_durations.py). The four-argument fire's ready step (+0x18, the list's first element) plays after the pay, not before it (read 2026-09-27: 0x47bd00 scores on its first call, 0x47bdb4-0x47be4f, then pushes the list, 0x47be5b-0x47be7c; E09's thermometer jumps as the hand leaves the cactus, 2346.6 s, before the bed's LEAVE): the stands of 109's cactus clock, 102's laxative beer, 101's fart bag and 110's fuel beer fire at PCFireAt (3.0, 1.417, 4.333, 2.75 s) with their ready steps after it (tools/pcref/trick_branches.py `_ready_after`) — 109's bed to the alarm clock 38.1 s against the video's 38.0, where it had run 39.9 |
| a slip's fall | PCSlipSeconds 2.75: slip1/slip3's 31 frames and the fire's two ticks | the fall is an ACTION step of the fire's list: `auto` over the 31-frame oneshot is 30 (the Loader's frames less one), the step 32 ticks, as the doubletake's 16 | **fixed 2026-10-04**: PCSlipSeconds 2.833 on the twelve levels' floor tricks (tools/pcref/pc_reactions.py SLIP, per level `Level.action`) |
| the floor tricks' place | the mobile's fixed floor spots (55 Ground and GroundMarbles items on the Season 1 levels): Woody walks to the spot's TargetLocation to lay the trick and the neighbour notices it there (NoticeWhenNearTrickedDistance of TargetLocation) | game.exe creates a floor trick where Woody lays it: toi/groundsoap and kit/groundsoap (106), the bananas and the marbles are objects with hotspots 0/0 (woody) and 0/6 (neighbor), none of them in level.xml, laid by Woody's `laydown` (generic/objects.xml, 3 ticks) at his position, and noticed by the nearobj trigger (the same room, \|x − hotspot x\| < 15 px, fcn.00471bc0) — E06's soap lies at the bathroom door, where the mobile's bathroom spot is 0.74 units into the room | differed; carried since 2026-09-27: under the profile a floor click with the trick's item walks Woody to the clicked point of the room's floor (`World.woody_click` → `Item.pc_drop_x`, `Pawn.goto_item`) and the laid trick's notice point and overlay move there (`Item.pc_drop_dx` in TargetLocation, `World._woody_trick_done`); the harness lays at the mobile's spot unless the leg says `x=` (106's soap at -4.2 by the door at -4.07, whose box takes a click nearer; 113's bedroom marbles at 3.8 by the balcony door) |
| the ReuseAfterFix redo | the mobile redoes the station's normal use after the fix (102's sofa, 104's microwave, 105's piano, 108's deck chair and toothbrush, 109's bed, 110's chair, 113's ladder), the profile at the station's PCUseSeconds | the PC's case goes on after the repair with its own remaining actions (tools/pcref/trick_branches.py, the stand's actions after the fire): 110's table re-enters and eats — its `give` is the case before the chair's, which the tricked visit plays before the trick — and the walk leaves the table; 108's brush brushes and puts the brush back, its first take3 the tricked stand's | differed on two stations; carried since 2026-09-27: `PCRedoSeconds` (pc_reactions.py `redo`: the actions after the fire and the station's tail, a `leave` less the tick the walk's first move shares) for the redo's pace and `pre` into PCUseSecondsTricked (110's give) — 110's chair to the wine +0.8 s against Badinfos' where it had been +1.4; the others' redo is the PC's after-part as it is (104's microwave, 108's deck chair) or the PC's next case (102, 109, 113), and 105's piano's after-part crosses into the football's (left as the mobile's) |
| Woody's trick actions | the remaster's use clip at its own pace (MakeTrick 12 frames at 10 a second, 1.2 s; TakeGround 0.57 s; 102's SawSofa 4.8 s) | a trick is a combination of combine.xml (the object and the inventory item it takes; the tricked object its name), and Woody plays it as the object's action named after the item (lir/sofa's `fartbag`, kit/binoculars' `superglue`) or `use` where it takes none, at the record's time as the Loader stores it — 23 ticks (1.92 s) on most, 11 (0.92 s) on a quarter, 16 on 103's mousetrap and 109's pig key, 180 (15 s, Woody `inv`) on 102's saw; a trick on a room's floor (kit/groundbanana ← kit + banana, the soap, the marbles) is Woody's own `laydown` (generic/objects.xml, the ACTION step at 0x44b109-0x44b141), 3 ticks; the action's next animation (`smile`) is an idle, no time; a container's take is his `take` of the object (its `open` and `close` are 0 ticks for him — a one-frame oneshot of his, none of the object's): take0/1/3 18 ticks on 73 containers (the remaster's TakeInventory, 1.5 s), take_low0 11 on 18 (the rubbish bins), take_high 14 on 10 (the first aid); a hideout's `enter` and `leave` of his — the wardrobe 19 and 19 ticks, the bed 4 and 4, where the remaster's Hide_In and its leave clip take 2.0 s each — the LEAVE step clearing flag 4 once its `leave` has played (game.exe: its update 0x473ae0 frees the object and pushes the `leave` ACTION with the run-now flag 1, and its next update, in the tick that ACTION ends, finds nothing occupied and clears flag 4 — the branch 0x473b2b → 0x473ccc; read so on 2026-09-27, the earlier reading had put the clear at the step's start): the Season 1 catch reads him from the clip's end, as the Season 2 one does (`Pawn.pc_leaving_hideout`, since 2026-09-27; the port had caught him from the clip's start); Season 2's hideouts' `enter` and `leave` jobs 8-13 ticks each (the pipe, the beach chair, the baskets, the deck chairs, the lorry, the statue), carried the same way, its flag 4 cleared once the `leave` has played (the port keeps him hidden through the clip) | differed; carried since 2026-09-26 (`tools/pcref/pc_woody.py` → PCWoodySeconds by the inventory type Woody holds, `World.woody_use`: the remaster's clips at the pace that lasts it via `AnimPlayer.clip_pace`), each an ACTION step of its time + 2 (the row "the action durations": 25 ticks, 2.08 s, on most tricks, the laydown 5, the takes 20, 13 and 16, the wardrobe 21 and 21, the bed 6 and 6); the remaster's TrickLaugh after it stays, a click leaves it at once as on the mobile. Season 2 plays the same records as a DoActions job on Woody's queue, the Loader's time + 2: 13 ticks (1.08 s) on most tricks (uselow/usemid), 10-15 on the rest, 208's safety line 25, 209's drain 19, 210's pylon 29 — carried the same way on the tricks paired by the inventory the mobile item takes (a combination with a mini-game left to the game; the tricks that take no item keep the remaster's clip); its containers' `take` is a 16-tick job (1.33 s) where the remaster's search is a one-frame pick-up, ItemFound and TakeLow or TakeHigh, 1.9-2.9 s — paced as a whole to it (the level's mini-game item left to the game) |
| the walking speed | the mobile's `Speed` 1.25 u/s (Season 1), 1.0 (Season 2), `SpeedSneaking` 0.65 | objects.xml `<speed name=… speed=… start=… noise=…/>` per actor and gait animation (`SetSpeedMsg` → fcn.0044dd20: +8 speed, +0xc start, +0x10 noise); the walk fiber fcn.00475b30 waits one tick between steps (0x476148) and fcn.0047c7f0 moves the actor by the record of the facing animation (fcn.004459c0): `speed` px a tick plus `start` once when he leaves the standing animation `ms`, clamped at the target (0x47cc9f–0x47cd59) — the neighbour 8 px a tick along the floor, 3 up and down, running 18/9, Woody 17/6, sneaking 5/2, the dog 4; Season 2 the same for the neighbour, Olga and the mother (GameLogic.dll's walk step fcn.10009215, one axis a tick; the stair records 8/5 are never selected — nothing writes the gait 7) | differs: at the mobile scene's 96 px a unit (the house of 101: the living room's 586 px path ↔ the 6.8 u zone less the collider's margin, the hall 740 ↔ 8.4, the kitchen 412 ↔ 5.1; the neighbour's start 504 px ↔ −1.75 u within 9 px) the PC neighbour walks 1.00 u/s to the mobile's 1.25, Woody 2.1 to 1.25, sneaking 0.62 to 0.65; Season 2's scenes are 93–100 px a unit (208: the neighbour to Woody 338 px ↔ 3.69 u, the mother to Woody 446 ↔ 4.49; 201: the bridge to the right rail 1460 ↔ 14.5), so there the PC neighbour's 96 px/s is the mobile's 1.0 u/s — the remaster kept the Season 2 walk, sped Season 1's neighbour up by a quarter and halved Woody (2.0–2.1 u/s on PC in both seasons, 1.25 and 1.0 on the mobile) — carried since 2026-09-17 (and since 2026-09-26 the Season 1 neighbour's walk on the PC's legs, since 2026-09-27 Woody's: the movers' ticks between the door types' standing points and the stations' hotspots — while x is off the target's, y to the room's floor line first (the room's point, fcn.0044bac0; 0x47cbc6–0x47cc9d, read 2026-09-27), then x, then y to the target's — docs/PC_FIDELITY.md "Season 1 walks"): `pcprofile.walk_speed` moves every pawn at its floor record on a walk (whatever the direction — the mobile scene's depth offsets to its items are the remaster's; the axis-by-axis mix over them made the Season 2 laps 20-30 % longer than the PC video's) and at the vertical record on a door approach (the DOOR_CLIMB / DESCEND states, the PC's ~50 px climb to a back door), `tests/run_tricks.py` dodges by the same paces; the lap model below checks the climbs; since 2026-09-23 the Season 1 neighbour takes the gait the level class sets (+0x38, the index into the facing tables 0x51b5f0 / 0x51b648: 0 mg, 1 sn, 2 mr, 3 mrwc, 4 mgbowling1, 5 skate1, 6 piewalk — directly or through the step fcn.0045f6b0, run by 0x479660) before a GoTo and back to 0 at the next case: the run at mr1 18 / mr0 9 on every `noise` case (the pets' alarm, 107-114), the toilet and first-aid rushes (102, 103, 105, 106, 108's rinse), the antenna's shout (101, 102), the extinguisher's fetch and the way back to the barbecue (110), 113's runs to the main valve after the flood and to the heat valve after the hot heater and 112's way back in after the skate; the skate's slide at 18, the bowling ball's carry at 9 (`Routine._pc_runs`, `Pawn._pc_gait`, `pcprofile.GAIT_PX_PER_TICK`); the mobile's other urgents (111's vacuum and carpet) the PC walks, and the port shows the walk set on them; Season 2 (GameLogic.dll +0x3c, the level scripts' writes of 2 before a walk): the 21 writes carried (206's pillow errands, 208's and 210's runs to the Mother's call, 211's phone and WC, the co-actors' runs to him on 201, 204-207, 210 and 214, 201's tutorial and 205's ski — docs/PC_FIDELITY.md, "Season 2's runs"), the engine's two since 2026-10-04: the catcher's approach (the `fight` fiber, `World._pc_catch_approach`) and the player's walk, whose gait 2 Woody has no `mr` record for ("The Season 2 catcher's approach") |
| a click in a door's pass | the profile's pass places the pawn in the far room as its clips start; a path given then started there and replaced the door step — Woody walked on hidden and passing (`is_warping` for good: the catch blind to him; Level101's porch door, the click at 2.10 s) | the door step places the actor at the far door's point as it starts (0x474590) | **fixed 2026-10-04**: the pass in flight completes and its enter clip's end walks the new path (`Pawn._route`); the mobile walks the door again from the near room, as before |
| door transit | the pawns' door clips at 10 fps (Woody 16/13/10 frames out and 25/22/16 in by the left/right/back door, the neighbour 20/20/12 and 20/20/13); a flat door plays both at once, a walk-up door one after the other; the zone changes at the far clip's end | every Season 1 door is a `<door>` of the level's objects.xml with an `enter` action on the near door and a `leave` on the far one, `time` ticks each and the same on every inner door of a type in all 14 levels: the neighbour 19 + 19 (side), 11 + 22 (back), Woody 15 + 23 (right), 18 + 24 (left), 9 + 25 (back), each clip an ACTION step of its time + 2 (the row "the action durations"; `pcprofile.DOOR_TICKS` 21 + 21, 13 + 24, 17 + 25, 20 + 26, 11 + 27 since 2026-09-26) — 107's doors are `auto`, which the Loader stores as the same figures (the animations' frames less one); the front door pair differs for Woody on twelve levels (anc/fro, a right door, `enter` 18 where the type has 15; fro/anc, a left one, `leave` 23 on 101-106 and 109, 25 on 108, 110, 111, 113 and 114, where the type has 24; 107's `auto` pair and 112's are the type's, 15 + 23 and 18 + 24 — the only door records of the 14 levels off their type's, tools/pcref/pc_walks_s1.py): his way in from the porch (fro/anc's `enter` 18, anc/fro's `leave` 23) is the type's, his way out to it is not — with the two clips together the exit's pass lasts 25 ticks on 101-106 and 109 and 27 on 108, 110, 111, 113 and 114, where the type's figures gave 26 (107 and 112 keep 26); the exit door's pass, after its confirmation, ends the level as it finishes (World.finish_game_on_hud_click) and a Season 1 score carries no time, so the tick moves nothing but the end screen's moment; game.exe's door step (vtable 0x4e5370, update 0x474590 → fcn.004741e0) claims the pair, places the actor at the far door's hotspot — the room pointer follows the placement (fcn.00448d70) — and pushes one ACTION step (fcn.00478030 over fcn.00477ed0, vtable 0x4e546c) with two entries, the near door's `enter` and the far door's `leave`; the ACTION update starts every entry in one pass over its list (0x477391-0x47793c) and times the step by the longest entry (the running max at 0x477785-0x4777ab, less the step's +0x20, which the door step sets from its own +0x20, 0 from its constructor 0x474109): the two clips run together and the pass lasts the far `leave`'s time + 2 on every door (the neighbour 21 through a side door, 24 through a back door; Woody 25, 26, 27). Read 2026-09-26: E14's frames at 12 a second, the camera on the neighbour (192-212 s), put the kitchen's side door at 17-18 ticks from his arrival to his step out, the living room's back door at ~23 and the bedroom's side door at ~18, the far door opening a tick or two after the near one, and his walk between them at the movers' ticks (41, 38, 25) — the kitchen polish to the cups 16.7 s against the concurrent model's 17.6 and the sequential one's 22.2; the "~3 s" read on E10's back door in 2026-09-17 (and taken for the sum) is the climb to the door's hotspot, 50 px at 3 a tick, and the pass | differed in three ways, carried since 2026-09-17 (`pcprofile.door_ticks`, `door_warp_early`): each strip plays at the rate that lasts its PC ticks (the neighbour's far back-door strip has 13 frames for the PC's 24), and the pawn's zone flips as the pass starts, where the PC's room pointer does — a pawn inside a door clip is caught, and catches, by that room (`World._detect_common`'s PC branch drops the door term); the two strips ran one after the other through every door on the 2026-09-17 reading of the video, and since 2026-09-26 they run together (`doors_concurrent`), the walk-up door's too, where the mobile runs those one after the other. Season 2's 126 `<door>` objects carry hotspots (`<actor>`, `<actor>_in`, `<actor>_out` per actor) and 8 of them `enter`/`leave` actions (211's cabin, 212's and 213's topright/midright, 214's bridge): a pair is one step of GameLogic.dll (vtable 0x100ab1b8) — the walk to the near `<actor>_in`, then out of every room the movement straight to the far `<actor>_out` (or the enter, the placement, the leave), the far room set there and the run down to its floor (docs/PC_FIDELITY.md, "Season 2 walks") | differed: the mobile walks its transitions at the floor pace (a stair ~3 s where the PC's is 9-11 s for the neighbour); carried since 2026-09-23 (`PCPass`, tools/pcref/pc_walks_s2.py): the hop stands the `in` run, walks its complex steps for the straight movement's ticks (the zone flips at `<actor>_out`) and stands the `out` run; the back doors' climb, strips and descent last the `in` run, the two clips and the `out` run; since 2026-09-24 the `out` run is stood indeed (it had been lost with the step's hand-over), no floor record caps the pass, the floor between the stations and the doors lasts the PC's |dx| (PCPass `xi` / `xo`, PCApproach `x` and `tx`), and the pair is claimed as the step starts (flag 8 on both doors, 0x1000339d; freed at `<actor>_out`, fcn.10003454) — the next actor stands at the near door (since 2026-10-04: the route pushes the pass once its movement to the door's `<actor>` hotspot is done, 0x1000aac2-0x1000ab8d; where it was before; since 2026-09-30 with that movement's part of the `in` run, `nb`, before the wait and the pass's own after it — 213's picnic to the pinata 37.7 s against E13's 37.2, 38.5 before); since 2026-09-27 the Season 1 doors whose own records differ from the type's carry them (`PCDoorTicks` on the two front doors, Woody's `enter` 20 and `leave` 25 or 27 as ACTION steps; Door.pc_door_ticks paces the strip, World._transit_animations): his exit measures 25, 26 and 27 ticks on 102, 107 and 108, the type's 26 before; since 2026-09-27 a Season 2 pass has its job boundaries (every job of the walk pushed with a first run in the tick the last is done, a movement done in its last step's tick, the run back to the far floor pushed without one, 0x10003544-0x100035ba): PCPass `jt` [`in`, straight, `out`] — 3 ticks less a pass, 2 where `<actor>_out` is on the far floor —, `nb` (the `in` run split at the near `<actor>` hotspot), `ox` and the clamped `xo` (the run back along x where `<actor>_out` lies beyond the far floor line: 212's and 213's bottom doors) |
| the lap's timing | the mobile clips and speeds through the port's routine engine | `tools/pcref/lap_model.py`: the walker's lap tokens (ICON / GOTO / ENTER / LEAVE / ACTION along the level class's cases, `LAPS=1 routine_order.py`) timed from the data — 8 px a tick along the floor and 3 px up and down the room to the objects' `neighbor` hotspots, the doors' standing points (the door type's hotspot + level.xml `position`) with their `enter` and `leave` ticks, the actions' `time` or animation frames — against the PC video's natural laps (docs/PC_LAPS.md): 101 33.5/32 s, 102 28.2/28 (since 2026-09-30 40.6/41 and 35.8/36: the sofa's five rounds, `lap_model.CASE_ROUNDS`, and the video's lap from its second station — the first from the level start has no walk back), 105 45.8/40, 108 90.4/94, 109 112.1/113, 110 60.8/59, 111 113.6/122 (the first lap — the 219 of 2026-09-06 paired the second, tricked lap; the washer and the drier are their three DoActions, no wait step), 112 147.3/155, 113 167.2/191, 114 168.9/168; 106 a two-lap cycle since 2026-09-25 (Level_Bath::isBathFilled: the fill, then the bath and the towel) 59.8 + 65.0 against the video's 57 + 60; no unknown step left (the actors' own records, the actor targets, the action's name by its record); 103 28/42 and 107 37/54 fell short then (2026-09-17; the model's walks and doors read since: 103 32.5 against the video's median lap 32, 107 57.3 against 58) | the walk, the doors and the actions hold together as a model on the fourteen laps; since 2026-10-04 103 and 107 too, station by station against the bubbles (docs/PC_LAPS_DETAIL.md; the model of 2026-09-27, `lap_model.py -v`): 107's second lap (the painting's icon 56 s to 114) 58 s against the model's 57.3 — the painting 17 / 17.7, the camera 9 / 8.3, the bottle 1 / 1.3, its give 2 / 2.0, the pottery 18 / 17.4, the statue 11 / 10.6; 103's laps by the letter box 16, 32 and 47 s (the first from the level start, the third with Woody's doings) against 32.5 — the cake 8-9 / 9.8, the mail and the walk back to the candle box 22 / 22.8 (the bubble's LetterBox label covers the candle icon) |
| the Season 2 lap's timing | the mobile clips and walks; the PC videos' stays (span less the port's walk) since 2026-09-17 | `tools/pcref/lap_model_s2.py`: the level script's untricked lap (GameLogic.dll's step chain) timed from the data — the DoActions' `time` or clips, the hideouts, the bars' ticks, the GoTo's route (the Dijkstra of fcn.1000a421), the door passes and the station runs of the walk step — 203 105 s, 208 85.5, 209 104, 211 85, 212 124, 213 123, 214 90.3, 202 80.7 and the wait against the video's 84-112, 86, 97, 85, 113, 136, 91, 70-94 | carried 2026-09-23: the walk (the door passes, the station runs, the routes between stations: `PCPass` / `PCApproach`, tools/pcref/pc_walks_s2.py) and the code's stays on 203, 208, 209, 211, 212, 213 and since the same night 214 and 202 (210, 205, 207 and 204 since 2026-09-24, their laps from her `order`, from his play, from his dive and from the gong's leave) (pc_durations_s2.py CODE; 214 with its Mother's script and the pistol's poll, docs/PC_FIDELITY.md "214's handshake"; 202 per clip with his wait for Olga's sub and the shark paid at the sea's `enter`, "202's mat and swim"), the video's re-derived against the PC walk elsewhere; the port's idle legs within about a second of the model's (208's lap 82.5 s); since the same evening every walk's route is the path finder's (`world.pc_route` over the zones' PCRoom, from the station's hotspot or the pawn's x on the floor line — the 338 station pairs reproduced) and Woody's runs to his items' `woody` hotspots are carried (PCApproach `Woody`, 204 items); the idle laps under it (2026-09-24, the stays the walk writer had dropped since the routes restored): 203 99.5 s, 208 82.5, 209 100.8 (the model 105 with the fakir's `spit`), 211 80.8, 212 119.4, 213 126.6, 214 85.3 (the model 90.3), 202 81.7 (the model 80.7 and the wait), 210 98.7 call to call (its call by code since 2026-09-24: her naps and checks, his chair's bar and wakeup, the call, the run to her chair, the order and Fifi's tickle; ~101 with the PC's walks, the video's first lap 107; 106.2 since 2026-09-30, the elephant's stay waiting for Fifi's round, 11.2 s), 205 101.6 (its table by code since 2026-09-24: the talk that calls Olga, the 72-tick wait, the play once she is there; the model 111.9, the video 102), 207 100.0 (its board by code: the dive once the Mother sits in her chair, she in it while he is in the pool room; the model 106, the video 107), 204 84.3 (its stays by code; the model 92.8, the video 81) — within 6 % of the model but 204 and 205, whose videos sit with the port (docs/PC_LAPS.md); since 2026-09-27 the model's walks are the code's job by job (`walk_span`) and a walking step's own ticks 2, not 3 (the GoTo's first update makes the walk's first step): the model's laps 0.6-2.3 s shorter (203 105.6 s, 208 85.7, 209 107.6, 211 85.7, 212 126.2, 213 124.3, 214 90.8, 202 88.3), the stays a tick shorter per walking step, 213's picnic 10.8 s against the re-measured walk (docs/PC_FIDELITY.md "Season 2 walks"); the same night 213's picnic by code, 12.83 s — its `boat` latch set by Olga's `enter` before he arrives on the video's laps, whose 29-s spans are the model's 16.4-s walk and the code's stay (docs/PC_FIDELITY.md "213's picnic") |
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

| | the port (mobile) | game.exe | status |
|---|---|---|---|
| the first case | DelayStart 1.5 s (Rottweiler.cs:153), the first action's icon up from the first frame | the start job fcn.004718b0 pushed at the queue's head after the class's (0x43a7cb, vtable 0x4e5260): for the neighbour a wait of 36 on its first tick (fcn.004715c0 -> fcn.00471410 -> fcn.0047e520), 37 steps (0x47e500 ends on the count 0), then `normal` (fcn.00471570) — the class's case 0 and its SetIcon (0x46f96a) 37 ticks after the first tick of play (the title card's end: the running byte +0x88, 0x4417d9, gates the actors' pass at 0x43b2d0); the catch meanwhile the state function's rooms test (fcn.00436bb0), no script needed. Video: the first icon 3.07-3.10 s after the card on E01-E06 | **carried 2026-10-04** (`pcprofile.S1_START_TICKS`, `Routine.tick`, the HUD bubble, `can_rottweiler_see_woody`): his first move 3.117 s (1.517 before); since 2026-09-30 his first walk from level.xml's place (PCStart on the Rottweiler, `Pawn.pc1_stand_at`), where the port's had left from its mobile start mapped into the room: the first stations at the code's 4.3-5.4 s within 0.3 s, up to 1.45 s off before |
| Woody's start | the entrance: 0.5 s (Woody.cs:114), a walk from StartLocation to EntranceLocation, Hello, then his input (3.65 s on 101) | the start job on his queue (fcn.004718b0 at 0x43a207, Woody branch fcn.00471960): a tick, the walk to the room `anc` (0x4e0c80) moving on the third, from level.xml's fro 380/218 to the front door's point 56 (19 moves) and its pass (25 ticks), then `start` (generic/objects.xml, `auto` 8: a job of 10) and `normal` — commands from tick 55. E01: at the door 232.5, the pass to ~234.6, the first walk to the chest 235.4 (4.57 s after the card) | **carried 2026-10-04** (PCStart on Player, tools/pcref/pc_walks_s1.py; `World.spawn_pawn`, the entrance, `Pawn._pc1_marks` from the stood point): input 4.55 s, the first walk 4.567 on 101 |
| Woody's start, Season 2 | the Entrance clip (HelloAnimationNFH2) locks him, its end (0.983 s) frees him | GameLogic's Woody class (vtable 0x100abbe8, its first step 0x1001387d) idles a tick, then (0x10013743) pushes his `start` (generic/objects.xml: the triumph's last nine frames, `auto` 8) without a first run (fcn.10049216), a DoActions job of 10 ticks from its first update; a command offered meanwhile (fcn.1004abcf) passes it (slot 5, 0x10034d8e) but finds its +4 clear and waits — his input on tick 12, 1.0 s | agrees within a frame (read 2026-10-04) |

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

### The tutorials

game.exe runs tutorial_1-3 as level classes of their own (Level_Tutorial1,
vtable 0x4e2ec8; tutorial_2's director 0x45a550 and neighbour 0x45acd0;
tutorial_3's 0x459520 and 0x459b10), read 2026-10-03: a switch on the
state at +0xc once a level tick, the director's opening count of 12, the
waiting states moved on by trigger.xml's behaviours (nearobj and room
triggers to HAL and the neighbour), the actions' `behavior` records and
the scripts' messages; the PC video shows the three from 20 s to 220 s.

| rule | port | binary / data | verdict |
|---|---|---|---|
| the director's opening | the remaster's LevelScript: the first box as the tutorial activates | state 0 stores 12, state 1 counts it down, state 2 speaks: tick 15 (tutorial_2's box at 74.17, tutorial_3's at 149.92, 1.17 s after the title card goes) | differed; carried 2026-10-03 (TutorialPC101-103: the box on tick 15) |
| the flow | the LevelScript actions (location, door, zone, item signals) and the camera scripts | the states, the triggers (nearobj: the same room, \|dx\| < 15 px; room: every tick; `once`/`always`), the filter slots, `take`/`marker`/`hide` posted as Woody's action ends, `start`/`target`/`whistle` on the next tick | differed in the details (the signs' reach, the stops, the doors' moments, the camera, the level won at the location action); carried 2026-10-03 — the PC's states step by step |
| tutorial_2's neighbour | back and forth between the signs, no wait | `start`, then GoTo lir_sign1, 96 updates, GoTo kit_sign2, round again (0x45acd0) | differed; carried 2026-10-03: from `start` the doubletake +5.85 s (the video +6.0), tut_laugh1 +7.17 (+7.33), the picture back +12.8 (+12.91), at sign 1 +16.38 (+16.5), off to sign 2 +24.42 (+24.58) |
| the reactions | the mobile pace (AngryHard 6.7 s) | the look walk-by's list with tut_laugh1's message step before the OBJ2 fire; FIRE4 (`marbles`, index 2: `!= 0`, shout2; flags 0) pushed alone, its ready list [StopMsg, (tutorial_3: tut_laugh), the fall, (the empty message)] | differed; carried 2026-10-03 (the items' PC data, PCFireWait; "Ha, ha!" 0.33 s to 3.08 s after the fire — the video's 210.08 to 212.83 after its ≈209.75) |
| tutorial_3's walk to sign 2 | the mobile's three MoveOnly steps (lir, anc, kit) | lir/kit closed (its dummy shown) right before the GoTo to kit_sign2: the path finder leaves out a link whose door is not present (fcn.004471a0, 0x4472a7-0x4472cc) — through anc | carried 2026-10-03 (`Level.find_path_open` under the Season 1 profile, where the mobile's shortest hops across a locked door are refused) |
| tutorial_3's dog | AlertOnStartTimer 3 s | the director's `whistle` on tick 15 (the pet class's filter sets +0x1d, its handler state 3; in state 4 the flag makes it bark with Woody away, 0x45c2ae); the neighbour's noise icon and camera at 151.92, 2.0 s after the whistle, the dog awake from 150.92 with no bark seen before the icon | the whistle carried; the PC 12 ticks later here (tick 39): his script starts on tick 37, after the start job's wait (fcn.004718b0 / fcn.004715c0, a wait of 36 not breakable), which holds the alarm pending — carried on 2026-10-04 (`pcprofile.S1_START_TICKS`; `TutorialPCS1._level_tick` holds his script and what comes for him until then, `pc_nb_wait` defers World's hear_alerter): his run from tick 39, 2.02 s after the whistle (0.83 before); E11's dog (woken by Woody) has him answer on the wake-up's end (2707.63 / 2708.42) as the model does |

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
| the moment it completes | since 2026-10-04 under the profile the PC's: the level runs on past the last credit until the reaction's scene drops (`World.pc_scene_start`, `_pc_s2_success`), Woody's win clip lasts 25 ticks and the score is read at the board (`pcprofile.S2_WON_TICKS`); the mobile's WinGameOnCompleteAllTricks (GameEnding at the last credit, PlayWinAnimations 2.5 s later) before | the level update's status tick tests the status on every tick (fcn.10041086 at 0x100447f8), done == reachable only while the level's byte +0x6e is clear: the camera callbacks' flag (SwitchObjectsJobCallback, update 0x1000d70b: fcn.1000d31a sets it for a start, fcn.1000d559 clears it for an end, both first, fcn.10040137 at 0x1000d338 / 0x1000d57a; the camera and the freeze after it only with the `autoscroll` option, flag 8), and the scripts wrap each reaction's list in a start and an end (fcn.1000f5c9, or fcn.1000f51a / fcn.1000ebbf): in every flow the lap model reads it drops right after the SHOUT (lap_model_s2._scene_span; 210's dog basket alone as its flow ends, 213's bull controls after Olga's fight — the hurt step's latch, SCENE_CONT). The success: the camera on Woody (slot 0x40), the neighbour and the Mother frozen (fcn.100450bf(0x100000)), `won` to Woody, whose step plays `triumph` (24 ticks) and ends the level (slot 0x34, fcn.1004256d) — the board, its time the status's count then. E02: the last credit (the electrified rail, the statue lit at 496.5), the cut to Woody 502.636, the board 504.705 (the fifth coin read at 502.83 before was the wrong slot: it fills at 497.0); E03: the bicycle's credit 729.3, the cut 734.603, the board 736.671 — each the stand's rest, a freakout (39-40 ticks) and 25 ticks | **carried 2026-10-04**: 202's plan ends 6.2 s after its last credit and boards 2.08 s later (the video 6.1 and 2.07); the Trick Camera (the camera on him, Woody and the Mother frozen through a scene) was off in the reference run — GFXEngine labels every camera change (fcn.10003df0 / fcn.10004e90, gate +0x131 always set), 201's tutorial forces its camera (its Ef51a push the bool 1 with flags 0: `Neighbor camera` at 79.3, 105.6, 118, 142.6, 199.6), a regular level passes the option's byte (fcn.1000e116) and none of its scenes shows a label — and stays off; the items whose tricked flow the model does not read (PCLaugh's stand-ins) hold their scene over the stand-in reaction — 202's beer mat, 209's fire fakir, 212's boat coin slot and empty throne and 213's piñata read on 2026-10-04 (SCENE_STEPS: after the SHOUT, as the default), since then 202's weeded rake, 205's chef, 208's elephant line, platform, tap and rake (walk-bys: the surprise holds its scene, `Routine._on_surprise_near`), 211's cabin phone (the alarm run's use, `Routine._pc_s2_arm`) with the kid in its linked variant, 209's fakir and coals, 210's hedgehog chair and 211's boat by their steps and 204's vase, 209's gully and trough, 210's diving board and 212's second throne in their partners' linked flows; 210's pole in the hedgehog chair's linked variant since (PCSceneLinked); and 207's diving board by its step since (its linked crash the Mother's fight) — none left unread (docs/PC_FIDELITY.md, "The Season 2 level's end") |
| the pass mark | `won` at WinningTricksCount | leveldata `mincoins`, checked when a flagged request comes in (byte +0x6f, set by the virtual at 0x1004717f — the menu's exit-level path, `mm_exitlevel`; coins ≥ mincoins passes) | agrees in effect: `mincoins` equals the mobile's WinningTricksCount on 13 levels and the 211 overlay carries the PC's 5 (data); the PC lets a player leave a level early through the menu, the port's menus do not model that |
| the catch | `_catch`: fear, the beating, `_respawn` | the catch fiber (vtable 0x100ab258 slot 10, entry 0x100061dc) on Woody's queue: Woody's `fear1`/`fear3` facing the catcher (0x10006510), the catcher's `fight` action (generic/objects.xml: `fight_woody` with `fly_away_neighbor` / `fly_away_mother` on Woody — invisible, then 900 px up over the action's ticks 36-44 / 41-49, its `<translation>` — and `inv` after it), then case 4 (0x100062cc) picks the room, fcn.10005f58: every room of the level in its map's order (the names': the iterator fcn.1004018d, the UTF-16 compare fcn.10058390) scores 50 with more than one `<neighbor>` record and 0 with one (0x1000610c), 101 more with an object flagged `hideout` in it (0x100060b7), 50 less with a `bad` actor in it in his hideout (flag 4, 0x100060a0) and 10000 less with one out of it (0x10006139) — an actor counts in the room its pointer names (fcn.10040a7d) — and the first room above 0 and above every earlier one is taken (0x1000613f; none: the assert "Kein leerer Raum!!!"); Woody goes 900 px above the middle of its path (0x10006330-0x1000634a: x the two ends' mean, y path1's less 900; fcn.10041ad0 the room, fcn.100418f6 the point) and his `respawn` action goes in front of the fiber (fcn.10049246 without a first run): the fall back over its ticks 0-5 (translation 0/900) and the landing (generic/anims.xml `respawn`, 38 frames: 37 by the Loader's rule, a job of 39 ticks); case 5 (0x10006274), the job done, clears the catch's flag 0x10000 off Woody and takes the life (fcn.10042471) | carried since 2026-09-25 (`World._pc_respawn_zone`, `_respawn`, `_pc_respawn_landed`; PCRoom `hideout` from tools/pcref/pc_walks_s2.py): the room, Woody on the middle of its floor, his input held from the catch to case 5 (the fiber heads his queue; a click then is kept: the GoToPos handler, slot 71 of the level's message class 0x100b18b0 at 0x10046adc, offers the command to the queue's jobs, fcn.1004b27f → fcn.1004abcf asking each job's slot 5, and when the queue refuses it the handler keeps it in [level+0x60], which the level update re-offers on every tick, 0x100443ea — the port's StoreBlockedInput, replayed when the lock lifts); since 2026-09-25 (later) the landing itself (`World._pc_landing_tick`, levels/pc/Season2.overlay.json from tools/pcref/pc_respawn_s2.py): the remaster ships the fifteen images unused as W_Landing.png, played as the PC's 38 frames with their sounds, registered by gfxdata.xml's offsets against W_Stand, unseen on case 4's tick and falling 180 px a tick over the job's counts 1-5 (fcn.100015c4); and the fight at the PC's pace — the remaster's FightWoody / MotherHitWoody are fight_woody frame for frame and sound for sound, slowed to 8 / 9 frames a second, played a frame a tick with the respawn at the `fight` job's 45th / 51st tick (`pcprofile.S2_FIGHT_TICKS`). Not in the remaster: fly_away.tga (Woody kicked 900 px up over the fight's last ticks — the port keeps him hidden). The fear is the PC's (case 1: fear1 for a catcher on the right, else fear3; six frames, then the loop until the fight) over W_Fear, whose halves hold fear3_0000-0009 and fear1_0000-0009 (`PCFear1`/`PCFear3`, tools/pcref/pc_respawn_s2.py) — at the remaster's own placement, its halves cropped apart and the loop frames 6 px off. Before, the level entrance; the let's play's respawns (5:04, 6:05) land in the beach's left room — by Olga's mat, then at the foot of the gate's stairs, x 360 of its path 100-620 — the first room of that map, not Woody's start (the shop) |
| the catcher's approach | HitWoody walks the catcher over (HitWoodyAction.Urgent false) until the x distance drops under MaximumPawnDistanceToAction (0.8) | the `fight` behaviour's start (0x1003d4d3 -> fcn.10007238) pushes a fiber on the catcher (vtable 0x100ab36c, step 0x10006e9f): case 0 keeps his gait (+0x3c into +0x10) and walks him (fcn.10006d0a) to 70 px short of Woody on his own side, inside the room's path (0x10006da1-0x10006de1), on gait 2 — mr1 18 px a tick — when that point lies more than 80 px off and his gait was the walk (0x10006dec-0x10006df6); case 1 puts the gait back (0x10007034) and the fight follows; a catcher out of Woody's room ends it (case 3) | **carried 2026-10-04** (`World._pc_catch_approach`): the run to the point 70 px short (202, forced from 3 u: the hit 1.25 s after the catch, the walk had taken 2.3 s), the gait back at the hit |
| the respawn timer | none: a catch could follow at once | case 5 (fcn.10042471 at 0x100424b6) sets status +0x18 to leveldata.xml's `respawntime="60"`, the level update counts it down after its watch walker (0x10044725 past 0x100445f1), and while it runs the `fight` and `die` behaviours of generic/trigger.xml refuse Woody: their predicates (slot 4 of the vtables 0x100b0eec / 0x100b0e8c, fcn.1003d526 / fcn.1003cd8e) read it with Woody either party (0x1003d5f9, 0x1003d646 / 0x1003ce61, 0x1003ceae — fcn.1003cc45 there is the actor's name, not an action runner), beside the catch's flag 0x10000 on the behaviour's actor (set by both behaviours' starts, 0x1003d4bf / 0x1003cd27; refused at 0x1003d6b5 / 0x1003cf1d) and the scenes' flag 0x100000 on either (fcn.1000885f); the same span GFXEngine outlines Woody (the message of vtable 0x100b145c from 0x10042515 on / 0x10044765 off, visitor slot 80 0x1000ac00 → his sprite's +0x39, which draw slot 10 at 0x10011c50 turns into the frame in black at x±1 and y±1 under it; ship1's tutorial: "As long as Woody's image flashes, the neighbour is unable to see him") | carried since 2026-09-25 (`World._pc_catch_barred`, `pc_outlined`, render.draw_sprite's `outline`): no catch from the catch through the landing and 60 ticks (5 s) after it, the outline one PC px wide |
| lives out | game over | fcn.10042471 on the last life — status +0x14 at 1 before the decrement (fcn.1004012a, 0x10042483) — ends the level (slot 13 with 0, 0x100424d8-0x100424dc), case 4 having skipped the fall (0x1000634d) and set state 5 unfinished (0x10006405), so case 5 runs a tick after it: three attempts, x3, x2, x1; the level, its clock and its completion check run on through the beating | differed: the port respawned on the last life as well, a fourth attempt; carried since 2026-09-25 (`_catch`: a respawn above one life); the moment since 2026-10-04 — the port had ended the level at the catch (FinishGame there, the check dead through the beating): now the fiber to case 5, a tick past the fight (`_after_hit`, `World._pc_lives_out`; 207 forced at 300 s: the hit 306.567, FAILURE 310.900) |
| the success against a catch | the mobile's chain: the win only past both sights (GameInfo.cs:212-236) | the level update's watch walker (fcn.1003fc90, 0x100445f1) and then, on its own, the completion check (0x100447f8); a success with the catch's flag 0x10000 on Woody ends the level at once — vf34(1), 0x10041159-0x10041162, no freeze, no `won` step, no life taken — and every success ends it with vf34's byte 1 | **carried 2026-10-04** (`World._pc_s2_check`, `_pc_s2_success`): the check after either catch, the board at once under a catch, won set at the success (a catch had cleared it: FAILURE on a success); 207 with the Mother forced on Woody at the last credit, lives 3 or 1: the scene's drop 454.767 the board, a success, the lives as they were |
| the gauge, the decay, the board, the clock | `pcprofile.s2_rage_tick`, `calculate_score` | the level update 0x100442b3 (its status tick 0x10044710-0x100447f1), fcn.10040226 | agrees (docs/PC_ROUTINES.md) |
| the reaction to a trick | `pcprofile.s2_reaction_seconds`, `World.play_angry`: the mobile's angry set paced to the SHOUT's action | fcn.1000f977: the step's last parameter picks [shout2_light] / [shout2, shout2] / [shout2_hard] x3 / [shout2_high] — the static initializers 0x1007b54b-0x1007b61d fill 0x100df45c / 0x100df434 / 0x100df450 / 0x100df41c — after a first pick of [freakout1, freakout2, freakout3] (0x100df43c), which the SHOUT element (vtable 0x100ab99c, update 0x1000d751) plays instead once the status byte +0x28 is set: the credit sets it as the rage reaches 100 000 (0x10001500) and nothing clears it; the actions' animations (generic/objects.xml, anims.xml) 26 / 26 / 85 / 26 frames, the freakouts 37 / 38 / 63 — the Loader's times one less; the element's first update pushes the action's DoActions job in front of itself without a first run (fcn.10049216) and returns 0 (0x1000d8a2), the job runs its time + 2 from the tick after (states 0-2 of 0x100020c0, the count fcn.100011f2 past the time), the element's next update — in the job's last tick, the runner going on past a done job — returns 1 at once (0x1000d8a6): time + 3 ticks, shout2 28, shout2_hard 87, the freakouts 39 / 40 / 65 | **fixed 2026-09-24**: the tables had been read as mixed (1: shout2 or shout2_hard, 2: shout2_hard or shout2, 3: the freakouts) and the freakout after the overflow was missing (`Pawn.pc_rage_full`); **2026-09-25**: the lengths the element's ticks (`S2_SHOUT_TICKS`, the frames before); **2026-09-27**: a tick less (time + 4 had counted the element's done update as a tick of its own) |
| a tricked visit's credit | `Routine.pc_credit_timer` / `pc_credit2_timer`, `World.pc_s2_credit` / `pc_s2_linked_credit` | fcn.1000140b credits each named record of a playing action on the tick its `time` equals the action's count (0x10001455), from the action step's playing state (0x1000254d) and its end (0x100025bf): 202's rail over the eels' pond pays bridge_crash 8 ticks into the crash and bridge_electrify 5 into the electrify, 22 ticks apart | **carried 2026-09-24**: PCCreditAt / PCCreditAtLinked for the item's own record, PCLinkedPaysAt for the linked trick's (the ladder's linked arm paid apart, `_s2_credit(part=)`); the done count is the trick table's credited records (fcn.100522e6, fcn.1005225b), so the pair's completion is booked with its last record (`Item.pc_done_due`) |
| a tricked step with no SHOUT of its own | `code_stays_tricked` (`TRICKED_CONT` 'steps', `TRICKED_VIA`, `TRICKED_ROWS`), PCShout -1 | the step hands over to its continuation, which plays the SHOUT and the repair: 204's gong 0x10032f52 (SHOUT 3), 205's skis 0x10024fc2, 211's sweets 0x10030dc2 / 0x10030d0f / 0x10030b9d (the toilet run, wcright's `puke` 40 ticks), 214's wheel from the door 0x1003af18; 206's weights and dynamite at their rows; 210's dog basket alone plays none; 214's door is visited tricked in neither game (CaptainDoorBehavior's ExtraItem, Item.cs:2606-2623) | **carried 2026-09-24**: the stand to the continuation's SHOUT, its level and repair; -1 skips the reaction; 212's ledge (the aux script's parrot shit, fcn.10034e05) and 213's bull (the step's byte +0x28 through eax, 0x10038ab1) read to their records later the same day |
| an action's behaviour | the mobile's hand-offs at the use's end (play_angry's affect, PawnToAbortMutexOnFinish, the once-loop flags) | the DoActions job (update 0x100020c0): state 0 sets the participants' animations and sends the start message (fcn.100018a6: the job's +0x14 / +0x18, a text the GFX shows — "string" / "alreadyininv" of fcn.10002d71's callers — slot 48 of the GFX visitor, 0x1000a220), state 1 counts +0x28 past +0x24 (fcn.100011f2), state 2 sets the next animations and posts the action record's behavior (+0x1c) to its behavioractor (+0x20) with fcn.1004000a (0x10002708) and ends the job; the abort slot (0x10001d1b) posts it too when the record's `always` byte (+0x24) is set (0x10002009-0x1000203f); Loader.dll's time="auto" is the longer of the actor's and the object's oneshot animation less one (a loop or "inv" not counted, 0x10009704-0x10009842) — the post the Loader's time + 2 ticks after the job's first update, the offer on the tick after | **fixed 2026-09-25**: the 2026-09-24 reading (the behaviour posted at the job's start) is withdrawn with its carries — the lost game's run (13 ticks after the loss), 203's shout (his run 71 ticks after hers begins), the co-actor's fight (below), 205's talk (0.33 s into his mat, PCBehaviourAt) and play (her table mutex at his use's end), 210's call (his chair 1.83 s after her call begins) and order (his stands there 1.58 s), 211's puke (below), 213's bull (Olga's ride on the `bull` his step posts as he arrives, his wait on its `leave`: PCBehaviourAt, PCBehaviourAtEnd), 214's pistol (her `standup` at his play's end); `lap_model_s2.Data.loader_time` / `job_ticks` |
| the co-actor's hit | `Routine._hit_begin` / `_hit_pawn_done`, play_angry's affect, PCHitSeconds | the action's behavior (hurt_neighbor …) is posted as its job ends; Olga's / the Mother's script runs her to him (gait 2) and plays the generic `fight` (fcn.1000eb19: 42 / 39 ticks; its object is he: `inv` in its state 0, `ms2` in its state 2; olga_fight / mother_fight on him as it ends), his handler then sets the SHOUT step (204 0x10032b6f, 207 0x1001596a, 210 0x1001a379, 214 0x1003ba90 / 0x1003b677 / 0x1003b328) | **fixed 2026-09-25**: she sets off as his tricked use ends, her hit hides him for the fight's ticks and his SHOUT follows it — the mobile's order (the early set-off of 2026-09-24, `World.pc_affect_early`, is gone); DoAction's job goes on her queue alone (fcn.10049216; the queue fcn.100492a8 locks no other actor); her run to him (PCHitRun) ends at fcn.1000e601's point, 50 px beside him at his y (the left for an equal x), and goes round him where a step heads at him — the walk step's check (fcn.10009889 → fcn.10009489): a standing actor within 15 px across and 50 along the step sets a detour 50 px beside him, its first step taken on the same tick, a walking one stops the step — 207's Olga off her mat 26 ticks where the floor route is 43, carried 2026-09-30 (docs/PC_FIDELITY.md, 207's shell; the neighbour's own walks past a co-actor are not modelled) |
| 206's pad and harpoon | `Level206RoutineBehavior._pc_gate`, `Item.pc_masked`, PCTrickArm / PCTrickFire, PCExtraPaysAtLinked | the load step 0x1002e3df's IfVariant ramp / ramp_manip arms the shot after the take (0x1002e27f -> 0x1002df9b shootrabbit 81 / 0x1002e0fd rubberrabbit 73: records 40, 45, 50), the Mother's fight latch ([step+0x24], 0x1002de6a), SHOUT 1, the ramp's repair 19; the shoot step 0x1002d948 asks nothing; the take step's rubber branch 0x1002da29 (rubberbear 69, harpoon_rubber 40, SHOUT 1) goes on to the put 0x1002d578, which switches the harpoon back | **carried 2026-09-24**: the pad fires at the shoot after an armed load, else the shoot plain; the rubber on at the take fires through the pad's DependsOn at the shoot (the take marks GotTricked), a later one is dropped at the put; harpoonAux off; the ExtraCoin206 at its tick |
| 211's rush | the after-toilet angry of the rush's item, PCToiletPaysAt, PCHitSeconds | 0x10030dc2's puke at wcright (40 ticks, wcright at 27, behavior puke on Olga, posted as its job ends) -> her handler 0x100318ce: `mad` (34), her fight step 0x1003183a (42; olga_fight -> his latch +0xd, 0x100301fb) -> 0x10030d0f SHOUT 1 -> 0x10030b9d the sign's repair (walk 34, repair 24) | **carried 2026-09-24**: the angry after the wc (the mobile loses it, ActionManager.cs:597), the record in the puke; her hit her mad and fight after the puke, 6.33 s (**fixed 2026-09-25**: 3.0, the two less the puke under the start reading); differs: the repair at the wc, the walk on from there |
| the camera and the pose elements | instant (`INSTANT`, E2f40 'instant') | Ef51a (fcn.1000f51a): flag 8 only for a nonzero last argument, then it waits while [level+0xc] != 0 (Woody's mini-game); the pose element fcn.10014c5c / fcn.1000de51 (vtable 0x100ab990, update 0x1000cfaa) returns 1 at once; Ef779 (0x1000ce9c) likewise | **carried 2026-09-24**: 207's sand castle over the hedgehog's towel runs its linked continuation (0x1001513f: Olga's `n_lift`, the billboard's `enter` 56 ticks, SHOUT 2) — PCHitSecondsLinked, PCResumeHeadSeconds, PCExtraCoinLinked |
| the result screen | `COLLAPSE!` on an overflow, else the mobile's EXCELLENT / GOOD / PASSED | GUIEngine 0x10001536–0x10001652 fills `dialogs/gameover.xml` (`rating`, `coinsscore`, `lifesscore`, `bonusscore`, `timescore`, `wholescore`) from the status struct (eleven dwords, `push 0xb` at 0x1000515f) and a failed flag: `failed` (FAILURE), else `bonus` (COLLAPSE!) on the collapse byte +0x28, else `perfect` (GOOD JOB!) when coins +0 equal the total +4, else `success` (SUCCESS!) — `generic/strings.xml` | **fixed 2026-09-16**: `pcprofile.s2_result` under the profile; the rows were already the board's |
| the trick amounts | nine PC values in `levels/pc/*.overlay.json`, the rest the mobile's | tricks.xml `coins` / `rage` | agrees (data, the overlays' sources) |
| the routines | the mobile ActionManager orders | `tools/pcref/routine_order_s2.py`: each level script is a chain of step functions handing over through `[obj+8]`; followed with no trick fired, the laps by code are 201 rail → water puddle → captain's cap → buffet → water puddle (mobile: CaptainHat, Buffet, WaterPuddle, DeckRail, WaterPuddle), 203 bike → stage → image → toilet → melons (Microphone, ToiletPaper, ToiletFlush, Watermelon, Bicycle), 205 sand lion → mat → ping-pong → water skis → chef → tyre → firework, rocket → sand lion (OlgaMatBeach, TableTennis, WaterSkiis, Chef, Rockets, SandSculpture), 206 Fifi → blanket → Fifi → ramp → harpoon → dumbbell → Fifi → dynamite bag (DogFifi, DeckChair, Pillows, LaunchPad, Harpoon, Weights, Fifi, Dynamite…), 208 statue → platform → shoe cleaner → elephant (IndianPlatform, ShoeMachine, AngryElephant, ArmsBowl), 211 diving → dish → rod → boat → life vest (Sweets, FishingRod, LifeBoat, LifeJacket, DivingGear), 209 cow → ride → fakir → shoe mat → coal → trough → fuel (FireFakir, HotShoe, TadjMahal, HotShoe, Coal, IceCream, Cow), 212 cliff → parrot → boat → hands → whip → cigars → bank → bull ride (PreAztecThrone, AztecThrone, Whip, CigarBox, SleepBench, MechanicalBull, PreParrotLedge, ParrotLedge), 213 limber wall → carnivore → tortilla → piñata → bull-ride controls → washing tub (LiveBull, PlantCarnivore, Tortilla, BoatPicnic, Pinata, MechanicalBullControls, CementBath) | agrees in order on the nine laps that close; 202, 204, 207 and 214 end at a step that polls an action (202's `waitsea` swim, 0x10022534: the step stores no next and is re-entered until the level's event moves it on) or an event callback, 210 re-arms its deck-chair step — since 2026-10-04 the order past those steps too, by the lap model's rows (`lap_model_s2.py`, the polls taken as passed): 202 bridge → mat → beer → the rake's walk-by (0x10022589, its GoTo and crash only with the rake on the ground) → swim, back to the bridge, 204 gong → hot dog → jade → rickshaw → head-banging → gong, 207 after the dive bartender → elephant → shell → kid → mat, 210 Fifi's basket → turban shop → elephant → the basket's put → her call → deck chair, 214 hatch → shower → bouquet → door → pistol, back to the hatch — each the mobile's order in its cycle |
| the dexterity mini-games | `_dexterity_gate` + `DexterityState`: the remaster's lockpick game (fill 20 → 85 %) | objects.xml's `game` objects (one a level on 201-214, their Woody action's `time` 240-360, a `failed` action whose behaviour sends the neighbour running) and GameLogic's game object (vtable 0x100b1a7c, constructor fcn.100507f4, fcn.100508a1 once a level tick with the mouse): the first three ticks move the mouse onto the field's middle, then the rate 4/3/2/1/0 by the thumb's distance (under 200/400/600/800 in 1/10 px; -(progress x 4 / 10) in -40..-4 beyond it once the progress passed 10) and a push of three sinusoids (20/10/5, 0.0648/-0.1461/0.3696 rad a tick) times a factor from the combine.xml combination's startlevel to its endlevel with min(progress, 90)/90 (the object setter fcn.100452d7, the use_object step fcn.10004353 → fcn.10041735 → +0x40/+0x48); the DoAction step (fcn.10001b2c) adds the rate to the elapsed count clamped at `time`, the progress elapsed x 100 / time (fcn.100507dd), the win at `time`, the `failed` action below 0 — the earlier row's "no such code" was a search for the mobile's vocabulary | carried 2026-09-23: the PC's rates, counts, centring, push and alarm on the remaster's field, the thumb the mouse one to one (PCMinigameTicks / PCMinigameLevels, `DexterityState._pc_tick`, `pcprofile.s2_game_push`); a middle-held game lasts 3 + time/4 ticks; a lost game's neighbour runs onto the object (the `failed` behaviour `run`, registry 0x1003e278 — offered thirteen level ticks after the loss since 2026-09-25: the game's job ends on the next tick, the use_object step pushes the `failed` job in front of itself, which posts the behaviour 10 ticks after its first update, PCMinigameFailedTicks) or nobody comes (201's `aux`, 212, 213: PCMinigameFailed); the order in the level tick the PC's (2026-09-23): the DoAction step is Woody's job (fcn.10049246 pushes it on [actor+0x18], its first run only sets it up; fcn.100492a8 runs it from the actors' pass fcn.10044234, which the level update calls at 0x100445f8) and the game's update comes after it at 0x1004482b, the game made in that job pass (fcn.10041735) — a tick adds the rate the last update left, the first update at the game's start (`DexterityState._pc_update`); the field GFXEngine's since 2026-09-24 (the create message, slot 79 of the GFX visitor: the middle Woody's `minigame` hotspot, 0/-150, above his place for the game — the object's `woody` hotspot, off the room's floor line on thirteen levels (PCMinigameLift: 204 +24, 211 -92) — the camera scrolled onto it, 0x1000aa80 / 0x1000ab08; the draw fcn.1000fcf0: the textures at their own sizes, the icon centred, the thumb at (x + 1000) x (field - thumb) / 2000 of the state message's pair, fcn.1000fa00 — `hud._draw_pc_game`, `World.dexterity_focus`; the vertical progress bar 28 px in, the field's disk inside its ring, since 2026-09-25 — `Hud._draw_pc_game_bar`; its rows floor(progress x height / 100) as GFXEngine's progress widget draws them, vtable 0x100422b8 slot 9 0x10010e90, since 2026-09-26), measured on E04 759 s and E01 176 s (the middle at PC (400, 254)); a lost game's behaviour reaches its actor a level tick later and every tick after it until taken (the walker fcn.1003fc90 before the actors' pass, the votes of fcn.1004abcf: the level scripts' walks interruptible, their actions not — `DexterityState.pc_offer_tick`); open: the progress bar's front image (not in the data, the remaster's fill stands in) |
| detection ("sees Woody") | the mobile's predicate; since 2026-09-23 under the profile the PC's room trigger (`World._pc_s2_sees`) | the level update (at 0x100445f1) runs fcn.1003fc90 over a table of watch entries (an actor, a target, mode bits at +0x1c/+0x1d) and evaluates each with fcn.1003f573: the actor must carry flag 0x20, neither party flag 4 (the hideout flag — set on hiding, e.g. 0x100067e9, cleared by the `leave` action at 0x10006abc), the rooms compared through fcn.10040a7d (the record of the actor's +0x20 name), and in one mode a vertical distance below 15 (0x1003f7d0); a true entry fires an event object (fcn.1003f86d, fcn.1003f972, fcn.1003fa6b, fcn.1003fc6e — no strings); the table is filled from data and code: every action record carrying `behavior=`/`behavioractor=` (62 in the Season 2 objects.xml — the neighbour's `run` after a failed Woody action ×11, Olga's `kid_cry`, the mother's `crash`, …; parsed by fcn.1004fa5c/fcn.1004fbe7/fcn.10050c15 and flagged at +0x24, 0x1000a696), the engine's own per-action entries (fcn.1004008d from the DoActions job's state 0 for an action whose `noise` is above 0, 0x10002478/0x100024af, mode 0) and the scripts' explicit ones (fcn.1004000a: the tutorials' and 201's `tutorial` entries, 213's `bull` and `boat`) | agrees in kind with the mobile's zone containment plus the hiding exemption. The mode bits are read (2026-09-17, fcn.1003f573 with the entry's +0x1c dword as its fourth argument): bit 1 — the two objects' rooms (fcn.10040a7d) are the same; bit 2 — the same room, the actor on the floor's y (fcn.1004c945 / fcn.10049006) and less than 15 px across from the object's named hotspot (fcn.10049e01: its position plus the hotspot; 0x1003f7c4-0x1003f7d3 — read as a vertical distance until 2026-10-04); bit 4 — always true; no bit — never; and before any of them the second object must carry flag 0x20 and neither flag 4 (the hideout), with no sneaking, busy or animation term at all. The walker (fcn.1003fc90) tests an entry without a direct target against every other entry of the table whose ordinal (+0xc) reaches its threshold (+0x18), with the two modes ORed, and latches a hit in +0x1d bit 2. The engine's per-action entries (fcn.1004008d from the DoActions job's state 0, an action's `noise`) and the posted behaviours (fcn.1004000a: the scripts' explicit ones and the actions' own, from the job's state 2) are built with mode 0; the modes come from the parsed action records — `behavior=`/`behavioractor=` with `always="true"` (the 62 reactions: the neighbour's `run` after Woody's `failed`, `tongue`, `kid_cry`, `crash`, …) and the `room` keyword the level parsers compare (0x10070779 …). The catch itself (2026-09-17, later): fcn.1000eb19 (13 call sites, one per level class) runs the catcher's approach step fcn.1000e601 — the two rooms compared through fcn.10040a7d, a point beside the target at the fixed offset [0x100cc814], a path check (fcn.100072b1) and the move (fcn.10007d78) — and starts the `fight` action (the string global 0x100e1b50, fcn.10002cd5) once no step is left; the level classes call it with `neighbor` and a continuation from handlers they subscribe to engine events through fcn.1000e7f2 (18 subscriptions, e.g. event 0xf0 on `pool_deckchair` in the 207 class), and the data's `behavior="run" behavioractor="neighbor"` on Woody's `failed` action is the reaction after it. The per-actor watch entries carry mode 0 (fcn.10001b2c) or 0x100 (fcn.10008b74 — the lookup selector byte), the room bits come from the outer, data-side entries ORed in by the walker. The 13 sites are steps of the per-level actor scripts — fcn.10011655, run from the level constructors (fcn.10044bb5 / fcn.10044ce6), fills the level's table of actor → script (blocks of `woody`/`neighbor`/`mother`/`olga`/`fifi`/`bar_keeper`, one function per level and actor, Woody's the same fcn.100138d6 everywhere; the step chains tools/pcref/routine_order_s2.py reads) — and the step that calls fcn.1000eb19 is entered when fcn.100585c0(`crash`) holds (0x1001462e: `mov [edi+8], 0x1001452c`), i.e. it is the scripted fight with a co-actor after a crash reaction (the `m_hurt_n`, `olga_fight`, `mother_fight` scenes), not the catch of Woody. The catch objects themselves (the fear/fight fiber, vtable 0x100ab258 / 0x100ab278 with fcn.100061dc) are created by fcn.1003c4e3 — one level's `olga` script entry — and by the unheadered fcn.1003f086, which resolves an actor by name and tests its +0x14 flags 2 and 0x50 (the flag helpers fcn.100450bf / fcn.100450dc) and has no code reference at all: it is slot 2 of the vtables 0x100b0ff8 / 0x100b100c (radare2 `/x`), the event objects the level tick itself creates every tick while `[level+0x44]` is empty (the level update at 0x10044386 → fcn.10040f38 → fcn.100403d8 → fcn.100461eb, which resolves an actor by name and sets its flag 0x100000 → fcn.1003f431 → fcn.1003f3df, `new` of 0x18 bytes with four arguments). Those objects are the watch entries themselves: fcn.1003f4d9, which the walker's fire path fcn.1003f86d calls, is their equality (four string fields through the strcmp wrapper fcn.100585c0), fcn.1003f4b8 the list push, and slot 2 the entry's action when it fires — for this class the catch: resolve the actor in the level, test its +0x14 flags 2 / 0x50, start the fiber. The predicate fcn.1003f573 (reread the same day) returns false when the entry's mode byte carries none of 1 / 2 / 4, so a catch entry must be registered with a mode; the per-tick object the tick builds at 0x10044386 is the probe the walker compares the table against. The entries the tick's probe is matched against are the script steps' own: the `use_object` step's start method (0x100469c3, in the step-class vtables 0x100b1328 / 0x100b19c8) registers (`use_object`, the object, …) through fcn.1003f431 — the string global 0x100e1b74 is `use_object`, one of the engine's step kinds next to `goto_pos`, `combine`, `stop`, `crash`, `olga_fight`, `mother_fight` — and the data's `behavior=` records on that object's actions bring the modes (`room`, `always`); a matched pair fires slot 2, which resolves the behaviour's actor, tests its flags and starts the behaviour fiber (fcn.10005b94: the `run` that plays fear, `fight` and the respawn). That is the reaction path — the neighbour's `run` after Woody's failed minigame, Olga's shout — read end to end; a catch on Woody merely walking into the room does not pass through it (no data record names a walk), and where the PC's Season 2 tests that is what remains unread, so the profile's Season 2 keeps the mobile predicates. Read on 2026-09-23 — the walk-in catch is data after all: generic/trigger.xml gives the neighbour and the Mother a `fight` behaviour on Woody, `<trigger object="woody" position="room" type="always"/>` (and Woody a `die` one on either; Olga and the other actors have none), Loader.dll's trigger parser (0x1000a869-0x1000a936) makes `position` room / nearobj / house the mode bits 1 / 2 / 4 and `type` once / always 0x1000 / 0x2000 of the AddObjectTriggerMsg `flag`, and GameLogic's handler (fcn.1004fa5c: actor, actionactor, behavior, flag, object — the message registry binds it at 0x100505a3) files it in the watch table; so the catch is mode 1: both room pointers set and equal, the target placed (0x20), neither party's flag 4. Flag 4 is set by the enter step (vtable 0x100ab2ec, 0x100067d4-0x100067e9) when the entered object carries hideout or neighbor_hideout (0x140), cleared when the leave step's `leave` has played (0x10006ab7), and set or cleared by nine level steps (the complete list of the setter's mask-4 calls: 202's sea and beer, 206's, 210's and 214's Mother asleep and awake, 209's shoe mat — tools/pcref/pc_catch_s2.py) | differed in kind: the mobile's catch had IgnoreWoody, the blocking animations, IsSleeping, PassingComplexMove and DonePassingToOtherZone, its sleep windows the ProgressBars' sequence spans on the same stations; carried since 2026-09-23 (`pcprofile.s2_sight`, `World._pc_s2_sees`, `_pc_flag4_tick`, `Pawn.pc_room`, PCHideout): the room pointer — none on a hop's steps up to the transfer, less the `out` run stood before one, and inside a back door's clips — Woody's hiding through his hideout's leave clip, the catchers' flag 4 at their neighbor_hideout stations with the level steps' clears; the crossing check reads the same predicate |

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
  the far door's last tick; the mover, the walk job and the GOTO are done in the tick of the last
  move (0x47cf93-0x47d00d, 0x476112-0x476209, 0x44a81b-0x44aab0) — the
  next step starts on the tick after, two ticks with no move — and the
  door step and its ACTION are pushed with the run-now flag 1 in the
  arrival's update (0x476004-0x476070, 0x474480-0x474496), as is the walk
  job's own LEAVE (0x475ce6): each shares its first tick with the segment
  before (tools/pcref/lap_model.py, `Pawn._pc1_close`; read so on
  2026-09-27 — the earlier reading, a tick after the last move and three
  with no move, counted a tick too many a walk and one more a door and a
  leave). ENTER and LEAVE of an object, read 2026-09-27: the
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
  The lists' own first updates, their message steps and StopMsgs are
  carried since 2026-09-27 (the row "the instant steps and the fire
  step"). The skate's list (Level_Fitness 0x46303e-0x46355a) is carried
  in the RollerSkater since the same day: the slide's first move six ticks
  after the trigger (the case's push, the list's start, a StopMsg, the
  skate's and the gait's message steps, a StopMsg: PCReactLead 6), the
  slide at the skate gait from his PC point to kit/window's hotspot
  (PCSlideTo, skate1 18 px a tick), the `fallout`, the list's 12-tick
  timer (fcn.0047e520 — the ACTION's timer, an element's time + 1) and a
  StopMsg before the fire (PCFallSeconds 50 ticks where the mobile's
  FallDelay is 48), the gait message after the fire and before the
  `wheeze`, the StopMsg after the shout2 — 112's bicycle-skates-marbles
  pairs are +0.6 and −0.5 s against Badinfos' (+0.1 and −0.7 before), their
  sum +0.1 (−0.6 before): the walk back in through the front door (the
  fallout lands him on the porch, anc/inside past fro/anc) is the mobile's
  way from EntranceLocation to BreathLocation, not the PC's. The pet
  alarm's list (fcn.0047a690, built by the level class's case after the
  `noise` run and pushed with the run-now flag 0, no StopMsg) is carried
  the same day: its first update a tick before the `search` (the Alerters'
  PCSurpriseSeconds 27 ticks), and after it — the pet found in his room
  (fcn.0047a1d0) — `wakeup` sent to the pet, the `dog_shout` or
  `chili_shout` icon, the GoTo to the pet and `shout0_light` (26 ticks,
  PCAlarmShoutSeconds: the remaster's AngryHard at that pace; the mobile's
  run already ends at the pet), else the icon and `shout2` where he stands.
  Corrected 2026-10-03: the remaster's run ends at the pet's zone, and
  its SameZone choreography walks him on to the pet after the surprise and
  yells there (ActionManager.cs:459-481) — the list's GoTo and its
  `shout0_light` —, so the AngryHard played after the search had doubled
  the shout (114's dog: the search at the bedroom door, the shout there,
  the walk of 3.8 u, the yell: 2.2 s long); the yell is the shout now, at
  its PC pace (Routine._pc_yell_secs, _same_zone_yell), the walk after
  the list's `wakeup` and icon message steps (two ticks standing): 114's
  polish to the phonograph 78.6 s against Badinfos' 79.5 (80.7 before).
  game.exe
  tests the nearobj triggers every tick wherever he stands (fcn.00472390
  over fcn.00471bc0); the port notices on the walk's frames and, under
  the profile since 2026-09-27, on the arrival's (Pawn.walk_hook: a walk
  that lasts the PC's ticks can reach its target without a frame inside
  the notice distance — 102's rush to the stuffed toilet sat down on it
  unnoticed, the missing paper's reaction lost with it): a trick laid
  within 15 px of where he stands still is noticed on the PC at once, on
  the port at his next walk — carried since 2026-10-03 for the floor
  tricks (Routine._pc_notice_standing on his standing ticks; the reach
  15 px, pcprofile.S1_NEAROBJ_PX, where the mobile's
  NoticeWhenNearTrickedDistance is 0.1 u, 9.6 px): fcn.00471bc0's nearobj
  mode is the actor in the object's room, not in a hideout (flag 4,
  fcn.0043c2b0 at 0x471cee) and |x - the object's `neighbor` hotspot x| <
  15 (`setl` at 0x471e1a), and fcn.00472390's state machine delivers a
  flag-2 trigger as its condition turns true (0x4724fa-0x472525: the
  0x200 bit set until it turns false, 0x47252c-0x472542; 0x1000 removes a
  one-shot, 0x47254c). The triggers are the level's data: trigger.xml,
  per actor a behaviour and its triggers — `object`, `position` nearobj /
  room / house, `type` once / always, `noise` — the floor tricks
  (groundbanana, groundsoap, marbles, skate) and the stations
  kit/microwavedirty, toi/toiletstuffed, anc/mum_smeared (`always` on
  level_piano), bas/electrotrap and 111's bed/ironingboard_burn (`always`)
  nearobj, 111's lir/dirtycarpet `room always`, 105's anc/phoneringing and
  the generic `alarm` `house always`, the pets' `wakeup` `room always
  noise`: the walk-by stations with a nearobj trigger take the same reach
  and the standing ticks (pcprofile.S1_NEAROBJ_ITEMS: the microwave, the
  toilet, the mum picture, the electric trap, the iron), where the
  mobile's Drawing (107), Pig (109) and Airer (111) have no trigger on
  the PC and keep their walk frames. Season 2's trigger.xml files hold
  the generic catch (`fight` / `die`, `room always`) and one nearobj,
  208's elephant/tap_electricity (`electrify`, `always`), which
  GameLogic.dll tests on every level tick the same way (fcn.1003f573:
  the actors' flag 4, the room, |dx| < 15 at 0x1003f7d0): the mobile's
  ElectricTap takes the reach and the standing ticks as well
  (pcprofile.S2_NEAROBJ_ITEMS; not in a hideout, pc_flag4).
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
  Remeasured 2026-09-27 after the job ticks (the fire step, the lists'
  instants, the walk's boundaries, the pet alarm's list; runs/alarm_s1):
  the 45 order-comparable pairs of 103, 104, 109, 110, 111, 112 and 114
  average +0.04 s against Badinfos' (−0.40 before the pass), their mean
  distance 0.38 s (0.52); the widest left are 109's bed to the alarm clock
  +1.9, 114's polish to the phonograph +1.2 (the dog's alarm in between)
  and 111's drier to the vacuum −0.9 (case 22's take to the carpet: E11's
  1.7 s against the model's 0.8). Again on 2026-10-03 (runs/near2_s1,
  the floor tricks' nearobj notice in): 109's bed to the alarm clock
  38.1 s against 38.0 since the four-argument fire's ready step; every
  pair within 0.6 s of Badinfos' but 114's polish to the phonograph +1.2
  (80.7 against 79.5), 111's drier to the vacuum −0.9 (25.4 / 26.3) and
  110's steak chair to the wine +0.8 (19.5 / 18.7); 103's first two
  swapped (the port's microwave before the candle). On 2026-10-04
  (runs/plain202v_pc, thermo_jumps.py E10 E11 E14): 114's polish to the
  phonograph −0.9 (78.6 / 79.5), 111's drier to the vacuum −0.9 (25.4 /
  26.3), 110's steak chair to the wine −0.1 (18.6 / 18.7) and its first
  three −0.6, −0.7, +0.5 (14.3 / 14.9, 14.8 / 15.5, 17.1 / 16.6), the
  rest within 0.5 s (114's hat and horn read through the full tube, ~8.1
  and ~20.4 against 8.6 and 20.0). Localized the same evening by the
  HUD bubble (bubble.py at 4 fps against the port's stations on the
  video's clock): 114 — the reaction to 220 (the port 220.4), the polish
  from 221 (220.6), the pipe 239 (239.6), the phonograph 250 (250.1), the
  CDs 256 (255.7), the alarm's `?!` 258 (the run 258.7), the dog to 271
  (271.6), the CDs 271-286 (at the rack 283 on the frames, the port's
  283.1, its 25-tick search_record to 285.2), the phonograph from 286
  (285.2) — the −0.9 s lie at the rack; 111 — the vacuum's icon from
  215.0 (the port's walk from its search 214.9) to the vacuum clip, the
  PC's ~218.8 (2.92 s before its fire at 221.8) against the port's
  217.9: the walk to the vacuum, the take and the walk to the carpet
  (68 px, the take's 0.5 s, 79 px: 3.0 s) — the camera pans over him
  in both, so neither is read closer. Season 2's chains the same evening
  (the anger gauge's jumps, tools/pcref/gauge.py at 4 fps, against the
  port's credits where the plan's order is the run's): 202 9.5 / 10.7 /
  33.5 s against E02's 9.5 / 11.0 / 33.5 and 203 37.3 / 5.8 / 35.0 / 17.5
  against E03's 37.5 / 5.5 / 34.75 / 17.2 — once the shark's SHOUT 1 and
  the toilet pair's SHOUT 2 were read (38.3 and 30.0 before; docs/
  PC_FIDELITY.md, "Season 2's chains against Badinfos' gauge"); the other
  twelve plans run another order than the run's. Case 22's message
  before the carpet's GOTO is the vacuum's OBJ1 (fcn.00451e80, vtable
  0x4e1bdc: its slot 2 fcn.00438c80 — no gait), so its 0.7 s lie in the
  GOTO's legs, not read against E11's frames.
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
  Reread 2026-09-27: game.exe reads no clock per frame outside the fps timer — QueryPerformanceCounter and timeGetTime only in fcn.00402da0 (the fps timer's), GetTickCount in the level constructor's random seed (0x43bce0, the generator at +0x8c), the double-click test (0x407eef), fcn.00408c6e, a stamp at 0x40fc37 and fcn.0040eb00 (0x40ebc9), which hands the start time to the object it stores at app+0x20 through that object's slot 0 — the object the frame drives by its slot 15, its class chosen by fcn.0040eb00's caller (not followed). Followed 2026-10-03: fcn.0040eb00 (called by fcn.00410a40 for an 0xa8-byte object of vtable 0x4e6e80) passes GetTickCount to the object embedded at its +0x40 (fcn.004198d0, vtable 0x4dc624), whose slot 0 (0x419700) seeds a Mersenne Twister — 624 words (0x270) of 0x9c0 bytes, the multiplier 0x10dcd, slot 1 (0x419740) its regeneration — a random generator, not a clock; the object it stores at +0x20 is its second argument. The pacer stays unlocated.
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
  66) — the frames before; time + 3 since 2026-09-27 (its second update
  falls in the job's last tick: 28, 87, 28; 39, 40, 65).
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
- `tools/pcref/lap_model_s2.py`, `tools/pcref/pc_walks_s2.py`,
  `runtime/pcprofile.py`, `runtime/world.py`, `levels/pc/Level2*.overlay.json`
  (2026-09-27): Season 2's walk by its jobs (docs/PC_FIDELITY.md "Season 2
  walks", the paragraph of that day): a walking step's own ticks 2 (the
  GoTo's first update pushes the route with a first run, whose first
  movement steps at once — 0x10007504, 0x1000ab8d, fcn.10009889), each pass
  3 ticks shorter than its runs (the jobs' shared ticks: `jt`), the run
  back to the far floor along x first where the floor line ends short of
  `<actor>_out` (`ox`, the clamped `xo`), the `in` run split at the near
  `<actor>` hotspot (`nb`); the lap model's walks by `walk_span`; the
  tricked flows on the lap's clock (`_flow`: the per-event station_ticks
  had given each part a step's tick and the instants none). The idle
  visits re-measured (runs/idlejt2; the 2026-09-23 file had outlived the
  walks): 213's picnic 12.8 -> 10.8 s, 206's chair and pillows +0.1 and
  +0.5 s. Every Season 2 writer re-run.
- `tools/pcref/lap_model_s2.py`, `tools/pcref/pc_durations_s2.py`,
  `runtime/scene.py`, `runtime/world.py`, `levels/pc/Level2*.overlay.json`
  (2026-09-27): the SHOUT's step's tail stood — PCShoutTail /
  PCShoutTailLinked (`_shout_tail`: the step after its repair, or after
  the SHOUT with none, to its end; 31 visits, 1-4 ticks, 210's turban shop
  1.25 s, 205's sand lion 7.58 s with the kid's laugh). All 14 at 100.
- `tools/pcref/trick_branches.py`, `levels/pc/Level10[1290].overlay.json`,
  `docs/PC_ROUTINES.md` (2026-09-27): the four-argument fire pays before its
  ready step (`_ready_after`): 109's cactus clock fires 1.75 s into its
  stand, before the bed's LEAVE (PCFireAt 3.0), 102's laxative beer before
  the sofa's LEAVE and the spit, 101's fart bag before the sofa's LEAVE,
  110's fuel beer before the barbecue's switch. All 14 Season 1 at 100;
  109's bed to the alarm clock 38.1 s (the video's 38.0; 39.9 before).
- `tools/pcref/lap_model_s2.py`, `tools/pcref/pc_walks_s2.py`,
  `runtime/world.py`, `tests/run_tricks.py`, `levels/pc/Level2*.overlay.json`
  (2026-09-27): the Season 2 GoTo's own argument — the walker had taken the
  step object loaded into ecx for the thiscall for the object's name, the
  lap's walks falling back on the IsVariant pick or the DoActions' object
  and step_ticks comparing `$` names. 203's toilet step walks to the toilet
  (the model's lap 107.5 s, the port's idle lap's own; 208 87.2 the same),
  212's ledge step to the cliff (STATIONS; the lap 4 s longer), 205's put
  step to the guarded skis through edx (PCApproach x / px per visit,
  VISIT_OBJECTS, world.pc_ap_px); a tick more or less on nine stays.
- `tools/pcref/lap_model_s2.py`, `tools/pcref/pc_walks_s2.py`,
  `runtime/world.py`, `levels/pc/Level2*.overlay.json` (2026-09-27): a
  step's place by its hotspot (fcn.1000e3e0 pushes no GoTo at the target's
  hotspot: 212's bench after the cigars, one spot), the bar helper's own
  GoTo (fcn.1000e7f2 -> fcn.1000e3e0 unless inside: 209's curtain is
  entered from the shoe mat), and a hideout's leave placing him at its
  `<actor>_out` (fcn.10006c2e -> 0x1000690a: 212's ledge leaves the water
  exit, 265 px left of the cliff; 209's tricked hot coal 293 px right,
  212's tricked bench 75 right, 210's hedgehog chair 47 left (back at
  the chair by its GoTo element since 2026-10-04) — PCApproach
  `tx`/`dpx`, `txt`/`dpxt`). All 14 Season 2 at 100, the mobile
  regression byte-identical.
- `runtime/pcprofile.py` (2026-09-27): Season 2's SHOUT element lasts its
  DoActions job and one tick, the Loader's time + 3 (`S2_SHOUT_TICKS` 28,
  87, 28; `S2_FREAKOUT_TICKS` 39, 40, 65): its first update pushes the job
  without a first run (0x1000d8a2), the job's third state finishes past the
  time (0x100020c0, fcn.100011f2), and the runner goes on to the element in
  the same tick (fcn.100492a8), whose second update returns 1 at once
  (0x1000d8a6) — time + 4 had given its done update a tick of its own. All
  14 Season 2 at 100.
- `tools/pcref/lap_model_s2.py`, `tools/pcref/pc_durations_s2.py`,
  `runtime/scene.py`, `runtime/world.py`, `levels/pc/Level213.overlay.json`
  (2026-09-27): 213's picnic read — the steps' event latches
  (fcn.10013269 over the byte fcn.10013319 sets for a behaviour of the
  latch's name; run_step `latch`), the GoTo a step appends to its sequence
  (fcn.10007a10: the object and the hotspot it names — GOEL, timed by
  walk_span from the position the flow tracks), the string a step assigns
  to a local from a global's address (fcn.10009b58: 211's wc by the sign),
  and the co-actor's own steps before her walk and fight (FIGHT_BEFORE:
  Olga's `leave` of the boat and her jump into the water; fcn.1000e601's
  walk to 50 px short of him, [0x100cc814]). The untricked stay 12.83 s
  (the video's 10.8 had been derived against the port's first-lap walk),
  the tricked one 11.92 s, its credit at 4.08, SHOUT 1, her fight 3.58 s
  after 5.67 s of her own (PCHitAfter, World.play_angry) — the port's
  tricked picnic 23.67 s from his arrival to the pinata, the code's 23.75.
  211's toilet continuation (not carried) gains its walk to wcright's
  `beat` (17 ticks). The model's script run: its `__main__` block moved
  below the Geometry it now needs.
- `tools/pcref/lap_model_s2.py`, `levels/pc/Level205.overlay.json`,
  `levels/pc/Level208.overlay.json` (2026-10-03): other actors' jobs — a
  DoActions job or a sequence a step pushes onto the actor fcn.1004ba02
  finds (fcn.10049216 with it for `this`) is that actor's (ODO), his
  only where its record posts him a behaviour he waits for (204's Elvis's
  gong); a walk that starts inside a hideout leaves it first (the route,
  fcn.10049190 -> fcn.10006c2e, 0x1000a840-0x1000a87e); a step that
  calls its next itself builds no sequence (CALLNEXT, a tick less). 208's
  IndianPlatform 11.42 s (the fakir's `play` and `stop` off, the
  platform's leave on), ShoeMachine 4.58, its lap by code 86.0 s — the
  video's 86; 205's OlgaMatBeach 6.5, the sand lion's PCShoutTail 7.58
  gone (the kid laughs on his own queue); 202's lap by code 73.2 s (the
  kid's dive his own).
- `tools/pcref/pc_durations_others.py`, `tools/pcref/lap_model_s2.py`,
  `tools/pcref/pc_durations_s2.py`, `tests/run_tricks.py`,
  `levels/pc/Level2*.overlay.json` (2026-10-03): the Mother's stands by
  her script (ROLE_LAPS over lap_model_s2.role_lap: each a step's GoTo,
  its `use` job and the step's two ticks; 212's statue 8.67 s and red bull
  12.0, 213's water 12.83 and flowers 17.0 — her 213 lap has no statue —,
  214's reling 7.0 and chair sit 1.0); a stand timed per clip takes the
  step's two ticks with its first clip after the walk ('step'); a tricked
  visit whose first step plays the same leads the flow of the one that
  differs (212's bench: 10.92 s, its credit at 10.08); 204's gong's
  continuation `leave` on its stand (5.5 s); 210's elephant's credit in
  Fifi's `dogattack_bat`, 1.83 s (CREDIT_BY: her step starts once his
  `put1` shows her). Plan 212 v8. The harness: a rush leg
  (`op!`), whose gate does not run, clicked the way-round waypoint the
  last gated leg had left (Level214's fish from the chair walked off
  through Zone04 into his shower room): the waypoint is the leg's own now.
- `tools/pcref/lap_model_s2.py` (2026-10-03): the lap is the walk from its
  loop's step on — lap_estimate and _paired_parts had rotated the steps
  before it in (213's tub repair, 206's reling: the level's start). The
  port's idle laps under the profile against the model (runs/idle9, Woody
  waiting): 203 107.5-107.7 s (the model 107.5), 208 86.0-86.2 (86.0, the
  video's 86), 209 108.0-108.2 (107.6), 211 85.7-85.8 (85.7), 212
  128.2-128.3 (128.2), 213 122.7-122.8 (122.2; 124.0 with the tub's
  repair), 214 90.8 (90.8); 202 78.0 (73.2 and his wait at the shore for
  Olga's sub, which the model does not time). The open laps against the
  videos span by span (a span the walk in and the stay): 204's karate
  10.5 s (the video's first lap 9-10), gong 21.8 (22), hot dog 17.0
  (15-16), jade 23.5 (23-24) — its "81 s" lap is the first one, from the
  level start at the kart without the walk to it (the port's 92.5 with
  it); 205's skis 37.5 (36), chef 17.8 (17), rockets 18.7 (18), sand lion
  13.1 (12) — its "102 s" the first lap, without the mat's talk and wait
  that the code's lap has (111.9; the port's 112.0). The Mother's rounds
  by her script (role_lap and walk_span for her records) against the same
  idle runs: 212's 37.33 s (the port's 37.33), 213's 70.5 (70.0-70.2).
- `runtime/pcprofile.py`, `runtime/world.py` (2026-10-03): a co-actor's
  fight on him posts its behaviour as its job ends, his handler's step
  reads it on the tick after and pushes its sequence without a first run,
  the SHOUT first: the shout two ticks after the fight's end
  (pcprofile.S2_HIT_TAIL_TICKS, Routine._hit_pawn_done; lap_model_s2's
  `cont` of every 'fight' continuation a tick, and the offer's), where
  the port had shouted as the hit ended — 204's rickshaw, 207's shell,
  210's elephant, 213's picnic, 214's shower, bouquet and pistol.
- `tools/pcref/lap_model_s2.py`, `levels/pc/Level204.overlay.json`,
  `levels/pc/Level214.overlay.json` (2026-10-03): a builder set up for
  another actor (fcn.1000ee93 with fcn.1004ba02's actor, pushed by
  fcn.1000eec6) builds that actor's sequence — 214's pistol: the Mother's
  `die` in her deck chair off his stand (8.42 s, 18.83 before); a
  co-actor's first move two ticks after his part posts her behaviour
  (PCHitAfter: 204's rickshaw 0.08, 214's shower and bouquet 0.08, its
  pistol 0.17).
- Read 2026-10-03, nothing to carry: the watch predicate fcn.1003f573
  also asks the watched actor's flag 0x20 (0x1003f610: cleared, the
  actor counts as absent, 0x1003f6e1) — the shown bit the hide element
  clears (fcn.10042b9e, 0x10042c26) and the show sets (fcn.10043b9e,
  0x10043c34); Woody is hidden only in the catch fiber and the respawn,
  when the port tests no catch. 210's elephant: Fifi's attack (59 ticks
  from 17), the bat's hide and her `fall` (36) post `crash` to the Mother
  at 113, her first move at 115 — a tick after his stand's end (114),
  not carried (PCHitAfter 0) — carried later the same day (below).
- `tools/pcref/lap_model_s2.py`, `tools/pcref/pc_durations_s2.py`,
  `tools/pcref/pc_walks_s2.py`, `levels/pc/Level206.overlay.json`,
  `runtime/scene.py`, `runtime/world.py` (2026-10-03): 206's lap by code
  (PAIRS: the mobile's loop from its selected index against the script's
  lap after the pillow lesson, 0x1002e63c-0x1002c674). An idle run past
  the lesson under the profile (runs/idle206q: the plan's four lesson legs,
  then 420 s): the port's lap 118.5, 118.67 and 118.5 s (DogFifi's take to
  take), the model's 118.5 — 105.3 s before (runs/idle206p), the dynamite
  4.4 s of the mobile's clip where the code's bag, walk and reling take
  16.2. The lesson's rows up to the lap's first take byte for byte the
  same in both runs (its opening DogFifi visit at its own length,
  PCUseSecondsLead — withdrawn the same day with the PC's own lesson,
  below). The idle run without the lesson's legs stops at 34 s
  on both profiles: TutorialScriptCameraNFH2206's Hold waits for the
  LevelScript's action 4 (the player's steps), the neighbour frozen after
  the in-game move to Zone04 (AddInGameActions(4)) — the mobile's lesson,
  not a stall. Plan 206 unchanged: 100 at 266.5 s (253.5 before).
- `runtime/tutorial.py`, `runtime/hud.py`, `tools/pcref/pc_tutorial206.py`,
  `levels/pc/Level206.overlay.json`, `tests/run_tutorial.py` (2026-10-03):
  206's lesson by the PC's scripts (TutorialPC206: the director, the
  Mother's and the neighbour's steps on the level's ticks). Against the
  let's play (pc_nfh2_all_720, E06; frames at 4 and 2 fps from 1242 s):
  he starts for her chair at ~1245.9 s — the port 8.32 s —, for the
  pillows 3.1 s later (the port 2.66: her order's 18-tick job and its
  offer, the step's own tick), takes them 6.6-7.6 s after his start
  (7.0), gives them 12.6-13.6 (12.66), and step2 shows 14.6-15.1 (14.2).
  The video's HUD clock reads 0:01 at 1238.0 s: his start at ~8.9 s of
  it, the port's 0.6 s earlier (the clock's zero against the scripts'
  first tick unread). The lap past the lesson 118.5, 118.67 and 118.5 s
  (runs/les206f), his put at Fifi FifiPutLeft. tests/run_tutorial.py
  (59 checks, 60 since 2026-10-03, 88 with the Season 1 tutorials by the PC's code): the remaster's lesson under the mobile profile, the PC's
  under the PC one — the binding, step1 and his laugh, her call, her
  order, step2 and the toy box, step2a and the pillows, step3 and the
  pipe, step4 and her second call, the fart paying the chair's trick, her
  fight, his shout and the lap from Fifi's take, step5. Plan 206 (the fart
  bag on the pillows after step2a): 100 at 246.3 s, PC 16030 (15876 on
  the remaster's lesson, whose fart had paid the pillows' 30).
- `tools/pcref/trick_branches.py`, `levels/pc/Level110.overlay.json`
  (2026-10-03): an ENTER on an object while he still occupies one plays
  no `enter` — the step's update finds the occupied object (fcn.00444ad0
  at 0x47388a, not null) and ends at once (0x473a22), its own tick; the
  lap model had it (lap_model.py), the tricked stands' tails did not.
  110's chair: after the pins' fire the case repairs, switches the chair
  back and ENTERs the table again with no LEAVE between — the redo is the
  switch's and the ENTER's ticks and the `eat`, then the walk's leave:
  PCRedoSeconds 5.417 where it had been 6.333. Against Badinfos' E10
  (pc_s1_all_720 at 8 fps, the thermometer's 5/6 at 2600.8-2601.0 s):
  the shout's end and the repair's start ~2608.85 (3 + 93 ticks after the
  fire), the pins out and the chair switched ~2609.8, seated at once
  (2610.0 standing, 2610.125 seated), the `eat` to ~2614.5, the wine's
  icon ~2614.5, the fire ~2619.45 — the icon to the fire 59 ticks, the
  leave 11, the walk 11 and the drink 37 of the model. The chair to the
  wine 18.59 s (runs/p110occ), Badinfos' 18.7 (19.5 before); 110 at 100.
- `tools/pcref/pc_walks_s1.py`, `runtime/world.py`, `runtime/scene.py`,
  `levels/pc/Level107.overlay.json` (2026-10-03): the Season 1 idle laps
  against the lap model (runs/idleS1b, the neighbour alone): 101 30.0 s
  (the model 30.4), 102 25.2 (25.2), 103 32.0 (32.5), 104 76.7 (75.9),
  105 48.3 (48.4), 106 116.6 (116.4), 107 56.2 (57.5), 108 92.3 (92.2),
  109 118.7 (118.2), 110 54.5 (54.9), 111 115.7 (115.5), 112 150.8
  (150.9), 113 176.6 (176.2), 114 179.3 (178.7). 107's 1.3 s: the dove
  case's GOTO to bal/dove_free before the painting's (the lap model's
  `walk 14 -> bal/dove_free`, then `walk 7 -> bal/picture_empty`), which
  the port walked straight — the only GOTO of the fourteen laps with no
  action before the next one in its room but 107's statue on the way to
  the footstool. Carried (PCWalkVia): 107's lap 57.3 s (runs/idle107v).
- `tools/pcref/lap_model_s2.py`, `levels/pc/Level210.overlay.json`
  (2026-10-03): a co-actor's fight whose behaviour her own job posts, his
  flow's parts posting none (POST_BY): 210's elephant — Fifi's sequence
  0x10018239 with the bat in the scene, its first update the tick after
  the offer of his `put1`'s end: dogattack_bat 59, the bat hidden, her
  `fall` 36, whose record posts `crash` to the Mother as its job ends;
  the Mother's first move two ticks after that post, a tick after his
  stand's end: PCHitAfter 0.08 s (0 before). Plan 210 at 100.
- `tools/pcref/pc_durations_others.py`, `runtime/tutorial.py`,
  `levels/pc/Level206.overlay.json` (2026-10-03): 206's Mother after the
  lesson by her script — 0x1002b9fe walks her to her chair, enters it
  (sitdown_pillow) and holds her asleep for fcn.1000e7f2's 720 ticks, the
  chair's `sleep`; 0x1002b972 clears her flag 4 and shows the chair's
  `look`, 0x1002b72a counts 360 ticks (0x168 at 0x1002b73f), then the
  chair's `sleep_pillow` and her flag 4, and the 720 again. The port had
  her look 11.8 s after sitting (the mobile's first use, MotherSitPillow
  and MotherLook), then 58.0 s asleep and 30.7 awake: now her first visit
  is the sit alone and the second use's set her loop at her script's
  pace (CLIPS_ROLE: the sit 1.67 s, the nine sleeps 60, the two looks
  30) — runs/les206h: sat 67.15, asleep 68.82-128.98, awake to 158.98,
  asleep to 219.15. Plan 206 at 100.
- `tools/pcref/pc_durations_others.py`, `tools/pcref/pc_walks_s2.py`,
  `tools/pcref/lap_model_s2.py`, `levels/pc/Level208.overlay.json`,
  `Level209.overlay.json`, `Level211.overlay.json` (2026-10-03): 208's,
  209's and 211's Mother by her script (GameLogic.dll's registry of the
  level folders' actor scripts: in_c1's `mother` 0x1001d2ec, in_c2's
  0x1001f87a, ship3's 0x1002f92e). The video (pc_nfh2_all_720, her HUD
  portrait at 10 fps: the bubble's icons and the bar's green): 208's
  bar onsets 5.7, 49.4, 93.2, 136.9 s into E08 — 43.7-43.8 s apart
  (the dressing room's 360 ticks, its `enter` and `leave`, the walks to
  Fifi's spot and back, the Fifi step's two ticks: 526 ticks, 43.8 s);
  209's shop icon at 0.0, 48.4, 102.6, the dressing room's at 11.4,
  65.6, 119.8 and the bar's green at 18.6, 72.8, 126.9 — a 54.2-s cycle
  of the shop to the room 17.2 s (the leave, the walk, the `use`'s 124
  ticks), the room's icon to the bar 7.2 (the walk and the `enter`) and
  the bar 29.8 (360 ticks); 211's bar onsets 0.0, 38.5, 77.2, 115.9,
  154.5, 193.2 — 38.6-38.7 apart. The port (runs/idlemo1): 208 43.83-
  44.0 (the mobile stands' 41.5-41.67), 209 54.33 with the segments 17.3,
  7.16 and 30.0 (41.17), 211 38.67-38.83 (33.67-33.83 — the new
  approach to the kid takes the PC's door pass, 7.2 s a way where the
  mobile's walk had 4.3). Plans 208 and 211 at 100 unchanged; 209 at 100
  with its two Zone02 takes moved to her next Hide_In (v3, runs/g209b:
  432.2 s). Mobile 270/270.
- `tools/pcref/lap_model_s2.py`, `tools/pcref/pc_durations_others.py`,
  `levels/pc/Level204.overlay.json`, `Level210.overlay.json` (2026-10-03):
  the go-and-enter helper fcn.1000ea30 read as a GoTo and the hideout's
  `enter` unless inside (lap_model_s2 `EA30`): of the neighbour's laps only
  204's changes — the gong's `enter` (time 0: two ticks, and the walking
  step's own) with its `use`, 3.92 s (3.67); tricked 5.75, credit 3.58.
  Plan 204 at 100 (runs/g204a). 210's Olga by her script (runs/olga210idle):
  the mat 11.67-11.83 s (the model's 142 ticks, 11.83), the shower
  14.17-14.33 (173, 14.42), walks 2.0-2.3 (25 ticks), the cycle 30.5-30.67
  (the model's 30.4; the mobile stands' 36.2-36.3); the bra's water loop
  19.3-29.3, 49.8-59.8, 80.3-90.3. Plan 210 at 100 with the bra at her
  second shower (v26, runs/p210olge: 407.7 s).
- `runtime/world.py`, `tools/pcref/pc_durations_others.py`,
  `levels/pc/Level211.overlay.json` (2026-10-03): 211's Olga on his use
  ends (her script's handler 0x10031888: `bonbons`, `roddone`, `goup`).
  runs/o211idle, lap 2: the diving gear's use ends 69.48 — she walks at
  69.65, is at the toilet 72.98 and in it 73.98-75.65; the sweets end
  ~90.98 — her leave 91.15-93.48, the kid 96.15; the rod ends 104.65 —
  she walks at 104.82, the reling 107.32; the diving gear ends ~155.15 —
  she walks at 155.32. The model: the leave 27 ticks, the walks 32, 30
  and 52, the enter 21 — each within 0.17 s. Before: her WC enter clip
  looped from lap 2 through the toilet stay, the leave came 1.3 s after
  the sweets' end and lasted 3.25 s. Plan 211 at 100 (runs/o211plan,
  unchanged 261.6 s).
- `runtime/world.py`, `runtime/scene.py`, `tools/pcref/pc_durations_others.py`,
  `tools/pcref/pc_walks_s2.py`, `levels/pc/Level213.overlay.json`
  (2026-10-03): 213's Olga on his uses (her latches `boat`, `leave`,
  `bull`). runs/o213bidle: his tortilla begins 36.65 — she walks from the
  water at once, 5.17 s to the picnic (the PC's 63 ticks, 5.25), enters
  41.82-43.82 (24 ticks, 2.0); his picnic ends 67.3 — her leave 67.32-69.32
  (24); the bull at 90.65 (a door claim while he passes to the pinata),
  his controls begin 93.65 — the ride 93.65-100.65 (7.0); to the water
  100.65-115.98 (184 ticks, 15.33); lap 2 the same at 164.82 / 195.65 /
  221.98. Before (runs/o213base): in the picnic from 14.15 while he was at
  the carnivore, out at 33.65, at the bull through his picnic, the lap-2
  ride at his tortilla. Plan 213 at 100 (runs/o213bplan, 391.4 s).
- `runtime/world.py`, `tools/pcref/pc_durations_others.py`,
  `tools/pcref/pc_walks_s2.py`, `levels/pc/Level214.overlay.json`
  (2026-10-03): 214's Olga on his bouquet (`flowers`: her `wait`, the
  pillar's `wait`). runs/o214bidle: his Bouquet use ends 30.98 — she walks
  at 33.65 (the wait's 32 ticks, 2.67), at the pillar 37.65 (4.0 s, the PC's
  49 ticks, 4.08), off it 40.65 (3.0; 34 ticks, 2.83), at the bouquet
  44.65 (4.0). Before: off 1.0 s after his next action's start, 5.8 s at
  the perch. Plan 214 at 100 (runs/o214bplan: the tricked bouquet's fight
  and shower as before — the Washbucket at 525.0, the end 733.3 s).
- `tools/pcref/pc_durations_others.py`, `levels/pc/Level201.overlay.json`,
  `Level204.overlay.json`, `Level207.overlay.json` (2026-10-03): 201's Olga
  at the buffet (BuffetEat 4.17 s a bite, BuffetCrash 2.58 — runs/o201plan:
  the crash 142.82-145.48), 204's rickshaw enter (2.0 s) and 207's mat
  (0.92 s) at the PC's ticks. Plans 201, 204, 207 at 100 (runs/o201plan,
  runs/o20x: the same scores).
- `runtime/world.py`, `runtime/scene.py`, `tools/pcref/pc_walks_s2.py`,
  `levels/pc/Level2*.overlay.json`, `tests/plans/pc/s2/Level208.txt`
  (2026-10-03): the Season 2 start. pc_nfh2_all_720 at 30 fps: 209's
  first icons at 2088.47 (the intro card's end), the Mother's dressing
  room icon at 2101.23 — 12.76 s; runs/st209b: 12.98 (the walk from
  level.xml's 1100/870 to the shop 2.33 s, the model's 30 ticks 2.5; the
  use 10.17). 211: the portrait at 2647.20, the bar at 2648.20; runs/st211:
  the sit 0.32, the bar 1.32. Before: 13.98 and 3.32. The neighbours' first
  stations are the mobile lists' first on the ten levels whose first step
  the registry's constructor names (202 mat, 203 speech, 204 rickshaw, 205
  talk, 207 dive, 208 platform, 209 fakir, 210 chair, 212 throne, 214
  shower). All 14 Season 2 plans at 100 with 208's v3 (runs/p208st2:
  276.4 s).
- `tools/pcref/lap_model_s2.py`, `tools/pcref/pc_durations_s2.py`,
  `levels/pc/Level209.overlay.json` (2026-10-03): 209's fakir (the spit the
  fakir's job, his burn 16 ticks: 1.33 s) and the shoes (the put with the
  curtain's enter, 35 ticks: 2.92 s; the Taj the bar and the leave, 11.08).
  runs/ff209bidle: the fakir 7.82-8.98, the shoes 18.15-20.98, the Taj
  21.15-31.98, the take 32.15-33.98; the lap 106.83-107.0 (the model
  106.0). Plan 209 at 100 (runs/ff209bplan, 426.2 s).
- `runtime/hud.py`, `runtime/world.py`, `runtime/scene.py`,
  `runtime/record.py`, `tools/pcref/lap_model_s2.py`,
  `tools/pcref/pc_durations_s2.py`, `levels/pc/Level201/202/206-210/212/
  213.overlay.json` (2026-09-30): the Season 2 bubble by the script's icons
  (PCIcon, PCIconAt, PCIconClips; a null icon and a bar hide it). The
  videos on the level's clock (the HUD clock's second ticks; E09 +1.55),
  the port's fine idle laps (a state row a tick, hud.think): 209 the Taj
  icon 9.13 / 9.15, hidden 20.85 / 21.03, the slippers 30.88 / 31.12, the
  coals 33.82 / 34.05, the ice cream 44.92 / 45.35; 212 hidden from the
  bench 51.23 / 51.33, the bull ride's icon 64.30 / 64.37; 210 hidden
  from the chair step 1.57 / 1.37, the Mother's icon 25.94 / 25.85 (the
  port's deck chair icon to 27.35 before), hidden again 117.97 / 117.55;
  208 hidden for the platform's bar 5.53 / 5.38, the shoe cleaner's icon
  10.57 / 10.38; 202 the swim's hide 36.54 / 34.87 and the bridge's icon
  44.70 / 42.95 (the open wait at the shore); 213 the limberwall at the
  start, then 8.13 / 8.03 ... 100.27 / 100.38. All 28 plans at 100 as
  before (runs/icons1_pc: the same legs and scores), mobile 270/270, both
  tutorials ALL OK.
- `runtime/world.py`, `runtime/scene.py`, `runtime/record.py`,
  `tools/pcref/pc_durations_others.py`, `levels/pc/Level206-214.overlay.json`
  (2026-09-30): the Mother's bubble (PCIconRole, PCIconClipsRole) and 212's
  waits paired by room. Her cloud in the videos (the white of it outside
  the icon, 30 fps) against hud.think_m (fine idle laps): 209 the fakir's
  shop from the start, the dressing room 12.98 / 12.85, hidden 19.82 /
  19.88, the shop 49.98 / 49.88 (the dressing room's icon to 50.72 and the
  shoe cleaner's after it before); 208 hidden 6.87 / 6.72, Fifi's 36.47 /
  36.72, the dressing room 43.77 / 43.77; 210 hidden 2.60 / 2.50, the
  neighbour's 22.34 / 22.57, hidden from 34.54 / 34.60 through her awake
  wait (the deck chair's icon at 54.67 and 89.72 before); 207 the deck
  chair's 47.87 / 48.00 over the ladder; 212 the whip 15.30 / 15.18, the
  bull 32.27 / 32.20, 52.47 / 52.52, 69.43 / 69.53, 89.67 / 89.85; 211
  none throughout (bring_pillow and scold_kid before); 213 and 214's
  water. Plan 212 at 100 (PC 17539); all 28 at 100 (runs/mom1_pc).
