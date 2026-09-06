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
| routines / timing | laps re-authored by Nordi; PC laps unknown in numbers | only with PC data in hand |
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

PC: points (coins + a COLLAPSE bonus + time; E10's end screen 8000 + 3000 +
5000 + 1398, the map counting 8/8 coins), and the gauge may fill more than
once — Badinfos' 100 % run fills it twice in 210 and 214. The gauge decays
at ~0.4 %/s on PC as well (`tools/pcref/gauge.py`), so the mobile's 0.37/s
is the PC's constant; only the "exactly one" is the remake's.

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

### 2.6 Dexterity mini-games (confidence: high)

PC has none. Port: `_dexterity_gate` (world.py:7228) arms the minigame on
the first pass and lets the second through. Profile switch: return the
"done" branch on the first pass (auto-solve). The `unlock` legs in the plans
become no-ops under the profile; the plans still run.

### 2.7 Routines and timings (confidence: high — MEASURED, docs/PC_LAPS.md)

Measured for all 28 episodes from the PC videos' HUD bubble: the ORDER of
the neighbour's activities is the PC's in every episode; the periods are
within ±15 % in 17 of 27, and the mobile is slower by 20-80 % in 101, 105,
107, 110, 112, 114, 210, 211, 212 (single actions that last longer — the
sofa, the pottery chain, the deck-chair sleep). A PC-timing profile would
therefore not re-order anything; it would shorten specific action
durations, and `docs/PC_LAPS_DETAIL.md` has the PC per-activity durations
to set them from. Still not from PC data — from video, ±2 s.

### 2.8 Not worth it

Art, menus, HUD, tap controls (the port is already mouse-driven), IAP gates
(the port has none), Olga/Mother as catchers (the PC NFH2 mum catches too —
"avoid mum or else you will get beaten").

## 3. Shape of a PC profile in the port

- `--profile pc` (default `mobile`, i.e. today's behaviour, untouched).
- `levels/pc/<Level>.overlay.json`: JSON merge patches applied after the
  mobile load — flags (108), collider rects (211/214), added objects (114's
  whistle). Each entry carries a `"source"` string (guide URL / video
  timestamp), the PC analogue of the runtime's `// cs:` citations.
- `Game.rules`: `overflow_bonus = 'exactly_one' | 'at_least_one'`,
  `dexterity = 'minigame' | 'auto'`, `lives = 0 | 3`.
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
| PC laps | fidelity | large | high if guessed | yes |

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

## 7. Implemented (2026-09-06): `NFH_PROFILE=pc`

- Switch: `python3 runtime/app.py --profile=pc …` for the game,
  `tests/run_tricks.py … --profile=pc` for the harness (both set
  `NFH_PROFILE`; `runtime/pcprofile.py` reads it live). Default `mobile`:
  every mobile-profile number in `tools/livediff/README.md` is unchanged
  (the full 54-plan regression re-run after the change).
- Overlays: `levels/pc/<Level>.overlay.json`, applied to the raw objects
  after the mobile load (`scene.Level.__init__`), each with a `source`.
  Ops: `set` fields, `append` list fields, `anim`/`anim_set` on a
  controller's animation, `actions` to rebuild an ActionManager's list by
  item names (addressed by `owner`). Shipped: Level113 (the electric trap
  lifted to the depth it has in L111/L114, so the click ray reaches it),
  Level114 (the dog whistle in the hall's chest of drawers), Level205 and
  Level210 (the PC trick amounts off the gauge).
- Rules (`world.py`, all behind `pcprofile.is_pc()`): the Season 2 bonus
  for ANY overflow (`GameState.calculate_score`), three lives on Season 2
  levels (`_catch` → `_respawn`: the beating plays, Woody reappears at the
  level entrance, the neighbour resumes his routine), no dexterity
  mini-games (`_dexterity_gate` runs WinDexterity's side effects on the
  first click), `World.blow_whistle()` — the targetless inventory use
  that wakes every alerter (the W key in the viewer, the `whistle` plan
  leg; the icon is the PC's own, cropped from the video).
- Harness: `whistle`, `whenusing <Item>` and `whenzone <Zone>` legs (the
  neighbour's lap landmarks a plan can wait for); `unlock` on a dexterity
  search takes the item outright under the profile.
- Plans: `tests/plans/pc/` holds the nine that differ (113, 114, 202, 205,
  206, 208, 210, 211, 214); the other nineteen run the standard plans under
  the profile.

### Results under the profile (the final run, 2026-09-06)

Every level pays every trick. Rating 100 on all 28. The lever on the
levels that sat at 90 was the same every time: arm each coin right after
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
| 101 | 4/4 | 100 | 201 | 4/4 | 100 |
| 102 | 6/6 | 100 | 202 | 5/5 | 100 (the mat armed after his lap-2 visit) |
| 103 | 6/6 | 100 | 203 | 5/5 | 100 |
| 104 | 7/7 | 100 | 204 | 6/6 | 100 |
| 105 | 8/8 | 100 | 205 | 5/5 | 100 (the PC amounts, the sculpture before the rockets) |
| 106 | 9/9 | 100 | 206 | 6/6 | 100 (the PC payment order: weights, dynamite, then the pad) |
| 107 | 7/7 | 100 | 207 | 7/7 | 100 |
| 108 | 6/6 | 100 | 208 | 7/7 | 100 (armed in his lap order after each lap-2 visit; Fifi and the rake last) |
| 109 | 7/7 | 100 | 209 | 7/7 | 100 |
| 110 | 6/6 | 100 | 210 | 8/8 | 100 (the PC amounts; basket triple, shop and elephant on his lap 2) |
| 111 | 8/8 | 100 | 211 | 8/8 | 100 (the rod) |
| 112 | 10/10 | 100 | 212 | 9/9 | 100 |
| 113 | 8/8 | 100 (the electric trap's depth) | 213 | 9/9 | 100 |
| 114 | 9/9 | 100 (the whistle) | 214 | 6/6 | 100 (no wait before the pistol) |

The mobile profile's 54-plan regression after the change: 33 PERFECT, 0
failed — the same table as before it. The `whenzone` leg that followed (the 210 plan)
left a four-plan mobile subset (108/114/204/210) byte-identical.
