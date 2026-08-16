# Pass 3 — the trick matrix, group s2a: Level201 … Level207

Plans: `tests/plans/s2/Level201.txt` … `Level207.txt`. Driver:
`tests/run_tricks.py` (`SDL_VIDEODRIVER=offscreen python3 tests/run_tricks.py
tests/plans/s2/Level20X.txt --out=/tmp/nfh-tricks-s2a`). Traces:
`/tmp/nfh-tricks-s2a/s2_Level20X/{results.json,state.jsonl}` (the last run of
each plan, made with the runtime as of the end of the pass — the fix agents
changed it under the runs several times: the animation double-tick, the
Collider.enabled byte).

Season 2 particulars that shape every plan (all read from the source and the
data): every S2 `TrickScore` is 0 (`GameInfo.CalculateScore`'s NFH2 formula
counts completed tricks), so every `await` asserts `0` and the pay is read
from `GameInfo.TrickDone` (`completed`); Woody runs everywhere (no sneak);
transitions are walked (README "The walk-through stairs"); the Mother catches
on 206/207 (`GameInfo.cs:222-224`); the tutorial layer of 201 is unported;
205 runs on the mutex handshake; the anger ladder is NFH2.

## Status per level

Status legend: PAID (the leg `await <Item> 0` passed — `Item.OnTrickDone`
paid it into `GameInfo.TrickDone`), MANUAL (a `tutorial n` leg: the unported
LevelScript action applied by the driver), KNOWN (the open-bugs list), PORT (a
finding below), DRIVER (the driver cannot do what a human can), DEAD (not
reachable by the data — listed once per level with the reason).

### Level201 — the NFH2 tutorial (TotalTricksCount 4, winning 3) — 4/4 paid, 18 legs / 0 failed

| trick | status | leg |
| --- | --- | --- |
| WaterPuddle (IT2_Soap, Primed at load, RottweilerUseTogglesPrime) | PAID | `usewith WaterPuddle IT2_Soap` → `await WaterPuddle 0` |
| Buffet (IT2_Knife from the hairpin → ToolBox dexterity; PawnToAffectWhenTricked Olga, DontUseOn) | PAID | `unlock ToolBox IT2_Hairpin`, `take ToolBox IT2_Knife`, `usewith Buffet IT2_Knife` → `await Buffet 0` |
| DeckRail (IT2_Pipetongs; DependsOn/linked WaterPuddle) | PAID (alone) | `usewith DeckRail IT2_Pipetongs` → `await DeckRail 0` |
| CaptainHat (IT2_Spaghetti) | PAID | `usewith CaptainHat IT2_Spaghetti` → `await CaptainHat 0` |
| the tutorial gates | MANUAL ×5 | `tutorial 1` (UnfreezeNeighbor), `tutorial 5` (VanityBag), `tutorial 12` (DeckRail), `tutorial 14` (CaptainHat + unfreeze), `tutorial end` |
| CaptainHatHook (IT_Fartbag, Neutral, no collider) | DEAD | no fart-bag source in the level, no collider |

Notes. The neighbour's `ActionManager.Frozen` ships true, `VanityBag`,
`DeckRail`, `CaptainHat` ship `Locked`, and only `LevelScriptAction`
1/4/9/14 (`UnfreezeNeighbor`) / 5/12/14 (`ItemsToUnlock`) open them
(LevelScriptAction.cs:110-160); the routine's action [5] is the script's
`FreezeAfterCompletion` park (`ActionManager.cs:539-543`) that
`TutorialScriptCameraNFH2` juggles (`AddAction`/`RemoveAction`,
cs:213-249). Without the layer nothing in this level ever pays, so the
driver's `tutorial n` applies the serialized action's effects (a manual
step in the results) and `tutorial end` drops the park action the way
`TutorialScriptCameraNFH2.End1` leaves the routine. The script's linked
demonstration (a second soap on the puddle after `WaterPuddle.UseOnce =
false`, TableTrick2 state) is not reproducible: `WaterPuddle` is `UseOnce`
and `Fix` leaves `Used` (Item.cs:2063-2118) — the second soap is refused
(`Item.cs:1654-1669`), the rail pays alone at action [3] (`Tricked &&
!Neutral`, TrickItem.cs:260). Total 4 reached, the level wins.

