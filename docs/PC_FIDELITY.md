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
routine and the clock never stops. The profile's `_respawn` does exactly
that (the entrance location, the routine unfrozen, nothing reset).

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

The profile plays it on the remaster's field with the PC's rules
(PCMinigameTicks, PCMinigameLevels — tools/pcref/pc_minigames.py;
pcprofile.s2_game_rate / s2_game_push; DexterityState._pc_tick): the thumb
follows the mouse one to one with no remaster drift or margins, the first
three ticks centre it, the push and the alarm field are the PC's, the
drawn thumb stops at the 100 px radius (thumb_rect); a lost game sends
the neighbour onto the object at a run where the `failed` behaviour
reaches him (the mobile's surprise, Routine.pc_run_next) and nobody on
201, 212 and 213 (PCMinigameFailed; 201's toolbox loses like the rest, the
mobile's DexterityCannotLose aside). 214's game is the
hatch's shards round (bottomright/hatch_closed, the phase his first fall
leaves: the mobile Hatch's Dexterity set by HatchFixBehavior). The harness
steers the thumb half the way back a frame and counts the game's length
into its gate (use_time): 212's plate now goes before the whip, its take
straight after the game (v2), and 208's rat during his lap-2 shoe
(tests/plans/pc/s2). Open, with numbers: the field — the remaster's
reference pixels (1280 x 800) stand for the PC's, the PC's field.tga is not
on hand; the order of a tick's DoAction step against the game's update
(0x1004482b) — whether the elapsed count takes this tick's rate or the last
one's, one tick (0.083 s) on every game; 203's Olga shout_chinese before
his run is not played (the port's Olga has no such clip; he starts at the
loss), and his run keeps the mobile's moment (at once if he walks, else
when his clip ends) where the PC's `always` may start it at once.

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
  level entrance, the neighbour resumes his routine), no dexterity
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
  menu's exit), the catch fiber with its respawn 900 px above the start
  spot, and the data (time limits, minquota, reachable/mincoins, trick
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
  not) — no IgnoreWoodyWhenUse, IsSleeping or blocking-animation windows
  (Season 1; Season 2 keeps the mobile's windows until GameLogic's watch
  mode bits are read). The harness's dodging reads the same paces (`_speed`, `woody_speed`,
  `door_time`, and `_door_climb` — the ~0.65 u climb to a back door, one
  axis a tick: 1.7 s for the neighbour, 0.9 for a walking Woody, 2.6
  sneaking; a catcher is in the far room once the Leave/Enter pair has
  played at once after his climb, the descent happens inside it) and the
  same windows
  (`_asleep_safe`, `_ignoring_safe`); `NFH_PC_RULES=walk,doors,sight`
  keeps a subset for bisecting a plan.
