# Pass 3 — the trick matrix, group s1c: Level111 … Level114

Plans: `tests/plans/s1/Level111.txt` … `Level114.txt`. Driver:
`tests/run_tricks.py` (`SDL_VIDEODRIVER=offscreen python3 tests/run_tricks.py
tests/plans/s1/Level11X.txt --out=/tmp/nfh-tricks-s1c`). Traces of the last
run of each plan: `/tmp/nfh-tricks-s1c/s1_Level11X/{results.json,state.jsonl}`
(copies: `/tmp/nfh-tricks-s1c/L11X_results_final.json`; the click-by-click
logs of the debug runs: `/tmp/nfh-tricks-s1c/dbg_L11X.log`). Final tally:
**L111 33 legs / 1 failed, L112 30 / 1, L113 24 / 2, L114 27 / 0 (+2 manual)
— 0 restarts everywhere, every level inside its 10-minute clock; 30 of the
35 scoring tricks the levels count (TotalTricksCounts 8+10+8+9) are PAID at
the C# score** (L111 7/8, L112 9/10, L113 7/8, L114 7/9). The five misses:
one PORT finding (L111's Vacuum: the dog-alarm yell never fires when he
arrives from another zone), three tricks dead in the shipped data (L112's
GroundSkates, L113's ElectricTrap, L114's Gramaphone + Pipe — the last two
recorded as `manual`), all below.

The house is the same in all four levels: Zone01 the hall (entrance from
Zone05, the street; the Wardrobe HideItem, the Drawer), Zone04 a dead end
off the hall (FirstAid), Zone03 the kitchen (side door to Zone02, back door
to the hall), Zone09 the basement (a dead end off the hall), Zone02 the
living room (the hall's back door, the kitchen's side door, the back door up
to Zone06), Zone06 the bedroom (the Bed HideItem; dead ends Zone07 the
balcony and Zone08 the study). Facts that shaped the plans (each read from
the source and the data):

