# Getting closer to the PC original — analysis, no changes made

The port's truth is the mobile decompile, and every runtime line cites it.
"Closer to PC" therefore cannot mean editing that runtime: it means an
explicit, switchable overlay — data patches plus a handful of rule switches —
whose every deviation cites a PC source the way the parity code cites
`Assembly-CSharp`. Without the PC data files the PC side is known only from
the 100 % guides and videos (see `docs/PC_VS_MOBILE.md`), so each item below
carries a confidence.

## 1. Five axes, three worth pursuing

| axis | what differs | pursue? |
|---|---|---|
| rules | S2 rating (+10 only for EXACTLY one overflow), no lives | yes — two switches |
| reachability | 114 (no whistle), 211/214 (colliders), 108 (one-off brushing), 206 (double overflow) | yes — data overlays, one small hook |
| routines / timing | laps re-authored by Nordi as ActionManager lists — the PC order everywhere, and without tricks the PC speed (±15 % on 21 of 26, §2.7) | no — measured equal |
| content / UX | dexterity mini-games, IAP gates, tap controls | yes for dexterity (a bypass), no for the rest |
| presentation | re-rendered sprites, cocos menus, HUD | no — assets, not behaviour |

## 2. Item by item

### 2.1 Level114 — the dog whistle (confidence: high on mechanism, medium on timing)

PC (guide): "wait for the neighbour to get vinyl, use dog whistle, use rusty
nail with record player, use gunpowder with tobacco tin, go back to the
kitchen". The whistle is an inventory item used from the kitchen; the dog
barks; the neighbour leaves the living room to check the dog and comes back.

Mobile: no whistle. The Dog is an `Alerter` in Zone06 that fires only with
Woody in its zone (Alerter.cs:81-84). The call chain it would need exists
already: `Alerter.WakeUp()` → `CoRoutineRottweilerHearAlerter` →
`Rottweiler.HearAlerter(alerter, triggeredByWoody)` → `StartSurpriseActionFar`
(he walks to the dog, Zone06, and returns to the interrupted action). In the
port: `AlerterFSM.wake_up` (world.py:1821) and `Routine.hear_alerter`
(world.py:4279).

Smallest PC-like change:

- overlay: a SearchItem "DogWhistle" (say in the hall's chest of drawers,
  where the PC keeps it) yielding an inventory type IT_Whistle;
- hook: an inventory use with no target ("use the whistle") that calls the
  Dog's `wake_up()` with `triggered_by_woody = False`, whatever zone Woody
  is in — about 40 lines in the port, behind the profile flag;
- nothing else: the graph already allows Zone03 ↔ Zone02, and the primed
  Gramaphone/Pipe accept Woody as soon as he is out (Item.cs:1520 is about
  `Primed`, not about his presence).

Expected result: 9 of 9 and 100 (57 points + 9 × 3 = 84 … with the two
tens 77 + 27 = 104 → capped). Risk: the length of his dog visit (the
SurpriseActionFar walk Zone02→Zone06→Zone02 ≈ 12-15 s in the port's
geometry) must cover the walk from the kitchen door to the Pipe (x −3.16)
and the Gramaphone (x 0.86) and back — the PC video is the reference for
how tight that was on PC.

### 2.2 Level108 — brushing (confidence: high — MEASURED, see docs/PC_LAPS.md)

Measured on the PC video: the neighbour brushes his teeth ONCE at the
start (5-23 s) and never again in the routine; the toothbrush comes back
only as the rinse after the soil coffee. That is exactly the mobile data
(`RemoveFromRoutineAfterFirstUse` on the ToothBrush, the CoffeeMaker's
RushToToilet with the ToothBrush as his ToiletAction). Nothing to change
here; the earlier claim that "PC brushes every lap" was a misread of the
frame sheets (Woody in the bathroom, not the neighbour).

### 2.3 Level211 rod, Level214 wheel — colliders (confidence: high)

PC: both tricks are ordinary clicks. Mobile: the FishingRod's box lies inside
the door's (x −5.27..−4.42, y 1.91..2.25 within −5.86..−4.06, 1.67..2.93)
and the door is nearer the camera, so the raycast — and the port's z-ordered
stand-in for it — answers "door"; the wheel is the same defect in a smaller
form (the App Store review: "only works if you touch its top").

Two ways, choose the overlay:

- overlay: shrink the door's collider (or lift the rod's z) in
  `levels/pc/Level211.overlay.json` — data only, touches one level;
- code: "a TrickItem beats a Door on overlap" in the hit-test — one rule for
  every level, but it changes what the parity runtime answers on the
  mobile's own bugs, so it must stay behind the profile.

Expected: 211 → 8 of 8, 90 (+10 with the overflow rule below).

### 2.4 Season 2 rating — "fill the gauge" (confidence: high — measured)

PC: points — read off all thirteen end screens as 1000 a coin, 3000
once for any collapse, 5000 for the trophy and ⌊500000 / seconds played⌋
for the clock (docs/PC_VS_MOBILE.md, "The rating rules"; E10's 8000 +
3000 + 5000 + 1398 = 17398); GameLogic.dll's own sum (fcn.10040226,
docs/PC_ROUTINES.md) is 1000 × (coins + lives left) + 5000 when the
gauge overflowed + 6 000 000 / the level's ticks (12 a second — the
500 000 / seconds) — Badinfos' three untouched lives were the "3000 for
a collapse", the overflow the "5000 trophy" (the HUD statue lights with
the last coin, but the points follow the flag). The gauge may fill more
than once — Badinfos' 100 % run fills it twice in 210 and 214 — and the
5000 is paid once. It decays by leveldata's `time`, 30, every 1/12 s
(0.36 %/s; the mobile's 0.37 rounds it); only the "exactly one" is the
remake's.

Switch: `ticks >= 1`. Effect: Level206's two overflows stop costing the
bonus (100), and the arm-the-earliest-last constraint relaxes to "overflow
at all" — 202/205/208/210 still need the meter to cross once, which their
spread does not give (peaks 68-97), so they stay at 90 unless the overlay
also tightens the arming (it should not: that is the runner, not the game).

### 2.5 Lives (confidence: high — checked on video)

PC "On Vacation" gives three attempts (4PDA, 2017); PC Season 1 has none,
like the mobile. What a catch does on PC, read off a let's play of the
PC game (youtube awWiuFm9llc, 5:03-5:10 and 6:05, the counter x3 → x2 →
x1 found with tools/pcref/lives2.py): the neighbour beats Woody for ~4 s,
Woody reappears in the level's start area with his inventory, the anger
gauge and the tricks stay as they were, the neighbour walks back into his
routine and the clock never stops. The profile's `_respawn` did that
with the entrance location; since 2026-09-25 it is the catch fiber's
(docs/PC_VERIFICATION.md "the catch", "the respawn timer", "lives out"):
the room GameLogic picks (fcn.10005f58: rooms with more than one door
pair, a Woody hideout first, none with the neighbour or the Mother out of
their hideouts, the first by name among equals — the video's beach left
room, not his start in the shop), Woody on the middle of its floor after
the landing's 39 ticks — the PC's fall and landing, from the remaster's
unused W_Landing sheet — then 5 s in which neither catches him while he
is drawn outlined; the third catch ends the level (x3, x2, x1). The
beating is the PC's `fight` a frame a tick (3.75 s for the neighbour,
4.25 s for the Mother), where the remaster slowed the same frames to 8
and 9 a second.

### 2.6 Dexterity mini-games (confidence: high — read in GameLogic.dll 2026-09-23)

