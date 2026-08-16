# Pass 3 — the trick matrix, group s1a: Level102 … Level106

Plans: `tests/plans/s1/Level102.txt` … `Level106.txt`. Driver:
`tests/run_tricks.py` (`SDL_VIDEODRIVER=offscreen python3 tests/run_tricks.py
tests/plans/s1/Level10X.txt --out=/tmp/nfh-tricks-s1a`). Traces of the last
run of each plan: `/tmp/nfh-tricks-s1a/s1_Level10X/{results.json,state.jsonl}`
(copies: `/tmp/nfh-tricks-s1a/final/L10X_results.json`). Final tally:
**L102 16 legs / 0 failed, L103 16 / 0, L104 19 / 0, L105 23 / 0, L106 25 / 2
(the Pudding: PORT) — 0 restarts everywhere; 34 of the 36 scoring tricks the
data can express (the levels' TotalTricksCounts: 6+6+7+8+9) are PAID at the
C# score** — the two misses are PORT findings #2 (L106 Pudding) and #3
(L102's second loo trick); a third PORT finding (#1) was fixed in-tree by the
fix agents mid-pass. All below.

The house is the same in all five levels: Zone01 the hall (entrance from
Zone05, the street; the Wardrobe HideItem, the Drawer), Zone04 the bathroom
(a dead end off the hall: ToiletPaper, Toilet, FirstAid, SoapDish), Zone02
the living room and Zone03 the kitchen upstairs (walk-up stairs from the hall,
a flat side door between them). Facts that shape every plan (each read from
the source and the data):

- ONE soap per level: `SoapDish` hands `IT_Soap` (UseCount 0) once —
  `Woody.AddInventory`, then `InventoryItems = null` (SearchItem.cs:167-201),
  and the first use spends it (TrickItem.cs:277-282). The two `Ground`
  TrickItems of L103/L104/L105/L106 are therefore mutually exclusive; each
  plan pays the kitchen one (Zone03, on his walk from the side door to the
  cooker/pie/football/pudding) and names the bathroom one as the alternative.
- `IT_Magnesium` has no source in L103/L104 (no SearchItem holds it): the
  BirthdayCake, ApplePie, SinkAftershave and SinkDeodrant `RequiredInventory`
  branches are dead data — those items pay through `DependsOn`
  (`RoutineActionUse.GetTrickedItem`, cs:556-571, returns the dependency when
  the item itself is not Tricked): the cake pays the Candle's 25, the sinks
  the AfterShave's 20 / Deodrant's 15, the pie the WhippedCream's 15.
  `IT_Knotbook` (L106 Ground@Zone01) has no source either — DEAD.
- The toilets: `ToiletPaper` is a SearchItem with `TrickAfterWoodyUse` +
  `GetTrickedAtOnce` (taking the roll marks the holder Tricked+GotTricked at
  once, SearchItem.cs:203-206, Item.cs:1955-1962). L103/L104/L106's Toilet
  is `Neutral` and off the routine: it pays only raw-Tricked (the roll used ON
  it: "blocked-up toilet") through the `NoticeWhenWalkNearby` surprise
  (Rottweiler.UpdateWalking, cs:833-849 → RoutineActionSurpriseNear.StopAction
  reads the raw flag, cs:47-57). NoticeWhenNearTrickedDistance is 0.1 in all
  five levels: he must cross the item's TargetLocation.x.
- Pawn animations were playing at 2× until mid-pass (PORT #1 below); the
  timings quoted are the sheet times at 1×, which the runtime now honours.

## Status per level

Status legend: PAID n (the leg `await <Item> n` passed: `Item.OnTrickDone`
paid n into `GameInfo.TrickDone`, attributed per item by the driver), PORT (a
finding), DEAD (unreachable by the data), ALT (the mutually exclusive twin).

### Level102 (TotalTricksCount 6, winning 4) — 5/6 paid, 78 points, 16 legs / 0 failed

Routine: Sofa (Zone02, a 7 s sit) ↔ Beer (Zone03, TakeInventory); the toilet
(Zone04) only on the laxative rush (`Beer.RushToToilet`, `Rottweiler.
MoveToToilet` → the serialized ToiletAction, cs:863-867).

| trick | status | leg |
| --- | --- | --- |
| Microwave (IT_Egg, NoticeWhenWalkNearby, UseOnce) | PAID 10 | `take Fridge IT_Egg`, `usewith Microwave IT_Egg`, `reclick Microwave` (WrongTrick/NoNo, no change) → `await Microwave 10` (the beer run passes it, t=65) |
| Beer (IT_Laxative, UseAtOtherPlace, RushToToilet; Sofa.DependsOn → Beer) | PAID 18 | `take FirstAid IT_Laxative`, `usewith Beer IT_Laxative` → `await Beer 18` (SitBeer, SitSurprise, SpitLeft at the sofa: GetTrickedItem returns the dependency; then the loo rush, t=92) |
| Toilet (IT_Wcpaper, DependsOn → ToiletPaper, NoticeWhenWalkNearby) | PAID 10 | `take ToiletPaper IT_Wcpaper`, `usewith Toilet IT_Wcpaper` → `await Toilet 10` (the ToiletAction visit: ShitNormal, ShitNoPaper, angry, t=~120) |
| ToiletPaper (SearchItem, TrickScore 10 — the "no paper" holder, paid via `GetTrickedItem` → DependsOn when the toilet itself is not Tricked) | PORT #3 | in the original the SAME loo visit pays both: the surprise-near at the blocked toilet on the approach (10) and the paperless use (the holder, 10) — TotalTricksCount is 6 for that reason; the port skips the near-notice during an urgent run, so at most 5 of 6 pay (see PORT #3) |
| Sofa (IT_Saw, UseWoodyAnimationSequence SawSofa x3 = 14.3 s at 13 fps + TrickLaugh) | PAID 25 | `take Drawer IT_Saw`, `park Zone03` (once he sits down again), `usewith Sofa IT_Saw` (sawn during the ~30 s loo trip — the 12.7 s beer run cannot hold the 15.6 s use; the trick lands at the sequence end, Woody.cs:412-416) → `await Sofa 25` (SitDown, SitFall, SofaBlur, t=170) |
| Television (bare hand, NoticeWhenEnterZone) | PAID 15 | `use Television` → `await Television 15` (t=219) |

### Level103 (TotalTricksCount 6, winning 4) — 6/6 paid, 85 points, 16 legs / 0 failed

Routine: Candle, BirthdayCake, BirthdayCake (all Zone03), LetterBox (Zone01);
the "ToiletAction" is the FirstAid kit in Zone04 (`LetterBox.RushToToilet`:
the mousetrapped finger runs to the kit). Zone02 is never visited.

| trick | status | leg |
| --- | --- | --- |
| Candle (IT_Boom, UseAtOtherPlace; BirthdayCake.DependsOn → Candle, RottweilerUseTogglesPrime on the cake) | PAID 25 | `take Drawer IT_Boom` (Boom+Marker+Mousetrap in one take), `usewith Candle IT_Boom` → `await Candle 25` (the candle taken at [0] marks GotTricked, Item.cs:836-838; the cake's use visit plays the dependency's BirthdayExplode; GetTrickedItem returns the Candle) |
| BirthdayCake (own IT_Magnesium branch) | DEAD | no IT_Magnesium source; the cake pays the Candle above |
| MumPicture (IT_Marker, NoticeWhenWalkNearby) | PAID 10 | `usewith MumPicture IT_Marker` → `await MumPicture 10` (crossed on the first-aid rush) |
| Toilet (Neutral, IT_Wcpaper, DependsOn → ToiletPaper) | PAID 10 | `take ToiletPaper IT_Wcpaper`, `usewith Toilet IT_Wcpaper` → `await Toilet 10` (walk-by after the first-aid kit) |
| LetterBox (IT_Mousetrap, RushToToilet) | PAID 20 | `usewith LetterBox IT_Mousetrap` → `await LetterBox 20` |
| Ground@Zone03 (IT_Soap, CauseSlip) | PAID 10 | `take SoapDish IT_Soap`, `usewith Ground@Zone03 IT_Soap` → `await Ground@Zone03 10` |
| Ground@Zone04 | ALT | the one soap went to the kitchen floor |
| Microwave (IT_Egg, NoticeWhenWalkNearby) | PAID 10 | `take Fridge IT_Egg`, `usewith Microwave IT_Egg` → `await Microwave 10` (t=163, the level wins on it) |

### Level104 (TotalTricksCount 7, winning 5) — 7/7 paid, 82 points, 19 legs / 0 failed

Routine: ApplePie (take, CakeAction), Microwave, WhippedCream, ApplePie (eat)
in the kitchen; Deodrant, AfterShave, SinkAftershave, SinkDeodrant, AfterShave,
Deodrant in the bathroom; the hall crossed between them. Deodrant/AfterShave
are Neutral RottweilerUseTogglesPrime shelf items that ship Primed (on the
shelf); his [4]/[5] take them (unprime, GotTricked), [8]/[9] put them back.

| trick | status | leg |
| --- | --- | --- |
| AfterShave (IT_Superglue; SinkAftershave.DependsOn → AfterShave) | PAID 20 | `take Drawer IT_Superglue`, `usewith AfterShave IT_Superglue` (on the shelf) → `await AfterShave 20` (Shave, AftershaveNormal, AftershaveGlue at [6]) |
| Deodrant (IT_Hairrestorer; SinkDeodrant.DependsOn → Deodrant) | PAID 15 | `take FirstAid IT_Shavingfoam` (foam+restorer), `usewith Deodrant IT_Hairrestorer` → `await Deodrant 15` (DeodrantNormal, DeodrantHair at [7]) |
| SinkAftershave / SinkDeodrant / ApplePie (own IT_Magnesium branches) | DEAD | no source; they pay their dependencies (above/below) |
| WhippedCream (IT_Shavingfoam, UseAtOtherPlace, PlayCustomTrickedSequence ShavingCream; ApplePie.DependsOn → WhippedCream) | PAID 15 | `usewith WhippedCream IT_Shavingfoam` → `await WhippedCream 15` (CakeEat, SpitRight at the pie's eat) |
| Toilet (Neutral, IT_Wcpaper) | PAID 8 | `take ToiletPaper IT_Wcpaper`, `usewith Toilet IT_Wcpaper` → `await Toilet 8` (walk-by on the way to the shelf) |
| Microwave (IT_Egg, routine use [1], ReuseAfterFix) | PAID 8 | `take Fridge IT_Egg`, `usewith Microwave IT_Egg` → `await Microwave 8` |
| MumPicture (IT_Marker, NoticeWhenWalkNearby) | PAID 8 | `usewith MumPicture IT_Marker` → `await MumPicture 8` (a hall crossing) |
| Ground@Zone03 (IT_Soap) | PAID 8 | `take SoapDish IT_Soap`, `usewith Ground@Zone03 IT_Soap` → `await Ground@Zone03 8` |
| Ground@Zone04 | ALT | the one soap |

### Level105 (TotalTricksCount 8, winning 6) — 8/8 paid, 79 points, 23 legs / 0 failed

Routine: Piano (Zone02, AlertNext), Football + Window (Zone03, PostponeAlarm),
PlantStink (Zone01); the toilet on the cheese rush. The kitchen is reachable
for Woody only from the living room (the hall stairs cross the plant visit):
`park Zone02` while he is in the kitchen, the side door when he heads for the
piano.

| trick | status | leg |
| --- | --- | --- |
| Football (IT_Bowling; CanUse false + collider off until the piano's last element alerts it — `OnLastSequenceElementPlaying` → `PlayAlertAnimation`, EnableColliderWhenAlerted + the Football CanUse hack, TrickItem.cs:1150-1162; RemoveFromRoutineAfterUseTricked, GiveBowlingBallWhenTricked) | PAID 15 | `take BowlingBag IT_Bowling`, `usewith Football IT_Bowling` (the driver waits by it and fires the click the frame it turns usable, then runs) → `await Football 15` (StartKickBowling, KickBowling, t=97) |
| Window (IT_Bowling, score 0) | DEAD | the one ball goes to the football; scores 0 anyway |
| Phone (Tricked from the start; Mobile SearchItem: GrabDirectly, CauseAlarm, AlarmItem = Phone) | PAID 10 | `take Mobile IT_Handy`, `icon IT_Handy` (the HUD inventory icon: `Item.OnIconPressed` → RaiseAlarm, Item.cs:2176-2205; MobileCall) → `await Phone 10` (TalkPhone once the postponed use ends, t=169) |
| Piano (IT_Marker, ReuseAfterFix; PlayPianoLong after the football, Level105Behavior) | PAID 13 | `take Drawer IT_Marker` (x9999), `usewith Piano IT_Marker` → `await Piano 13` (PlayPianoSmeared) |
| PlantStink (IT_Cheese, RushToToilet) | PAID 13 | `take Fridge IT_Egg` (egg+cheese), `usewith PlantStink IT_Cheese` → `await PlantStink 13` (SniffBad, t=139) |
| Toilet (IT_Wcpaper, not Neutral here) | PAID 7 | `take ToiletPaper IT_Wcpaper`, `usewith Toilet IT_Wcpaper` → `await Toilet 7` (the cheese rush: Puke x3 tricked, angry, t=145) |
| MumPicture (IT_Marker, NoticeWhenWalkNearby, no UseOnce) | PAID 7 | `usewith MumPicture IT_Marker` → `await MumPicture 7` |
| Microwave (IT_Egg, NoticeWhenWalkNearby) | PAID 7 | `usewith Microwave IT_Egg` → `await Microwave 7` |
| Ground@Zone03 (IT_Soap) | PAID 7 | `take SoapDish IT_Soap`, `usewith Ground@Zone03 IT_Soap` → `await Ground@Zone03 7` |
| Ground@Zone04 | ALT | the one soap |

### Level106 (TotalTricksCount 9, winning 7) — 8/9 paid, 68 points, 25 legs / 2 failed (Pudding, PORT #2)

Routine: PhotoAlbum, Candy (Zone02), Pudding (Zone03), BathTub prime (Zone04),
PhotoAlbum, Candy, Pudding, BathTub bath, Towel (Zone04); the toilet on the
candy rush. The tub is filled (Primed) by his own [3] visit and emptied by [7]
(RottweilerUseTogglesPrime, Item.cs:1065-1094): only between them does the
empty bottle fill on it (RubbishBinBottle.RequirePriming, PrimingItem =
BathTub, PrimedInventoryType IT_Fullbottle — Item.cs:1537-1572 → WoodyPrime
1246-1250 `UsedInventory.ChangeType`) and only then does the hair restorer go
in (the 1520 gate).

| trick | status | leg |
| --- | --- | --- |
| Towel (IT_Shoepolish) | PAID 12 | `take Drawer IT_Glue` (glue+marker+polish), `usewith Towel IT_Shoepolish` → `await Towel 12` (BathTowelPolish at [8]) |
| BathTub (IT_Hairrestorer, RequirePriming) | PAID 12 | `take FirstAid IT_Foamballs` (balls+restorer), `usewith BathTub IT_Hairrestorer` (while full) → `await BathTub 12` (BathHair at [7]) |
| Pudding (IT_Fullbottle) | PORT #2 | `take RubbishBinBottle IT_Emptybottle`, `prime BathTub IT_Emptybottle` (the bottle fills: the inventory reads IT_Fullbottle, RubbishBinBottle.primed — verified in the trace), `usewith Pudding IT_Fullbottle` → FAIL "predicate never held": the pudding cannot be clicked in the port (negative collider height, PORT #2); `await Pudding 8` FAIL |
| Candy (IT_Foamballs, RushToToilet) | PAID 8 | `usewith Candy IT_Foamballs` → `await Candy 8` (CandyEat, SpitRight) |
| PhotoAlbum (IT_Glue) | PAID 8 | `usewith PhotoAlbum IT_Glue` → `await PhotoAlbum 8` (PhotoAlbumSticky) |
| Toilet (Neutral, IT_Wcpaper) | PAID 7 | `take ToiletPaper IT_Wcpaper`, `usewith Toilet IT_Wcpaper` → `await Toilet 7` (walk-by) |
| MumPicture (IT_Marker) | PAID 7 | `usewith MumPicture IT_Marker` → `await MumPicture 7` |
| Microwave (IT_Egg, NoticeWhenWalkNearby; not in the routine) | PAID 7 | `take Fridge IT_Egg`, `usewith Microwave IT_Egg` → `await Microwave 7` |
| Ground@Zone03 (IT_Soap) | PAID 7 | `take SoapDish IT_Soap`, `usewith Ground@Zone03 IT_Soap` → `await Ground@Zone03 7` |
| Ground@Zone04 | ALT | the one soap |
| Ground@Zone01 (IT_Knotbook) | DEAD | no IT_Knotbook in the level |

## PORT findings

### 1. Pawn animations ran at 2× — every pawn AnimPlayer was ticked twice per frame (fixed in-tree by the fix agents during this pass)

- C#: `AnimationControllerBase.OnGUI` calls `Refresh()` once per Repaint
  event (cs:172-189); `Refresh` subtracts `Time.deltaTime` once and adds
  `1/FrameRate` per advanced frame (cs:102-142) — a 62-frame pattern at 13 fps
  is 4.77 s, `SawSofa x3` 14.3 s, `SitBeer` (28 fr @10) 2.8 s.
- Port (HEAD `dca965a`, `runtime/world.py` World.tick): `for p in
  self.players.values(): p.tick(dt)` AND `Pawn.tick(dt)` → `self.anim.tick(dt)`
  on the SAME AnimPlayer object (a pawn's player is registered in
  `world.players` and handed to the Pawn, `spawn_pawn`/`spawn_woody`).
  Measured with a tick-count probe: 2 calls per world tick for Woody and the
  Rottweiler, 1 for item players (`git show HEAD:runtime/world.py`, lines
  994 `self.anim.tick(dt)` in Pawn.tick and 5628-5632 / 5675 in World.tick).
  Trace of an early L102 run (its state.jsonl since overwritten by the final
  runs; the numbers reproduce against HEAD): SawSofa 80.08→87.22 = 7.13 s
  for the 14.3 s sequence; SitBeer 1.4 s; AngryHard (67 fr @10 = 6.7 s)
  3.36 s; MakeTrick (12 fr @10 = 1.2 s) 0.56 s. In isolation (`w.anim.tick`
  once per frame) the same sequence took 14.27 s.
- Consequence: every use / angry / sit / walk-animation window was half the
  original's (the neighbour's whole lap ~2× faster than the sheets, Woody's
  uses too); the port's routine timings and the pass-2 verifications were
  measured against that.
- State now: `world.py` World.tick skips pawn players in the `players` loop
  (`if id(p) not in pawn_players`); the driver's rate probe reads 1 — the
  timing model reads the sheets over the measured rate either way
  (`Driver._install_anim_probes` / `anim_rate`).

### 2. A BoxCollider with a negative size component is unclickable in the port — Level106 Pudding (h < 0), Level210 ElephantCricketBat (w < 0)

- Data: Level106 `Pudding` (327) BoxCollider `size = (14.31, 17.69, -14.05)`,
  world scale (0.0375, 1, 0.04), rotation X-90 → the local z is the screen
  height; Level210 `ElephantCricketBat` `size = (-2.21, 8.0, 6.47)`.
- Port: `scene.Level._world_box` (scene.py:1534-1571) keeps the sign of
  `size * scale` (`half = size[j]*ws[j]*0.5`, then `h += abs(axis)*half`) →
  the Pudding's collider tuple is `(4.445, 1.559, w=0.537, h=-0.562, ...)`;
  `Viewer._hit_at` (viewer.py:182-207) tests `abs(wy - c[1]) <= c[3] * 0.5`
  → never true → no click on the pudding ever hits (`_hit_at(c[0], c[1])`
  → `(None, None)`, verified; the driver's leg walks Woody to the floor
  point under it and nothing else happens).
- Original: `Physics.Raycast` against the BoxCollider — the physics shape
  uses the absolute half-extents (Unity's BoxCollider clamps a negative size
  to its magnitude for the PhysX box; the sign only mirrors the gizmo), so
  the pudding takes the bottle click and `PourMilk` pays 8. The fix is a
  `abs()` on the scaled half-extents in `_world_box`.
- Consequence: Level106's Pudding trick (8, TotalTricksCount 9) cannot be
  played in the port; the plan keeps the two legs (they go green with the fix).

### 3. `Routine._update_walking` skips the NoticeWhenWalkNearby run during an urgent action — Level102's loo visit pays one trick, the original pays two (TotalTricksCount 6)

- C#: `Pawn.WalkOnPath` calls `UpdateWalking()` on every walk step
  (Pawn.cs:981) — urgent moves included; `Rottweiler.UpdateWalking`
  (cs:833-849) starts `SurpriseActionNear` for a raw-Tricked item within
  NoticeWhenNearTrickedDistance; `ActionManager.StartUrgentAction`
  (cs:651-721) accepts it during another urgent action and chains
  `action.OriginalAction = ActiveAction` (cs:715-718; a running
  RoutineActionMove is stopped and its NextAction becomes the ActiveAction,
  cs:662-667), so the interrupted toilet use resumes after the surprise's
  angry set (StopUrgentAction).
- Port: `world.py` `Routine._update_walking`: `if ... or self.urgent_item is
  not None: return` — the near check is off for the whole urgent run
  (the toilet rush, an alarm run, a surprise-far run).
- Level102 as shipped: the toilet blocked with the roll (Toilet.Tricked raw)
  AND the roll gone (ToiletPaper Tricked+GotTricked). His loo rush walks him
  onto the toilet's TargetLocation (-4.42, he stops there): the original
  fires the near surprise (10, the Toilet; CanFix fixes it), then the
  resumed ToiletAction use plays the dependency's `ShitNormal, ShitNoPaper`
  and `GetTrickedItem` returns the holder (10, the ToiletPaper SearchItem,
  TrickScore 10) — 6 tricks, the level's TotalTricksCount. The port pays the
  Toilet's use (10) only: 5 of 6 (`/tmp/nfh-tricks-s1a/s1_Level102/
  state.jsonl`: `tricks` ends at 5, the win at 4 is reached; the all-done
  end never is). L103/L104/L106's Neutral toilets still pay because he
  walks past them on ordinary routine legs (or on the way back after the
  urgent use, when `urgent_item` is cleared).

## KNOWN (open bugs hit by this group)

- None blocked a leg. The "WasPriming never written" bug (angry on the prime
  visit) did not change any score here: L103's cake pays the Candle at one
  of the cake visits either way; L106's tub is primed by his [3] visit and
  the bottle/restorer land in the [3]-[7] window as planned.

## Data facts worth keeping (no divergence)

- L102: after the laxative beer the sofa keeps replaying the beer scene and
  the loo rush on every sit (the Beer has no CanFix; TryFix → FuckedUp, but
  `Sofa.IsTricked()` reads `DependsOn.Tricked && GotTricked`, TrickItem.cs:
  258-261, and nothing clears the beer's flag) — in the C# too.
- L102's Sofa: `SawSofa x3` = 14.3 s + TrickLaugh, non-blocking (Blocking
  false on the sheet), so Woody is catchable throughout; the beer run frees
  the room for ~12.7 s, the loo trip for ~30 s — the saw needs the trip.
- L105's Football: usable only after the piano's AlertNext (the ball rolls
  in as the last piano element starts); a smeared piano suppresses the alert
  that visit (`!IsTricked()`, Rottweiler.cs:256-263) — the plan swaps the
  ball before smearing the piano.

## Driver changes (tests/run_tricks.py)

All small and localized; the plans of L101 (12/12) and the other groups were
re-run green after each.

- `routine_zones` also counts the serialized ToiletAction's zone (the
  bathroom is not a parking spot in the loo-rush levels).
- `door_time(door, p)`: the catcher's door pass by door type — flat 2.0 s
  (Leave and Enter play at once, 20 fr @10), walk-up 3.5 s — instead of the
  flat 4.0 s that read the side doors 2× long (the flee came when he was
  already through). `woody_door_time` (4.4 walk-up / 2.5 flat), path-based
  `woody_need`, USE_TIME 3.5, MARGIN 1.5; `use_time` uncapped (the 14.3 s
  saw is real).
- `eta_to_zone`: the walk to each door of the actions-ahead path; a use in
  progress (`_anim_left`) counted BEFORE the live steps (a surprise/toilet
  detour pauses him with his route still queued); the urgent detour and the
  interrupted routine action travelled and used before the actions ahead
  (`ahead`), the about-to-start use of an item he has just reached; a
  per-item `use_len` (his use sequence for the item's tricked state plus
  the angry set by the meter — AngryEasyUp cold, AngryEasyDown+AngryHard
  hot — and the fix); the loo rush foreseen after a tricked RushToToilet
  use (`_rush_target`); `after=` reads a catcher standing in a zone but
  leaving before the caller cares by his return.
- `_install_anim_probes` / `anim_rate`: the pawn AnimPlayer tick rate per
  world tick, measured; `_anim_left`, `use_len`, `use_time` divide the sheet
  times by it (PORT #1).
- The dodge: the flee route by the catchers' slack (`_flee_target`, since
  extended by other groups), the exit time from the route's first door; no
  flee while climbing into a door pass (DOOR_CLIMB/DOOR_ANIM), none mid-use
  when the use ends before the catcher arrives (`_anim_left`), the
  route-ahead occupancy time-aware (`_dwell` — a catcher walking out before
  Woody reaches the door does not block; `_woody_door_eta`), the sealing
  flee only with slack left and only when a catcher will actually come here
  (`coming`), a route through the door pair a catcher is passing skipped,
  the `heading` set reads the urgent item.
- `_stage_toward` / `wait_gate` / `click_point`: while a leg's gate is shut
  Woody stands at the foot of the route's first door (0.75 past its
  collider) — the way a player waits at the stairs.
- `_escape_slack` in `gate_open`: a dead-end target (the bathroom) is not
  entered when the way back out seals while Woody is still inside.
- `wait_until(fire=)` + `_use_leg`: an item not usable yet (CanUse false /
  collider off) is clicked the frame it turns usable, gate or not (L105's
  football); `_woody_free`: no poke/staging click on a Woody mid-use (a
  re-click restarts the use — the 3x SawSofa was restarted by the 8 s poke).
- `leg_icon` — `icon <Type>`: the HUD inventory icon click
  (`HUD.check_click` → `Item.OnIconPressed`; L105's mobile).
- `leg_park` gated and re-clicked; `leg_prime` succeeds on the SOURCE
  priming when the held type's source needs it (L106's bottle); `in_use_now`
  reads the urgent item.