- The door pass (2026-09-17, `pcprofile.door_ticks` / `doors_sequential` /
  `door_warp_early`, docs/PC_VERIFICATION.md "door transit"): the PC runs
  the near door's `enter` and the far door's `leave` one after the other
  through every door (the mobile fires a flat door's two strips at once),
  each `time` ticks long — the neighbour 19 + 19 by a side door and
  11 + 22 by a back door, Woody 15 + 23 / 18 + 24 / 9 + 25 — so the mobile
  strips play at the rate that lasts those ticks; and the far door places
  the pawn, zone and all, at its clip's start, where the PC's room pointer
  changes (the mobile warps at the clip's end). Season 2's doors are not
  `<door>` objects and keep the mobile's pass at a frame a tick.
- The stations' durations (2026-09-17, `tools/pcref/pc_durations.py`):
  every Season 1 overlay carries `PCUseSeconds` per routine item — the
  PC station's DoActions at 12 ticks a second, from the lap model's
  tokens of the level class, one value per visit — and the neighbour's
  use plays the mobile clips at the pace that lasts it
  (`RoutineAction._pc_use_seconds`, `AnimPlayer.time_scale`), or holds a
  walk-by stand for it where the remaster only passes (the shout at
  105's window, 112's yoga). 111's machines, 106's bath and 104's shaving
  chain keep the mobile's (the PC neighbour waits on the object there —
  docs/PC_VERIFICATION.md).
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
| 104 | 7/7 | 100 (6: the PC lap order — the microwave after the pie — and no second use after the egg, levels/pc/Level104.overlay.json) | 204 | 6/6 | 100 |
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
the PC's (levels/pc, each overlay with its source): 104's lap is put in
the PC order (the microwave after the pie, `actions_by_index`) and the
oven is not used a second time after the egg (ReuseAfterFix off), so the
cream, the egg, the slip and the bathroom chain as on E04; 109 pays the
PC's scores (the milk 10, the chips 15 — the mobile routes the chili's
15 through a CornChips whose score is 0) and needs four ticks, not six.
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
(106), no activity off by five seconds. The other three stay open: 111
(−17 %) is a routine of three washer and three drier visits against the
PC's one long visit each (47 s and 26 s), 213 (−17 %) a cement bath
whose PC spell is twice the mobile's two animations, 210 (+16 %) a deck
chair he leaves on the Mother's call — none is a loop count. (Tried
anyway on 2026-09-09: with her nap cut to one MotherSleepSingle his
spell fell only from 54 to 45 s — his ChairAwake runs 27 s after her
call, so the wait is not her nap alone — and both levels' plans, tuned
to the mobile laps, lost; the overlays were withdrawn. The PC original's
own data, `data/gamedata.bnd` — a plain ZIP of the levels' XML,
tools/pcref/gamedata.py — is the way to settle these three and the tick
window alike, once a copy is at hand.) A catch under the profile puts
Woody back at the entrance in one frame; the respawn now marks that
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
  clip picked by the trick record's `laugh` level (GameLogic.dll
  0x1000f9b5-0x1000fa9b: the level chooses a table, a seeded random the
  entry — 0: shout2_light; 1: shout2 or shout2_hard; 2: shout2_hard and
  two of the shout2 set; 3 and above: freakout1, freakout2 or
  freakout3, the tables at 0x100df45c/0x100df434/0x100df450/0x100df43c),
  2.2 s for the shouts, 7.1 for shout2_hard, 3.1/3.2/5.2 s for the
  freakouts (generic/anims.xml's frames at 12 a second) — where the
  mobile plays AngryEasyUp and AngryHard, ~7.6 s, after every trick. The
  tricked bubble spans agree (213's tortilla is 11 s for a 4-s stay and a
  3.5-s trick action). The profile paces the mobile's angry set to the PC
  clip (PCLaugh on the item from tools/pcref/coins.py --write-laugh, the
  level's commonest level where the pairing does not reach a record;
  pcprofile.S2_REACTION_CLIPS, World.play_angry). This is what the PC's
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
  plays a shout whose length hangs on the bonus — shout2_extra 7.67 s after
  a bonus trick, 2.08–3.75 s after a cold one (shout2 2.17 at the index-1
  sites) and none where the step carries flag 2 (the tub's hair, the dirty
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
  theirs (PCSurpriseSeconds, PCSlipSeconds). The stands come out of the
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
  — and the carpet's room trigger runs cases 20-22 at once, without the
  startled look of the mobile's RunToTrickedItem (the SurpriseFar, 2.1
  s). 109's pig visit is one station: Level_Pig's case 18 fires the
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
  CaptainWheel — the door's stay is the mobile's), a port visit the PC
  never makes keeps the mobile length as a leading 0 in the per-visit
  list (209's first shoe: the PC does the Taj before the shoes, so the
  Taj span is the Taj's alone, 10 s, and the shoe span the second
  visit's, 2 s), and a lap that is a two-actor handshake keeps the
  mobile pace as a whole (214: his pistol sequence fires mother_sleep,
  the Mother's sit fires mother_sit and releases his WaitWatch at the
  second pistol — the Level214 behaviour, cs:62-65 and 130-147; with the
  PC stays he reaches the pistol after her sit and the two wait for each
  other for good, and the PC's Mother script is unread — so 214 carries
  the mobile pace whole). Under the carry 202-209 rate 100 as before
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
  bar (17.3). No pace beats the gait's floor record (a mobile climb longer
  than the PC's run — 205's water skis, 3 px — takes the walk's pace). The
  port's idle laps then walk within about a second of the model per leg
  (208: the shoe machine 26.2 / 27.9, the elephant 4.5 / 3.8, the bowl
  10.8 / 11.8, the platform 15.3 / 15.2; 213: the plant 16.7 / 16.5, the
  picnic 16.2 / 16.7, the cement 17.2 / 17.6), and with the code's stays
  208's lap is 82.5 s for the model's 85.5 and the video's 86. Open: Woody's
  own runs to his items (his `woody` hotspots at 6 px a tick) are not
  carried — it needs his ~295 items paired with the PC objects, which the
  nearest-object proposal leaves ambiguous on 97; a walk that does not
  leave a station (after a trick's reaction, a run, a chase) keeps the
  mobile's route; the detection keeps the mobile's PassingComplexMove
  window over a pass, where the PC's actor is in no room from
  `<actor>_in` to `<actor>_out`.
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
  214's handshake keeps the mobile pace whole.
- *111 under the PC scores.* Badinfos' E11 chains the eight in one lap
  (the thermometer's jumps, tools/pcref/thermo_jumps.py, and his bubbles:
  the trap on the basement walk-in 155.8, the washer 179.5, the drier
  195.5, the glued vacuum 221.8 — his vacuum icon from 215 — the marbles
  249.4 on his walk from the bedroom to the balcony, the fish tank 278.8,
  the ironing board 301.3 as he passes it between the tank and the
  balcony, the airer 322.2), every gap 16-29 s, seven ticks: the PC data's
  79 points make the 100. The PC rules the port had to take from game.exe
  and the data: the dirty carpet is a room trigger
  (`level_laundry/trigger.xml`: `position="room" type="always"`; the
  mobile's OnChangeZone skips the carpet, Rottweiler.cs:188, and only the
  dog's yell sends him, cs:485-510) that runs Level_Laundry's cases 20-22
  at once, and the glued vacuum is that case's tool (the playing trick,
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
  mobile's Urgent DeckChair / Pillows / DeckChair), 210's run to the
  Mother's call (0x10018dd9 — the Urgent CallRTMother), 211's run to the
  ringing cabin phone (0x1002fd04 — the alarm, CabinPhone's PCRunTo) and
  to the WC after the sweets (0x10030e07 — the toilet run), and the
  co-actors' runs to him after his crash, each a gait write before
  fcn.1000eb19's walk to "neighbor" — the mobile's hit-pawn of the trick
  item's PawnToAffectWhenTricked, run where the item carries PCRunTo
  (World.play_angry; pc_reactions.py RUNTO_S2): 201's Olga at the damaged
  buffet (0x1002ad27), 204's at the rickshaw (0x10033486), 205's at the
  table tennis (0x1002637e), 206's Mother to the ramp on the rabbit's crash
  (0x1002bbd1), 207's Olga to the destroyed sand castle to lift him
  (0x10017606), 214's Olga after the shower and the bouquet (0x1003c035,
  one handler) and its Mother after the pistol (0x1003a27f); the stairs
  keep their records. Their other walks to him the PC walks. Open, with
  their sites: the runs of 201's tutorial (the buffet 0x10028b74, the soap
  puddle 0x10029797), 205's nailed water ski (0x10024fde), 208's rake
  (0x1001d889) and 210's second (0x10019270), which the mobile has no
  moment for. A PC mechanic the mobile lacks — the `failed` action of
  every level's game object (§2.6) dispatches the neighbour's `run`
  behaviour (0x1003e278: the alarm sound, a running GoTo fcn.100080e1,
  `search`) — carried: a lost game's surprise onto the object runs
  (Routine.pc_run_next), nobody comes on 201, 212 and 213. The `fight`
  step (0x1003d8a3: gait 2, the walk to Woody, `fight_woody`) is the
  registry's other generic behaviour. The catch fiber itself (0x100061dc)
  sets no gait.
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
| walk-by tricks (nearobj triggers vs NoticeWhenWalkNearby) | equal, 111's ironing board included |
| rooms and doors | equal room graphs (the PC's extra "fro" is the entrance hall; the mobile numbers its zones) |
| the neighbour's routine | read out of game.exe (docs/PC_ROUTINES.md, tools/pcref/exe_scripts.py): one compiled class per level, its `run` a script of Icon / GoTo / Action / branch / SwitchObjects calls on the level's object names; the actions and repeats are there (the laundry's washer and drier one station each — give, wash, get_clothes; give, dry, take — the mobile's three-phase machine; their tricked branch ends the station), the lap order still from the video where the compiler laid branches out of line |
| action lengths | the PC's `time`/frames at 20 per second are of the mobile's order (album 5.7 vs 3.3 s, pudding 4.8 vs 0.8, sofa 4.4 vs 11.8, microwave 9.4 vs 15) — the laps are walks and structure, see docs/PC_LAPS.md |
| speeds | the PC neighbour walks at 8 px a frame, Woody 17 — the same 1:2 the port shows; the mobile's 1.25 units/s is the PC pace (E06: ~120 px/s) |
| doors | the PC's enter/leave take 9-25 ticks; not compared frame by frame |
| Season 1 anger | thermometer drain = `angrytime` (exact, applied); the tick meter and the hold are game.exe's |
| Season 2 anger | rage = the mobile amounts but eight items (applied); the gauge is 100 000 long — the dialog's range, the code's flag, the bar's cap on E10 (the mobile's 100, applied); the decay is leveldata's `time` (30) per 1/12 s tick = 0.36 %/s (GameLogic fcn.10044234; PCRageDecay, applied — the mobile's 0.37 rounded it) |
| HUD | the PC's rating popups are yellow (240/240/0) for the score and orange (255/160/0) for the bonus, as drawn |

The mobile profile's 54-plan regression after the change: 33 PERFECT, 0
failed — the same table as before it. The `whenzone` leg that followed (the 210 plan)
left a four-plan mobile subset (108/114/204/210) byte-identical.