### Level202 (TotalTricksCount 5, winning 3) — 3/5 paid, 18 legs / 4 failed (all KNOWN)

| trick | status | leg |
| --- | --- | --- |
| Swimming via Submarine (IT2_Fin; `SetTrickedOnItem`) | PAID | `usewith Submarine IT2_Fin` → `await Swimming 0` |
| Pond + BridgeRail linked (IT2_Sandbucket primed on EelBox → IT2_Sandbucketeel; IT2_Sawfish) | PAID ×2 | `prime EelBox IT2_Sandbucket`, `usewith Pond IT2_Sandbucketeel`, `usewith BridgeRail IT2_Sawfish` → `await BridgeRail 0` (final `completed` 3) |
| BeerMat (IT2_Crayfish, RottweilerUseTogglesPrime) | KNOWN — blocked by the CrayFish dexterity take | `unlock CrayFish IT2_Reed` ok, `take CrayFish IT2_Crayfish` FAIL "no IT2_Crayfish after take" |
| Rake (bare-hand trick + IT2_Weed compound) | KNOWN — "Drawing/Rake tricks never go angry" | `use Rake` ok, `usewith Rake IT2_Weed` ok, `await Rake 0` FAIL "trick never paid" |
| Fence1 / Fence2 / Rocks (IT2_Knife) | DEAD | no knife source; the 15x10 fence boxes ship `Collider.enabled=false` (see PORT 1) |
| OlgaMat (IT2_Crayfish, Olga's routine only), BridgeRailFront (Neutral), EelBox as a trick (IT_Detergent) | DEAD | collider off / not in the neighbour's routine / no source |

Notes. The CrayFish is `Dexterity` with `DexterityUnlocker IT2_Reed` and a
junk `RequiredInventory IT_Fuel`: after the won game the port continues
into the else-cluster of `CanWoodyUse` and refuses on the never-held
IT_Fuel (world.py `_can_woody_use`, the `dex == 'done'` fall-through into
the RequiredInventory gate), where the C# `if/else if/else` chain skips
that cluster on the dexterity branch (Item.cs:1438-1507 vs 1652-1700) —
the KNOWN "dexterity win does not take the item". A re-click without the
reed is refused in the original too (IT_Fuel is never held), so the win is
the only take. The Rake's bare-hand click lands (`Tricked`), the weed
compound lands (`CompoundTricked`), and the neighbour's Rake action goes
straight to `_finish()` without the postponed angry (world.py, the Rake
branch of `Routine._use`; Rake.cs:3-11 → `StopCurrentAction(true)` →
`StopAction` → `IsTricked()` → `PlayAngryAnimation`) — KNOWN.

### Level203 (TotalTricksCount 5, winning 3) — 5/5 paid, 16 legs / 0 failed

| trick | status | leg |
| --- | --- | --- |
| Microphone via DieselGenerator (IT2_Tights from OlgaBag, bare dexterity; `ActivateItemTrick`) | PAID | `unlock OlgaBag`, `usewith DieselGenerator IT2_Tights` → `await Microphone 0` |
| ToiletPaper (IT2_Piripiri) | PAID | `usewith ToiletPaper IT2_Piripiri` → `await ToiletPaper 0` |
| ToiletFlush (IT2_Oilcan) | PAID | `usewith ToiletFlush IT2_Oilcan` → `await ToiletFlush 0` |
| Watermelon (IT2_Cannonball; DependsOn Bicycle) | PAID | `usewith Watermelon IT2_Cannonball` → `await Watermelon 0` |
| Bicycle (IT2_Wrench) | PAID | `usewith Bicycle IT2_Wrench` → `await Bicycle 0` |
| Toilet (IT2_Sawfish), MicrophoneStage (IT2_Crayfish), Microphone's own click, ToiletRocket, DictatorPhoto | DEAD | no source in the level and/or `Collider.enabled=false` |

The level wins (all 5) — the driver used to read the win as a catch and
restart four times; `run_plan` now ends the plan on `GameInfo.Won`.

### Level204 (TotalTricksCount 6, winning 4) — 6/6 paid, 20 legs / 0 failed

| trick | status | leg |
| --- | --- | --- |
| Karate (IT2_Brick) | PAID | `usewith Karate IT2_Brick` → `await Karate 0` |
| GongDrumstick (IT2_Sunshade) | PAID | `usewith GongDrumstick IT2_Sunshade` → `await GongDrumstick 0` |
| PullKart (IT2_Rice_full: RiceBowl x2 primed on GongGrease; PawnToAffectWhenTricked Olga) | PAID | `prime GongGrease IT2_Rice_empty`, `usewith PullKart IT2_Rice_full` → `await PullKart 0` |
| JadeNecklace + Vase linked (IT2_Scissors x2; IT2_Rice_full's second use) | PAID ×2 | `usewith Vase IT2_Rice_full`, `usewith JadeNecklace IT2_Scissors` → `await JadeNecklace 0`, `await Vase 0` |
| HotDog (IT2_Confetti: ToyDispenser bare dexterity → teddy primed on OlgaKid) | PAID | `unlock ToyDispenser`, `prime OlgaKid IT2_Teddy`, `usewith HotDog IT2_Confetti` → `await HotDog 0` |
| GongMan (IT2_Crayfish), OlgaKid as a trick (IT_Detergent), GongGrease as a trick (IT_Emptybottle) | DEAD | no source / collider off; the last two are only priming targets |

### Level205 (TotalTricksCount 5, winning 3) — 2/5 paid, 19 legs / 4 failed (PORT 2)

| trick | status | leg |
| --- | --- | --- |
| Chef via Eals (IT2_Tube; `SetTrickedOnItem`) | PAID | `usewith Eals IT2_Tube` → `await Chef 0` |
| Rockets (IT2_Rope) | PAID | `usewith Rockets IT2_Rope` → `await Rockets 0` |
| WaterSkiis (IT2_Tools; Primed at load, RottweilerUseTogglesPrime) | PORT 2 — tricked, never used again | `usewith WaterSkiis IT2_Tools` ok, `await WaterSkiis 0` FAIL |
| SandSculpture (IT2_Lionhead: Glasses primed on the tricked LionStatue) | PORT 2 — tricked, never used again | `usewith LionStatue IT2_Bangers`, `prime LionStatue IT2_Glasses`, `usewith SandSculpture IT2_Lionhead` ok, `await SandSculpture 0` FAIL |
| TabbleTennis (IT2_Egg, DuckCage bare dexterity; PawnToAffectWhenTricked Olga) | PORT 2 — the neighbour parks in its zone for good | `usewith TabbleTennis IT2_Egg` FAIL "zone never clear" |
| Fence1/Fence2, BridgeRailFront, WaterSkiisAux, RocketsBackground, OlgaKid, OlgaMatBeach as a trick, Chef's own click (IT_Fuel), LionStatue alone (not in the routine) | DEAD | colliders off / no source / priming target only |

The plan is ordered by the neighbour's first lap (the only lap the port
plays, see PORT 2): Chef at ~64 s, Rockets at ~94 s, SandSculpture at
~112 s — the driver reached the Eals and the Rockets in time; the skis
(action [2] at 27 s) and the sculpture were tricked after their visits and
never revisited.

### Level206 (TotalTricksCount 6, winning 4) — 5/6 coins paid, 17 legs / 7 failed

| trick | status | leg |
| --- | --- | --- |
| Pillows (IT2_Fartbag; ActivateItemTrick → DeckChair) | PAID | `usewith! Pillows IT2_Fartbag` (the rush: action [2] is his ONE Pillows visit at ~18 s) → `await Pillows 0` |
| DeckChair (armed by the Pillows; PawnToAffectWhenTricked Mother) | PAID | `await DeckChair 0` |
| Harpoon (IT2_Rubber, Neutral, RottweilerUseTogglesPrime) + LaunchPad (IT2_Rabbit, RequireUnprime) linked | PAID ×3 (the pair + `ExtraCoin206Calculation`) | `usewith Harpoon IT2_Rubber`, `usewith LaunchPad IT2_Rabbit` → `await Harpoon 0`, `await LaunchPad 0` (completed 3 → 5) |
| Weights (IT2_Fleablanket from the FleaBlanket, Zone04) | DRIVER/DATA — Zone04 sealed (below) | `take FleaBlanket IT2_Fleablanket` FAIL "zone never clear" |
| DynamiteBox (IT2_Kukident, DentureAdhesive bare dexterity, Zone04) | DRIVER/DATA — Zone04 sealed | `unlock DentureAdhesive` FAIL "zone never clear" |
| DogFifi / DeckChair as clicks, DeckChairThrow/Call/Order, FifiHarpoon/FifiWeights/Drop/Grab | DEAD | `Collider.enabled=false` (the fart bag goes into the Pillows) |

Zone04 (FleaBlanket, DentureAdhesive) is never clear in the port's run:
the Mother stands awake there from 2.5 s (DeckChairThrow → Call → Order →
DeckChair), her infinite poses (`MotherStandDownInfinite`,
`MotherLookLoop`, InfiniteLoop in the data) are released only by the
neighbour's DeckChair actions [1]/[3] (`PawnToStopInfiniteAnimation`,
RoutineActionUse.cs:160-163 / 334-337), and those run once
(`LoopFromSelectedIndex`, `ActionSelectedIndex 4`: the routine wraps to
[4], AdvanceActionIndex, ActionManager.cs:566-584); after the DeckChair
trick's `RunToHitPawn` her manager restarts at [0] and parks at [1]'s
`MotherStandDownInfinite` for good (trace: `Moth usi DeckChairCall
MotherStandDownInfinite` from 92 s to the end). Her 58 s sleep
(`MotherSecondUse`) never comes, so the two Zone04 pickups have no window
— the C# reads the same, so this is not filed as a PORT finding; the level
is won at 5 ≥ 4 without them. A human has no better window than the
driver.