The PC has them, one a level on 201-214 (the earlier "PC has none" and the
profile's auto-solve are withdrawn): an objects.xml object flagged `game`
whose Woody action (the hairpin, the reed, the tongs, the air pump, the
brailer, the rasp, the crowbar, the beehive, the shards or a bare `use`)
carries a `time` of 240-360, beside a `failed` action (game_failed and a
behaviour: the neighbour's `run` on eleven levels, Olga's `shout` on 203 —
her shout_chinese, whose own behaviour is his `run` — `run` on 201's
invisible `aux`, none on 212 and 213); the level's
combine.xml combination that takes the object names minigame/<tool>.xml
(the field, the alarm field, the tool as the thumb, a vertical progress
bar) and a `startlevel` / `endlevel` (1..4 on 201, 1..5 on 202-205, 1..6 on
206, 2..6 on 207-210, 2..7 on 211 and 214, 3..7 on 212-213). GameLogic's
DoAction step (fcn.10001b2c) advances the action's elapsed count by the
game's rate instead of 1 and hands the game the progress (elapsed x 100 /
time, fcn.100507dd, latching at 10). The game object (vtable 0x100b1a7c,
constructor fcn.100507f4, fcn.100508a1 once a level tick with the mouse,
from 0x1004482b) measures the thumb — the mouse itself — from the field's
middle in 1/10 px, each axis held in -1000..1000 and the pair to a radius of
1000; over its first three ticks it moves the mouse back onto the middle
with the rate left at 0, after them it rates the distance — 4 under 200, 3
under 400, 2 under 600, 1 under 800, beyond it 0 or, once latched,
-(progress x 4 / 10) in -40..-4 — and pushes the mouse by three sinusoids,
amplitudes 20, 10 and 5 times a factor that grows from startlevel to
endlevel with min(progress, 90) / 90, 0.0648 / -0.1461 / 0.3696 rad a tick,
the y a quarter turn ahead, each phase started at rand(8) quarter turns;
the level tick moves the mouse by the push and shows the alarm field while
the rate is negative. The levels reach the game through the object: the
level parser's setter fcn.100452d7 (0x10048b74) stores the object message's
game and the two levels at +0x10/+0x28/+0x2c, and the use_object step
(fcn.10004353) hands them to fcn.10041735 as doubles, which the constructor
keeps at +0x40/+0x48. The count reaching `time` is the object's action (the
use step's progress == 100 at 0x10004c68), below 0 the `failed` one. Held
in the middle the game lasts 3 + time/4 ticks: 5.25 s (210's brailer), 5.9 s
(201, 205, 206, 209), 7.75 s (the 360s); a player who holds still loses it
(the push walks the thumb out, the latched rate turns negative). The `run`
behaviour (GameLogic's registry fcn.1003ef32 maps the UTF-16 `run` at
0x100b21c4 to 0x1003e278; its step 0x1003dec1, vtable 0x100b0f7c) plays the
alarm sound, runs the actor to the object (the running GoTo fcn.100080e1)
and starts `search` there.

The profile plays it on the PC's field with the PC's rules
(PCMinigameTicks, PCMinigameLevels — tools/pcref/pc_minigames.py;
pcprofile.s2_game_rate / s2_game_push; DexterityState._pc_tick): the thumb
follows the mouse one to one with no remaster drift or margins, the first
three ticks centre it, the push and the alarm field are the PC's, the
drawn thumb is the state message's pair (below); a lost game sends
the neighbour onto the object at a run where the `failed` behaviour
reaches him (the mobile's surprise, Routine.pc_run_next — thirteen level
ticks after the loss, the `failed` job's end and the offer,
DexterityState.pc_offer_tick; "The lost game's run" below) and nobody on
201, 212 and 213 (PCMinigameFailed; 201's toolbox loses like the rest, the
mobile's DexterityCannotLose aside). 214's game is the
hatch's shards round (bottomright/hatch_closed, the phase his first fall
leaves: the mobile Hatch's Dexterity set by HatchFixBehavior). The harness
steers the thumb half the way back a frame and counts the game's length
into its gate (use_time): 212's plate now goes before the whip, its take
straight after the game (v2), and 208's rat during his lap-2 shoe
(tests/plans/pc/s2). The order within a level tick is the PC's
(2026-09-23): the DoAction step is Woody's job — the use_object step
makes it (fcn.10002cd5, the action step's vtable 0x100aa19c, its run
0x100020c0 in slot 2) and pushes it on his list with a first run
(fcn.10049246, [actor+0x18]), which only sets it up (state 0 -> 1) — and
his tick runs it (fcn.100492a8, from the actors' pass fcn.10044234 the level update 0x100442b3 calls at 0x100445f8), while
the game's update (fcn.100508a1) comes later in the same level update, at
0x1004482b; the game itself is made in that job pass (fcn.10041735,
[level+0xc]), so its first update is at the end of its first tick. A
tick so adds the rate the last update left, and the update after it rates
the thumb anew (DexterityState._pc_tick / _pc_update: the first update at
the game's start). A game's length is unchanged by it (a thumb in the
middle: 3 + time/4 ticks) — the rate is the thumb's of one tick earlier;
the fourteen Season 2 runs are byte-identical under it. 203's lost game
plays Olga's shout first since 2026-09-24: her `shout` action is
shout_chinese (69 frames, 5.75 s) then eat_chinese (cn_c2's olga record),
and its own behaviour, his `run`, is posted as its job ends — the port's
Olga plays her Shout clip paced to the 69 frames and goes back to her
EatChinese (PCMinigameFailedClip, DexterityState._pc_failed_clip), his
run offered 71 ticks after her shout begins (its job's 70, the Loader's
time 68 + 2, and the offer's tick); 201's reaches the tutorial's director
("201's tutorial"). The field is GFXEngine.dll's since 2026-09-24 (read that day). Its middle
is Woody's `minigame` hotspot, `<hotspot name="minigame" offset="0/-150"/>`
in generic/objects.xml: the use_object step (fcn.10041735) reads it as the
actor's +0x2c/+0x30 plus the offset (fcn.10049e01) into the game's middle
(the constructor's +0xc/+0x10, from which fcn.100508a1 measures the mouse)
and into the create message (vtable 0x100b1444, slot 79 of the GFX
visitor 0x10042100: the object's name at +4, the minigame file at +8, the
point at +0xc/+0x10); GFXEngine's handler 0x1000aa80 makes the field round
it (fcn.10004b00 -> fcn.10004540 -> fcn.1000fb30: +0x24/+0x28, the
progress bar from createProgressBar), scrolls the camera to put it at
(400, 256), the middle of the 800 x 512 scene, held within the level
(0x1000ab08-0x1000ab7e), and puts the mouse there (0x1000ab81-0x1000abb8).
The draw (fcn.1000fcf0, from the scene's render while it holds one) puts
the field — the alarm field while the message's alarm byte is up — with its
corner at the middle less half its size, the progress bar from that corner,
the icon centred in the field and the thumb at the corner plus the thumb
setter's offset (fcn.1000fa00): (x + 1000) x (field - thumb) / 2000 on
each axis, x and y the pair of the state message (vtable 0x100b1450, slot
78: the game's +4/+8 at 0x10044864-0x1004486f — each axis held, past the
first three ticks the pair to the radius — the progress at +0xc, rate < 0
at +0x11, sent before the push), so the thumb's edge meets the field's at
the radius, a picture at the level tick's rate rather than the mouse; each
texture keeps its own size (fcn.1000ff70 / fcn.10010000 / fcn.10010090 /
fcn.10010120). Badinfos' E04 (759 s, the toy dispenser) shows the middle
at (640, 305) of the 1280 x 720 stretch — (400, 254) PC px — with Woody's
shoes 150-154 px below it, E01 (176 s, the toolbox) the same (400, 254).
The profile carries it (hud._draw_pc_game, World.dexterity_focus,
pcprofile.S2_GAME_HOTSPOT / s2_game_thumb / s2_thumb_corner): the middle
150 level px above Woody's point, the camera held on it, the field, the
alarm field, the icon and the thumb at their textures' sizes in level px
(PX_PER_UNIT, in which the game measures the mouse as well — where the
port's screen fraction of an 800 x 600 screen had stood in), the thumb
from the pair. The textures are the remaster's by name and size: the PC
data copy holds no images, and textures/s2 carries minigame/<tool>.xml's
gui/game names — field, field_alarm, <tool>_cursor, <tool>_white, 211's
hornhautraspel the remaster's rasp — at 138 x 138 and 75 x 57, the
field's disk 86 px wide as on the videos. The progress bar (every
minigame/<tool>.xml: vertical="true", front="gui/ingame/
minigame_progress_front.tga", offset="28/28"), drawn from the field's
corner (fcn.1000fcf0, slot 9 of the game's +4), is the field's disk
inside its ring: the ring of the 138 px field lies at 26-27 and 110-111,
so the front's 82 px are the disk's own; the PC data copy holds no
images and the remaster's full field carries that disk at those px — the
port draws its rows from the bottom up to the progress, 28 px in
(pcprofile.S2_GAME_BAR, Hud._draw_pc_game_bar; the videos fill the disk
from below up to the ring; since 2026-09-25 — the remaster's whole
138 px fill stood in before). The rows are GFXEngine's progress widget's
(vtable 0x100422b8, made by fcn.100103f0 into the game's +4 with its
maximum 100): its draw (slot 9, 0x10010e90) fills the vertical bar from
the bottom by value x height / maximum in unsigned integers
(0x10010f13-0x10010f1e), the port the same since 2026-09-26. Woody plays
the game where the use put him — the object's `woody` hotspot, its
level.xml position plus the offset — which lies off the room's floor line
on thirteen levels: 24 px above it at 204's dispenser (whose `use` hides
him, actoranim `inv`, and draws him in the object's play_toyomat), 84 at
214's hatch, 92 below it at 211's boat, level with it only at 209's coal
(PCMinigameLift, tools/pcref/pc_minigames.py). The middle is 150 px above
that place. The port keeps Woody's point on its walking line or the
remaster's use height and draws him from it by the clip's offset
(204's GetToyMachineDexterity raised 37 px), so the middle is taken from
the walking line plus the lift (2026-09-24, later): the field of 204 shows
150 px above the drawn shoes as on the video, 127 px while it stood on his
point. The moment of his run is the PC's (below, "the lost game's
run").

The lost game's run (read 2026-09-24, corrected 2026-09-25). The game's
DoActions job ends on the tick after its count drops below 0 (fcn.10001b2c
returns done at once, the job's state 2 a tick later); the use_object step
behind it (fcn.10004526) then reads the game's result (fcn.100507f0 not
100) and pushes the object's `failed` job in front of itself
(fcn.10002cd5 and fcn.10049216, whose insert is the queue's front,
0x100082fe; 0x10004d51-0x10004d69), returning 0, so the job's first
update is on the tick after. The job posts the action's behaviour as it
ends (state 2, fcn.1004000a at 0x10002708): Woody's game_failed is 9
frames, the Loader's time 8 (time="auto": the longer of the actor's and
the object's oneshot animation less one — 205's duck cage `ms`, a
179-frame loop, counts for nothing), the job's end 10 ticks after its
first update (PCMinigameFailedTicks, tools/pcref/pc_minigames.py). The
level update's walker (fcn.1003fc90 at 0x100445f1, before the actors'
pass at 0x100445f8) makes the behaviour by name on the next tick
(fcn.1003e769 over the registry) and offers it to the actor
(fcn.1004b27f -> fcn.1004abcf), again every tick until it is taken — the
offer thirteen ticks after the loss. His jobs vote front to back through
slot 5 — 1 passes (the walk and action steps, 0x10034d8e), 0 takes it (a
runner under them: the classes with the never-finishing update
0x10013f16 / 0x1002f45d vote 0x10013f1b) — and a passing job whose +4
byte is 0 refuses the offer. A taker aborts the jobs in front of it
through their slot 3 and hands the behaviour over (slot 4, which runs its
update: `run` pushes the running GoTo). The level scripts make the
neighbour's walks with +4 = 1 (fcn.1000e3e0 -> fcn.10007a10 -> the GoTo
job, vtable 0x100ab3d8, whose base constructor stores the flag at
0x10007350) and his actions with 0 (the builder fcn.1000efcd pushes 0,
and 229 of fcn.10002cd5's 287 call sites push two zeros, 203 of them a
zeroed ebx; the use_object job, whose base constructor sets 1 at
0x100042a1, is Woody's use); the co-actor's `fight` is made with 0 as
well (fcn.1000eb19). So the run cuts a walk on the offer and waits out an
action, taken as his next walk begins. The profile carries the ticks
(DexterityState.pc_offer_tick): the offer thirteen level ticks after the
loss and every tick after it until he walks, 203's Olga shouting on that
tick (her eat_chinese is her actions' next animation, no job; her
handler's update pushes the shout, whose job starts in that tick's pass)
and his run offered 71 ticks later, 201's `aux` latched on the offer. On
the twelve levels whose lost game sends him (the plans run with
NFH_DEX_LOSE) his run starts about a second after the mobile moment — the
reading of 2026-09-24 had the behaviour posted at the job's start
(fcn.100018a6, which carries a text, "Behaviours are posted as the action
ends") and the offer a tick after the loss.

### 2.7 Routines and timings (confidence: high — MEASURED, docs/PC_LAPS.md)

Measured for all 28 episodes from the PC videos' HUD bubble: the ORDER of
the neighbour's activities is the PC's in every episode. The periods were
first compared against the port's plan runs, which read "mobile slower by
20-80 % on nine levels" — wrong: those laps carried the tricks' angry
sequences (a 41 s "shotgun aim" in 114 was ElectricShock + AngryHard +
FixMid; the aim itself is 3 s of animation). Measured again on idle runs
(`tools/pcref/laps_natural.py`: the harness with a wait-only plan, nothing
armed) the natural laps are the PC's within ±15 % on 21 of 26 comparable
levels (docs/PC_LAPS.md, "Natural laps"). What differs is not speed but
single scripted scenes: 210's deck chair (54 s against 25 — he sits until
the Mother's call, her cycle sets it), 101's sofa (+6 s), 108's walks
between the coffee and the deck chair, 205's Olga-mat scene (the PC has no
mat); and 106/111/113/213 run 12-19 % FASTER on mobile. No duration overlay
is warranted; 210's chair is tied to the Mother's cycle that the profile's
100 plan is timed against.

### 2.8 Not worth it

Art, menus, HUD, tap controls (the port is already mouse-driven), IAP gates
(the port has none), Olga/Mother as catchers (the PC NFH2 mum catches too —
"avoid mum or else you will get beaten").

## 3. Shape of a PC profile in the port

- `--profile pc` (the default since 2026-09-09; `--profile mobile` is the
  mobile-parity runtime, untouched).
- `levels/pc/<Level>.overlay.json`: JSON merge patches applied after the
  mobile load — flags (108), collider rects (211/214), added objects (114's
  whistle). Each entry carries a `"source"` string (guide URL / video
  timestamp), the PC analogue of the runtime's `// cs:` citations.
- `Game.rules`: `overflow_bonus = 'exactly_one' | 'at_least_one'`,
  `dexterity = 'minigame' | 'auto'`, `lives = 0 | 3` (the sketch; the
  dexterity became the PC's own game, §2.6).
- The whistle hook is the only new mechanism; it lives in the profile
  branch and is inert in `mobile`.
- `tests/plans/pc/`: the plans that differ (114 with the whistle, 211 with
  the rod, 206 unchanged but expected 100); the summary table gains a
  profile column. The bench stays mobile-only: the emulator cannot validate
  PC claims.

## 4. Validation

1. Plans: the same harness, `--profile pc`; expected: 114 → 9/9 100,
   211 → 8/8 100, 206 → 100, 108 unchanged, everything else identical to
   the mobile profile (a regression that must hold — the profile must not
   move a single mobile number).
2. PC references: for 114 and 211 the Badinfos / Steam-guide videos give the
   sequence; if frame timing matters (the whistle window), the storyboard
   frames are too coarse (10 s) — a full download needs YouTube cookies
   from a logged-in browser (this machine's IP is bot-checked without them).
3. If the PC data ever arrives: diff its routines against
   `levels/*.json` ActionManager lists and turn §2.7 into overlays too.

## 5. Order of work

| item | gains | effort | risk to parity | needs PC data |
|---|---|---|---|---|
| S2 overflow rule `>= 1` | 206 → 100 | trivial | none (switch) | no |
| 211 / 214 collider overlays | 211 → 100 | small | none (profile data) | no |
| 114 whistle | 114 → 100 | small-medium (one hook) | low (profile-only code) | timing only |
| dexterity auto | fidelity | trivial | none | no |
| 108 brushing flag | fidelity | trivial | none | no |
| lives | fidelity | medium | low | video |
| PC laps | none — measured equal without tricks (§2.7) | done | — | had |

With the first three, every level the mobile machinery blocks reaches 100
under the profile; the levels that then sat at 90 (202/205/208/210) were
the runner's arming pace against the neighbour's lap — the same problem as
on PC, not a fidelity question — and each yielded to an arming order (§7).

## 6. PC references on disk

`~/nfh-bench/pcref/` (outside /tmp, survives the nightly reboot; index in
its README.txt): Badinfos' two full 100 % runs (PC episodes 1-14 and
On Vacation 1-14, 360p) and TheMusician05's episodes 1-6 / 7-10 (the
latter 720p). Fetched with `yt-dlp -4`: pcnew's IPv6 route exits through
BlueVPS (Madrid) and gets YouTube's bot check, the IPv4 route does not —
no cookies needed.

Reading them: `ffmpeg -ss <s> -t 60 -i x.mp4 -vf "fps=1/2,scale=384:-1,
tile=5x6" -frames:v 1 t.png` gives a minute per sheet; the PC HUD clock
(top right, counting down from the episode's 7:00) is the time base, and
the episode title card marks the start (A Sunny Morning: 5:08 into
pc_ep7-10_tm05.mp4).

The frame-sheet reading of A Sunny Morning that first stood here
("a bathroom visit every lap") was wrong — it counted Woody. The
measurement that holds is the HUD bubble method of `tools/pcref/` and
its results in `docs/PC_LAPS.md`: 108's PC lap is 95-97 s, the mobile's
95, the order identical, the toothbrush once at the start on both.

## 7. Implemented (2026-09-06): `NFH_PROFILE=pc`, the default since 2026-09-09

- Switch: the profile is the default — `runtime/pcprofile.is_pc()` is true
  unless `NFH_PROFILE=mobile`; `python3 runtime/app.py --profile=mobile …`
  for the game and `tests/run_tricks.py … --profile=mobile` for the harness
  select the mobile-parity runtime (both set `NFH_PROFILE`; pcprofile reads
  it live). Every mobile-profile number in `tools/livediff/README.md` is
  unchanged under it (the full 54-plan regression, `--all --profile=mobile`).
- Overlays: `levels/pc/<Level>.overlay.json`, applied to the raw objects
  after the mobile load (`scene.Level.__init__`), each with a `source`.
  Ops: `set` fields, `append` list fields, `anim`/`anim_set` on a
  controller's animation, `actions` to rebuild an ActionManager's list by
  item names (addressed by `owner`). Shipped: Level113 (the electric trap
  lifted to the depth it has in L111/L114, so the click ray reaches it),
  Level114 (the dog whistle in the hall's chest of drawers; since
  2026-09-17 the pipe's tin without the remaster's priming and the
  phonograph unlocked for good by the neighbour's first `open`, as
  level_hunter's objects.xml has them — the catch-on-sight rule leaves no
  window for a trick that needs him in the room), and every
  Season 2 level's PC trick amounts off the gauge of Badinfos' run
  (`tools/pcref/amounts.py`: the jump per second labelled with the bubble's
  activity, scaled to the full bar; a jump on the full bar keeps the
  mobile value where that is higher, a shared jump is split in the mobile
  proportions, an unmeasured coin keeps the mobile value). The amounts sit
  near the mobile's — the common coin is 25 against the mobile's 20, the
  big ones 38-51 against 30-45 — and all fourteen plans still rate 100
  (205 re-timed: the chef is one 51, not the mobile's chef + eels).
- Rules (`world.py`, all behind `pcprofile.is_pc()`): the PC scores
  themselves (`GameState.calculate_score`): Season 1's viewer rating =
  the tricks' TrickScores + 3 per angry tick (the HUD shows it live
  beside the tick counter), Season 2's COLLAPSE! board = 1000 a coin +
  3000 for a collapse + 5000 for every coin + ⌊500000 / seconds⌋ (the
  score screen lists the rows; the harness prints `PC N pts` and keeps
  `pc_points`/`pc_lines` in rating.json) — measured in §2.4 and
  docs/PC_VS_MOBILE.md; the HUD statue lights with the last coin, not at
  the overflow; the Season 2 HUD shows the PC's clock — the seconds
  played, counting up, in the TimeRect the mobile data carries but its
  DrawTime never uses on NFH2; the Season 2 bonus for ANY overflow, three lives on Season 2
  levels (`_catch` → `_respawn`: the beating plays, Woody reappears at the
  level entrance — since 2026-09-25 in the room of the catch fiber's case 4,
  §2.5 —, the neighbour resumes his routine), no dexterity
  mini-games (`_dexterity_gate` runs WinDexterity's side effects on the
  first click), `World.blow_whistle()` — the targetless inventory use
  that wakes every alerter (the W key in the viewer, the `whistle` plan
  leg; the icon is the PC's own, cropped from the video).
- Verified against the binaries (2026-09-16, `docs/PC_VERIFICATION.md`,
  rule by rule with the addresses): the Season 1 level-end state machine
  (fcn.00436bb0 — success at a rating of 100 or every trick, time's up
  by minquota, a catch with the quota reached still a success), the
  result captions of the game-over dialog (GFXEngine 0x1000e0f9: BRILLIANT!
  from a rating of 90, SUCCESS!, TIME'S UP!, FAILED! — `pcprofile.s1_result`
  under the profile, and the map's perfect episode at 90 — `s1_perfect`;
  the Season 2 board's caption from GUIEngine 0x10001536: FAILURE,
  COLLAPSE! on an overflow, GOOD JOB! with every coin, SUCCESS! —
  `s2_result`),
  the catch's per-tick rule and cutscene, the Season 2 completion check
  (fcn.10041086: every reachable trick, or coins ≥ mincoins on the
  menu's exit), the catch fiber with its respawn 900 px above the middle
  of the room fcn.10005f58 picks (§2.5), and the data (time limits, minquota, reachable/mincoins, trick
  values, angrytime) — the open items are listed there.
- The walk, the doors and the sight (2026-09-17, from the binaries and
  the data — docs/PC_VERIFICATION.md "the walking speed", "door
  transit", "a busy neighbour"): every pawn moves at its PC speed record
  (`pcprofile.walk_speed`: the neighbour, the Mother and Olga 8 px a tick
  along the floor, Woody 17, sneaking 5 — 12 ticks a second at the
  scene's 96 px a unit, whatever the direction of a walk to an item, the
  mobile scene's depth offsets being the remaster's; a door approach —
  the DOOR_CLIMB / DESCEND states, the PC's ~50 px up to a back door —
  at the room's vertical record, 3/6/2, Season 2's stairs at 5/6), the
  pawns' door clips run a frame a tick (`clip_fps`, 12 a
  second), and the neighbour sees Woody in his room whatever he is doing
  except from inside a `neighbor_hideout` (`sees_while_busy`: 109's bed,
  where a walking Woody's noise 1 wakes him and a sneaking one's 0 does
  not; since 2026-09-25 the wake is the pig class's: he leaves the bed —
  BedOut at the `leave`'s 16 ticks (2026-09-26) — skips the alarm clock
  and catches from the room after) — no IgnoreWoodyWhenUse, IsSleeping or blocking-animation windows
  (Season 1; Season 2 keeps the mobile's windows until GameLogic's watch
  mode bits are read). The harness's dodging reads the same paces (`_speed`, `woody_speed`,
  `door_time`, and `_door_climb` — the ~0.65 u climb to a back door, one
  axis a tick: 1.7 s for the neighbour, 0.9 for a walking Woody, 2.6
  sneaking; a catcher is in the far room once the Leave/Enter pair has
  played at once after his climb, the descent happens inside it) and the
  same windows
  (`_asleep_safe`, `_ignoring_safe`); `NFH_PC_RULES=walk,doors,sight`
  keeps a subset for bisecting a plan.
- The door pass (2026-09-17, `pcprofile.door_ticks` / `door_warp_early`,
  docs/PC_VERIFICATION.md "door transit"): the near door's `enter` and the
  far door's `leave`, each `time` ticks long — the neighbour 19 + 19 by a
  side door and 11 + 22 by a back door, Woody 15 + 23 / 18 + 24 / 9 + 25 —
  so the mobile strips play at the rate that lasts those ticks; and the
  door step places the pawn at the far door, zone and all, as the pass
  starts, where the PC's room pointer changes (the mobile warps at the
  clip's end). The two ran one after the other through every door from
  that day's reading of E10 until 2026-09-26, when game.exe's door step
  was read to its ACTION (one step of two entries, started together, the
  longer timing it — docs/PC_VERIFICATION.md "door transit") and E14's
  frames confirmed it: they run together (`pcprofile.doors_concurrent`), a
  walk-up door's too, the pass as long as the far door's `leave`. Season
  2's doors are not `<door>` objects and keep the mobile's pass at a frame
  a tick.
- The stations' durations (2026-09-17, `tools/pcref/pc_durations.py`):
  every Season 1 overlay carries `PCUseSeconds` per routine item — the
  PC station's DoActions at 12 ticks a second, from the lap model's
  tokens of the level class, one value per visit — and the neighbour's
  use plays the mobile clips at the pace that lasts it
  (`RoutineAction._pc_use_seconds`, `AnimPlayer.time_scale`), or holds a
  walk-by stand for it where the remaster only passes (the shout at
  105's window, 112's yoga). 111's machines are split by the case's
  actions (2026-09-23), and since 2026-09-25 every routine item has its
  PC seconds: 104's shaving chain (the basin's two takes, shave,
  grease_hair, two gives) and the pie's second visit (the neighbour's own
  `eat` after the cream), 106's two-lap cycle (the tub's fill, the bath —
  the shower's `enter` — and the towel), 107's drawing, 113's Ladder (the
  climb) and LadderDrill (drill, touch, climb_down), 114's Hat (take and
  takehat; putbackhat and give) and MedalBox (wearmedals), 112's mixer by
  its two actions (mix, drink) — docs/PC_VERIFICATION.md.
- The plans under the door rule (2026-09-17, tests/plans/pc): the catch
  reads the room pointer, door clips included, so a Woody still in his near
  clip is caught by a neighbour who is (or wakes) in that room, and a walk
  THROUGH a room he sits in is a catch — 106's pudding is armed from the
  living room once his lap-3 pour is over (2026-09-22: the PC's own order,
  94); 110's bedroom banana is dropped from the bed hideout while he fights
  the fire (the same day, 97); 111's airer, primed by his own balcony use
  and un-primed by the next, is dropped and its errands split over his
  descents (70). Every other Season 1 level
  is re-timed to runs/idlepc4's laps and won: 101/102/107 100, 103/104/105
  97, 114 94 and, after the chain pass below, 113 96, 108/109/112 94. The 100 on a Season 1 level is the
  score plus 3 per trick that lands while he is still angry
  (World.calculate_score under the profile; the run's rating.json lists
  every payment with its hot/cold mark): a trick's window is the level's
  angrytime plus the 60 ticks of hold (18-28 s) and his own tantrum after
  each trick stretches the lap by ~10 s, so the chains are set by the
  stations' order — 102 chains its six once the television is armed on the
  loo trip; 103, 104 and 105 keep one cold trick by a second or two (the
  kitchen three a lap after the mailbox rush, the dirty microwave 26 s after
  the cream at the eat, the phone answered 23 s after the loo); 114 chains
  six of its eight once the pipe and the gramophone are armed on his first
  basement trip (97 — the cup's tin 52 s after the horn and the pipe 43 s
  after the tin stay cold); 112 spreads ten tricks over a lap of 143 s (94).
  The chain pass of 2026-09-17 (runs/chain1, the pay logs; a window is the
  60-tick hold plus the trick's own angrytime where tricks.xml gives one —
  the marbles 27-29 s, the skates 30, a banana 26-30 — else the level's):
  108 — the pins, the lotion at his re-sit 10 s later (a tick), the banana
  on the bedroom floor as he leaves the balcony 20.0 s after the lotion (the
  level's 20: cold by no margin at all), the plant 23 s after the slip
  inside the banana's 30 (a tick); the coffee's brush rush is 24 s, and a
  banana laid on the rush's hall path slips him 6 s after the coffee but
  its tantrum pushes the brushing 32 s past the slip (runs/chain2), so
  the rush stays cold either way (94).
  109 — the milk's blast at the pig, the banana in the living room 27.7 s
  later (the milk's 25: cold), the chili's chips 14.6 s after the slip (a
  tick), the tabasco brushing 1.3 s after the cactus alarm on his third
  waking (a tick — the tabasco goes in on the third sleep, after the pins'
  jump and his second lie-down); the bed's sleep is 37 s (94). 112 — the
  fish to the yoga book 26.0 s (25: cold); the one marbles set bridges the
  skates to the chest expander (27.6 s inside the skates' 30) and cannot
  also bridge the yoga book to the trampoline (36 s): six ticks (94). 113 —
  the trap, the hall marbles 19.4 s later (the spot between the basement
  door and the kitchen door, `GroundMarbles@Zone01:2`; it pays 7 where the
  kitchen's pays 8), the sink 21.5 s after the slip, the ladder's tongs and
  the fuse at the drill 18.3 s later (three ticks); the hot valve is armed
  before his first basement trip, and the marbles' surprise then drops his
  tricked radiator (ActionManager.cs:614-619, the interrupted action of a
  GotTricked item), so it pays alone a lap later (96). The 108 and 112
  ceilings are a second of his lap each; 109's and 113's are the routine's. Season 2 (the
  mobile predicates): thirteen levels at 100 — 209 with its hot shoe used
  inside his Taj Mahal stay, where the mobile predicate is blind; 202 with
  the PC coins of cn_b1's tricks.xml (the mat 20, the shark 35 on the
  Swimming item, the rake 20 — two overlay patches had missed their
  items) and its four coins in one lap, armed from the ring's far side;
  205 with the tennis armed after his lap-2 tennis so it lands last; 207
  with the awning on his lap-3 bar visit from the beach side. 210 is won
  (v18, 2026-09-17: 8/8, no restart, 90): the pool is the Mother's, who
  sleeps 19 s and looks around 15 s in turn on her own clock — and keeps
  doing so after her last call (v14 met her looking at 310; the idle
  reading of one long sleep from 246 was wrong) — the four rooms are a
  ring (beach - pool - elephant - shop - beach) he takes one after another
  every 90 s, and each paid trick shifts him ~10 s against her clock, so
  the crossings Woody needs go through the pool on her naps: the plan waits
  for them with the harness's `whenanim Mother MotherSleepSingle` (after a
  `MotherLookLoop`, so the nap is a fresh one) instead of his room entries
  (v13's crossing on his shop entry met her looking; v17, with no early
  coin and so no tantrum, met him at the elephant before her nap — the
  crossing at 191 needs the ~10 s his basket and shop tantrums add). The
  overflow does not come: the shop takes one trick at a time (the octopus
  refused on the armed hedgehog), the basket pays 20 at his lap-2 call
  and 30 at his lap-3 call where the PC's E10 lands the 70 at once, and
  the coins fall 35-60 s apart on his tantrum-stretched laps (the gauge
  peaks at 63 in runs/chain2/s2_Level210f), so the level rates 90. The
  overlay's Elephant is 30 (dogattack_bat — in_b2/objects.xml the bat's
  attack is `bar/elefant`'s action, Fifi the actor), not the octopus's 27.
  The PC's own triple is the board's: `pool/divingboard_oil` fires three
  trick records in one `fall_empty` action (fifi_bone, fall_water,
  fall_empty — 20 each in tricks.xml, the drained pool) and two in
  `fall_water`; GameLogic.dll's accounting (fcn.1000140b, the "Season 2
  compound coins" entry below) credits each named record once. The
  profile pays that (the basket's extra 20, PCExtraCoin), and with the PC
  station stays (the entry below) his lap is the
  Mother's call cycle of ~125 s: the plan (v23) lays the pylon and the
  chair while he shops on lap 1, the oil and then the bone on her nap at
  128 while he sits on the beach, so lap 2 piles the chair (20), the
  basket's three (60), the shop's hedgehog (27) and the elephant (30) —
  the overflow at 234, 100; under the PC reactions the lap-1 arming
  alone tops the gauge, so v21's lap-2 crossings of the pool room on her
  naps (his beach stay shrank to 2 s and they met in the shop) are gone
  and the octopus goes in gated once the hedgehog has paid.
- Harness: `whistle`, `whenusing <Item>` and `whenzone <Zone>` legs (the
  neighbour's lap landmarks a plan can wait for); `unlock` on a dexterity
  search takes the item outright under the profile.
- Plans: `tests/plans/pc/` holds the ones that differ — since 2026-09-17
  the Season 1 plans re-timed to the PC paces and the catch on sight (102,
  105, 106, 107, 108, 109, 110, 113, 114, from the idle runs under the
  profile: `runs/idlepc`) and the Season 2 nine (202, 205, 206, 208, 210,
  211, 214 and the amounts' re-chains); the rest run the standard plans
  under the profile. A plan's `whenzone` fires on any visit of the zone,
  so a landmark names the wanted moment (`whenusing <station>`).

### Results under the profile (the final run, 2026-09-06)

The 2026-09-17 state, under the PC walk, doors and catch rules and the
re-timed plans: Season 1 — 101, 104, 105, 107 at 100; 102, 103, 109, 111
at 97; 112 and 114 at 94; 113 at 91; 106 at 80, 108 at 81, 110 at 78
(won, a trick or the anger chain short). Season 2 — 201, 203, 204,
206, 208, 211, 212, 213, 214 at 100; 202, 205 at 90 (all coins, no
overflow); 207, 209 at 64 (a trick each behind a window the PC rules
close); 210 lost. The section below is the 2026-09-06 run.

Every level pays every trick. Under the PC's own scores (the COLLAPSE!
board on Season 2, the viewer rating's 3 a tick on Season 1 — §2.4,
docs/PC_VS_MOBILE.md) all twenty-eight levels rated 100 under the
mobile's tick meter. Since the anger rule moved to game.exe's
(2026-09-16: the 12 Hz tick, the 60-tick hold, the window 5 s + the
trick's angrytime over 12, no pause for the tantrum) the same plans
rated 100 on Season 2 and on 101 and 104, and 91-97 on the other twelve
Season 1 levels — their chains leaned on the mobile's 23.6 s plus the
angry latch (a gap of 24-33 s still paid). Re-chained to the PC's
windows (the same day): 102 (the beer first, the microwave on his next
beer run, the TV after the sofa), 109 (the banana on the kitchen floor
only once he is down at the pig, so it pays on his second kitchen
round) and 110 (the banana on the bedroom floor after the extinguisher
fetch, on his walk to the chair) are back at 100 — 19 of 28. The rest
sit where one of his walks outlasts the window the trick before it
carries, measured on the run (the fire-to-fire gap against 5 s + the
trick's angrytime over 12): 103 at 97 (the hall to the candle after the
picture, 21.7 s against 20), 105 at 97 (the toilet to the phone, 22.3
against 22), 107 at 97 (the statue to the balcony, 21.8 against 20; the
kitchen banana moved to the living-room floor, where it no longer sends
him out of the kitchen and back), 111 at 97 (the drier to the vacuum,
32.7 against 27.5 — the marbles can bridge that walk or the iron-to-tank
stretch, not both; the PC video pays both with a 26 s drier-to-vacuum),
114 at 97 (the pipe to the trap down the stairs, 29.7 against 25 — the
PC video's neighbour is quicker down), 112 at 94 (three walks of 29-34 s
against 25-29), 106 at 94 in the PC's own order (Badinfos' E06 chain read
off the thermometer, tools/pcref/thermo_jumps.py: microwave > pudding >
picture > the bathroom-door soap > hair > towel > album > sweets > the loo on
the sweets rush, nine tricks and eight bonuses at 15.0, 22.0, 17.5, 15.5,
7.0, 18.0, 12.0 and 8.5 s; the port's plan pays the same nine with two
cold links — microwave to pudding 18.7 s against the PC's 15.0, the port
stretching the tricked pour to the NORMAL station's 8.0 s where the PC's
make_foampudding is 38 frames = 3.17 s, and picture to soap 21.0 against
17.5, the port paying a walk-by after its surprise clip (SlipRight 3.3 s,
FindRight 1.5 s) where game.exe fires the trick before the animation, and
cleaning the picture in the mobile's 3.4 s against the PC's 2.0 —
tools/pcref/pc_tricked_actions.py tabulates the tricked actions), 110 at 97
in the PC's own order too (Badinfos' E10: fire > extinguisher > spray > the
bedroom banana > chair > wine at 14.9, 15.5, 16.6, 24.5 and 18.7 s; the
port's banana lies on the bedroom floor again, dropped from the bed hideout
while he fights the fire, and pays the slip, the chair and the wine hot —
the fire to the extinguisher stays cold at 23.2 s against the PC's 14.9
and the 20 s window: his fetch through the bedroom costs two door passes
of 2.7 s each, and the port pays the extinguisher after its 3.8 s clip
where game.exe fires it first), 108 at 94 (the
toothbrush to the deck chair 31.6 s, the lotion to the plant 33, against
20), 113 at 91 (the raid's long waits; one gap of 24.3 against 24).
Every one of these is a routine-timing difference between the port's
neighbour and the PC's, not a scoring one: the walks are the mobile
data's, the windows game.exe's. On Season 2 the lever
on the levels that sat at 90 was the same every time: arm each coin right after
the neighbour's previous visit to it — the `whenusing` leg — so the whole
set pays on ONE lap, and put the biggest coin (or the walk-by ones, 208's
Fifi + rake) last. Level210 was the last to yield (twenty-two orderings).
Compared with the PC run (Badinfos' E10, the gauge against the bubble):
the PC player paid the shop +26 (170 s), the elephant +35 (191), the
chair +11.5 and the pylon +11.2 (238-239), then the dog basket +23, the
diving board +23 and the drained pool +15 (297-299 — the gauge full), the
second shop coin capped (342). The mobile shop pays one coin per visit as
well (the octopus is accepted only after the urchin's coin). With the PC
amounts (levels/pc/Level210.overlay.json) the plan that works arms
EVERYTHING on his lap 1 and lets his lap 2 pay three coins in a row:
the basket with its board and the drained pool (62 at 162-178 s), the
shop (28 at 214: meter 77), the elephant (37 at 245: 100, the overflow);
the chair with its pylon pays on his lap-3 chair (290, a second
overflow), the octopus coin a lap later (three ticks in all, no
restart). The lap-1 arming is a timetable, not a gate question: Olga's
bra in her first shower while he sleeps in the chair (5-16 s), the melons
and the bowl, the net during his basket (the Mother asleep 66-86), then
Zone01 from 80.5 — `whenzone! Zone02` (his door pass into the shop's
zone, no dodging meanwhile: the runner's flight from the waking Mother
went up to Zone03 in two runs out of three) — for the bat, the oil, the
belt, the valve and the puddle by 97, the board and the basket in the
Mother's second sleep (101-120, he is at the elephant) by 107, down
before he comes up (116), the shop, the second urchin and the elephant
by 126, the chair and pylon once he has left the chair for the Mother's
call (`whenzone Zone04`, 156) by 165. The Mother sleeps 19 s at a time
(66-86, 101-120, 164-184, 199-218, ...), shorter than the gate's escape
margin, so her room is entered by rushes timed to those windows.

| S1 | tricks | rating | S2 | tricks | rating |
|---|---|---|---|---|---|
| 101 | 4/4 | 100 (3 ticks) | 201 | 4/4 | 100 |
| 102 | 6/6 | 100 (7) | 202 | 5/5 | 100 (the mat armed after his lap-2 visit) |
| 103 | 6/6 | 100 (5) | 203 | 5/5 | 100 |
| 104 | 7/7 | 100 (6: E04's chain — the cream's eat, the bathroom four, the picture, the dirty oven on the next lap) | 204 | 6/6 | 100 |
| 105 | 8/8 | 100 (7) | 205 | 5/5 | 100 (the PC amounts: tennis, skis, chef, rockets on one lap) |
| 106 | 9/9 | 100 (8: the whole set on [2]-[8] of one lap, Woody in the hall's wardrobe between the raids) | 206 | 6/6 | 100 (the PC payment order: weights, dynamite, then the pad) |
| 107 | 7/7 | 100 (6: armed behind him, the lap pays all seven) | 207 | 7/7 | 100 |
| 108 | 6/6 | 100 (5: the balcony raid first, the kitchen and the balcony armed behind him) | 208 | 7/7 | 100 (armed in his lap order after each lap-2 visit; Fifi and the rake last) |
| 109 | 7/7 | 100 (5: the PC's scores — the milk 10, the chips 15 — read off the live rating, levels/pc/Level109.overlay.json) | 209 | 7/7 | 100 |
| 110 | 6/6 | 100 (5: the bed hide, the balcony and the bedroom rushed as he sits) | 210 | 8/8 | 100 (the PC amounts; basket triple, shop and elephant on his lap 2) |
| 111 | 8/8 | 100 (5) | 211 | 8/8 | 100 (the rod) |
| 112 | 10/10 | 100 (8, the PC run's eight: the walk-bys send him for the tool and back to the expander and the weights) | 212 | 9/9 | 100 |
| 113 | 8/8 | 100 (4, the electric trap's depth) | 213 | 9/9 | 100 |
| 114 | 9/9 | 100 (7, the PC run's seven: pipe > the trap on his way down > shotgun > the marbles laid while he is down there, on his way up > hat > medals > horn) | 214 | 6/6 | 100 (no wait before the pistol) |

Season 1 under the PC rule is a chaining problem: the tricks' scores
sum to 76-91, so four to eight of a level's payments must land while he
is still hot (23.6 s of decay from the last angry, the angries themselves
not counting). The plans in tests/plans/pc/s1 arm everything for ONE lap,
each item right after his previous visit, timed by `whenusing`/`whenzone`
landmarks and rushes where the gate's escape margin would wait a window
out (108, 110, 106). Where the mobile routine itself stood in the way, the profile copies
the PC's (levels/pc, each overlay with its source): 109 pays the
PC's scores (the milk 10, the chips 15 — the mobile routes the chili's
15 through a CornChips whose score is 0) and needs four ticks, not six.
104's lap had been put in an order read off E04's thermometer (the
microwave after the eat, no second use of the oven after the egg) until
2026-09-26: game.exe's level_pie runs the mobile's order — the pie, the
oven (put_apple_pie, cook, take_apple_pie, after the dirty oven's trick
step as well), the cream and the eat, the basin — and E04's frames pay
the cream's eat first (114.6 s, cold), the bathroom soap, toilet,
aftershave and deodorant, the picture on his walk back and the dirty
oven on that lap's visit last (225.7), which the plan now arms.
One rule of the mobile ActionManager looked like the next obstacle:
after an urgent action it skips the interrupted routine action when that
item's GotTricked is set (ActionManager.cs:614-619 — the marbles'
surprise seemed to cost the expander, the trap's the weights, while the
PC neighbour, on the videos, walks on to both: E12 chains eight of ten).
It is not: GotTricked is the sticky "its trick has fired on him" mark of
Item.Use (Item.cs:836-838), not the armed state, and the expander, the
weights and E14's shotgun are unfired at those walk-bys (the port's
routine log shows got_tricked False at both urgent ends of 112), so the
rule never fires there — the profile ran without it for a while, which
cost Level106 (the pudding, fired at [2], must be skipped at [6] after
the candy's toilet rush or the chain runs past the six minutes), and it
is back on both profiles. The two skips actually seen were port faults,
fixed for both profiles:
the roller-skater scene (Level112's skates) ended without closing its
SurpriseNear urgent, so the next surprise inherited its OriginalAction —
the mixer — and sent him back to it, past the expander (`abandon_urgent`
at the scene's end); and the nailed record player's skip
(ActionManager.cs:200-204, NextActionAfterGramaphoneTricked, two actions
after its fix) moved the index past the player's second use but kept
starting the entry already fetched, so the port played the broken player
and lost the shotgun instead — the original's StartAction(Actions[
ActiveActionIndex]) starts the shotgun, as Badinfos' E14 shows (pipe
301-313 > shotgun 319, no second listen). The mobile runs of 112 and 114
are unchanged (the skates never fire there, the shotgun was never armed).
Level114's chain then reads like the video, frame by frame (220-460 s):
the polish at the cup and the gramophone cold, then pipe > the trap on
his way down > shotgun > the marbles — laid in the hall while he is at
the shotgun — on his way up > hat > medals > horn, seven ticks. The
bedroom door stands beside the Zone02 door (in his sight while he
reads), so the bedroom and the balcony are armed while he is down there
(`whenzone Zone09`: his routine's item reads `Shotgun` from the hall on)
and Woody waits out his slip, hat, medals and horn in the bed. (The
routine's turns are visible with `NFH_ROUTINE_LOG=1`: the ActionManager
prints its urgent starts and ends with the interrupted action, the
surprise stashes and the inactive-item skips to stderr — the runner's
single-plan runs pass it through.) The runner seeds the world's random
draws per level (`NFH_SEED`, default 0; Woody's idle animations, the
catch sequence, the dexterity sway) so a plan's result is repeatable: the
seeded regression of 2026-09-09 rates all 54 mobile plans exactly as the
unseeded reference (33 PERFECT, the same 21 non-perfect ratings, end
times within half a second) and all 28 PC plans at 100 — under the
cs:614-619 skip on both profiles; the profile's earlier exception to it
had rated Level106 at 82 in the same seeded sweep (the pudding [6]
played, the towel [8] past the six minutes). The PC
thermometer (the S1 HUD's bottom-left tube; tools/pcref/thermo.py reads
the mercury column at 10 Hz, 93 px from y 592 to the bulb's neck, a full
tube reading 89 on that scale) is two things at once. Its mercury jumps
to full on every trick (Rottweiler.cs:611 on mobile — no gradual fill),
stays full while the angry plays (7.0-7.5 s on E03/E06-E10, 8.1-8.9 s
on E01/E02/E11-E14 for the plain angries, 11-24 s for the rushes; the
port's plain hard angry holds 10.5 s, its easy one 2.3-3.8 s) and then
drains to empty in a time that is a constant of the level: 7.8 s on
E06, 8.9-9.6 s on E03/E07-E10, 10.1-10.3 s on E04/E05, 11.3-12.2 s on
E02/E11-E14, ~16 s on E01 — 8.3-12.9 %/s, two to three times the mobile
data's 4.23 %/s. The tick counter beside it follows a
different clock, and game.exe says which (docs/PC_ROUTINES.md, "The
anger and the bonus"): a trick sets the rage current to max(current,
its angrytime — the level's when it has none), holds it for 60 ticks
and then counts it down by one per tick at 20 Hz; the mercury is
current × 100 / the level's angrytime clipped at 100, so it pins at full
for 60 + (amount − level) ticks and drains over the level's value —
the drains above are those values over 20 (bath 156 = 7.8 s, laundry
240 = 12 s) — and the bonus of the next trick is paid iff the current
is still above zero, +3 on the rating. The window is 3 s plus the
amount over 20: 10.8 s after a bath trick with no own value, 15 s after
its foam pudding (240), 21 s after the hunter's marbles (360). The
HUD digit read one second before and five after every trick of
Badinfos' fourteen runs agrees with the bracket that reading gives
(ticks for every gap whose decay is 18 s or shorter, never for 25 s or
longer). The tick is 12 Hz, not 20 (docs/PC_ROUTINES.md: the clock
unit, the HUD's division by 12, the raw column), so the hold is 5 s
and the window 5 s + the amount over 12 — 18 s on the bath, 20 s on
the 180 levels, 25 s on the 240 ones, 35 s after the hunter's marbles
— and the drains above are the red-only reader's artifact: the column's
white-hot top is not red, and the tube shows the top ~70 % of the bar
(tools/pcref/thermo_rows.py reads the first non-blue row: the fill
holds 5.4-5.8 s and falls 0.7 × angrytime ticks over the tube, 10.6 s
on E03, 11.7 on E04). The profile carries that rule since 2026-09-16
(pcprofile.s1_rage_fire / s1_rage_tick / s1_rage_percent, run by
Pawn.tick and World.play_angry's PC branch; the data as PCAngryTime in
ticks — the level's on the neighbour, a trick's own on the item): the
meter the HUD draws is the state's percentage and the +3 is paid off the
current, so the mobile's tick meter (4.23 %/s, 23.6 s after any trick)
is the mobile profile's alone — an earlier attempt to put the mercury
rates into AngryMeterDecay under the mobile rule had lost ticks on
thirteen levels, 88-98 %, and 113 outright, which is why the drawing
and the rule had to move together. (An earlier reading of 3.7-4.6
%/s here came from an uncalibrated crop and is withdrawn.) The percentage beside the tick counter is
counted up the PC's way, too: a trick's score arrives as a yellow "+N %"
popup above the figure, a tick's 3 as an orange one; the popup sits for
a second (1.0 s for the score, 1.2 s for the tick, E06 304-318 at five
frames a second), then the figure climbs by the amount over 0.9 s while
the popup shows what is left, and the next popup follows 0.2 s later
(HUD._pc_rating_step). The end-of-level score is the game's own value,
untouched by the drawing.

The angry itself is the last piece of the tick window. The mobile plays
its anger levels (Rottweiler.cs:597-607): AngryEasyUp alone, 2.5 s, on an
empty meter, and AngryEasyDown before AngryHard, 2.5 + 6.7 s, on a full
one — the meter holds full for the sequence plus the fix (10.7 s with
FixMid), so the port's window after a first trick was 4 s + 23.6 and
after a chained one 10.7 s + 23.6. The PC neighbour has one tantrum: on
every angry of Badinfos' runs, first tricks included, the mercury holds
7.0-7.5 s (E03, E06-E10) or 8.1-8.9 s (E01, E02, E11-E14) — AngryHard's
6.7 s plus the item's fix. Under the profile the sequence is AngryHard
alone for both cases (World.play_angry's Classic branch); the tick, the
HUD face level and the audience laugh keep the mobile's rule; the
port's meter now holds 6.7-8.2 s on the plain angries (the S1 set stays
14/14 once 113's hot valve is gated on his sink visit — the 5 s the
longer first angry moved his lap by had put the ungated leg in the hall
with him). (The
HUD arithmetic of the profile — the count-up queue and the drawn drain —
has a window-less test: `python3 -m unittest tests.test_hud_pc` inside
the project's nix-shell.)

Two of the natural laps that sat outside ±15 % of the PC's
(docs/PC_LAPS.md) are activity lengths the data can carry: E01's sofa
spell is 15 s against the mobile's 21, E06's album 19 against 12, both
plain sequences of loop entries in the item's RottweilerUseAnimation —
the overlays give the sofa one SitRemote fewer and one SitLoop more
(12.6 s of sitting, 15 with the walk) and the album eighteen 0.54 s
PhotoAlbumLoop entries instead of five (a 9.7 s read, 19 with the
walk); the idle laps under the profile come to +11 % (101) and −6 %
(106), no activity off by five seconds. The other three were open then
and are the code's since: 111 (−17 %) is a routine of three washer and
three drier visits against the PC's one long visit each (47 s and 26 s)
— one station each in the level class, its DoActions timed (the
laundry's give, wash, get_clothes; give, dry, take — "111's washer and
drier" below); 213 (−17 %) a cement bath whose PC spell is twice the
mobile's two animations — the level script's stay, 9.25 s, the video's
spell holding a wait (tools/pcref/lap_model_s2.py, "Season 2 station
durations"); 210 (+16 %) a deck chair he leaves on the Mother's call —
her cycle and her call's behaviour ("210's call"). None was a loop count.
(Tried
anyway on 2026-09-09: with her nap cut to one MotherSleepSingle his
spell fell only from 54 to 45 s — his ChairAwake runs 27 s after her
call, so the wait is not her nap alone — and both levels' plans, tuned
to the mobile laps, lost; the overlays were withdrawn. The PC original's
own data, `data/gamedata.bnd` — a plain ZIP of the levels' XML,
tools/pcref/gamedata.py — is the way to settle these three and the tick
window alike, once a copy is at hand.) A catch under the profile puts
Woody back at the entrance in one frame (since 2026-09-25 in the room
of the catch fiber, §2.5); the respawn now marks that
frame as a snap for the continuity invariant (`pos_snap`), which had
flagged it as a teleport.

**The PC's own data (2026-09-10).** The user's Steam installs of both
PC games are on the Windows partition; `data/gamedata.bnd` (a ZIP) holds
per level `level.xml`, `objects.xml`, `tricks.xml`, `anims.xml`,
`trigger.xml`, `combine.xml`, `strings.xml` — tools/pcref/gamedata.py
reads it, copies live in ~/nfh-bench/pcref/pc. What it settled:

- *Season 1 scores.* `tricks.xml`'s `quota1` per trick is the mobile
  TrickScore on every level but three: 109 pays the nitro milk 20 and the
  pig 10 (the video reading had them the other way round — the overlay
  now sets Pig 10 and leaves PigMilk), 111 pays the vacuum 13, the airer
  12 and the trap 7 (mobile 15/13/11 — 79 for the eight, so the PC's 100
  takes all seven ticks — see below), 112 pays the skates 8 (mobile
  14 — 76 for the ten, eight ticks). Every episode's
  100 in Badinfos' runs is exactly Σ quota + 3 × ticks (E04 82 + 18, E07
  82 + 18, E11 79 + 21, E12 76 + 24, E14 79 + 21), which is the rule.
  The mobile's extra rated items (103's magnesium cake, the sink/shelf
  pairs of 104, the valve/radiator pairs of 113) are not paid by the
  plans and not counted by the HUD's total, so nothing to zero.
- *The thermometer.* `level.xml`'s `angrytime` (1/12 s ticks: 156 on
  the bath, 280 on the first trick, 240 on the laundry, fitness and
  hunter) is the mercury's full scale and its drain — the fourteen
  values sit on the neighbour as PCAngryTime, in ticks. Some tricks
  carry their own `angrytime` (the foam pudding 240, the dirty towel
  216): per game.exe (docs/PC_ROUTINES.md) that is the amount the rage
  current is set to, the level's value both the amount of a trick
  without one and the mercury's full scale — the foam pudding pins the
  column 60 + 84 ticks (12 s) before the level's 13 s drain. The bonus
  window is 60 + amount ticks at 12 Hz, and the profile runs exactly
  that (pcprofile.s1_rage_*).
- *Season 2 amounts.* `tricks.xml`'s `rage` per trick, in thousandths,
  is the mobile AngerAmount on all but eight items (202: rake 20, shark
  35, the electrified rail 30; 203: the chilli paper 30; 204: the jade
  17; 206: the fleas 30; 208: the snake statue 15; 210: the hedgehog 27,
  the octopus 27) — the amounts read off the gauge on 2026-09-08 were
  read 1.25× the data and are withdrawn — the reader (tools/pcref/
  gauge.py) counts the bar's orange and yellow rows and the bar's top is
  red, so it saturates at ~74 % of the gauge: a jump reads 1/0.74 of its
  size, a trick-free plateau falls 0.42-0.46 %/s for the true 0.36, and a
  "capped" plateau (213's tortilla at 186 s, E10's triple) is a fill in
  the red zone, not the collapse (2026-09-18). The gauge is 100 000 rage
  long, the mobile's AngryMeterMaximum 100: the PC dialog gives the
  `rageometer` a range of 0..100000 (nfh2 dialogs/*/menuleft_bar.xml),
  GameLogic.dll's trick accounting flags 100000 (docs/PC_ROUTINES.md),
  and the bar itself says so on E10 — the shop's 27 000 reads +26, and
  the basket triple's 30 + 20 + 20 on top of 31 pins the bar for 21 s
  before it falls again, which is 101 capped at 100 and 8 % of decay
  spent invisibly (tools/pcref/gauge.py at 160 s for 190 s). The decay
  is continuous and the mobile's 0.37 %/s within the reader's noise
  (0.40-0.43 %/s on every trick-free plateau: 26 → 18 over 20 s, 52 →
  33 over 46, 55 → 31 over 58 on E10; 41 → 11 over 70 on E01), and
  GameLogic.dll's level tick says exactly what it is: leveldata.xml's
  `time` (30 on every level) off the rage every 1/12 s — 0.36 %/s,
  carried as PCRageDecay (docs/PC_ROUTINES.md). A profile of
  80 (2026-09-09 to 2026-09-16) was that video reading taken for the
  bar; withdrawn with this. (The Season 2 neighbour's GameObject is
  `Rottweiler2`; the first overlay addressed `Rottweiler` and matched
  nothing, silently — `pcprofile.apply_overlay` now reports every patch
  that touches no component.) With the data's amounts and the 100 gauge
  the Season 2 set is 12/14 at COLLAPSE!: 204 re-chained (the karate's
  bricks and the gong's sunshade laid after his lap-2 visits, so both
  pay on lap 3 on top of the kart — 30 on 72 at the gong, 101.7); 205
  and 210 pay every coin but never overflow (90): 205's chain peaks at
  96 (the sculpture's 20 on 76) and the table's egg cannot move last —
  Olga sits on the rockets until it fires; 210's basket toggles its
  prime at his every visit (RottweilerUseTogglesPrime), so the bone goes
  in before his lap-2 basket only and the 70-point triple lands first
  (peak 97 at the chair), while the PC's E10 lands it last on a bar
  still at 31.
  Under the 80 gauge the Season 2 set had been 14/14, the Season 1 set 14/14 — 111 on its PC plan
  (below).
- *Season 2 compound coins.* GameLogic.dll pays coins per `<trick
  name=...>` record of the action that plays (fcn.1000140b, from the
  action-play code at 0x1000254d / 0x100025bf): each record is looked up
  in the level's tricks.xml table by name (fcn.10052345), its use count at
  +0x10 is raised (fcn.100522e6, capped at 3), and coins and rage are added
  only on the first use — so a record credited by several actions pays
  once, and an action listing three records pays three coins at one
  moment. The mobile's ladder (Rottweiler.cs:613-693) pays its compounds
  as one item plus hard-coded extras (+20, +15, +10) and linked items;
  the profile keeps the ladder's events and takes the amounts from the PC
  records (tools/pcref/coins.py lays the mobile items next to the PC
  combinations, variant objects and their records): 210's basket extra 20
  (fall_empty), 213's Tortilla 15 + 20 (tortilla_sharp, tortilla_tequila)
  and PlantCarnivore 15 + 20 (carnivore_big, carnivore_bigmanip), 211's
  OlgaChild 20 (phone_loud, with phone_normal 10), 206's pad 30 + harpoon
  20 + one extra of 30 (rubberrabbit, harpoon_rubber, harpoon_fifi — the
  mobile's 30 + 20 + 20 + 15 were 85 for the PC's 80). Every other linked
  pair already matched the PC's records (201's puddle 40 + rail 50 = auweh
  + owe, 204's jade 17 + vase 25, 208's platform 20 + seesaw 30, 209's
  coal 20 + trough 20 and shoe 20 + drain 20, 212's whip 20 + spikes 20,
  hands 10 + 10, ledge 15 + boat 15, 214's hatch 40 + 40). The record's
  `time` is the tick into the action at which the coin lands (the boat 21,
  the jacket 25, the gear 10, the rod 15, the phone 26 and 31, the fall's
  bone 2 / water 20 / empty 25, the tortilla 20 and 30, the pinata 11 …),
  — a frame of the record's own action, not a credit tick: the PC's bar
  jumps 4-12 s BEFORE the neighbour leaves a tricked station, at the
  reaction's start (tools/pcref/amounts.py's jump times against the
  bubble spans of docs/PC_LAPS_DETAIL.md — 213's plant at 22 s of its 26,
  the tortilla at 6 of 11, the picnic at 21 of 28, the pinata at 18 of
  25; 212's throne at 30 of 38, the whip at 15 of 25), which is where the
  mobile pays too. A carry that credited the coin `time` ticks into the
  use (PCCoinTicks, 2026-09-17) is withdrawn on 2026-09-18: it decayed
  every coin from too early a moment.
- *Season 2 reactions.* After a trick the PC neighbour plays one short
  clip, the level script's SHOUT (GameLogic.dll fcn.1000f977): its last
  parameter picks the action from one of four tables the DLL's static
  initializers fill (0x1007b54b-0x1007b61d) — 0 [shout2_light]
  (0x100df45c), 1 [shout2, shout2] (0x100df434), 2 [shout2_hard] three
  times (0x100df450), 3 [shout2_high] (0x100df41c) — and it always picks
  one of [freakout1, freakout2, freakout3] (0x100df43c) first, which the
  SHOUT element (vtable 0x100ab99c, update 0x1000d751) plays instead once
  the level's status byte +0x28 is set: the trick credit fcn.1000140b sets
  it as the rage reaches 100 000 (0x10001500) and the level tick never
  clears it (0x10044710-0x100447f1), so every shout after the gauge's
  first overflow is a freakout. The actions (generic/objects.xml) play the
  neighbour's animations of their names — shout2_light the shout2 one —
  for their frames (time="auto", which the Loader stores less one), and
  the SHOUT element lasts the action's DoActions job — the time + 2 — and
  its own two updates (2026-09-25): 2.42 s for shout2 and shout2_high,
  7.33 for shout2_hard, 3.33/3.42/5.5 for the freakouts (the frames at 12
  a second before: 2.17, 7.08, 3.08/3.17/5.25) — where the mobile plays
  AngryEasyUp and AngryHard, ~7.6 s, after every trick. The tricked bubble spans agree (213's tortilla is 11
  s for a 4-s stay and a 3.5-s trick action). The profile paces the
  mobile's angry set to the PC clip: the step's own SHOUT level where the
  lap model reads it (PCShout, "the tricked visits" below), else the
  trick record's `laugh` level standing in for it (PCLaugh from
  tools/pcref/coins.py --write-laugh, the level's commonest where the
  pairing does not reach a record) — pcprofile.s2_reaction_seconds,
  World.play_angry, the freakout once Pawn.pc_rage_full. (Read until
  2026-09-24 as a seeded random over mixed tables — 1: shout2 or
  shout2_hard, 2: shout2_hard or shout2, 3: the freakouts; the static
  initializers settle each level to one clip.) This is what the PC's
  overflows rest on: with the same coins, decay and lap the port's 7.6-s
  tantrums spread six coins ~25 s further apart than the PC's reactions,
  a tenth of the gauge in decay — 204, 211 and 213 sat at 90 for it.
- *Season 1 reactions (read 2026-09-22, carried the same day).* game.exe's
  trick step (docs/PC_ROUTINES.md, "The fire's tail" and "The stands")
  pays after the tricked object's OWN action (kit/foambottle's
  make_foampudding 3.17 s, lir/stickybook's read_stickybook 3.92 — where the
  port stretched the mobile's tricked clip to the NORMAL station's stay,
  8.0 and 9.42 s), after the doubletake for a walk-by, or BEFORE its own
  clip at the five-argument sites (the soap slip: the fire, then slip1
  2.58 s; the tub's hair after the 2.83 s shower clip, the dirty towel), then
  plays a shout whose length hangs on the bonus — shout2_extra 7.58 s after
  a bonus trick, 2.0–3.67 s after a cold one (shout2 2.08 at the index-1
  sites; the Loader's times, the frames less one, since 2026-09-25 — 7.67,
  2.08–3.75 and 2.17 before) and none where the step carries flag 2 (the tub's hair, the dirty
  towel and the bath candy at flags 3, 110's fuel beer, the laxative beer,
  the coffee soil, the broken sofa, the cactus clock) — where the port
  played AngryHard, 6.8 s, after every trick; and the repair is the tricked
  object's `repair`/`clean` action (the picture 2.0 s, the microwave and the
  soap 1.9, the loo 3.9, the foam pudding 1.9) where the port played the
  mobile's fix clips (MumPictureClean ×3 3.4 s, FixMid 1.4). The port's cold
  links on 106 and 110 were these numbers: microwave to pudding 18.7 s (the
  PC 15.0 — a 3.75 s shout and a 3.17 s pour against 6.8 and 8.0), picture
  to soap 21.0 (17.5 — the 3.4 s clean and the pay after SlipRight's 3.3 s
  against 2.0 and the pay before slip1), fire to extinguisher 23.2 (14.9 —
  the fuel beer's step carries flags 3, no shout at all, against the port's
  6.8 s AngryHard, plus the two door passes). The profile carries them on
  every Season 1 level: `World.s1_fire` is the step's fire (the bonus test,
  the score, the rage, the face, the shout's choice), called by
  `play_angry` after the tricked stand (an OBJ2 station, a doubletake), by
  the routine's use PCFireAt seconds into it (the five-argument stations,
  the stands with actions after the fire — 0 = on arrival, the dirty
  microwave of 104 before its 16.4 s of cooking) and by the near surprise
  before the fall (PCFireBefore: the slips, the electric trap) — a rush's
  use (108's toothbrush on the coffee rush, an AlarmAction) fires and paces
  the same way; where the step plays nothing at all (a flag-3 step with
  no repair: 112's skates) the angry sequence still ends for the behaviours
  (Rottweiler.cs:448 — the RollerSkater's SHOUT state waits for it), and the
  skates fire as the PC's site does, after the fall out of the window and
  before the way back in (RollerSkaterBehavior's comeback); the mobile's
  tricked clips play at the pace that lasts the PC stand
  (PCUseSecondsTricked: the actions before the fire, the step's own clip,
  the actions after it — less the normal use the mobile redoes after the
  fix at a ReuseAfterFix item), AngryHard at the pace of the PC shout (none at
  flags 2), the fix clips at the pace of the PC repair or clean
  (PCFixSeconds, dropped at 0), the doubletake, the fall and the shock at
  theirs (PCSurpriseSeconds, PCSlipSeconds). Since 2026-09-27 the walks
  inside a reaction as well: a look walk-by's list (the picture's
  fcn.0047d520, the microwave's, the toilet's, 111's board) opens with
  CreateGoToObjXJob (fcn.0047a4a0: a GOTO to the tricked object's hotspot
  x at his own y) before the doubletake, an ACTION step of 16 ticks (the
  frames' 15 before), and the repair helper (fcn.0047ae70) walks to the
  tricked object's `neighbor` hotspot first whenever he does not stand on
  it (isActorAtObject, fcn.0047aa90 — the picture's 435/390 lies 30 px
  above the hall's floor line, so he climbs to clean it and the next walk
  comes down first); the port stands those GOTOs' mover ticks (PCAlignX,
  PCFixPoint; `Pawn.pc1_goto_ticks`) and leaves from the hotspot. The
  stands come out of the
  level classes' case chains simulated with the trick in place
  (tools/pcref/trick_branches.py, the keys through tools/pcref/
  pc_reactions.py, the shout index and flags through tools/pcref/
  fire_sites.py); the pairings and the stands two tricks share (104's basin,
  107's stool on the potter's wheel, 114's hat and medal box) are by hand in
  pc_reactions.py's TABLE. With the carry 106 and 110 rate 100 in the PC's
  own chain order (runs pcreact1: 106's gaps 11.7/19.1/17.2/13.6/6.3/17.2/
  10.8/10.1 s, all hot; 110's 16.5/16.3/17.4/24.0/16.3), and the other
  plans re-timed to the PC stands (runs pcreactS1c and pcfix5): 104, 105,
  108, 109 and 112 rate 100 as well — 105 with the piano opening its chain
  (the phone answered 26 s after the loo under the PC's loo stand, so it
  rings after the kick instead), 108 with the toothbrush firing 1.9 s into
  the coffee rush's use, 109 with the tabasco going in as the PC's 1.6-s
  pins jump lets him lie down again, 112 with the skates firing at the
  fall. 103 and 114 stayed 97 and 113 96 on those plans; re-planned on
  2026-09-23 in Badinfos' own chains (his HUD and thermometer,
  tools/pcref/thermo_jumps.py) they rate 100 — 103 with the microwave's
  egg cold at the head of the candle, the letter box, the picture, the
  soap and the loo; 113 with the sink first, the trap on his rush to the
  main valve, the cut ladder, the fuse at his drill, the pain book, the
  bedroom marbles, the grinder and the hot radiator (Woody leaves the
  study through the living room's side door to the kitchen while he takes
  the fuse); 114 with the polish and the phonograph cold, then the pipe,
  the trap, the shotgun, the hall marbles, the medal box, the hat and the
  horn, the whistle calling him down between the phonograph and the pipe
  — and the mobile profile keeps its own clips and order (the 54-plan
  regression is byte-identical to regmob4).
- *The playing trick (2026-09-23).* A station tricked through its
  DependsOn plays the dependency's trick — its stand, its fire and its pay
  — the item RoutineActionUse.GetTrickedItem hands the angry
  (`World._pc_trick_item`). The carry had fired the host's own score at
  the host's PCFireAt and let the angry pay the dependency after it: 113's
  chair kit paid the mobile's honey 10 and then the pain book's 10 (the
  PC's lir/stoolkit_pain pays once), 109's chili its mobile 15 and then
  the chips' 15 (kit/cookiebox_hot once), 102's sofa its 25 at the beer
  visit under the broken sofa's 7.1-s stand where the laxative beer's is
  3.2 s — 109's 100 stood on the double pay (97 without it) and 113's
  level ended on the pair before the radiator. The chips carry
  cookiebox_hot's keys beside the chili (pc_reactions.py), and with the
  playing trick's stand 104 rates 100 too (the whipped cream's 5.9 s at
  the pie). A fixing tool plays its own case: 111's glued vacuum
  (Level_Laundry's case 22) is the take (PCGrabSeconds 0.33), the stand at
  the carpet with the fire before the explode clip (vacuum_hole 2.92, then
  FIRE5's vacuum_explode 2.58: PCUseSecondsTricked 5.5, PCFireAt 2.92),
  the repair, vacuum2 after it (PCFixUseSeconds 2.92) and the give on the
  way back (PCReturnSeconds) — where the port paid after the mobile's
  VacuumLoop and explosion clips, 12.9 s after his living-room entry
  against the PC's 6.8 (Badinfos' vacuum icon at 215, the fire at 221.8)
  — and the carpet's room trigger runs case 20 first, the neighbour's
  `search` (fcn.00479ba0 at 0x4564ee, 26 ticks: the carpet's SurpriseFar,
  the remaster's Search, at that pace since 2026-09-27 — the earlier
  reading had cases 20-22 at once, the search missed), then case 21's
  vacuum icon and walk and case 22. 109's pig visit is one station: Level_Pig's case 18 fires the
  pigout, catches the pig and returns to case 17, which feeds it (case
  20: shake_bottle, the nitro bottle's fire) — ReuseAfterFix on the Pig
  restarts the station after the catch, and the PigMilk's trick plays in
  the same visit (Badinfos' E09: the pig +10 cold at 192.8, the bottle +20
  hot at 204.0). 111's washer and drier are one station each (give, wash,
  get_clothes; give, dry, take — the two branches of the case, not two
  cycles), the mobile's three phases kept and a tricked use ending the
  station at the case's yield (0x455639; PCStationEndsOnTrick,
  `Routine._end_pc_station`); the 2026-09-16 patch that kept two of the
  three entries read the two branches as two cycles and is withdrawn.
- *Season 2 station durations.* The PC videos' HUD bubble (docs/
  PC_LAPS_DETAIL.md, the first lap of each episode) gives the neighbour's
  stay at each station once the walk to it is taken off (the icon shows
  through the walk where the spans touch; an unlabelled gap before a span
  is walk outside it — tools/pcref/pc_durations_s2.py), and the profile
  plays the mobile use clips at the pace that lasts it (PCUseSeconds, the
  Season 1 mechanism) — first (2026-09-17) on the four episodes whose
  natural laps sat more than 15 % off the PC's: 210 (the deck chair 10.5 s for the mobile's
  50-s sleep, the shop 11.7, the elephant 8.0, the basket put 13.7 — a lap
  of ~90 s for the PC's 102-120), 211 (the boat 17.3, the jacket 10.2, the
  rod 8.2, the gear 7.0, the sweets 0.5), 212 (the throne 2.9 + 7.0, the
  whip 6.7, the cigars 14.0, the bull 19.0, the ledge 5.3 + 9.9) and 213
  (the bull 3.5, the plant 12.8, the tortilla 4.0, the boat 21.5, the
  pinata 12.5, the bull ride 0.9 + 8.2 + 1.1, the cement 28.5 — 135 s for
  the PC's 136), and since 2026-09-18 on every Season 2 episode (the
  canon rule: the PC profile carries the PC's trick logic and timing
  wherever the data gives it), 202-209 and 214 included — with the coin
  ticks of their records (the "compound coins" entry). Three rules of the
  pairing: a PC bubble the port has no station for is skipped (214's
  CaptainWheel — the door's stay was the mobile's until 214's became the
  code's), a port visit the PC
  never makes keeps the mobile length as a leading 0 in the per-visit
  list (209's first shoe: the PC does the Taj before the shoes, so the
  Taj span is the Taj's alone, 10 s, and the shoe span the second
  visit's, 2 s), and a lap that is a two-actor handshake kept the
  mobile pace as a whole until the handshake was read (214: his pistol
  sequence fires mother_sleep, the Mother's sit fires mother_sit and
  releases his WaitWatch at the second pistol — the Level214 behaviour,
  cs:62-65 and 130-147; with the PC stays he reached the pistol after her
  sit and the two waited for each other for good — carried by code since
  2026-09-23, "214's handshake" below). Under the carry 202-209 rate 100 as before
  (209 once the Taj/shoe pairing was the PC's order; a Taj of 3.2 s had
  him turn on Woody at the shoe).
  The overlay writers (tools/pcref/pc_durations_s2.py, coins.py,
  pc_durations_others.py) used to drop a whole patch to replace one key
  in it, so a stay sharing a patch with a coin tick or an amount went
  with it: the committed 212 lacked the whip, cigars and bull stays and
  213 the boat, controls and cement ones until 2026-09-18, when the
  writers became key-precise and the overlays were rebuilt from the
  tools — the numbers above are the files' now. Under the stays, the PC
  reactions and the Mother's stands 212 rates 100 and 213 stays at 90
  with every trick: the PC's own order of coins — Badinfos pays the
  cement at the end of lap 1 and then lap 2 in station order, bull,
  plant, tortilla, picnic, pinata, and the gauge tops at the bull ride —
  needs the picnic armed before his lap-2 picnic, and Olga sits in that
  room from 102 to 200 s; the flowers-and-hand trip into Zone05 (19 s,
  two door climbs) runs half a second past the Mother's 19-s absence
  from Zone03, and the room's hideout is in Zone03 on the mobile. Twelve
  plans were tried on 2026-09-18; 213's pile peaked at 90. The picnic's
  window is before Olga comes back, not after (2026-09-23, v7): the living
  room is empty from his lap-1 picnic to her return (70-104 s — the Mother
  in Zone05, Olga on the bull, he at the pinata and the controls), and her
  own lap-2 picnic only seats her in the boat (OlgaUseTrickedAnimation
  PicnicEnter/PicnicWait; the crash is his use, PawnToAffectWhenTricked
  Olga); with the bull and the cement armed right after the flowers-and-hand
  trip, the plant and the tortilla while the Mother stands in Zone02 and
  he is at the cement (Woody in the statue in between), and the wasp, the
  pinata and the controls once he has left the plant, the pile is
  Badinfos' own: the cement 140.5, the bull 149.5, the plant 163.7/176.3,
  the tortilla 180.7/184.7 (89 %), the picnic 216.0 (92.8), the pinata
  245.2 — the collapse — 100. On 212 the one-lap
  pile was tried seven ways (2026-09-18): the throne room is entered only
  through his whip room, the Mother sits in the cigar room and steps out
  for 12 s every ~45 s — on his lap-2 cigars — and the pair's second ruby
  must follow the plate before one sit, so the six coins cannot all be
  armed between two of his throne sits. What lifts 212 to 100 is the
  Mother's PC stands (the entry below): with her 8.3 s at the statue
  hideout for the mobile's 19.9 the cigar room opens more often, and the
  mobile plan under the profile overflows at 279 s.
  The source is the video, not the code — open, and read as far as it
  goes (2026-09-23): tools/pcref/lap_model_s2.py walks each level script
  of GameLogic.dll along the untricked path and times its sequences from
  the data (a DoAction's `time` or its animation's frames, a hideout's
  enter/leave, the message elements at once). On the seven levels whose
  laps it closes the actions are shorter than the video's stays at most
  stations — 212's bull ride 5.0 s (the `ride` clip, 60 frames) against
  19.0, the cigars 7.25 (`smoke`, 87) against 14.0, the whip 4.9 against
  6.7, 213's cement bath 9.25 against 28.5, its tortilla 1.5 against 4.0,
  211's life boat 8.8 against 17.3 — and the lap's actions sum to 29.6 s
  (211), 38.1 (212) and 42.7 (213) against video laps of 68-117, 113 and
  136 s: the rest is the walks and the waits the model does not time yet
  (212's bench `sleep` event, 209's curtain `inactive`, 213's polls on
  Olga's picnic and bull ride, 208's fakir). Until those are read the
  video's stays stay: the code's actions alone would make every Season 2
  lap shorter than the PC's.
  Read further (2026-09-23, later): the bars are timed — fcn.1000e7f2's
  object counts a level tick at a time up to its pushed ticks (212's
  bench `sleep` 60, 209's curtain 120, 208's platform 60, 202's mat and
  207's and 210's deck chairs 120) after the hideout's `enter`; the
  code's stays against the video's, per mobile item (lap_model_s2.py
  code_stays): 203 Microphone 15.1 / 11.8, ToiletPaper 11.0 / 12.6,
  ToiletFlush 4.9 / 6.1, Watermelon 3.6 / 14.7, Bicycle 8.5 / 12.5; 208
  ArmsBowl 4.9 / 12.0, IndianPlatform 12.1 / 0.5, ShoeMachine 4.25 / 23.2,
  AngryElephant 5.6 / 7.2; 211 Sweets 1.75 / 0.5, FishingRod 6.75 / 8.2,
  LifeBoat 8.8 / 17.3, LifeJacket 6.6 / 10.2, DivingGear 5.7 / 7.0; 212
  PreAztecThrone 3.6 / 2.9, AztecThrone 6.75 / 7.0, Whip 4.9 / 6.7,
  CigarBox 7.25 / 14.0, SleepBench 12.5 / the mobile's, MechanicalBull
  5.0 / 19.0, PreParrotLedge 1.9 / 5.3, ParrotLedge 8.7 / 9.9; 213 LiveBull
  3.5 / 3.5, PlantCarnivore 8.2 / 12.8, Tortilla 1.5 / 4.0, Pinata 6.8 /
  12.5, CementBath 9.25 / 28.5. The video's spans put a station's time on
  its neighbour (208's platform in the shoe machine's span) and hold the
  walk the port's geometry does not have: the PC's walk step
  (fcn.10009215, one axis a tick, the vertical first at mg0 / mg2 3 px)
  runs over the level.xml geometry through door pairs whose points the
  path builder fcn.10009489 lays and which is not read yet. The switch to
  the code's stays waits for that walk: carried alone they would shorten
  every Season 2 lap by about a fifth. — Done 2026-09-23 with the walk
  (the entry below): the profile takes the code's stays on 203, 208, 209,
  211, 212 and 213 (pc_durations_s2.py's CODE; an item the model leaves
  untimed — 209's fire fakir behind its untimed `spit`, 213's picnic
  behind its polls — and the other levels keep the video's), and the
  video's are re-derived against the port's idle laps with the PC walk,
  so the walk they take off is the PC's. Against the code they now agree
  within about a second where both exist: 203 bicycle 8.3 / 8.5, melon
  3.2 / 3.6; 208 elephant 5.7 / 5.6, bowl 4.7 / 4.9; 209 coal 3.8 / 4.1,
  ice cream 9.5 / 9.9, second shoe 2.0 / 1.8, Taj 10.0 / 11.7, cow 13.0 /
  15.4; 211 rod 6.3 / 6.75, boat 8.5 / 8.8, jacket 5.7 / 6.6, gear 6.8 /
  5.7; 212 throne 7.0 / 6.75, whip 5.2 / 4.9; 213 plant 7.3 / 8.2,
  tortilla 1.3 / 1.5, pinata 5.8 / 6.8 — what is left apart is where a
  span holds its neighbour's time (208's platform 0.5 + shoe 10.7 against
  12.1 + 4.25, 212's bull 19.0 holding the bench's 12.5 and its own 5.0)
  or a wait the video's lap carries (213's cement 18.8 / 9.25).
- *Season 2 walks (2026-09-23, read in GameLogic.dll and carried).* The
  GoTo (fcn.1000a711) routes over the rooms with the path finder
  fcn.1000a421 / fcn.1000a12d: a Dijkstra whose hop costs the Manhattan
  distance from the node's point to the near door's `<actor>` hotspot
  (fcn.10049e01) plus the <neighbor> record's `costs` (500 on all 125
  records), the hop into the target room the far door's distance to the
  target as well; a room is entered at the far door's hotspot, the open
  list is kept sorted with a new node before the equal ones
  (fcn.1000a097), and the door between two rooms is the first record that
  names the next (fcn.1004ca13). A door pair is one step (vtable
  0x100ab1b8, 0x10003a19): the walk to the near door's `<actor>_in` in the
  near room (fcn.10003130), then — out of every room (fcn.10049467 and
  fcn.10041ad0 with none) — a movement straight to the far door's
  `<actor>_out` (fcn.100037f8 → fcn.100090bd), or where the near door has
  an `enter` action for the actor (211's cabin, 212's and 213's
  topright/midright, 214's bridge: the mobile's back doors) its `enter`,
  the placement and the far door's `leave` (fcn.10003647, fcn.10003236);
  the far room is set at `<actor>_out` (fcn.10003454) and the step's last
  movement brings the actor down to its floor. A movement steps one axis
  a tick at the gait's records (fcn.10009215: mg0 / mg2 3 px up and down,
  mg1 / mg3 8 px along for the neighbour, the Mother and Olga, Woody 6 /
  17; nothing writes the stair gait 7) through the waypoints of
  fcn.10009177: off the floor line and off the target's x down or up to
  the floor, along it, then straight to the target — so every station
  whose `<actor>` hotspot sits off the floor costs a run each way (213's
  picnic 85 px, 29 ticks), and a stair pass is 285-395 px at 3 px a tick
  (208's bazar to the Taj 132 ticks, 11 s, where the mobile's climb took
  ~3 s). tools/pcref/lap_model_s2.py times the untricked laps with it:
  203 105 s, 208 85.5, 209 104, 211 85, 212 124, 213 123 against the
  video's 84-112, 86, 97, 85, 113, 136. Carried (tools/pcref/
  pc_walks_s2.py; `Pawn._pc_pass_pace`, `_pc_hop_steps`,
  `_pc_departure_step`, `_pc_station_route`): each Transition and back
  door carries its pair's PC pass per pawn (PCPass: the `in` run, the
  straight movement or the two clips, the `out` run, in px of the PC
  scene; the room map is the geometric one the door graph confirms on all
  14 levels), and the port's hop stands the `in` run at the near door,
  walks its complex steps through the transfer at the pace that lasts the
  straight movement (the zone flips there, at `<actor>_out`) and stands
  the `out` run beyond it; a back door's climb, strips and descent last
  the `in` run, the two clips and the `out` run. Each routine station of
  the neighbour, the Mother and Olga carries its PC object's hotspot
  height (PCApproach, 112 by the level scripts' GoTo / DoAction
  targets): the mobile's climb to the item lasts the run up or down, a
  station the mobile scene keeps on the floor stands it out before the
  use, and the walk away takes the run down first (the floor step
  BuildPathToTarget inserts, or a stand) — none between two stations at
  the same PC x. A walk from one station to another takes the PC's
  route (the Dijkstra from hotspot to hotspot, precomputed per pair): the
  mobile's Helpers.GetShortestPath (1 a hop, ties to Mono's qsort) takes
  39 of the 338 legs through the other side of a ring — 210's basket to
  the shop went through the beach (24.7 s) where the PC goes through the
  bar (17.3). (Woody's own runs, the routes of the other walks and the
  detection over a pass: the entries below.)
  2026-09-24: the `out` run had never been stood — `Pawn._next_step` read
  the hand-over (`pc_after_run`) from the step it had already cleared —
  and the floor between the doors and the stations was the mobile scene's
  length at the floor record, the passes capped at that record ("no pace
  beats the gait's floor record"); where the mobile's complex steps dip to
  a corridor and back (208's Zone02 door: 3.8 u for the PC's 230 px, 29
  ticks) the cap made the pass 1.4 s long. All three are the PC's now: the
  hop stands the `out` run; the straight movement lasts its ticks whatever
  the mobile path's length; and a stretch of floor between two points the
  PC data places — the station the walk leaves or goes to (PCApproach
  `x`), a door's `<actor>_in` it walks to or the far door's `<actor>_out`
  it comes from (PCPass `xi` / `xo`) — lasts the PC's |dx| at the gait's
  record over the mobile steps between them (`Pawn._pc_floor_marks`, the
  PC px per stretch; 205's mat to the table is 359 px, 3.75 s, where the
  mobile scene has 2.1 u; 208's elephant to the shoe machine 121 px for
  1.8 u). A station is left from its hotspot, whatever the mobile clip did
  to the pawn's spot (205's table +0.4 u, 212's bench), or from where its
  actions' `<translation>`s leave the actor when a GoTo follows them
  (PCApproach `tx`, lap_model_s2.code_moves: 205's skiing 400 px left of
  the skis, 4.2 s back to put them away; 209's coal walk 190 px on — not
  where the step's parts go on without a GoTo, nor after a `leave`). A
  station is the object its step's GoTo goes to (pc_walks_s2.py
  STATIONS, checked against the lap model's GoTo targets): 212's ledge
  step walks to the parrot and plays the cliff's `enter` and `use`, the
  water's and the water exit's from there, so both mobile ledge stations
  are the parrot's (the same-object snap between them); 209's shoe step
  puts the shoes on the mat and enters the curtain from it, so the Taj
  is the shoe mat's; 204's jade step walks to the jade, not its dummy
  (67 px).
  The idle laps against the model's walks (walk_ticks, the translations
  in) per leg: 203 +0.1..+0.3 s, 205 +0.1..+0.3, 208 +0.1..+0.2, 211
  +0.1..+0.2, 212 +0.1..+0.3 — and three exceptions with their reasons:
  209's shoe mat and curtain are one spot of the mobile scene and 52 px
  with the runs up and down on the PC (3.1 s each way the port does not
  walk; the lap agrees within 0.7 s all the same), 212's whip to the
  cigars +2.5 s where he stood at the door while the Mother passed it
  (the mobile's IsOtherPawnPassing wait — the PC's own claim below),
  213's bull controls' poll on Olga (not modelled).
  The door claim (read the same day): the door-pass step waits in its
  first state while its door carries flag 8 (0x10003c54, fcn.100450dc),
  sets flag 8 on both doors of the pair as it starts (0x1000339d) — the
  walk to the near door's `<actor>_in` comes after — and clears it when
  the far room is set at `<actor>_out` (fcn.10003454 -> 0x100033d4; the
  step's cleanup 0x10004169 too). So a pair is held from the moment an
  actor sets off for it, and the next actor stands where it is — not at
  the door — until it is free; every actor's GoTo, Woody's included.
  Carried (`Pawn._pc_claim_marks`, `_pc_claim_pair`, `_pc_release`;
  `Door.pc_claim`): the first step of the stretch that leads to a door
  with a PC pass claims its pair or stands, the transfer (a back door's
  placement) lets it go, a new path aborts it, and a pair whose holder
  has dropped its path is free; the mobile's IsOtherPawnPassing waits
  (Door.PassingPawnTransitionNFH2, Door.PassingPawn) give way to it on
  the doors with a PC pass. The harness reads the same (the floor
  stretches in its ETAs, a held pair in its gate and its flee). The plans
  of 207 (v8: the pile leads with the board), 209 (v2), 211, 212 (v6)
  and 214 (v3) were re-timed to the walk; all 28 levels rate 100 again,
  Season 1 and the mobile regression byte-identical. The laps:
  203 106.8 s (model 105.2), 205 112.5, 208 86.6 (85.5), 209 107.4
  (106.7), 211 85.2 (85.3), 212 127.2 (123.8), 204 92.5, 207 105.5, 210
  99.7. The translations of the tricked actions are carried since
  2026-09-24 (PCApproach `txt`, lap_model_s2.code_moves_tricked: the
  station's step run again with the tricked variants of its IsVariant
  pairs shown): 207's crayfish splash -154, 214's manipulated pistol +95,
  209's hot coal a placement (its walk_fuel +110 then the coal's enter
  and leave: 0); 201's puddle, a two-way station, takes its slip's
  hotspot per visit (`neighbor` 1020 for the slip, +80; `neighborleft`
  1130 for the left slip, -100 — PCApproach `x` and `tx` per visit,
  pc_walks_s2.VISIT_HOTSPOTS; the tutorial sets the visit by the prime
  the mobile's toggle plays next). A two-way station's tricked
  visit takes its side's tricked move (code_moves_tricked per visit, `txt`
  per visit: 201's soaped puddle [200, -100] where the slips move [80,
  -100]; 2026-09-24). 203's stage crash moves him +30/+10 inside the
  stage, whose `leave` then places him at its hotspot as the untricked
  speech's does: no move to carry. Woody's own: his action's
  translation on the object, the action the inventory the mobile item
  takes (208's chalk_sponge on the elephant's line, -45 px over its first
  tick) — PCApproach `tx` on his side (pc_walks_s2), his next walk leaving
  from there (`Pawn._pc_arrived`, the same departure as the neighbour's);
  the only one the data has (201's soap and 214's swiffer had been read
  across a self-closing object's end).
- *Season 1 walks (2026-09-26, read in game.exe and carried).* The GOTO
  step (vtable 0x4e19e8, update 0x44a7b0) pushes the walk job (vtable
  0x4e53d0, update 0x475c80) with the run-now flag 1 (0x44a970), which
  leaves the object the actor stands at first and then, over the room list
  of the path (fcn.00475b30), for each next room pushes a mover to the
  near door's standing point — the door's entity position plus the door
  type's `neighbor` hotspot (fcn.00445aa0) — and the door step (vtable
  0x4e5370, update 0x474590: the pair claimed by its flag 8, the actor
  placed at the far door's point, and one ACTION step of the near door's
  `enter` and the far door's `leave` started together, the longer timing
  it — fcn.004741e0 over fcn.00478030), and at the end a mover to the
  target's hotspot, each with the run-now flag 1: a leg's first move falls
  in the tick the one before it ends (0x4760ad). A mover (vtable 0x4e59e8,
  update 0x47cb50) moves one axis a tick at the facing's speed record:
  while x is off the target's, y first goes to the room's floor line (the
  room's point, fcn.0044bac0 on the actor's room: its path's y; the up and
  down records, 0x47cbc6-0x47cc9d), then x along it — its first move the
  record's `start` px longer when it leaves the standing animation (the
  mover's +0x14 and the `ms` test, 0x47ccc6-0x47cd27: the neighbour's mg1
  8 + 8 facing right, mg3 8 + 10 facing left, mg0 / mg2 3 up and down with
  none; the runs' mr records 18 / 9) — and once x is the target's, y goes
  to the target's; clamped at the target, the arrival read in the update
  of its last move (0x47cf7f-0x47cfac); the GOTO's next update ends it a
  tick after the last move (0x44aab0) — three ticks with no move, the walk
  job done inside the GOTO's first update and the arrival read on its
  second. A walk between two raised points — two back doors' hotspots 50
  px above the floor, two stations' 30 — so goes down to the floor and up
  again, as the mobile scene's paths do on their own geometry: read on
  2026-09-27, when E13's frames put the living room's leg between its two
  back doors at ~4 s and the hall's at ~7.5 where straight lines gave 1.2
  and 4.3 (the reading of 2026-09-26 had the mover x before y, its
  comparison with the room's floor line missed). tools/pcref/lap_model.py
  times the laps with it (the steady lap, the steps at time + 2, the
  walker's arguments read along its path — the entry "The walker's
  arguments" below — the door pass as one step of its two clips,
  docs/PC_VERIFICATION.md "door transit"): 101 30.8 s (video 32), 102 25.6
  (28), 103 32.8 (42), 104 75.9, 105 48.8 (40), 106 116.8, 107 58.2 (54),
  108 92.9 (94), 109 117.8 (113), 110 55.7 (59), 111 116.2 (122), 112
  151.5 (155), 113 177.5 (191), 114 178.6 (168) — and station by station
  against the videos' bubbles within about a second on the four episodes
  read so (docs/PC_LAPS.md): E08's coffee 25.4 s against 24-25, the deck
  chair 22.1 against 21-22, the plant 22.4 against 22-23; E09's pig key
  5.2 against 5-6, the milk 18.9 against 18-19, the pig 15.1 against
  14-15, the parrot 12.7 against 12-13, the key back 14.0 against 13-14;
  E13's grinder 20.6 against 19-20, main valve 29.6 against 29-30,
  radiator 20.2, basin 20.4, second valve 14.6 against 14-15, fuse box 9.1
  against 8-9, ladder 25.1 against 24-25; E14's cups 19.9 against 19-20,
  polish 19.2 against 18-19, smoke 10.4, gun 25.2 against 24-25, hat 35.0
  against 34-35, horn 12.8 against 12-13. The laps of the videos' table
  carry Woody's doings (tricks, the pets' alarms). Carried for the
  neighbour (tools/pcref/pc_walks_s1.py; `Pawn._pc1_marks`, `_pc1_close`,
  `_pc1_leg`, `_pc1_here`, `_pc1_map`, `_pc1_item_point`, `_pc1_arrived`):
  each zone carries its PC room (PCWalkRoom: the room, its path's x range
  and floor line — the zones mapped onto the rooms geometrically, the
  house at 96 px a unit), each door its pair's two standing points
  (PCWalkDoor: the near door's, the far door's), each station item the
  hotspot its station's GOTO walks to (PCWalkPoint: the last GOTO before
  the paired actions in the lap model's first lap of the station
  tools/pcref/pc_durations.py pairs with the item — a list where the
  visits walk to different objects, 107's camera). A walk of the port is
  cut into the PC's legs at its door steps and its item; each leg lasts
  the mover's ticks between the PC's points (`pcprofile.s1_leg_ticks`; a
  leg after a door a tick less, the last one a tick more, three with no
  move) and its mobile steps — the floor, a back door's climb and the
  descent after it, an item's climb — run at the one pace that lasts it,
  from the PC point the pawn stood at (the station it came to, the door it
  came through) or its place mapped into the room. A walk through the
  front door keeps the mobile's pace: the porch is the PC's `fro`, the
  street's whole path, and anc/fro has no `neighbor` hotspot. The port's
  idle laps (the neighbour alone, runs/idlefloor1, 108 with Woody in the
  wardrobe): 101 30.3 s, 102 25.7, 103 32.3, 104 77.2, 105 48.7, 106
  117.3, 107 56.8, 108 93.2, 109 118.3, 110 54.8, 111 116.5, 112 151.7,
  113 178.0, 114 179.8 — within 1.4 s of the model on every level. Woody's
  walk is carried the same way since 2026-09-27: his clicks reach the same
  GOTO (the level's command handlers at 0x440088 / 0x44014f / 0x4401fd
  call fcn.004364f0 / fcn.004368d0, which build it through fcn.0044ad10 ->
  fcn.0044abe0, vtable 0x4e19e8; the target they compute is not read
  instruction by instruction), so his legs are the movers at his records
  (mg1 / mg3 17 px a tick with `start` 12, mg0 / mg2 6; sneaking sn1 / sn3
  5 with 2, sn0 / sn2 2 — `pcprofile.S1_START_PX`) between the door types'
  `woody` / `woody_out` hotspots and the `woody` hotspot of the object his
  action takes place at (PCWalkPoint `Woody`, pc_walks_s1.py
  `woody_targets`: the trick combination's base object, the one container
  holding the item's inventory, the hideout), a floor click's point mapped
  into its room, the far door placing him at its exit offset; a sneak
  toggled inside a leg keeps the leg's pace factor, so the rest of it runs
  at the new record over the same geometry. 107's plan was re-timed to it
  (the bed from his lap-1 kitchen through his lap-2 crossing, drawing and
  camera; the upstairs pair of tricks while he is in the kitchen and at
  the statue, the bed again before he comes up): the old plan had rested
  on an alarm of the living room's pet that Woody's slower crossing set
  off and his faster one does not.
- *Season 2 routes and Woody's runs (2026-09-23, carried).* Every GoTo
  routes with the path finder (fcn.1000a711 -> fcn.1000a421), not only the
  walks between two stations: `world.pc_route` runs the Dijkstra at the
  port's walk — from the station the pawn stands at (its hotspot) or its x
  on the room's floor line, to the last step's hotspot or x — over each
  zone's PC room (PCRoom: the floor line, the <neighbor> records in
  level.xml's order with the doors' `<actor>` hotspots per pawn and the
  `costs`); on the 338 station pairs it gives the precomputed routes
  exactly. Each of the 14 levels' zone graphs has one ring, so a walk to
  the far side of it — a run after a trick, a chase, a fetch of the fixing
  tool, Woody's own clicks — now goes the way the PC's distances pick, not
  the mobile's hop count. Woody's items carry his PC object's `woody`
  hotspot (PCApproach `Woody`, 204 items: a search item by its
  InventoryItems type against the PC container's <content>, a trick item by
  the inventory it takes against the PC action of that name, a hide item
  by the `hideout` object, in the room its zone maps to — tools/pcref/
  pc_walks_s2.py WOODY, seven by hand: 212's parrot nest holds `ruby_2`,
  202's and 207's crayfish share the game object's hotspot, 208's rake and
  Fifi are the primary objects' `use`, 210's octopus is spelled so, 204's
  gong grease stands at the gong; 208's Indian magician and 209's cow have
  no PC object), so his walk to an item stands the run up to it (6 px a
  tick, 8 on average for the hotspots off the floor, to 25 for 213's
  skeleton) and his next walk the run down, as the stations' do.
- *The Season 2 catch (2026-09-23, read in GameLogic.dll and Loader.dll,
  carried).* The catch is data: generic/trigger.xml gives the neighbour
  and the Mother a `fight` behaviour on Woody, `<trigger object="woody"
  position="room" type="always"/>`, and Woody a `die` one on either; Olga
  and the other actors have none. Loader.dll's trigger parser
  (0x1000a869-0x1000a936) makes `position` room / nearobj / house the
  mode bits 1 / 2 / 4 and `type` once / always 0x1000 / 0x2000 of the
  AddObjectTriggerMsg's `flag`; GameLogic.dll files the message
  (fcn.1004fa5c: actor, actionactor, behavior, flag, object) in the watch
  table the level tick walks (fcn.1003fc90), and a firing entry starts
  the behaviour (fcn.1003f086 -> fcn.10005b94: Woody's fear, the fight,
  the respawn). Mode 1 of the predicate fcn.1003f573 is the whole rule:
  both room pointers set and equal — a pass holds none from `<actor>_in`
  to `<actor>_out` — the target placed (flag 0x20) and neither party's
  flag 4; no busy, sleep, sneak or animation term. Flag 4 is the hideout:
  the enter step (vtable 0x100ab2ec) sets it when the entered object
  carries hideout or neighbor_hideout (0x100067d4), the leave step
  clears it once its `leave` has played (0x10006ab7), and nine level
  steps — every other mask-4 call of the flag setter — set or clear it
  themselves: 202's neighbour from his arrival at the sea (0x1002248d)
  and awake on his mat at the beer (0x10022a5b), 206's, 210's and 214's
  Mother asleep and awake in her deck chair (0x1002b77b / 0x1002b9e3,
  0x10018d60 / 0x1001866f, 0x1003a1c5 / 0x10039efa), 209's neighbour from
  the shoe mat on to the curtain's leave (0x10020d0e). The catchers'
  neighbor_hideout stations — the ones the level scripts enter
  (fcn.1000ea30, fcn.1000e7f2, fcn.10006bd4) — are the ones the mobile's
  ProgressBar sleep windows sit on (202's mat, 207's towel, 208's
  platform, 209's Taj, 210's chair, 212's bench, the Mothers' deck chairs,
  pool and dressing rooms) and 202's sea; the mobile's windows are the
  bars' sequence spans and its catch had its own terms (IgnoreWoodyWhenUse,
  the blocking animations, IsSleeping, PassingComplexMove,
  DonePassingToOtherZone). Carried (tools/pcref/pc_catch_s2.py,
  `pcprofile.s2_sight`, `World._pc_s2_sees` / `_pc_flag4_tick`,
  `Pawn.pc_room`): PCHideout on 16 stations, per role the flag's span —
  the whole use, less the clips from a level step's clear on
  (BeachGetBeer, MotherLook / MotherLookLoop) and back from a `set` clip
  (MotherSleep*), 209's shoe mat kept through the Taj's use; Woody hidden
  while hiding and through his hideout's leave clip; a pawn in no room on
  a hop's steps up to the transfer (less the `out` run stood before one)
  and inside a back door's clips; the crossing check reads the same
  predicate. The driver's dodge counts the `in` run into Woody's way out
  (on the mobile he was safe from the step that heads for the stairs:
  212's Mother walked in on him there).
- *The other actors' stands.* The PC level data times an actor's action in
  ticks (`<action actor="mother" … time="120">` in objects.xml, 12 per
  second) or `auto` (its clip: the enter/leave stretches of a stand, a
  second or two — a loop's length is not in the data), so the explicit
  waits are the stands the profile can carry for the Mother, Olga and the
  rest: 212's Mother waits 11.7 s at the red bull and 8.3 s at the statue
  hideout (the mobile's MumWaitZone3/Zone4 stand 13.2 and 19.9 s) — her
  cycle becomes ~33 s and the cigar room opens more often, which is what
  takes 212 to 100 on the mobile plan. PCUseSecondsRole carries them per
  role (tools/pcref/pc_durations_others.py pairs the PC actions with the
  idle runs' stands per level by hand; RoutineAction._pc_use_seconds
  cycles per role and visit). 213's Mother keeps the mobile stands: the
  PC's 12.5 s at the water and 5.0 + 16.7 s at the statue and the flowers
  are within 3 s of the mobile's 15.6 and 18.8 (the port's one Zone05
  stand covers both PC stations), and a paced stand that Woody's trip
  interrupts restarts whole — under the carry her Zone02 visit ran 26 s
  and caught the hand trip. 208/209's dressing room, 207/210/211's pool,
  nap and sea-view loops have no explicit time and keep the mobile clips;
  214's Mother takes her script's (the reling's 80 ticks, her bar in the
  chair — "214's handshake").
- *111 under the PC scores.* Badinfos' E11 chains the eight in one lap
  (the thermometer's jumps, tools/pcref/thermo_jumps.py, and his bubbles:
  the trap on the basement walk-in 155.8, the washer 179.5, the drier
  195.5, the glued vacuum 221.8 — his vacuum icon from 215 — the marbles
  249.4 by the bed on his walk from the board to the balcony, the ironing
  board 278.8 as he passes it on his way to the tank, the fish tank 301.3,
  the airer 322.2 on his arrival at the rack — the order read off the
  frames on 2026-09-26, the earlier reading had the tank and the board
  swapped), every gap 16-29 s, seven ticks: the PC data's 79 points make
  the 100. The drier-to-vacuum link is a run: Woody walks through the
  living room, the dog wakes and barks, and the `noise` alarm — the `?!`
  bubble from 205, 9.5 s after the drier's fire, as its shout and repair
  end — runs him up from the basement into the carpet's room (26.3 s;
  his walk there takes the port 27.6, past the drier's 27.5 s window). The PC rules the port had to take from game.exe
  and the data: the dirty carpet is a room trigger
  (`level_laundry/trigger.xml`: `position="room" type="always"`; the
  mobile's OnChangeZone skips the carpet, Rottweiler.cs:188, and only the
  dog's yell sends him, cs:485-510) that runs Level_Laundry's case 20 —
  his `search` — then cases 21 and 22, and the glued vacuum is that case's tool (the playing trick,
  above); the board burns only between his give and his ironing (case 8's
  give switches in bed/ironingboard_clothes, the one variant Woody's use
  burns, and case 16 irons it, 71 ticks — the mobile's phase; the
  `Primed: true` of 2026-09-11 put the port in the other half of the lap
  and is withdrawn); the washer and the drier are one station each, a
  tricked one ending it; and the stations last the PC's actions (the
  detergent 1.33 s, the give 0.33 and the ironing 5.92, the rack's
  putclothes 1.5 and take 0.33, the feed 1.92, and since the same evening
  the machines' legs — tools/pcref/pc_durations.py). Under the
  room-pointer catch the balcony and the study are reached only through
  the bedroom, so the bed hides Woody: the board goes in while he is on
  the balcony, the airer's bird food while he is at the tank. The plan
  (v17) arms the rest over two laps — the shovel on his first kitchen,
  the paperknife on his second, the machines and the trap while he is
  upstairs, the carpet, the vacuum, the tank and the bedroom marbles on
  his third descent — and plays his third lap: the trap 261.4, the washer
  283.0, the drier 297.7, the vacuum 324.4, the marbles 349.5 (Badinfos'
  are the bedroom's too, 2.4 s after he leaves the board — on the balcony
  they came 30.2 s after the vacuum, its window 30), the board 375.7, the
  tank 397.4, the airer 421.7: 8/8, 79 points, seven ticks, 100.
- *The neighbour's gaits (2026-09-23).* game.exe moves an actor by the
  speed record of his gait (+0x38: mg, sn, mr, mrwc, mgbowling1, skate1,
  piewalk — the facing tables 0x51b5f0 / 0x51b648), and the level classes
  set it before a GoTo — directly or by a step (fcn.0045f6b0) — and back
  to mg at the next case. The Season 1 neighbour runs (mr/mrwc 18 px a
  tick along the floor, 9 up and down, against his walk's 8/3) on every
  `noise` case (the pets' bark, 107-114), the toilet and first-aid rushes
  (102, 103, 105, 106, 108's rinse), the twisted antenna's shout (101,
  102), the extinguisher's fetch and the way back to the burning barbecue
  (110), 113's main valve after the flood and heat valve after the hot
  heater, and 112's way back in after the skate; the skate slides at
  skate1's 18 and the bowling ball goes to the window at mgbowling1's 9.
  The profile had walked every urgent at the floor record; it now runs
  those (`Routine._pc_runs`, the overlays' PCRunTo, `Pawn._pc_gait`,
  `pcprofile.GAIT_PX_PER_TICK`) and shows the walk set on the urgents the
  PC walks (111's vacuum and carpet). 113's valve station after the flood
  and the hot heater is the switch alone (bas/valve_on.switch_off, 0.33 s,
  for the mobile's grab and FixMid), and the lap's own valve and fuse
  visits are the switches and the take (0.33 s each, where the walker's
  false branch had put 2-s surprises): the run and the stations bring
  him to the fuse box ~11 s earlier than the plan of the day before, and
  Woody can no longer put the fuse back between his lap-1 take and his
  drill — the plan (v9) cuts the ladder and puts the fuse on his second
  lap, after the chair, the bedroom marbles and the grinder.
- *Season 2's runs (2026-09-23).* GameLogic.dll keeps the gait at the
  actor's +0x3c (the tables 0x100de870 / 0x100de8dc: mg, mg, mr, mrwc,
  mgbowling1, skiwalk, mg_fifi, stair); a level script sets it to 2 before
  a walk (fcn.1000e3e0), and generic/objects.xml gives the neighbour, the
  Mother and Olga mr1 18 / mr0 9. Carried where the mobile has the same
  moment: 206's pillow errands (six writes 0x1002ea9b-0x1002f0c4 — the
  mobile's Urgent DeckChair / Pillows / DeckChair); the neighbour's runs
  to the Mother's `call` — her callneighbor action (generic/objects.xml,
  behavior="call" on the neighbour), whose handler in his script sets the
  gait to 2 — on 210 from his beach deck chair to hers (the handler
  0x1001b4f6 -> 0x1001911e, the write 0x10019270; the Urgent CallRTMother)
  and on 208 when she finds Fifi gone (0x1001e50f -> 0x1001d828, the write
  0x1001d889: to the rake if it is tricked, where he crashes, else to the
  blades; the Urgent MotherRott the tricked Fifi injects, the rake
  crashing him on the way by NoticeWhenWalkNearby) — every Season 2 Urgent
  runs under the profile (Routine: pc_run); 211's run to the ringing cabin
  phone (0x1002fd04 — the alarm, CabinPhone's PCRunTo) and to the WC after
  the sweets (0x10030e07 — the toilet run); and the co-actors' runs to him
  after his crash, each a gait write before fcn.1000eb19's walk to
  "neighbor" — the mobile's hit-pawn of the trick item's
  PawnToAffectWhenTricked, run where the item carries PCRunTo
  (World.play_angry; pc_reactions.py RUNTO_S2): 201's Olga at the damaged
  buffet (0x1002ad27), 204's at the rickshaw (0x10033486), 205's at the
  table tennis (0x1002637e), 206's Mother to the ramp on the rabbit's crash
  (0x1002bbd1), 207's Olga to the destroyed sand castle to lift him
  (0x10017606), 210's Mother from her deck chair when Fifi falls off the
  elephant the bat tricked (fifi's `fall` is behavior="crash" on the
  mother; her script's handler, vtable 0x100aca38 slot 4, 0x10018e15 ->
  0x10018d76, the write 0x10018dd9 — since 2026-09-23; the mobile's
  Elephant hit on her, which had walked), 214's Olga after the shower and
  the bouquet (0x1003c035, one handler) and its Mother after the pistol
  (0x1003a27f); the stairs keep their records. Their other walks to him
  the PC walks. 201's tutorial is the PC's own since 2026-09-24 (below,
  "201's tutorial": after the combo's crash_long the script puts him at
  the entry, runs him to the shout spot, wheezes and shouts). 205's
  nailed water ski is carried since 2026-09-24: after
  the ride — whose record pays as it ends — the script runs him back to the
  ski (0x10024fde: gait 2), he pants there (`pant`, 34 ticks), shouts and
  repairs it (0x1002512d) before the lap goes on (0x10024929), where the
  mobile plays the anger and the fix at the ride's end and walks back on
  the skates to put them (SkiWalk, 8.5 s from x -5.8 to -3.7 on the 205
  run); under the profile the tricked ride pays at its end and its anger
  and fix wait for the station's next visit, reached at a run, after the
  pant standing (PCTrickReturn, tools/pcref/pc_reactions.py RETURN_S2;
  `Routine._pc_defer_angry`, `_pc_return_use`) — the scene 25 s from the
  ride's start where it had been 29.5.
  A PC mechanic the mobile lacks — the `failed` action of
  every level's game object (§2.6) dispatches the neighbour's `run`
  behaviour (0x1003e278: the alarm sound, a running GoTo fcn.100080e1,
  `search`) — carried: a lost game's surprise onto the object runs
  (Routine.pc_run_next); on 201 the `run` reaches the tutorial's
  director, which relays it to him with the toolbox as the object
  (0x10027407, TutorialPC201.on_behaviour / _nb_run); nobody comes on
  212 and 213. The `fight`
  step (0x1003d8a3: gait 2, the walk to Woody, `fight_woody`) is the
  registry's other generic behaviour. The catch fiber itself (0x100061dc)
  sets no gait.
- *201's tutorial (2026-09-24, carried).* The PC's 201 is not the
  remaster's lesson: GameLogic.dll runs it as two scripts, the invisible
  `aux` actor's director (steps 0x1002818c ... 0x10026640, one a level
  tick until it stores the next) and the neighbour's (0x1002aac8 ...),
  which hand each other the `tutorial` behaviour (fcn.1004000a) and wait
  on it (fcn.10013269). The director opens with the welcome box
  (fcn.1001029b: the level waits for its button), then the messages
  (fcn.100101f3, ship1/strings.xml) and their gates: waypoint1 (bottomleft
  450) and waypoint2 (bottomright 1000) reached — fcn.1000e2bd, the
  actor's y the sign's and |dx| within the dword at 0x100cc814, 50 px;
  each MSG step first waits for Woody to move, fcn.10008874 = his flag
  0x80000, set through a movement (fcn.10009489) — the chest opened
  (soapchest_closed hidden, 0x10027df6), the soap taken (fcn.10049cec),
  waypoint3 (1200) reached: TUTENTRY(neighbor) — his demo lap from the
  bridge (the entry's neighbor_entry, -150): the hat (lookaround 43 +
  use 73 ticks), the buffet's flirt (59), the closed puddle's slip (11,
  +80 px), the rail's look (48), the left slip (11, -100 px, from the
  puddle's neighborleft hotspot) — its step tells the director as it
  starts (0x1002a4ea), the trickable puddle is shown (0x10027ac5) — and to
  the hat to wait. The soap on the puddle, then Woody in the lower deck
  (either bottom room, 0x1002791d) sends him: the soaped puddle's
  crash_short (41, +200 px), SHOUT 1, the rail's look, the wait there;
  the vanity bag opens (0x10027820); the hairpin taken, waypoint4 (430)
  reached, the toolbox marked (0x10027581), the game on (the level's slot
  0x50), the knife (0x10027407) — or the lost game's `run`, relayed with
  the toolbox as the object (the hurry / auweia / wait1 / wait2 / goback
  steps: Woody and the neighbour in bottomleft is the thrashing, Woody in
  topleft escaped, then the neighbour out of bottomleft, then Woody at
  the toolbox again); the buffet cut, Woody down again (0x1002725b): the
  left slip, the hat, the damaged buffet (the flirt sends Olga's
  buffet_crash, his crash 44, her fight; then 0x10029a6c's SHOUT 1 — its
  level the ebx the step sets to 1, `xor ebx, ebx; inc ebx`), the
  repair (19), the wait at the buffet; then the combo (the chest marked
  unless he holds soap, the rail and the puddle marked; combo2 / combo3
  for the half done), combo4 and Woody down (0x10026d08): the crash_long
  by the open rail (75 ticks, `auweh` and `owe`), the entry
  (0x1002968d: fcn.100418f6 at neighbor_entry, the gait 2), the run to
  neighbor_shout (240), the wheeze (30 frames), SHOUT 2 (0x100294fc),
  then danke (the spaghetti pot opens) and the free lap from the puddle
  (0x100291cf -> 0x10029063: the rail still open is repaired, 19 ticks,
  before the look). The neighbour camera (0x1000f51a on, 0x1000ebbf off)
  follows him from each of his latches to its end. Carried under the
  profile (runtime/tutorial.py TutorialPC201, the overlay's PCTutorial,
  tools/pcref/pc_tutorial201.py; the plan tests/plans/pc/s2/Level201.txt):
  the director's steps by address, its texts, markers and signs over the
  remaster's arrow and sign strips, the welcome box; Woody starting at
  level.xml's 300 in bottomleft (the respawn's point until 2026-09-25; the
  PC's is topleft, the virtual hideout's room, §2.5), the neighbour at
  the bridge; the doors open (the remaster's stair locks are its lesson's);
  the chest, the puddle, the vanity bag and the spaghetti pot the mobile
  items locked until the director shows their open twins, the rail and
  the hat open from the start; his script on the mobile routine — the same
  five stations — by phase (`_nb_demo`, `_nb_slip`, `_nb_buffet`,
  `_nb_combo`: the action list set, the waits as the stations'
  FreezeAfterCompletion), the aftermath in Routine._finish's tricked stop
  (`pc_trick_hook`: the credit as the crash ends, the placement, the run,
  a stand for the wheeze — the remaster has no wheeze clip —, the shout);
  the shout after the wheeze (`pc_shout`, World.play_angry: SHOUT 2
  where the lap's puddle step shouts 1; the other shouts are the items'
  own, "the tricked visits" below);
  the free lap's first rail visit plays the repair (FixMid) and the look
  at their ticks with the rail shown open until then; the stays and moves
  of the free lap by code (lap_model_s2 LAP_START 201 = 0x10028f86: the hat
  9.67 s, the flirt 4.92, the look 4.0, the slips 0.92 at +80 / -100 px,
  the left slip from `neighborleft` — PCApproach `x` per visit,
  pc_walks_s2.VISIT_HOTSPOTS), the tricked stands (code_stays_tricked:
  crash_short 3.42, crash_long 6.25 — PCUseSecondsLinked —, the damaged
  buffet 3.67, the sauced hat 8.08). The plan reaches every message and
  rates 100 (4/4, 244.6 s). Against Badinfos' E01 (the level clock):
  the demo's walk from the bridge to the hat 4.2 s from the TUTENTRY
  (the video ~5.5 ± 0.5 s: the camera cut at 0:12, at the hook 0:17.5),
  moveaway's TUTENTRY to the crash_short 10.9 s (video 9-12 s), moveaway2's
  to the buffet crash 25.8 s (video ~25 s), combo4's to the crash_long
  11.3 s (video ~12 s); the crash_short's coin on the video ~0.9 s into
  the crash (4 fps frames 1:23.1 -> 1:24.0), the port's at its end —
  the credit moment is Season 2-wide (below, "the tricked visits").
- *The tricked visits (2026-09-24, carried).* A Season 2 station's
  tricked visit is its step with the trick in the scene — the combine.xml
  combination the mobile item's inventory makes: its object shown, its
  ingredients with remove="true" hidden (201's soap: soappuddle for the
  waterpuddle) — and the step then plays the variant's DoActions, a SHOUT
  (fcn.1000f977 or the builder's fcn.1000fede), often a `repair` and the
  switch back. Four things in it were the mobile's under the profile: the
  tricked use lasted the untricked stay (the whole use paced to
  PCUseSeconds); the reaction clip came from the trick record's `laugh`
  (PCLaugh), where fcn.1000f977's action is picked by the SHOUT's own
  last parameter, the step's constant (0 shout2_light 2.17 s, 1 shout2
  2.17, 2 shout2_hard 7.08, 3 shout2_high 2.17 — "Season 2 reactions"
  above; 204's gong pushes 3) — often a register the step sets: 208's shoe machine pushes
  the zeroed ebx, 201's buffet `xor ebx, ebx; inc ebx`, 212's bull `xor
  edi, edi` and more, 203's toilet 2 with both its paper and its flush
  tricked and 0 with one (`push 2; pop eax` or `xor eax, eax` by the step's
  bytes); the repair was folded into that clip's pace; and the coin came
  as the tricked use ended, where fcn.1000140b credits a record on the
  level tick its `time` equals the action's elapsed count (the cmp at
  0x10001455, from the action step's playing state at 0x1000254d) — 201's
  crash_short pays 5 ticks in (the video: the crash from 1:23.1, the coin
  flying at 1:24.0 on 4 fps frames of E01), not 41. Carried per item from
  the lap model (tools/pcref/lap_model_s2.py code_stays_tricked:
  `tricked_presence`, the station's own parts where two mobile stations
  share a step, TRICKED_STEP / LINKED_STEP for 201's tutorial steps;
  pc_durations_s2.py): PCUseSecondsTricked (the parts up to the SHOUT),
  PCShout, PCFixSeconds (the repair, 0 none), PCCreditAt (the record's
  second into the stand) — Routine._use paces the tricked use and times the
  credit (`pc_credit_timer`, World.pc_s2_credit), World.play_angry plays the
  mobile's angry clips at the SHOUT's pace and then its fix clips at the
  repair's (none where the step has none). The linked trick is the same
  step with both tricks in the scene (mobile_linked: the TrickItem's
  LinkedItemTrick) where that changes its DoActions — 202's damaged rail
  over the eels' pond plays crash, electrify and leave, SHOUT 2, where the
  crash alone plays crash and leave, SHOUT 1 — or another step of the script
  (201's crash_long, LINKED_STEP); its stand, SHOUT and repair
  (PCUseSecondsLinked, PCShoutLinked, PCFixSecondsLinked), the item's own
  record's second (PCCreditAtLinked) and the second the linked trick's own
  record pays (PCLinkedPaysAt: the first record the item-only variant does
  not play) — fcn.1000140b credits each named record at its own `time`,
  so the ladder's linked arm pays apart (`pc_credit2_timer`,
  World.pc_s2_linked_credit; `_s2_credit(part=)`, the arm's amount settled
  by the first part, before the trick's OnTrickDone marks the pair), and
  the pair is done with its last record: the level's done count is its
  trick table's credited records (fcn.1000140b -> fcn.100522e6, the count
  fcn.1005225b against the reachable fcn.10052272), so 202's level ends on
  bridge_electrify after its rage, not on bridge_crash. Linked stand / SHOUT /
  repair / own credit / linked credit, s: 202 bridge rail
  8.75/2/1.58/4.25/6.08 (bridge_crash, bridge_electrify); 204 jade
  6.58/2/1.0/1.0/4.17 (jade, vase); 210 dog basket 7.42/1/-/1.75/3.25
  (fifi_bone, fall_water); 212 parrot ledge 10.67/0/-/-/4.17 (boat, the
  ledge alone has no record). Two script elements the model had taken for
  timed are done on their first update (the element returns 1 at once):
  Ef82b hides an object (vtable 0x100ab984, update 0x1000cf2a) and Efac4
  sets an actor's flag (vtable 0x100ab9a8, update 0x1000d037) — which
  times 205's tricked rockets (3.08 s) and 210's linked dog basket. Stand / SHOUT / repair /
  credit, s: 201 buffet 3.67/1/1.58/0.42, hat 8.08/1/-/4.42, puddle
  3.42/1/-/0.42 (linked 6.25); 202 bridge rail 6.42/1/1.58/4.25; 203
  bicycle 5.33/0/1.58/3.5, flush 5.25/0/1.58/1.5, paper 14.67/0/1.58/10.92,
  watermelon 5.5/1/-/3.0; 204 hot dogs 9.75/1/-/9.0, jade 4.75/0/1.0/1.0,
  karate 3.25/1/1.58/1.17; 205 sand lion 5.92/0/1.58/4.75; 207 towel
  1.17/0/1.58/0.42, sand castle 8.25/0/-/4.25; 208 arms bowl 7.0/0/-/4.33,
  shoe machine 4.08/0/1.58/1.42; 209 cow 9.92/1/1.58/4.92, ice cream
  4.42/0/1.58/2.67; 210 dog basket 5.17 (no SHOUT)/1.75, turban shop
  3.83/0/-/1.92; 211 diving gear 6.83/1/1.58/0.83, rod 3.42/1/-/1.25, life
  jacket 5.33/1/1.58/2.08; 212 throne 6.25/0/2.0/4.0, cigars 6.0/0/-/3.58,
  bull 6.75/1/1.58/3.67, whip 6.25/0/1.58/3.92, parrot ledge 8.67 (no
  SHOUT), bench -/1; 213 cement bath 14.67/1/-/5.83, live bull 4.0 (a look,
  no SHOUT), carnivore 7.75/1/-/4.92, tortilla 4.5/1/-/1.67; 214 hatch
  10.83/0/-/0.83; 205 rockets 3.08/1/-/2.33; the other partial rows (a
  part of unknown length: 204's rickshaw credit 2.0, 207's elephant SHOUT 1
  credit 13.08). The rest carried on 2026-09-24 (later), the flow past the
  station's step read where the step itself has no SHOUT
  (lap_model_s2 TRICKED_CONT, CONT_SCENE, TRICKED_VIA, TRICKED_ROWS):
  the model had also taken three script elements for timed — the camera
  on the neighbour (Ef51a: the builder fcn.1000f51a sets the flag 8 only
  for a nonzero last argument, and with it the update fcn.1000d31a waits
  while the level's slot 0x50 answers [level+0xc] != 0, the mini-game
  object the level update runs at 0x10044816-0x1004482b: Woody's game
  running; else done at once), 207's pose element (E2f40 appending
  fcn.10014c5c's, vtable 0x100ab990, update 0x1000cfaa: the actor's
  animation set, 1 at once) and an object shown (Ef779: vtable 0x100ab978,
  update 0x1000ce9c) — and the tricked run starts from the scene the
  lap's walk has at the row (lap_state: 209's shoe mat holds his shoes as
  he leaves the curtain; the opening scene had sent the model down the
  coal path). Stand / SHOUT / repair / credit, s: 204 gong 5.0/3/1.58/3.17
  — the elvis hits him, the action's behavior `gong` sends his script to
  0x10032f52, whose tricked branch is the leave, SHOUT 3 (the one Season 2
  step that pushes 3), the camera off and the repair; 205 skis
  17.33/1/1.58/6.0 — the run back and the pant (2.83, PCTrickReturn) before
  the SHOUT; 209 hot shoe 2.75/0/-/1.42 (with the drain open 8.83/1/-/1.42,
  gully_open at 2.75); 207 elephant 15.5/1/-/13.08; 211 sweets
  2.08/1/2.0/1.25 — the run to the toilet, wcright's puke (40 ticks, the
  toilets' PCUseSeconds: ToiletWomen 3.33, ToiletMen 3.08; its record
  wcright at 27), SHOUT 1, the sign's repair; 214 wheel 12.5/2/-/4.58, up
  on the bridge from the opened door with the captain drugged; 206 weights
  13.0/1/-/8.33 (the flea blanket: Olga's laugh on the manipulated
  dumbbell) and dynamite 13.83/1/-/8.5 (the adhesive's bag taken, then
  0x1002c550's lookaround and the reling's explode); 210's dog basket
  alone plays no SHOUT anywhere in its flow (PCShout -1: no reaction);
  203's stage is broken by the generator's tights alone in the PC (cn_c2
  combine.xml has no microphone trick; the stage step asks for
  generator_manip, 0x1003450b) — the mobile's DieselGenerator activates
  the Microphone's trick: the stage's crash (enter, the image's crash, the
  stage's `crash` with its record stage at 8, leave) 13.25/1/1.58/6.92
  (lap_model_s2 TRICKED_BY); a SHOUT with no repair after it in a step
  that hands over off the lap takes the repair of the step it hands over
  to (203's generator 0x100343a5, 212's bench 0x10035fdf, 213's washing
  tub 0x1003761c: 1.58 each, 0 before);
  214's captain's door is visited tricked in neither game (the mobile's
  CaptainDoorBehavior swaps his routine's door for its ExtraItem,
  Item.cs:2606-2623; the PC's door step goes on up to the wheel) and its
  40 is paid nowhere. Two flows the walker had read short (later the same
  day): 213's live bull — the limberwall step tests its own byte +0x28
  through the step object reloaded into eax (0x10038ab1; the constructor
  clears it, 0x10038cf4, the charge sets it, 0x10038c18), which the walker
  had left unknown: the first visit with the flowered bull charges him into
  the wall (the horseshoe's and the bull's `inv`, the limberwall's `crash`
  with its record limberwall at 66, the beehive shown, SHOUT 3), 8.58/3/-/
  5.5, the mobile's 20 the record's; 212's parrot ledge — the level's aux
  script (me_c1's `aux`: the factory 0x10034dba registered at 0x1001265b,
  its update 0x10034fec) has the fed parrot eat (parrot_manip's `use`,
  actor aux) and shows its shit on the ledge (fcn.10034e05; the show
  element built at 0x10034f09 by fcn.10014cf7, vtable 0x100ab978) before
  his visit finds it (0x10035577): the crash on it (cliffcrash, the record
  shit at 5), 7.75/0/-/0.42, and with the boat 9.75/2, the boat's record
  at 3.25 (lap_model_s2 AUX_UPDATE; 208's and 210's aux updates leave the
  tricked scenes as they are — 210's drains the pool after the valve's
  tongs, a combination with trick="false" the mobile has no item for).
  206's rabbit on the launch pad (lap_model_s2 TRICKED_ARM): the load step
  0x1002e3df asks IfVariant ramp / ramp_manip — the rabbit on the ramp at
  the load arms the shot, which follows the harpoon's take (0x1002e27f,
  whose IfVariant harpoon / harpoon_manip picks shootrabbit, 81 ticks,
  harpoon_fifi at 49, or with the rubber rubberrabbit, 73: harpoon_fifi
  40, harpoon_rubber 45, rubberrabbit 50); the shot's behavior fifi_crash
  sends the Mother to him and his being_hit step 0x1002de6a waits for her
  fight's latch ([step+0x24], fcn.10013269) before SHOUT 1 and the ramp's
  repair (19 ticks, 0x1002dbc4). The lap's shoot step 0x1002d948 asks
  nothing, so a rabbit put on after the load waits for the next load;
  without it the take step's rubber branch shoots the rubber bear at once
  (0x1002da29: 69 ticks, harpoon_rubber at 40, SHOUT 1) and goes on to the
  put past the shoot step, and the put step switches a manipulated harpoon
  back (0x1002d578: a rubber put on after the take is gone). The mobile
  fires the pad at its first visit after the trick and lets the plain pad
  shoot the tricked harpoon (harpoonAux, TrickItem.cs:896-902). Carried:
  Level206RoutineBehavior's PC arm counts the pad's and the harpoon's
  visits of the lap round (the mobile's LaunchPad, Harpoon, LaunchPad,
  Harpoon, LaunchPad are the rows load, take, shoot, put and Fifi's take)
  and plays the pad's other visits and the harpoon's take under an armed
  pad plain (Item.pc_masked); the pad fires at the shoot after an armed
  load (PCTrickArm [1, 2]: 6.75/1/1.58/4.08, linked 6.08 with the records
  at 3.33, 3.75 and 4.17 — PCExtraPaysAtLinked, the ExtraCoin206 and its
  completion at its own tick — and the Mother's fight, PCHitSeconds 3.25),
  the harpoon's rubber alone at the shoot — the mobile's structure has
  it there: the pad toggles prime three ways (load, shoot, Fifi's take:
  its prime leg, its use, its unprime leg), the harpoon two (take, put),
  and the harpoon's rubber (UseAtOtherPlace) fires through the pad's
  DependsOn at the pad's use, the PC's order (the take, the walk to the
  ramp, the rubber bear, SHOUT 1, the walk back, the put); the PC decides
  it at the take, so the take marks the harpoon's GotTricked (the mobile
  marks it only at the put, a lap late for the DependsOn), a rubber put
  on after the take leaves the shoot the bear's and is dropped at the put
  (PCTrickFire [1, 2]: the rubber bear 5.75/1/-/3.33, the walks the
  port's own between the stations). harpoonAux is off under the profile.
  206's plan awaits the count 6.
  The co-actor's hit: 204's rickshaw 3.67/0, 207's shell 4.67/0, 214's
  shower 4.0/1, bouquet 4.17/1 and pistol 18.33/0 (the shot and the
  Mother's `die`), 210's elephant 9.08/1 — his action's behavior (204's
  hurt_neighbor on Olga …) is posted as its job ends and her script runs
  her to him (gait 2) and plays the generic `fight` (fcn.1000eb19: Olga 42 ticks,
  the Mother 39; the action's behavior olga_fight / mother_fight on him),
  his behaviour handler then sets the step with the SHOUT and no repair
  (204 0x10032b6f, 207 0x1001596a, 210 0x1001a379, 214 0x1003ba90 /
  0x1003b677 / 0x1003b328). When his SHOUT comes, read on 2026-09-24
  (late) and corrected on 2026-09-25: DoAction (fcn.10002cd5) builds a job
  (vtable 0x100aa19c) with its participants and the caller queues it on
  the acting actor alone (fcn.10049216); an actor's queue (fcn.100492a8)
  runs its head job each tick and asks nothing of any other actor (only
  its own flag 0x100000, the camera's freeze); the job (update
  0x100020c0) sets its participants' animations in its states 0 and 2
  only (0x10002301-0x100024e9: the object's `inv` once at the start, `ms2`
  at the end), ends by its ticks (+0x28 up to +0x24, fcn.100011f2) and
  posts its behavior as it ends — state 2, fcn.1004000a at 0x10002708
  with the action record's +0x1c / +0x20, the behavior and its actor (the
  start's message, fcn.100018a6, carries the job's +0x14 / +0x18, a text
  the GFX shows: "string" / "alreadyininv" of fcn.10002d71's callers;
  "Behaviours are posted as the action ends" below). So he waits in his
  fear pose through his action's end and her walk, is `inv` through her
  fight (its object is he), shows `ms2` as it ends, and its olga_fight /
  mother_fight sets his step's latch on the tick after: his SHOUT follows
  her fight — the mobile's order (RoutineActionHitPawn: the target hidden,
  its parked angry resumed at the hit's end). Carried since 2026-09-25
  (Routine._hit_begin / _hit_pawn_done, play_angry's affect, the mobile's
  flow): she sets off as his tricked use ends, her hit hides him and lasts
  the fight's ticks (PCHitSeconds), his angry resumes at its end; the
  early set-off of 2026-09-24 (World.pc_affect_early) and its two kept
  hand-offs (214's StopOlgaInfiniteLoop sent to her next pose, 207's
  linked lift) are gone with the reading. 207's sand castle with the hedgehog on the
  towel: its linked step (lookaround, the hedgehog's splash 45, the
  castle's fall 22 — its behavior kid_cry on Olga) hands over to
  0x1001513f, which re-runs until the destroyed castle shows Olga's
  `n_lift` (fcn.1004948f, the object's animation, against the global
  n_lift; her script runs her there, 0x100175f0) and then plays his
  billboard (`bill`'s enter, 56 ticks, the record bill at 30), SHOUT 2
  and the camera off (LINKED_CONT): PCUseSecondsLinked 9.17,
  PCCreditAtLinked 4.25 (splash_crayfish), PCLinkedPaysAt 7.33
  (mat_hedgehog), PCHitSecondsLinked {Olga: 2.5} (the lift),
  PCResumeHeadSeconds 2.17 (the billboard from the lift's start: the poll
  sees her `n_lift` as it begins) and
  PCExtraCoinLinked 30 (bill, paid and done at his resume: the level's
  done count is its records, so the level ends there — 207's plan awaits
  the count 7), PCShoutLinked 2; the castle's own amount is the PC's 20
  (the mobile's 40 was its linked total's share). 211's sweets with the
  sign swapped (lap_model_s2 TRICKED_RUSH): the puke at the women's wc
  carries the wcright record at 27 of its 40 ticks and the behavior
  `puke` on Olga, whose handler (0x100318ce) queues her wc `mad` (34
  ticks) and makes her fight step 0x1003183a her next (the generic
  `fight`, 42); its olga_fight sets his step's latch +0xd (0x100301fb),
  on which 0x10030d0f plays SHOUT 1, then the sign's repair (the walk to
  it, 34 ticks, and its `repair`, 24). The mobile loses the after-toilet
  angry — StopUrgentAction reads the interrupted action's item
  (ActionManager.cs:597), the fishing rod by then — and pays the extra
  with the sweets' own. Carried: the after-toilet angry is the rush's own
  item under the profile; the puke's job posts `puke` as it ends, her mad
  starts on the offer and her fight follows it, so his SHOUT follows the
  puke by her mad and fight (76 ticks, PCHitSeconds 6.33: the mobile's
  HitPawnSequence OlgaWCMad, HitPawn — 3.0 until 2026-09-25, the mad and
  fight less the puke under the start reading); the
  wcright record — the Toilet211 extra coin and its completion — pays
  2.25 s into the puke (PCToiletPaysAt, World.pc_s2_extra_credit); the
  repair's walk to the sign, below. Open, with numbers: 210's
  TurbanShop 27 and 213's Tortilla 15 and PlantCarnivore 15 + PCExtraCoin
  20 had been dropped from the overlays by the stays writer of 2026-09-12
  (it replaced its patches' sets) and are back. The repair's walk:
  211's sign after the women's wc (34 ticks, then its `repair` 24: 4.83,
  PCFixSeconds) and 203's generator after the stage (32 and 19: 4.25) —
  the repair plays where he stands for the walk and the repair, and his
  next walk leaves the repaired object's hotspot (PCFixDepart,
  lap_model_s2._repair_walk); a station tricked through its DependsOn
  pays its dependency's record at its tick (206's pad shooting the rubber
  bear: the harpoon's PCCreditAt), and a linked variant needs the
  station's own trick too.
Plans (runs/sw18s2, all 14 at 100; 207's plan awaits the count 7 — the
  billboard's coin is paid at his resume, 426.1 s; 206's the count 6,
  253.5 s; 201 at 238.0, 203 at 206.5, 204 at 339.3, 210 at 277.1, 211 at
  261.9, 212 at 875.2, 213 at 393.3, 214 at 792.6): 202 v6 piles its chain within one lap, the rail over the pond last (its
  sawfish placed while he is at the shore and in the sea, the swim step's
  flag 4) — the mat's 20 at 279 s to the electrify's 30 at 349 s, 69.4 s
  of decay, just over the top (the rail first a lap earlier spreads it over
  71.5 s: 99.3); 214 v4 plays the shards round a lap later from the deck
  chair (the tricked hatch holds him in Zone02 until too late for it) and
  its fish and bouquet in the windows of the laps after the second fall
  (100 at 796.6 s); 204 and 211 hold at 100 as they were.
- *214's handshake (2026-09-23).* The Mother's script (GameLogic.dll:
  fcn.1003a379, vtable 0x100b05b8, its first step 0x1003a0ae) starts her
  in the awake step 0x10039e6c — to the deck chair and in (its `enter`,
  sitdown, 9 frames), flag 4 off, `awake` — and waits there on her
  handler (0x1003a2bb): `standup` sends her to the sleep step 0x1003a0b8
  (the chair's `sleep`, flag 4 on, fcn.1000e7f2's bar of 600 ticks,
  0x1003a1e0), whose continuation is the reling step 0x10039f34 (the
  chair's `leave`, getup, 16 frames; the walk; the reling's `use`, 80
  ticks) and back to the awake step; `crash` sends her running to him
  (0x1003a21c, gait 2) and then to sleep. `standup` is the pistol's: its
  `use` carries behavior="standup" for the mother (ship4 objects.xml),
  posted as the use's job ends. His pistol step (0x1003aa93) tests her after
  the walk — her current action the deck chair's and her flag 4 clear
  (0x1003abc9-0x1003ac19) — and otherwise plays `wait` and re-runs each
  tick (0x1003ad7d) until she sits awake. The mobile's Level214 pair is
  the same shape driven by events (mother_sleep at his play's end,
  mother_sit / mother_wake swapping the pistol's sets and releasing his
  WaitWatch) and races: a sit while he walks to the pistol leaves his
  WaitWatch with no release — the deadlock the PC stays had hit. Carried
  under the profile: RottweilerMotherBehaviour polls her each tick while
  he waits at the pistol and fires mother_sleep as his play ends — the
  mobile's moment, cs:116-119; as PistolPlay started until 2026-09-25,
  the start reading (the pistol's stay its `use` alone); MotherSleepBehaviour plays her
  sit at the chair's `enter`, her sleeps at the bar's 600 ticks and the
  get-up at the `leave` (PCSitSeconds / PCSleepSeconds / PCGetUpSeconds,
  tools/pcref/pc_durations_others.py BARS), MotherWait at the reling's
  6.7 s (PCUseSecondsRole); his stays are the code's (lap_model_s2, which
  now reads the hatch step's own byte and the bouquet's IsVariant null
  test: the hatch 5.17, the shower 3.58, the bouquet 4.17, the door 4.33,
  the pistol 8.25). The idle lap under it is 85.3 s against the model's
  90.3 and the video's 91 (shower to shower; the 75 of the 2026-09-06
  table had dropped the CaptainWheel span, the door's bubble, now paired
  in tools/pcref/laps_natural.py); her cycle is 83.4 s, so she sits back
  in her chair about 2 s before his next pistol and he does not wait.
  The old plan's windows were the mobile pace's; 214 was re-planned to it
  (tests/plans/pc/s2 v2): the shards round at once after the take, out of
  Zone02 each time through the Zone01 door while he climbs to Zone04 —
  its only way out before her reling walk — Woody in her chair while he
  comes up for the door, and the door, the mug, the wheel and the ammo
  right after one of his pistols, so the wheel's 80 (559 s) and the
  pistol's 40 (583) pay on one lap: 100.
- *202's mat and swim (2026-09-23).* The neighbour's lap in GameLogic.dll:
  the rail (0x1002168e: `lookaround`, the bridge's `look`), the mat
  (0x10022c8d: mat_hn swapped for mat_hn_guarded, its `enter` — laydown,
  behavior="tongue" on the kid — and fcn.1000e7f2's bar of 120 ticks), the
  beer (0x1002299f: the `use`, getbeer 64 frames, then its `leave`, getup,
  behavior="kid_cry" on Olga), the rake's walk-by (0x10022589) and the
  swim (0x10022410): the walk to the shore, flag 4 on, and `waitsea`,
  re-run each tick, until the `sub` object shows (0x100224a8-0x10022563).
  Olga's script (fcn.10022ecb) answers `kid_cry` on her mat (0x10023601 ->
  0x100233ed): `wakeup`, `leave`, the walk to the beach sub, its `take`
  (takesub) and the switch that puts the sub into the sea (0x10023087),
  then back to her mat. His dive step (0x10022046) pushes the kid's dive
  (sub_dive, 191 frames; the shark's 223), the switch to the beach sub and
  its run ashore onto the kid's own queue (fcn.1000aeb8's sequence,
  fcn.10049216 on the actor fcn.1004ba02 finds for `kid`, 0x100220a1-
  0x100221e3) and hands over to the bar step (0x10021d68) at once, which
  goes into the sea (its `enter`, entersea) for 97 ticks — he waits for
  none of the kid's actions (the video's second lap: 4 s at the shore,
  into the sea as the shark's fin shows, pc_nfh2_all_720 at 459-461 s;
  read on 2026-09-25 — until then the dive and the run ashore were held
  as his, 62 ticks each by the kid's play_remote loop); its
  continuation is the rail, whose GoTo leaves the sea (leavesea). The
  tricked sea is the shark's (0x10021fb9, 119 ticks), and its record
  `shark` sits on the shark sea's `enter`: the coin and the rage come as
  that action ends (the action step's end, fcn.1000140b), ten seconds
  before the bar is over. The mobile plays the same clips — [WaitSea,
  EnterSea, SeeSub, LeaveSea], her [BeachLayDown, TowelSleep,
  TowelLaydown, BeachGetUp] and OlgaPutSub, frame for frame the PC's at 8
  or 10 a second — with a fixed WaitSea, and its kid cries at his Rake
  start (ActionManager.KidActions), which ends Olga's sleep loop at its
  round. Carried under the profile: the mat per clip (PCClipSeconds: the
  lay-down 0.5 s, the bar's 120 ticks over the seven sleeps, the beer
  5.33, the get-up 0.42) and the swim per clip (EnterSea 3.08, SeeSub
  8.08, SeeShark 9.92, LeaveSea 1.67) with WaitSea held until Olga's
  Submarine use has ended (PCWaitFor; and 10.33 s more until 2026-09-25,
  the kid's dive read as his), the shark paid as
  EnterSea ends (PCCreditAfter, World.pc_s2_credit — the overflow's tick
  counted there), Olga's clips at the PC's (PCClipSecondsRole: lay-down
  0.67, wake-up 2.92, get-up 0.67, the sub's take 1.5) and her sleep loop
  cut at once on the kid's cry (the PC's handler wakes her on the next
  tick); the rail's stay is the code's 10.67 s. tools/pcref/lap_model_s2.py
  closes the lap with three readings of the same day — a poll's re-run
  takes the object it waits for as shown by the other script, another
  actor's action lasts its actor's animation first (Loader.dll's rule
  since 2026-09-25: the longer oneshot of the actor's and the object's),
  a bar's hideout is the one the step has just shown — and times it at
  80.7 s plus the wait for the sub; the idle lap under the profile was
  81.7 s (Olga's sub reaches the sea 4.7 s after he reaches the shore),
  and is ~77 s mat to mat without the kid's dive (2026-09-25), against the
  video's 70 (the first lap, from the level's start on the mat) and
  90-94. The earlier stays (the video's: the mat 0.5, the swim 9.5, the
  rail 21) had made it 60 s. 202 was re-planned to it (tests/plans/pc/s2
  v5): the rail pays at his lap-3 rail and the mat, the rake and the
  shark on his lap 4 — 104, the collapse, 100; v7 (2026-09-25) the same
  chain a lap-length earlier, 100 at 307.6 s.
- *210's call (2026-09-24).* The Mother's script (GameLogic.dll): her
  sleep step 0x10018c0b walks her into pool/deckchair (its `enter`,
  sitdown, 9 frames) for fcn.1000e7f2's bar of 240 ticks, the chair's
  `sleep` and her flag 4 on (0x10018d60); at the bar's end the check
  0x10018983 looks at his current object (fcn.10049190). Not his beach
  deck chair: the awake step 0x100187d8 — the chair's `awake`, her flag 4
  off (fcn.100185e5), a bar of 180 — and the sleep step again. The chair
  with his flag 4 on: she stays awake and the step re-runs each tick. The
  chair with his flag 4 off: her sequence is the chair's `leave` (getup,
  16 frames) and `callneighbor`, whose behavior="call" (generic/
  objects.xml, posted as its job ends, 21 ticks) his handler 0x1001b4f6
  answers on the offer — his call step 0x1001911e plays his chair's
  `leave` (17 frames), swaps
  the guarded chair for the plain one and runs him (the gait write
  0x10019270) to her chair's `neighbor` hotspot, where her order step
  0x10018682 polls for him (fcn.1000e172) and plays `order`: its
  behavior="order", posted as its job ends (18 ticks), sends him on on the
  tick after (0x1001aecc: the walk to Fifi, the
  `tickle`, 40 frames by the bone's bark — 19, the tickle_fifi of his, until
  2026-09-25 — then the take 0x1001aac8) and her back to the sleep
  step. Her call, her wait and her order stand where she got up (the
  chair's `mother` and `mother_out` hotspots are one point). His chair
  step 0x100195a4 is the chair's `enter`, a bar of 120 ticks and the
  `wakeup` (0x10018f4a), after which a flag element (fcn.1000fac4 — the
  only one of mask 4 in GameLogic.dll, 0x1001902c; its run 0x1000d037
  calls the setter) clears his flag 4: he sits awake, seen by the catch,
  until her call. The mobile's pair is the same shape driven by the data
  (MotherWakeSleepBehavior's check on his current item at her look's
  start, the calls' PawnToStopInfiniteAnimation ending the other's loop at
  its next round): her look always, a loop's round of latency both ways,
  and her walks between the chair and the call spot (1.0 and 2.3 s).
  Carried under the profile: her chair per clip (PCClipSecondsRole: the
  sit 0.75, the three sleeps 6.67 — the 240, which the mobile's repeat
  from TargetSequenceIndex 2 plays alone, the pillow pose none — the look
  15, the 180, the get-up 1.33); the check as her look starts
  (MotherWakeSleepBehavior: he away — the look and the sleeps again; he
  in his chair — the look held until his flag 4 is off, then the get-up);
  his chair per clip (the enter 0.58, the sun 2.5 × 4, the wakeup 0.33)
  with the awake loop held until her call begins and 1.83 s more — her
  call's job and the offer's tick (PCWaitFor `at` start and `then`; at
  once until 2026-09-25, the start reading) — and his flag 4 off from it
  (PCHideout, tools/pcref/pc_catch_s2.py with the flag element); his three
  stands at her chair her order's job and the offer's tick, 0.53 s each
  (PCClipSeconds Stand_Left; none until 2026-09-25) and her wait held
  until he has come (PCWaitForRole); a station of the same PC object
  reached with no walk (`Pawn._pc_departure_step`: her call spot and her
  chair; the routine actors only); his stays the code's from her order on
  (tools/pcref/lap_model_s2.py LAP_START: Fifi's tickle and take 2.5, the
  shop 6.33, the elephant 1.92, the put 1.0). A clip of 0 s is skipped
  (the AnimPlayer's clip_pace). The idle lap under it is 98.7 s call to
  call, the lap quantized by her checks (35 s, 180 + 240 ticks, each one
  he misses); the model with the PC's walks — 62.8 s of legs where the
  port walks 53.4 on the mobile rooms — comes to ~101, the video's first
  lap to 107 (the stays before, the video's, had it at 86.8). The v23
  plan rates 100 under it (runs/call210s2c: 262.7 s); its notes were
  re-timed (v24). With the behaviours at the actions' ends (2026-09-25)
  his lap is 3.4 s longer at the call (the call's job and offer before he
  leaves his chair, her order's before he goes on) and her naps later
  with it: the v25 plan takes the fishing net on her first nap on its way
  round to Zone03 (the v24's, on her second, had her wake on Woody) —
  100 at 296.0 s.
- *205's table (2026-09-24).* The neighbour's script (GameLogic.dll:
  its constructor 0x10025a88 starts him at the mat step and arms the
  step's `talk`, byte +0xd) walks him to Olga's mat (0x100258fd) and
  plays `talk` — behavior="pingpong" on Olga (cn_b2 objects.xml, posted
  as its job ends: 2 frames, 3 ticks) — then a wait element of 72 ticks (fcn.1000ca24, vtable
  0x100ab804: its run 0x1000c9de counts them down), and goes to the table
  (0x100254d5), where he waits, the step re-run each tick, until the
  guarded table shows, then plays `play` (51 ticks), whose behavior="sun",
  posted as its job ends, sends Olga back; then the skis (0x100251eb: `skiing`, 208 ticks, the
  ride's translations; 0x10024e37: the gait 5, skiwalk, back to the ski
  and `putski`, 7 ticks), the chef
  (`cut_eel`, `eat_eel`), the rocket (`ignite`), the sand lion
  (`lookaround`, `kick`; the kid's `dirt` and `build` are the kid's own
  sequences) and the mat again. Olga's script answers `pingpong` on her
  mat with its `wakeup` and `leave` (0x10025b2a) and walks to the table,
  where she swaps it for the guarded one (0x10025d76) — off her mat
  already, straight to the table — and `sun` with the walk back and the
  mat's `enter` (0x1002621c). The mobile's pair is a mutex handshake: he
  parks at the mat until her mat use ends — its sun loop set to end at its
  round by his arrival (ItemToStopInfiniteAnimation), up to 11 s, then the
  wake-up and get-up at 8 a second — and plays Tennis at the table at
  once, she parks there until his Tennis ends. Carried under the profile:
  his mat a timed mutex (PCUseSeconds 6.17 — the talk and the wait; her
  abort of it ignored), her mat's loop cut on the talk's offer, 0.33 s
  into his stay (PCBehaviourAt: the talk's job and the offer's tick,
  tools/pcref/pc_durations_s2.py BEHAVIOUR_AT; at his arrival until
  2026-09-25) — ItemToStopInfiniteAnimation at once; not on the mat yet,
  her next mat use passes at once, `Item.pc_cut_pending` — the mat's clips at the
  PC's ticks under her (PCItemClipSeconds: the lie-down and the get-up
  0.67, the sun loop 7.58, the wake-up 2.83), his Tennis held until her
  table use has begun and played for the `play` (PCWaitFor `at` start,
  4.25 s; her table mutex ends with his use, the mobile's
  PawnToAbortMutexOnFinish — at the play's start until 2026-09-25, the
  start reading's `abort`), and his stays the
  code's (the ride 17.33 and the put 0.58, the chef 4.58, the rocket 2.5 —
  7.25 and 2.17 until 2026-09-25, the chef's `cut_eel` by the neighbour's
  `wait` loop, the rocket's by his start_rocket alone —,
  the lion 7.08; tools/pcref/lap_model_s2.py now reads the wait element, a
  step in phases — the mat's `talk`, then its wait — and a level's own
  actor record over the generic one; the put's 0 of the first carry was the
  anims parser's: an empty `<animation … />` or `<object … />` took the
  next one's frames, which it gives back since — `putski` 7 frames, 204's
  gong 42 and jade dummy 45, 211's ladder 51, 209's fakir `spit` 18 in the
  model's lap). The idle lap is 101.6 s against the
  video's 102 (116.2 before; the model with the PC's walks 111.9). The v3
  plan rates 100 under it (runs/p205c: 334.5 s with the ski's return, the pile on lap 3); its
  notes were re-timed (v4).
- *207's board (2026-09-24).* The neighbour's script (GameLogic.dll): the
  board step 0x100169c5 walks him onto the diving board and plays `wait`,
  re-run each tick, until the Mother's current object is her deck chair
  (fcn.10049190 against pool_deckchair), then `dive` (54 ticks) into the
  pool (its `enter`, 0 ticks), whose `leave` (16) the bar step's walk plays;
  then the bar's `order_drink` (90), the elephant (`lookaround` 43,
  `spit_at_elefant` 83), the shell on Olga's mat (`shell` on the guarded
  mat, 68), the kid's castle (`lookaround`, his `splash` on the kid, 50)
  and his towel (the mat's `enter`, a bar of 120, its `leave`). The
  Mother's script bathes in the pool (0x100140af: its `enter`, m_enter 41,
  a bar of 200) and sleeps in the chair (0x1001447d: sitdown 9, a bar of
  240); her check 0x100141e0 at the chair bar's end keeps her there while
  his room pointer is the pool (fcn.10040a7d, none mid-pass) and else
  sends her to the pool again (the chair's getup 16, the pool's m_leave 50
  on the way). The mobile's pair: Level207MotherBehavior prefixes his
  board sets with WaitWatch as she enters the pool ladder and releases it
  at frame 49 of her ladder leave, and her DeckChair and PoolLadder uses
  cycle by themselves. Carried under the profile: the board's sets keep
  their WaitWatch and it is released as she sits in the chair (her
  DeckChair use), her chair's last sleep is held while he is in the pool
  room (the behaviour's PC arm), her clips at the code's ticks
  (PCClipSecondsRole: the sit 0.75, the sleeps 6.67 each, the get-up 1.33,
  the ladder's enter 3.42, the swims 8.33, the leave 4.17), his board per
  clip (the dive 4.5, the get-out 1.33) and his stays the code's (the bar
  7.83 — 7.5 until 2026-09-25, the keeper's `order_drink` by his own
  animation alone —, the elephant 10.5, the shell 5.67, the castle 7.75, the towel 10.92;
  tools/pcref/lap_model_s2.py LAP_START 0x100164ee with Olga's mat shown,
  LAP_PRESENT). The idle lap is 100.0 s (109.3 on the video's stays, whose
  towel was 0.8 s); the model with the PC's walks 106, the video 107. 207
  was re-planned (v7): the bartender, the ice bucket and the tap during
  his lap-2 shell and castle, the pile on lap 4 and the board with the
  awning on lap 5 — 100 at 441.7 s.
- *204's stays (2026-09-24).* His script is a chain but for one message:
  the gong step 0x10031e1d plays the gong's `use` — the elvis figure's
  hit_gong, 42 ticks, whose behavior="gong" is on him — and waits in the
  idle step 0x10031b70 until his handler (0x10033236) sends him on to the
  gong's `leave` (0x10032f52); then the hot dog (`lookaround` 43, `use` 16),
  the jade dummy's `look` (45), the rickshaw Olga sits in (`use`, pull, 70)
  and the headbanger (`use`, 51). Olga's script only enters the rickshaw
  and waits in it. His stays are the code's (tools/pcref/lap_model_s2.py
  LAP_START 0x10032f52): the hot dog 4.92, the jade 3.75, the kart 5.83, the
  karate 4.25, the gong 3.5 (the video's had the kart at 1.0); the idle lap
  is 84.3 s, the model with the PC's walks 92.8, the video 81. The plan
  still rates 100 (the pile on lap 4: 100 at 314.6 s).
- *Behaviours are posted as the action ends (2026-09-25).* GameLogic's
  DoActions job (the update 0x100020c0 of the vtables 0x100aa184 /
  0x100aa19c) walks its action list in three states: state 0 sets each
  participant's animation (the object's objanim, the actor's actoranim),
  makes the engine's watch entry for an action whose `noise` is above 0
  (fcn.1004008d, 0x10002478 / 0x100024af) and sends the start message
  (fcn.100018a6 — the job's +0x14 / +0x18, a text for the GFX's visitor
  slot 48, 0x1000a220: fcn.10002d71's callers pass "string" and
  "alreadyininv"), the job's count to the longest action's time (+0x24);
  state 1 counts +0x28 up past it (fcn.100011f2); state 2 sets the next
  animations (objnextanim, actornextanim), posts each action record's
  behavior (+0x1c) to its behavioractor (+0x20) — fcn.1004000a at
  0x10002708, the watch registry's record the level update's walker
  (fcn.1003fc90) offers on the next tick — and ends the job (the end
  message fcn.100019f7). The abort slot (0x10001d1b) sets the next
  animations and posts the behaviour too when the record's byte +0x24 is
  set (0x10002009-0x1000203f) — the `always` attribute, Loader.dll's
  default "true". Loader.dll stores the record's time at +0x28:
  time="N" as N, time="auto" as the longer of the actor's animation (the
  action's actor's set) and the object's (its gfx's set) less one, at
  least 0 — a oneshot's frame count, a loop or a missing animation -1
  (0x10004781 with its flag 1: the anim's loop byte), "inv" not asked
  (0x10009704-0x10009842). So an action's behaviour reaches its actor
  the Loader's time + 3 ticks after the job's first update, as the
  action ends; the reading of 2026-09-24 (posted as it starts, from the
  start message) is withdrawn, and with it the start carries: the lost
  game's run, 203's shout, the co-actor's fight, 205's talk and play,
  210's call and order, 211's puke and 214's pistol (the sections above,
  corrected), and 213's bull (below). tools/pcref/lap_model_s2.py
  `Data.loader_time` / `job_ticks` give the numbers, and its
  `action_ticks` follows the same rule since the same day: an auto
  action's time is its governing animation's — the longer oneshot of
  the actor's and the object's, not the actor's first with loops counted
  (205's chef `cut_eel` by the chef's cut, 31, not the neighbour's `wait`
  loop, 63; the rocket's `ignite` 30; 207's bar `order_drink` 94; 210's
  Fifi `tickle` by the bone's bark, 40). The elements' own ticks are
  carried too (2026-09-25, later): an action counts its whole job, the
  Loader's time + 2 (`action_ticks` = `job_ticks`); an element done on
  its first update takes its tick — the sequence (vtable 0x100ab6c0,
  update 0x1000ad52) pushes each element with a first run (fcn.10049246)
  and returns 0, and the queue runner (fcn.100492a8) goes on only past a
  job that is done; the bars (fcn.1000b154's counter, 0x1000b3a7-
  0x1000b3b3) and the wait element (0x1000c9de) last their ticks
  exactly; and a step takes its own — the script's job (213's neighbour:
  update 0x10037726 -> fcn.1000e131) runs the step and returns 0, the
  step's sequence pushed without a first run (fcn.10049216) starting on
  the tick after, and a step that walks has the GoTo's first tick before
  the walk (the GoTo job, fcn.1000e3e0 -> fcn.10007a10, pushed the same
  way) and its done tick after the arrival (the job sets +0x14 as the
  actor arrives and returns 1 on its next update, 0x10007670 /
  0x10007409): 3 ticks a walking step, 1 a step at the place of the
  last (`step_ticks`, with the step's first timed part). The laps the
  model closes grow by 0.9-2.4 s (202 88.8, 203 106.8, 208 87.3, 209
  109.3, 211 87.1, 212 127.3, 213 125.8, 214 92.2 s), each stay by
  0.1-0.5 s; 208's plan parks through Zone05 at once after the rat
  (`park!`, the gate had held Woody there a lap) and 211's waits for the
  Mother's sleep before her lap-3 visit to the child — all fourteen at
  100 (runs/end6s2). 204's gong already waited for the strike's
  end (its stay the strike's 42 ticks) and 202's `kid_cry` rides the
  mobile's crying at his next station, the mat's `leave` over. Under it
  210 and 211 were re-planned (210 v25: the fishing net on the Mother's
  first nap, 100 at 296.0 s; 211: the child and the phone from Zone02
  once she is back asleep after her lap-3 visit to the child, the
  overflow at 259.6 s), and all fourteen Season 2 plans rate 100
  (runs/end2s2); Season 1 and the mobile regression are byte-identical
  (end1s1, end1mob).
- *213's bull (2026-09-25).* His controls step (0x10037e80) walks him to
  bottomleft/bullride_controls and re-runs each tick until Olga stands at
  the bull's hotspot (fcn.1000e172 on bottomleft/bullride_olga), then
  posts `bull` to her (fcn.1004000a, 0x10037f5e — the step's own post, as
  he arrives) and plays the controls' `use` (activate, 11 frames); his
  next step waits for `leave` (the latch +0x20) and passes on the tick it
  is set. Olga's bull step (0x10039078) walks her to the bull and waits
  for her `bull` latch, then plays bottomleft/bullride_olga's `use` (the
  `ride`, 81 frames — `crash` with the manipulated controls shown),
  whose job posts `leave` to him as it ends (82 ticks). The PC's span
  from his walk to the controls to his going on: the walk (57 ticks) and
  the ride from the tick after his arrival to the offer of its `leave`
  (84) — 141 ticks, 11.75 s, against the video's 12.0 (the port's had
  been 17.2: the controls 0.3 + 0.4 and a 6.4 s wait split off the video,
  and his wait released at the round of his loop after her mobile 10.1 s
  ride). Carried: the controls' stays the code's (PCUseSeconds 0.92, the
  `use`, and 0.08, the latch step's pass; `STAYS_CODE`), no stay on the
  wait (MechanicalBullControlsWait's loop ends on her `leave`), her
  ride's clip at its frames (PCClipSecondsRole BullRide 6.75), her
  waiting loop cut 0.08 s into his controls (PCBehaviourAt: the `bull`
  offer; the mobile's once-loop flag at his use's start) and his cut
  0.17 s after her ride (PCBehaviourAtEnd: the job's tick past the frames
  and the offer; the mobile's once-on-end flag) — `Routine.
  _pc_behaviour_cut`.
- *The overlay writers' shared patches (2026-09-24).* tools/pcref/
  pc_walks_s2.py rebuilt its keys (PCPass, PCApproach, PCRoom) by dropping
  every patch that carried them, pc_catch_s2.py its PCHideout likewise, and
  a patch they share with the duration tools' keys lost those: since the
  routes of 2026-09-23 207's Bartender (8.7 s, the video's), 209's
  TadjMahal (11.67, the code's), 212's PreAztecThrone (his look at the
  hands, 3.58) and PreParrotLedge (the cliff's `enter`, 1.92), 213's
  MechanicalBullControlsWait (6.4) and its Mother's stands (12.5, 19.7)
  had played at the mobile's pace, and the source notes after theirs were
  gone. The writers rewrite their own keys in place now and end their
  notes at their own last words; run in any order they reproduce the
  overlays. With the stays back the idle laps are 209 100.8 s (102.7
  before), 212 119.4 (125.2) and 213 126.6 (125.3) against the model's
  104, 124 and 123; 212's pile had slid onto two laps (90), and was
  re-planned onto his lap 7 (tests/plans/pc/s2 v5: the whip armed after
  his lap-6 visit; runs/p212o, 100 at 837.6 s); the others keep 100.
- *The walker's object presence and the machines (2026-09-23).* The
  lap walker (tools/pcref/routine_order.py) took isObjectPresent
  (fcn.00479ff0: the object looked up, its flag 0x20 tested) as false; it
  now follows the objects' presence along the lap — level.xml places
  them, each switch (fcn.00451de0, the new object and the old) swaps one
  for the other — so 111's second ironing irons the clothes case 8 gave
  the board (the hand-written NATURAL entry of pc_durations.py is gone),
  113's valve is switched off and on and its fuse taken (0.33 s each for
  the 2-s surprises) and 114 goes back to the phonograph a third time to
  close it (the mobile's third Gramaphone visit, its own PCUseSeconds).
  111's washer and drier legs last the case's DoActions (give 0.33, wash
  4.92, get_clothes 2.0; give 0.33, dry 2.42, take 0.33 — pc_durations.py
  splits the station by action), the tricked use the rest of the tricked
  branch (the wine's wash and red get_clothes 9.5 s, the smashed drier's
  dry 3.33), and every visit takes its slot of the per-visit list even
  tricked, the skipped unprime included (`Routine._pc_use_seconds`,
  `_end_pc_station`: a tricked Teeth, Airer, Polish or phonograph visit no
  longer shifts the next visit's stay onto the wrong PC station).
- *The walker's arguments (2026-09-26).* The walker had read a call's
  string arguments back up the listing to the previous labelled call, and
  where a branch lay between it took the other branch's strings: 109's
  teeth after the alarm and the parrot's cookies carried the tabasco's and
  the hot cookies' `spit_fire` (34 and 31 ticks), where case 11 takes the
  teeth when bed/teeth_tabasco is not present (`take`, 5 ticks, and the
  switch to bed/teeth_empty) and case 26 gives the parrot its cookies
  (`give`, 17); 108's coffee had lost the `make_coffee` (49 ticks) case 4
  loads before its IFVARIANT and plays on both branches, the soiled box's
  and the clean one's. It reads them along its own path now (an
  IFVARIANT's strings go on to the call its pick feeds: 107's ENTER of the
  stool or its pinned twin). Two GoTo builders were missing from its table
  — fcn.0047a960 and fcn.0047a4a0 (their asserts: CreateGoToObjectJob,
  CreateGoToObjXJob) — and 114's case 7 walks the first smoke to
  lir/tabacbox with the first (the neighbour's own `give` there, 5 ticks),
  where the walker had stood him at the kitchen's polish: the port's walk
  to the living room's pipe was the PC's (E14's bubble: the pipe 54-63,
  ten seconds of walk). pc_durations.py rewrote 108's coffee 2.3 → 6.4 s,
  109's second teeth 2.8 → 0.4 and its parrot 5.2 → 4.1, 114's first smoke
  1.4 → 0.4 s, and pc_walks_s1.py the pipe's walk point (lir/tabacbox on
  both visits). The same day's rerun of the Season 1 writers put back the
  pets' search (the Alerters' PCSurpriseSeconds, 26 ticks: 107, 109,
  111-114): tools/pcref/pc_reactions.py stripped its keys from every patch
  and PCSurpriseSeconds is one of them, so its run on 2026-09-26 at 15:00
  had dropped pc_durations.py's alerter patches and the port played the
  remaster's Search (2.5 s) since; it strips its own TrickItem patches
  only now, and the writers run in any order reproduce the overlays.
  Against the videos: with the door pass as one step of its two clips
  (docs/PC_VERIFICATION.md "door transit") and the mover down to the floor
  line and up again between raised points (the entry "Season 1 walks"),
  both read the same night, every station of E08, E09, E13 and E14 sits on
  the bubbles within about a second — E08's coffee 25.4 s against the
  video's ~26, E14's gun 25.2 and hat 35.0 against 24-25 and 34-35, E13's
  main valve 29.6 against 29-30 — where the clips one after the other and
  the straight legs had put them 4-8 s off either way.
- *The tick rule, in the canon's own words.* The Season 1 manual
  (Docs/Manual.pdf, "Anger indicator"): "As soon as the neighbour becomes
  the victim of a trick, his anger indicator rises to the maximum value.
  Then it slowly begins to sink again, until it finally gets back to
  zero. If the neighbour gets mad again before his anger indicator is
  back to zero, he starts fuming ... the viewer ratings rise by a few
  additional points" — and under "Viewer ratings indicator": the trick's
  points "are shown as small yellow numbers above the score display",
  the bonus points "in bright red". That is Rottweiler.cs:597-611 (a tick
  while AngryMeter > 0, +3 as the PC HUD shows) and the count-up the
  profile draws. The indicator's length is not written down; the data's
  23.6 s sits inside the 18-25 s the tick digits bracket, so it stands.
- *The per-trick `angrytime`.* The manual adds that the indicator "will
  sink again steadily after each trick — with varying speed", and the
  thermometer says what varies: after a trick with its own `angrytime`
  the mercury holds at the top for that long before it drains at the
  level's rate — E14's marbles (360 = 18 s) hold 18.1 s, E09's nitro
  bottle (240) 12.6, E05's bowling ball (288) 14.6, E04's picture (264)
  12.8, E11's marbles and vacuum (300) 13.3 — where a plain trick holds
  for the angry animation (7-8.5 s). Read from game.exe (docs/
  PC_ROUTINES.md), the hold is not the trick's value: the value is the
  rage current the trick sets, the mercury pins while that current is at
  or above the level's angrytime — 60 ticks of hold plus the excess, at
  12 ticks a second (the marbles: 5 + 10 s) — and the profile carries
  the values as PCAngryTime (levels/pc, from tricks.xml, in ticks) for
  exactly that (pcprofile.s1_rage_fire).
- *In the binaries.* The neighbour's routine is a script in game.exe's
  level classes — read out with radare2 into docs/PC_ROUTINES.md (the
  object and action names are UTF-16 String globals the script code
  loads; seventeen copies of the engine's string tables, one per
  class); the anger timer and the bonus live in GFXEngine.dll with the
  HUD (`rageometer`, `bonuscount`), fed by game.exe's trick parser
  (quota1-4 and angrytime per trick) and level parser (angrytime at
  +0xc); Loader.dll parses the XML. The exact indicator length is the
  one number still to read, in GFXEngine.dll.

**The canon audit (tools/pcref/canon.py, 2026-09-10).** Every level of
both games, the PC data next to the mobile's, category by category:

| category | PC vs mobile |
|---|---|
| level time limits | equal: leveldata `time` is in 1/12 s — 300/360/420/600 s = the mobile's 5/6/7/10 minutes (E06's clock confirms 6:00); Season 2 has no limit on either |
| pass thresholds | equal tables: the mobile Entry scene's MinRatings (50-75 %) are the PC minquota, its WinningTricksCount the PC mincoins on every Season 2 level but 211 (6 against the PC's 5 — overlay); the rule differs on Season 1: the PC passes an episode on the minimum rating (the manual), the mobile on its trick count — the profile passes on the rating |
| trick sets and values | equal but 109 (milk 20 / pig 10), 111 (13/12/7), 112 (skates 8) — overlays; the mobile's extra rated items (103's cake, 112's Yoga, the 104/113 pairs, Season 2's fence and hook items) are not on the PC and not on the PC routes |
| recipes (combine.xml vs RequiredInventory) | equal on every trick the PC has; the mobile adds recipes of its own (108's balloon, the Season 2 knives) |
| containers and their contents | equal (the PC marks unlimited stock with count 99, the mobile with UseCount 0) |
| walk-by tricks (nearobj triggers vs NoticeWhenWalkNearby) | equal, 111's ironing board included; 111's rack is a walk-by on the mobile and a station on the PC (case 14 fires on his arrival) — fired on arrival under the profile since 2026-09-26 |
| rooms and doors | equal room graphs (the PC's extra "fro" is the entrance hall; the mobile numbers its zones) |
| the neighbour's routine | read out of game.exe (docs/PC_ROUTINES.md, tools/pcref/exe_scripts.py): one compiled class per level, its `run` a script of Icon / GoTo / Action / branch / SwitchObjects calls on the level's object names; the actions and repeats are there (the laundry's washer and drier one station each — give, wash, get_clothes; give, dry, take — the mobile's three-phase machine; their tricked branch ends the station), the lap order still from the video where the compiler laid branches out of line |
| action lengths | the PC's `time`/frames at 20 per second are of the mobile's order (album 5.7 vs 3.3 s, pudding 4.8 vs 0.8, sofa 4.4 vs 11.8, microwave 9.4 vs 15) — the laps are walks and structure, see docs/PC_LAPS.md |
| speeds | the PC neighbour walks at 8 px a frame, Woody 17 — the same 1:2 the port shows; the mobile's 1.25 units/s is the PC pace (E06: ~120 px/s) |
| doors | the PC's enter/leave take 9-25 ticks; not compared frame by frame |
| Season 1 anger | thermometer drain = `angrytime` (exact, applied); the tick meter and the hold are game.exe's |
| Season 2 anger | rage = the mobile amounts but eight items (applied); the gauge is 100 000 long — the dialog's range, the code's flag, the bar's cap on E10 (the mobile's 100, applied); the decay is leveldata's `time` (30) per 1/12 s tick = 0.36 %/s (GameLogic's level update 0x100442b3, 0x100447c4; PCRageDecay, applied — the mobile's 0.37 rounded it) |
| HUD | the PC's rating popups are yellow (240/240/0) for the score and orange (255/160/0) for the bonus, as drawn |

The mobile profile's 54-plan regression after the change: 33 PERFECT, 0
failed — the same table as before it. The `whenzone` leg that followed (the 210 plan)
left a four-plan mobile subset (108/114/204/210) byte-identical.