- ONE bag of marbles per level (`Drawer` hands `IT_Marbles` once,
  SearchItem.cs:167-201; the first use spends it, TrickItem.cs:277-282), so
  the 8-9 `GroundMarbles` strips of a level are mutually exclusive: each plan
  pays the one on a walk he makes (NoticeWhenNearTrickedDistance is 0.1, he
  must cross the strip's x). The `SlipperyGround` GroundItems score 0.
- The `DependsOn` victims pay as their chain, once (`RoutineActionUse.
  GetTrickedItem`, cs:556-570): the victim's own `RequiredInventory` has no
  source in the level (L113: IT_Honey / IT_Spring / IT_Glue; L112's Yoga:
  IT_Football; L114's GoldCup shares the Polish's munition) — those branches
  are dead data and the level's TotalTricksCount counts each chain once
  (12 scoring items → 8 in L113, 11 → 10 in L112, 9 → 9 with the GoldCup
  folded into the Polish in L114). Which item's `OnTrickDone` fires depends
  on `ForceFixOriginal` on the dependency (L113's valves have it → the Sink
  / Radiator pay their own; the FuseBox / ChairAssemblyBook / Polish /
  YogaBook do not → they pay).
- `Neutral` items (`TrickItem.IsTricked` false, cs:260) never go angry
  through StopAction: L111's DirtyCarpet is the trigger of the Vacuum trick
  (Item.cs:847-852, the fetch), its own TrickScore 15 dead (TotalTricksCount
  8 = 9 items − the carpet); L113's FuseBox and ValveMain pay through their
  dependants; the Aquariums score 0.
- `RequirePriming + RottweilerUseTogglesPrime` (Item.cs:1520-1535) refuses
  Woody until the neighbour's prime visit: L111's Iron / Airer, L113's
  FuseBox, L114's Pipe / Gramaphone. The driver's `use`/`usewith` legs now
  wait for that prime where Woody stands (the bed he hid in) — see driver
  changes.
- The dogs (Alerter): L111 and L113 in Zone02, L114 in Zone06 — the driver
  auto-sneaks in and into those rooms; the L112 dog is inactive.

## Status per level

Status legend: PAID n (the leg `await <Item> n` passed: `Item.OnTrickDone`
paid n into `GameInfo.TrickDone`, attributed per item by the driver), PORT
(a finding), DEAD (unreachable in the shipped data), MANUAL (recorded as
such in the plan), ALT (the mutually exclusive twin), TRIGGER (no score of
its own).

### Level111 (TotalTricksCount 8, winning 5) — 7/8 paid, 71 points, 33 legs / 1 failed

Routine (~110 s a lap): Detergent (Z03) → WashingMachine ×3, Drier ×3 (Z09,
the RequireUnprime trios: prime / use / unprime) → Iron (Z06) → Airer (Z07)
→ FishTank (Z08) → Airer → Iron. The upstairs dead ends are safe only while
he is in the kitchen/basement, the basement only while he is upstairs; the
plan works the two halves in alternate laps and hides in the bed for the
Iron/Airer lap.

| trick | status | leg |
| --- | --- | --- |
| FishTank (IT_Detergent) | PAID 10 | `take Detergent IT_Detergent` (Z03, after his [0]), `usewith FishTank IT_Detergent` (Z08 in lap 3, right before his Iron lap — the long tricked use is what widens the Airer window) → `await FishTank 10` |
| WashingMachine (IT_Winebottle, RequireUnprime) | PAID 10 | `take WineCellar IT_Winebottle`, `usewith WashingMachine IT_Winebottle` (basement, lap 2 while he is upstairs) → `await WashingMachine 10` (paid at the trio's use visit) |
| Drier (IT_Tongs, RequireUnprime) | PAID 10 | `take BasementDrawer IT_Tongs`, `usewith Drier IT_Tongs` → `await Drier 10` |
| ElectricTrap (IT_Cable, NoticeWhenWalkNearby) | PAID 11 | `take RubbishBinCable IT_Cable`, `usewith ElectricTrap IT_Cable` (x=2.06, on his door(2.21) → WashingMachine walk) → `await ElectricTrap 11` |
| GroundMarbles@Zone09 (IT_Marbles) | PAID 7 | `take Drawer IT_Marbles`, `usewith GroundMarbles@Zone09 IT_Marbles` (x=1.27, the same walk) → `await GroundMarbles@Zone09 7` |
| GroundMarbles × 7 elsewhere | ALT | the one bag |
| Iron (bare hand, RequirePriming + RottweilerUseTogglesPrime, TakeOffIronPrimed, NoticeWhenWalkNearby) | PAID 10 | `hide Bed` before his lap, `use Iron` (waits for his [7] prime, goes while he is on the balcony), `hide Bed` → `await Iron 10` (paid on his next walk past it — the walk-nearby surprise, Rottweiler.cs:833-849) |
| Airer (IT_Birdfood, RequirePriming + RottweilerUseTogglesPrime, NoticeWhenWalkNearby, FixingItem → itself: dead, not Neutral) | PAID 13 | `take Perch IT_Birdfood`, `usewith Airer IT_Birdfood` (primed at his [8]; the leg goes only while he is at the fish tank — an untricked FeedFish leaves the bedroom free for ~6 s, too little for the ~9 s balcony round trip; the tricked one with the meter still hot from the Iron kept him in the study 383.7-397.6, Woody's trip 381.3-390.0), `hide Bed` → `await Airer 13` (the walk-nearby surprise on his [10] approach, t=412) |
| Vacuum (IT_Paperknife; the DirtyCarpet's fixing tool: `RoutineActionUseFixingItem.TryUseFixingItem` fires the tricked tool's own use, and StopAction's angry pays it, RoutineActionUseFixingItem.cs:44-58, RoutineActionUse.cs:546-548) | **PORT #1** | `take DeskDrawer IT_Paperknife`, `usewith Vacuum IT_Paperknife`, the carpet dirtied (below), `sneak off` + `park Zone02` (the dog wakes: `Alerter.CanSeeWoody`), `park Zone03` → `await Vacuum 15` FAILS: he runs to the dog, plays the surprise (`Search`) and walks straight back to his routine — no `Angry` yell, no carpet urgent, no fetch (state.jsonl 417.8 Woody runs through Zone02, 422.8 the alarm run, 431.2 `Search`, 433.6 `moving Airer`, 447.7 the Airer's own fix, final tricks 7) |
| DirtyCarpet (IT_Soil, Neutral, NoticeWhenEnterZone — excluded from the generic notice run, Rottweiler.cs:188) | TRIGGER | `take TableShovel IT_Shovel`, `prime PlantSoil IT_Shovel` (the shovel's source primes on its PrimingItem and the held type becomes IT_Soil, Item.cs:1537-1572, 1246-1252), `usewith DirtyCarpet IT_Soil` — tricked (raw) all game; only the Dog yell can start its urgent |
| Dove (IT_Scissors, score 0) / PlantSoil (score 0) / Aquarium (Neutral, 0) | — | no score |

Timing notes: he leaves the basement 8 s after entering it (both trios are
~4 s), the whole lap is ~110 s; the Airer paid at t=412, the vacuum wait ran
out at 571 (the clock is 600).

### Level112 (TotalTricksCount 10, winning 7) — 9/10 paid, 68 points, 30 legs / 1 failed (+1 manual)

Routine (~120 s a lap): YogaBook, FishTank (Z08) → Yoga (Z02) → YogaBook →
Trampoline (Z06) → Bicycle (Z02) → Mixer ×2 (Z03) → ChestExpander, Weights
(Z09) → Rope (Z01). Zone04 (the steroids) is the only room he never visits.

| trick | status | leg |
| --- | --- | --- |
| Rope (bare hand, UseOnce; the Iron/Rope single-shot hack TrickItem.cs:311) | PAID 7 | `use Rope` → `await Rope 7` (his [10]: RopeKnotted ×4, RopeTiedUp) |
| GroundMarbles@Zone01 (IT_Marbles) | PAID 7 | `take Drawer IT_Marbles`, `usewith GroundMarbles@Zone01 IT_Marbles` (x=3.30, on his kitchen-door(4.26) → basement-door(2.18) walk) → `await GroundMarbles@Zone01 7` |
| GroundMarbles × 7 elsewhere | ALT | the one bag |
| ChestExpander (IT_Rubberrope) | PAID 8 | `take SportsBag IT_Skate` (skate + rubber rope in one take), `usewith ChestExpander IT_Rubberrope` → `await ChestExpander 8` |
| ElectricTrap (IT_Cable, NoticeWhenWalkNearby) | PAID 7 | `take RubbishBinCable IT_Cable`, `usewith ElectricTrap IT_Cable` (x=2.06, on his ChestExpander(3.38) → Weights(−0.01) walk) → `await ElectricTrap 7` |
| Weights (IT_Metalsaw) | PAID 8 | `take TableSaw IT_Metalsaw` (Z07), `usewith Weights IT_Metalsaw` → `await Weights 8` |
| Trampoline (IT_Spring) | PAID 8 | `take BasementSpring IT_Spring`, `usewith Trampoline IT_Spring` → `await Trampoline 8` |
| FishTank (IT_Steroids) | PAID 8 | `take FirstAid IT_Steroids`, `usewith FishTank IT_Steroids` → `await FishTank 8` |
| YogaBook (IT_Knotbook, UseAtOtherPlace/ShouldReturn: `IsTricked` false at the book; Yoga.DependsOn → YogaBook) | PAID 7 | `take BedDrawer IT_Knotbook`, `usewith YogaBook IT_Knotbook` → `await YogaBook 7` (his [0] take marks GotTricked, the mat's DependsOn branch plays YogaHurt and goes angry on the book, TrickItem.cs:857, GetTrickedItem) |
| Yoga (own IT_Football branch, TrickScore 7) | DEAD | no IT_Football source, no collider; the mat pays the book above |
| Bicycle (IT_Tongs) | PAID 8 | `take BasementDrawer IT_Tongs`, `usewith Bicycle IT_Tongs` (next to the sleeping dog, sneaking) → `await Bicycle 8` |
| GroundSkates (IT_Skate, CauseSlip, NoticeWhenWalkNearby, TrickScore 14; RollerSkaterBehavior) | DEAD (documented) | `usewith GroundSkates IT_Skate` last (x=4.12, on his Zone02-door → Mixer walk: SlideSkate, FallWindow at WindowX, 4 s later the comeback run from the street, `Stand_Down` at t=439 — parked, as README "The Level112 skate ride parks" reads it) → `await GroundSkates 14` FAILS; `manual` note. The 14 has two `OnTrickDone` paths and both are dead in the shipped data: the FallAction is a `RoutineActionSurpriseNear` whose SlideSkate ×4 sequence would pay at its end (StopAction(true) → Item.Tricked → PlayAngryAnimation, cs:49-58) — but `FallHideFrame` hides the controller (`ScriptFreeze`; a Hidden controller never `Refresh`es, AnimationControllerBase.cs:172-181) and the comeback's `UpdateWalkingAnimation` → `PlayLoopingAnimation` nulls `AnimationSequence` (Pawn.cs:1175, AnimationControllerBase.cs:344-347) before the fall's last frame plays; the Shout (`RollerSkaterBehavior.Shout`) sits behind a Breath the door-exit stand starts and the walk to `BreathLocation` (5.0, 2.0) kills the next frame (`Breath` is a Single, the walk swaps it out) — `BreathEndFrame` 29 is never reached. Note: an earlier runtime of this same session (before the fix agents' "Hidden controllers still ticking" fix, KNOWN) paid it 3 s after the fall (AngryEasyUp at 435, the resumed SlideSkate) — the current runtime parks him unpaid, which is the source's behaviour. |
| Mixer (RottweilerUseTogglesPrime, score 0) / YogaExercise (IT_Balloon, 0) / Aquarium | — | no score |

### Level113 (TotalTricksCount 8, winning 6) — 7/8 paid, 80 points, 24 legs / 2 failed

Routine (~150 s a lap): ChairAssembly (Z02) → AngleGrinder (Z07) →
ValveMain (Z09) → Radiator (Z03) → Sink (Z04) → ValveMain → FuseBox (Z01) →
Ladder, LadderDrill (Z08) → FuseBox. He crosses the hall between almost
every pair; the wardrobe there and the bed are the hides. `MainValveOpen`
ships TRUE (Item.cs:1714-1726): Woody's first click closes the valve, the
second arms it — his own [2] prime closes it too (Item.cs:1352-1355), after
which one Woody click arms (that is what the run did: `use ValveMain` at 139
after his [2]).

| trick | status | leg |
| --- | --- | --- |
| GroundMarbles@Zone03 (IT_Marbles, score 8 here) | PAID 8 | `take Drawer IT_Fuse` (fuse + marbles), `usewith GroundMarbles@Zone03 IT_Marbles` (x=4.63, on his side-door(4.09) → Radiator(6.51) walk) → `await GroundMarbles@Zone03 8` |
| GroundMarbles × 8 elsewhere | ALT | the one bag |
| Ladder (IT_Tongs, ReuseAfterFix) | PAID 15 | `take BasementDrawer IT_Tongs`, `usewith Ladder IT_Tongs` → `await Ladder 15` |
| FuseBox (IT_Fuse, RequirePriming + RottweilerUseTogglesPrime, Neutral, GetTrickedAtOnce, FixDirectly; LadderDrill.DependsOn → FuseBox) | PAID 10 | `usewith FuseBox IT_Fuse` (waits for his [6] prime, goes when he heads for the study) → `await FuseBox 10` (the drill's DependsOn branch plays the box's tricked set, angry on the FuseBox — no ForceFixOriginal — at [8]) |
| LadderDrill (own IT_Glue branch, 10) | DEAD | no IT_Glue source; pays the FuseBox above |
| ChairAssemblyBook (IT_Painbook, GetTrickedAtOnce, FixDirectly; ChairAssembly.DependsOn → book) | PAID 10 | `take BedDrawer IT_Painbook`, `usewith ChairAssemblyBook IT_Painbook` → `await ChairAssemblyBook 10` (his [0]) |
| ChairAssembly (own IT_Honey branch, 10) | DEAD | no IT_Honey source; pays the book |
| AngleGrinder (bare hand, UseOnce) | PAID 10 | `use AngleGrinder` → `await AngleGrinder 10` (his [1]) |
| ValveHot (bare hand, Neutral, GetTrickedAtOnce, CanUndoTrick, BlockValveAfterFix; Radiator.DependsOn → ValveHot, ForceFixOriginal, FixDependsOn, ForceUseFixingItem) | PAID 15 (as the Radiator) | `use ValveHot` → `await Radiator 15` (his [3]: the radiator plays the valve's tricked set, goes angry as itself — ForceFixOriginal — then fetches the valve: `TryFix` has no CanFix and a FixingItem, TrickItem.cs:1115-1124) |
| Radiator (own IT_Honey branch) | — | pays via the valve above (the 15 is the Radiator's `TrickScore`, `OnTrickDone(Radiator)`) |
| ValveMain (bare hand, the MainValveOpen hack, RemoveFromRoutineAfterUseTricked; Sink.DependsOn → ValveMain, ForceFixOriginal) | PAID 12 (as the Sink) | `use ValveMain` → `await Sink 12` (his [4]; the fetch turns the valve back; the sink's stop drops the two valve actions) |
| Sink (own IT_Spring branch) | — | pays via the valve above |
| ElectricTrap (IT_Cable, RequirePriming via the ElectricTrapTatter, NoticeWhenWalkNearby, 8) | DEAD (geometry) | `prime ElectricTrapTatter` (bare, Item.cs:1643-1651 — passes, its box peeks out of the door's), `usewith ElectricTrap IT_Cable` FAILS ("Use cable with door": every click on the trap hits the basement back door), `await ElectricTrap 8` FAILS. The trap's collider (transform z −0.001; world box x 1.97..2.16, y −4.54..−4.12, near face −4.001) lies entirely inside `DoorBack01@Zone09`'s box (x 1.81..2.61, y −4.78..−3.34, near face −4.068) — the click raycast (`Pawn.MoveToLocation`, Pawn.cs:403: origin `Camera.main.ScreenToWorldPoint(Input.mousePosition)` = the camera plane at z −10, Woody.cs:708, along +z; the first hit wins) reaches the door's face 0.067 before the trap's everywhere over the trap. L111 and L114 place the same trap at z −0.219 (near −4.219, in front of the door: it wins there, and their traps paid). The driver now searches an item's box for a point the raycast resolves to it (`_click_point_of`); the L113 trap has none. |
| Aquarium (Neutral, 0) / the invisible valves' 0-score kin | — | — |

### Level114 (TotalTricksCount 9, winning 7) — 7/9 paid, 59 points, 27 legs / 0 failed (+2 manual)

Routine (~155 s a lap): Polish (Z03) → GoldCup (Z08) → Polish → Pipe,
Gramaphone, CDs, Gramaphone, Pipe, Gramaphone (all Zone02, ~35 s, never
leaving it) → Shotgun (Z09) → Hat, MedalBox, Hat (Z06) → Horn (Z07). The dog
sleeps in the bedroom.

| trick | status | leg |
| --- | --- | --- |
| MedalBox (IT_Rat, AngryWithoutAnimations) | PAID 8 | `take MouseHole IT_Rat`, `usewith MedalBox IT_Rat` → `await MedalBox 8` (his [11]) |
| GroundMarbles@Zone01 (IT_Marbles) | PAID 7 | `take Drawer IT_Marbles` (marbles + shoe polish), `usewith GroundMarbles@Zone01 IT_Marbles` (x=−0.60, on his living-room-door(−1.92) → basement-door(2.18) walk) → `await GroundMarbles@Zone01 7` |
| GroundMarbles × 7 elsewhere | ALT | the one bag |
| ElectricTrap (IT_Cable, NoticeWhenWalkNearby) | PAID 7 | `take RubbishBinCable IT_Cable` (cable + cork), `usewith ElectricTrap IT_Cable` (x=2.06, on his door(2.21) → Shotgun(0.66) walk) → `await ElectricTrap 7` |
| Polish (IT_Shoepolish, UseAtOtherPlace/ShouldReturn, FixDirectly; GoldCup.DependsOn → Polish) | PAID 8 | `usewith Polish IT_Shoepolish` (after his [0]) → `await Polish 8` (his [2] take marks GotTricked, the cup's DependsOn branch goes angry on the Polish at the next [1]) |
| GoldCup (own IT_Munition branch, 8, no collider) | DEAD | pays the Polish above |
| Hat (IT_Superglue, RottweilerUseTogglesPrime without RequirePriming — usable any time) | PAID 8 | `take FirstAid IT_Superglue`, `usewith Hat IT_Superglue` → `await Hat 8` (his [10] primes — TryHatOn/TryHat — his [12] uses: TryHatGlue) |
| Horn (IT_Balloon) | PAID 8 | `take BedDrawer IT_Balloon`, `hide Bed` (he comes up for the hats), `usewith Horn IT_Balloon` (the moment he leaves the balcony for the kitchen), `hide Bed` → `await Horn 8` (his next [13]) |
| Shotgun (IT_Munition, Compound with IT_Cork, TrickScore 10 / CompoundTrickScore 13) | PAID 13 | `take ShotgunShells IT_Munition`, `usewith Shotgun IT_Munition`, `usewith Shotgun IT_Cork` (the compound lands in `TrickItem.CanWoodyUse` before the base gates, cs:509-529 — the driver's predicate for it is `compound_tricked`) → `await Shotgun 13` (`GetTrickScore` cs:391-398; the KNOWN "10 vs 13" no longer reproduces — 13 paid at t=346) |
| Gramaphone (IT_Nail, RequirePriming + RequireUnprime + RottweilerUseTogglesPrime, DoNothingWhileBeeingUsed) | MANUAL (DEAD) | `manual Gramaphone 10 …`: primed only between his [4] and [8] (`Item.Use`'s three-phase toggle, Item.cs:1065-1082; Woody refused unprimed, cs:1520; refused mid-use, cs:1429-1437), a stretch he spends entirely in Zone02 — no HideItem there, and `GameInfo.CanRottweilerSeeWoody` is zone-level (cs:181-192; his only Blocking animations are BedSleep / FireExtinguisher* / the four hits, so the `!IsPlayingBlockingAnimation || !Woody.Sneaking` clause never opens). The Zone06 dog alarm pulls him out of Zone02 for ~8 s, but Woody must be in Zone06 to raise it and Zone06 → Zone02 is the one door he comes through. No data path; the trick is dead in this build. |
| Pipe (IT_Gunpowder, RequirePriming + RottweilerUseTogglesPrime, ShowOnlyWhenPrimed) | MANUAL (DEAD) | `manual Pipe 10 …`: primed only between his [3] and [7], the same Zone02 stretch — same reasoning |
| CDs (IT_Munition, score 0) / Aquarium | — | no score |

## PORT findings

### PORT #1 — the Dog/Chili "SameZone" yell only fires when he is already in the pet's room (L111's Vacuum never pays)

The source evaluates `RoutineActionMove.SameZone()` on EVERY `Update` while
the urgent MoveAction to a Dog/Chili is active (`ActionManager.Update`,
ActionManager.cs:442-448: `if (MoveAction.SameZone() && !SameZone) {
SameZone = true; StartAction(MoveAction.NextAction); }`). `SameZone()`
(RoutineActionMove.cs:105-121) is true once `NextAction.Item.Zone ==
Owner.Zone && !IsPassingDoor() && (Dog|Chili) && IsUrgent()` and the pawn
sits at or past `RottLastDoor.RottweilerExitLocation + RottPos` — with
`RottweilerExitLocation` (0,0,0) on every door of the four levels (and
`RottPos` his position on that first check, `RottLastDoor` the door he came
in through, Pawn.cs:1644-1647) that is true on the very frame he lands in the
dog's zone from ANY other zone. From there: `StartAction(SurpriseActionFar)`
skips `MoveToAction` (`!IsAtActionLocation && !SameZone`, cs:152), the
surprise plays at the landing spot, `ActiveAction.Finished && SameZone`
walks him to the dog (cs:461-469), `RottweilerPositionToDog < 0.05` yells the
`SurpriseSequenceLeft` (["Angry"], cs:470-480), and its end runs the Angry
tail (Rottweiler.cs:485-510): a raw-Tricked `DirtyCarpet` in the zone gets
its `SurpriseActionFar` urgent → `Item.RottweilerUse` → `RunToFixingItem`
(the vacuum, Item.cs:847-852) → the glued vacuum's own tricked use and the
angry that pays its 15 (RoutineActionUseFixingItem.cs:44-58,
RoutineActionUse.cs:546-548).

The port (`runtime/world.py`, `Routine.start_urgent`, ~3335-3346) applies
the SameZone shortcut only when `item.zone == self.pawn.zone.pid` at the
moment the urgent starts; an alarm run that arrives from another zone goes
through the plain `_urgent_arrived` → the surprise at the dog →
`_urgent_finished` (the `_same_zone` flag is never set, so
`_same_zone_walk` / `_same_zone_yell` / `_yell_done` never run). Since the
dog wakes only when Woody walks its room openly, and Woody cannot share
that room with the neighbour, the arriving case is the only one a player
can produce — the DirtyCarpet urgent, and with it the Vacuum's 15, are
unreachable in the port. Evidence, the official L111 run
(`/tmp/nfh-tricks-s1c/s1_Level111/state.jsonl`): 417.8 Woody runs through
Zone02 (sneak off, the dog barks), 422.8 `moving Airer Run_Left` (the alarm
run from the balcony), 431.2 `using Airer Search` (the surprise at the dog),
433.6 `moving Airer` (the routine resumes: no `Angry`, no carpet urgent, no
vacuum grab), 447.7 the Airer's own FixMid, final `tricks 7`; the carpet was
tricked since t=76 (`usewith DirtyCarpet IT_Soil` ok) and the vacuum since
161. Fix sketch (for the fix agents): re-check the SameZone predicate on the
routine's tick while an urgent Dog/Chili move is in flight and the pawn's
zone becomes the item's (after the warp, not while warping), then take the
`_same_zone` path.

## Data findings (dead tricks, no manual step exists)

- **L112 GroundSkates (14)** — both `OnTrickDone` paths dead (table above):
  the SurpriseNear sequence is stalled by the hidden controller and dropped
  by the comeback walk; the Shout never reaches `BreathEndFrame`. The
  README's "parks" reading is confirmed; the level's TotalTricksCount 10
  counts a trick that cannot pay (the win comes at WinningTricksCount 7).
- **L113 ElectricTrap (8)** — its collider is fully covered by the basement
  back door's, behind its near face; the click raycast never reaches it
  (table above). Levels 111/114 place the trap at z −0.219 and it works.
- **L114 Gramaphone (10) and Pipe (10)** — primed only while he stands in
  their room, which has no hiding place; zone-level detection leaves no
  window (table above).
- Dead score fields (data, not bugs): L111 DirtyCarpet 15 (Neutral trigger),
  L112 Yoga 7, L113 LadderDrill 10 / ChairAssembly 10 (their `RequiredInventory`
  has no source), L114 GoldCup 8; the `CompoundRequiredInventory = IT_Antispot`
  on every non-Compound item; the marbles twins.

## KNOWN bugs met

- "Hidden controllers still ticking" — the earlier runtime of this session
  paid L112's GroundSkates through the resumed SlideSkate sequence; the fixed
  runtime parks him unpaid (faithful). Recorded above.
- "compound score of L114 Shotgun (10 vs 13)" — no longer reproduces: 13
  paid.
- "WasPriming never written" — not observed on the RequireUnprime trios: the
  WashingMachine / Drier paid at their use visit (L111 state.jsonl 291.3
  `using WashingMachine TakeInventory` (prime), 301.9 tricks 3).

## Driver changes (tests/run_tricks.py)

- `restart()` clears `_flee_at`: the flee throttle is a clock stamp, and a
  stale one from the previous attempt (t restarts at 0) suppressed every
  dodge of the new run — each retry died at the exact spot the first attempt
  survived.
- `_route_slack` / `_flee_target` (now `(zone, first door, slack)`) and the
  "sealing" flee in `_dodge_tick`: a route whose gateway zone the catcher
  reaches before Woody is through it is taken now — the dead-end rooms
  (balcony, study, basement, bathroom) trapped Woody while the neighbour
  walked into the hall behind him.
- `woody_speed(zone)`: the auto-sneak crawls the Alerter rooms at 0.52
  (force 0.8 × SpeedSneaking 0.65) — `woody_need`, the flee exit time and
  the route slack read it; `woody_need` charges each door's walk to the zone
  Woody is leaving (find_path lists the door with the zone it enters).
- `_auto_sneak_tick`: the toggle flips at the warp into a pet's room
  (`Woody.Sneaking` is read live; the one-frame gap on the landing tick woke
  L111's dog and sent him running every lap), and the "catcher due here"
  override applies only in Woody's own pet room.
- `_use_leg(wait_prime)`: `use`/`usewith` on a RequirePriming +
  RottweilerUseTogglesPrime item waits (dodging where he stands — in the bed
  he hid in) for the neighbour's prime instead of clicking a refusing item
  for the whole lap.
- `use_time` for a HideItem is 0.5 s (Woody.Hide sets Hiding on arrival) and
  `gate_open` skips the escape checks for hide legs — the bed IS the way out.
- `_click_point_of`: when a nearer collider covers the item's centre
  (`Viewer._hit_at`), click the first point of a 7×7 grid over the item's box
  the raycast resolves to the item (L112's SportsBag peeks 0.08 out of the
  back door's box).
- `leg_use`: the compound click (`typ == CompoundRequiredInventory` on a
  Compound item) succeeds on `compound_tricked`, not on the already-Tricked
  item.
- `TRICKS_VERBOSE=1`: a live per-leg log with the attempt number and time.