### Level207 (TotalTricksCount 7, winning 5) — 4/7 paid, 25 legs / 6 failed (all KNOWN)

| trick | status | leg |
| --- | --- | --- |
| PoolBoard (IT2_Spring; PawnToAffectWhenTricked Mother) | PAID | `usewith PoolBoard IT2_Spring` → `await PoolBoard 0` |
| PoolAwning (IT2_Pedal; Locked + collider off until the tricked board's use: `ItemsToUnlockWhenTricked`, PoolJumpBehavior frame 6) — linked with a second spring on the board | PAID | `usewith PoolAwning IT2_Pedal`, `take MopedPool IT2_Spring`, `usewith PoolBoard IT2_Spring` → `await PoolAwning 0` |
| BeachTowel (IT2_Hedgehog) | PAID | `usewith BeachTowel IT2_Hedgehog` → `await BeachTowel 0` |
| Elephant (IT2_Bucket: Whisky primed on the Bartender → the IceBucket unlocked and re-armed (Item.cs:1274-1281) → the empty bucket primed on the Tap) | PAID | `prime Bartender IT2_Whiskey`, `take IceBucket IT2_Bucket_empty`, `prime Tap IT2_Bucket_empty`, `usewith Elephant IT2_Bucket` → `await Elephant 0` |
| Shell (IT2_Crayfish; PawnToAffectWhenTricked Olga) | KNOWN — blocked by the CrayFish dexterity take | `unlock CrayFish IT2_Bbqtongs` ok, `take CrayFish IT2_Crayfish` FAIL |
| SandCastle (IT2_Crayfish; linked BeachTowel; ExtraCoinLinkedTrick) | KNOWN — the crayfish; the second TrickDone is on the KNOWN list too | `take CrayFish IT2_Crayfish` FAIL |
| Fence1/2, PoolLadder, BeachLogo (IT2_Knife), DeckChair (IT2_Fartbag), ShellLaydown, Pole, Tap/Bartender as tricks, ElephantBucket | DEAD | colliders off / no source / priming targets / ActivateItemTrick target |

## PORT findings

### 1. Item colliders that ship `enabled: false` took clicks — fixed during the pass

221 items serialize a `BoxCollider` with `enabled: false` (every S1
SlipperyGround strip, the S2 fences, Level206's DeckChair/DogFifi/Fifi*
poses, Level207's PoolLadder/BeachLogo/PoolAwning/Pole, Level202's
Fence1/Fence2/Rocks/OlgaMat/Swimming/BridgeRailFront …). `Physics.Raycast`
never returns a disabled collider, so `Helpers.GetItemFromCollider`
(Helpers.cs:138-141) never sees them; the port initialized
`Item.clickable = True` for every item regardless of the byte and its
raycast (`Viewer._hit_at`, the collider nearest the camera wins) picked
them: on Level202 the click at the RubbishBin's centre resolved to
`Fence1` (a 15x10 box at z=-0.05 covering the whole yard) — "use Fence1" —
and every plan of this group failed its first `take`. Evidence:
levels/s2/Level202.json BoxCollider of GO 46 (`Fence1`) `{"enabled":
false, "size": [15, 8, 10]}` vs. RubbishBin (`enabled: true`, z=-0.001);
the first `/tmp/nfh-tricks-s2a` run of Level202 (18/18 legs failed, Woody
never left the entrance). The fix agents took it: `runtime/scene.py`
`_link_item_sprites` now sets `it.clickable = bool(b.get('enabled',
True))`. The driver keeps `_apply_collider_enabled()` as a no-op mirror
from the data.

### 2. Level205's mutex handshake dead-locks after the first lap — Olga's use never ends on the item's `UseNormalSequence`

C#: `TrickItem.PlayOlgaAnimation` (TrickItem.cs:964-975) plays the item's
`UseNormalSequence` with `olga.OnItemAnimationSequenceEnded` as the
sequence delegate (`PlayUseAnimation(Func<bool>)`, cs:982-994 →
`AnimationControllerBase.PlayAnimationSequence(seq, alternateOnSequenceEnded)`,
cs:312-320, consumed at the drain, cs:243-246); `Olga.OnItemAnimationSequenceEnded`
(Olga.cs:154-158) stops Olga's CURRENT action (`ActionManager.CurrentAction.StopAction(true)`).
On Level205 the mat item's sequence is `[Extra1, UseNormal (InfiniteLoop, 91 fr),
Extra3, Extra2]` and the neighbour's mutex action [0] releases that loop
(`ItemToStopInfiniteAnimation`, RoutineActionUse.cs:152-155) — with the mutex
never running `OnActionStopped` (`AbortActiveMutex`, cs:127-134) the ignore
flag leaks and the item's sequence drains ~14 s after every Olga mat use.
That drain is what stops Olga's tennis mutex (`RoutineActionUse.StopAction`'s
`Finished = true` for a non-Rottweiler owner) and sends her back to the mat;
her mat stop is what aborts the neighbour's mat mutex
(`PawnToAbortMutexOnFinish`, cs:342-351). Without it the second lap
dead-locks: he parks on the mat mutex waiting for her mat stop, she parks on
the tennis mutex waiting for his tennis stop.

Port: `Routine._use` ends every pawn's use when the PAWN's own
sequence drains (`self.pawn.anim.play_sequence(list(seq), on_end=self._finish)`,
world.py ~2517) and `World.play_use_item_anim` (world.py ~5292) plays
the item's `UseNormalSequence` with no `on_end` — nothing ever calls the
Olga stop for the item's drain. Trace (`/tmp/nfh-tricks-s2a/s2_Level205/state.jsonl`,
last run): `Rott usi OlgaMatBeach WaitWatch` + `Olga usi TabbleTennis
EatChinese` from t=128.95 s to the end of the run (760 s); the neighbour's
lap 1 (WaterSkiis 26.8, Chef 64.1, Rockets 94.1, SandSculpture 111.8) is
the only lap. Consequence for the matrix: WaterSkiis and SandSculpture,
tricked after their lap-1 visits, are never used again ("trick never
paid"), TabbleTennis' zone is never clear — 3 of the 5 tricks unreachable
after ~130 s. Fix: play the item's use-normal sequence for an Olga use with
an on_end that stops Olga's current action (a `_finish`-like call on her
routine), and keep the leaked ignore flag as it is.

### Observations (not filed as PORT — the C# reads the same)

- Level206's Zone04 seal (above): the Mother's infinite poses have no
  release after the neighbour's one-shot DeckChair actions; Weights and
  DynamiteBox have no window in the port's run.
- Level201's linked demonstration depends on the tutorial script's
  `WaterPuddle.UseOnce=false` toggle (TutorialScriptCameraNFH2 TableTrick2);
  the plain data pays the rail alone.
- The neighbour's routines of 205 (mutex) and 206 (LoopFromSelectedIndex)
  make several tricks first-lap-only races; `usewith!` (the rush leg) is
  what a human's judgement call looks like in the plan language.

## KNOWN (open bugs hit by this group)

- dexterity win does not take the item — CrayFish on 202 (BeerMat) and 207
  (Shell, SandCastle): the port runs the else-cluster's RequiredInventory
  gate after the won game (the junk `IT_Fuel`/`IT_Foamballs` refuses).
- Drawing/Rake tricks never go angry — 202's Rake pays nothing.
- L207 SandCastle ExtraCoinLinkedTrick second TrickDone — behind the
  crayfish, untested.
- crab zone animations 202/207 — not exercised by the plans.
- WasPriming never written — the BeerMat/WaterSkiis prime visits would
  show it; the skis were never revisited (PORT 2), the mat is behind the
  crayfish.
- the animation double-tick (every pawn animation at 2x FrameRate) was
  live during the first half of the pass and fixed by the fix agents mid-way
  (`World.tick`'s item pass no longer ticks the pawn players): all timing
  conclusions above are from runs after that fix.

## Driver changes (tests/run_tricks.py)

- `tutorial <n>` / `tutorial end` legs (`leg_tutorial`): the serialized
  LevelScript action's `DoorsToUnlock` / `ItemsToUnlock` / `ItemsToLock` /
  `DoorsToLock` / `UnfreezeNeighbor` (only when the manager is frozen —
  the script completes those with the neighbour parked) and the
  TutorialScriptCameraNFH2 End1 removal of the FreezeAfterCompletion park
  action; recorded as MANUAL (ok=None).
- `prime <Item> <Type>`: success also when the held type's SOURCE item
  primes (Item.cs:1537-1573 — the Sandbucket on the EelBox, the RiceBowl on
  the GongGrease, the Glasses on the LionStatue, the Whisky on the
  Bartender, the IceBucket on the Tap).
- `unlock <Item>` without a type / `IT_NONE`: the bare-handed dexterity
  game (OlgaBag, ToyDispenser, DuckCage, DentureAdhesive).
- `look_at`: the free camera scrolls onto the click target (the S2 yards
  are wider than the view; clicks past the window / in the HUD strip were
  swallowed by `handle_click`).
- `_apply_collider_enabled`: the data's `Collider.enabled` mirrored at load
  and restart (PORT 1, since fixed in scene.py; kept as a no-op).
- `free_floor_x`: floor clicks (`click_zone` / `click_point`) avoid item and
  door hitboxes (Level203's DieselGenerator box over Zone03's centre turned
  a walk into a climb-and-refuse).
- `_click` guard: no click while Woody is on a walk-through transition
  (`DonePassingToOtherZone` latched, lifts after 4 s) — a mid-stairs re-click
  fed the Helpers.StepIndex statics a shape that expanded a hop to no steps
  (Woody walked from Zone02 to x=-3.7 with his zone unchanged, then climbed
  to a Zone03 item from below).
- S2 pass times: `woody_door_time` / `door_time` know the walked
  transitions (flat ~1.0/1.6 s, stairs ~1.5/4 s) instead of the S1 door
  animations; `use_time(item)` reads Woody's use animation length instead
  of a flat 5 s (the rake's 0.3 s TakeRight kept the Zone02 gate shut).
- `eta_to_zone`: a frozen manager and a parked MutexAction do not come
  (Level201's park, Level205's mat); Urgent actions ahead are approached
  at the run speed (Level206's DeckChair/Pillows legs).
- `in_use_now` counts catcher routines only (Olga sits in Level204's
  PullKart for good; the grease still goes on the axle).
- `sleep_left` off-by-one: the sleep window `[start, end)` on the
  post-increment stamp covers elements start-1..end-2 — the old sum
  included the get-up / pool-leave element (Level207's Mother read 5.6 s
  too long and Woody was mid-trick when she climbed out).
- `_dodge_tick`: the flee threshold carries `MARGIN`; a trapped Woody
  (no safe route) takes the wardrobe/pipe as soon as a catcher is < 8 s
  away; `safe_zone`'s fallback (every zone on some routine — the S2
  yards) picks the zone the catchers reach last, not the nearest (which
  was the Mother's own zone on 207).
- `_detour_toward` (in `wait_gate` and the poke phase): on the four-zone
  rings a BFS route may run through the neighbour's room while the other
  way round is free — walk to the free neighbouring zone first
  (Level201's deck rail from Zone01 via Zone02, Level203's toilet flush).
- `run_plan`: the win (`GameInfo.Won` + `ending`) ends the plan instead of
  counting as a catch (Level203 restarted four times on its own win).
