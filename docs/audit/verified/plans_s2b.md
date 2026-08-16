# Pass 3, group s2b — Level208 … Level214

Plans: `tests/plans/s2/Level208.txt`, `Level209.txt`, `Level210.txt`,
`Level211.txt`, `Level212.txt`, `Level213.txt`, `Level214.txt`. Runs:
`SDL_VIDEODRIVER=offscreen python3 tests/run_tricks.py tests/plans/s2/Level2XX.txt --out=/tmp/nfh-tricks-s2b`
(results.json copies: `/tmp/nfh-tricks-s2b/results_2XX.json`, run logs
`/tmp/nfh-tricks-s2b/run2XX.log`).

Season-2 facts every plan leans on (read from the source): the score is
`completed*90/total` (`GameInfo.CalculateScore` cs:411-431 — every S2 item
serializes `TrickScore=0`, so every `await` asserts 0); only the Rottweiler
and the Mother catch (`GameInfo.Update` cs:212-225, `CanRottweilerSeeWoody`
/ `CanMotherSeeWoody` cs:181-199 — Olga never does); `IsSleeping` gates both
predicates, so a neighbour's sleep bar (`ProgressBar.SetSleeping`) is the
window into his room; the transitions are walk-through stairs
(`Helpers.LinkNodes`), so a pawn's zone flips at the `transfer` step, not at
a door warp; the sneak toggle is a flag only in S2 (`Woody.ToggleSneak`,
Woody.cs:1151 — the sheets have no `Walk_*`), never set `Sneaking`.

## Status table

PAID = the driver saw `GameInfo.TrickDone` for the item (score 0 asserted).
`n/N` = CompletedTricksCount / TotalTricksCount reached in the final run.

### Level208 — total 7, reached 6/7 (0 restarts before the blocked tail)

| trick | leg | status |
|---|---|---|
| IndianPlatform (Rott action 0) | `usewith IndianMagician IT2_Balloon` (ActivateItemTrick, TrickItem.cs:323-327) → `await IndianPlatform 0` | PAID 0 |
| SeeSaw (LinkedItemTrick of the platform) | `usewith SeeSaw IT2_Shovel` → `await SeeSaw 0` | PAID 0 (the pair pays 2 in one `LinkedTrick` TrickDone, Item.cs:2137-2142, GameInfo.cs:470-475) |
| ShoeMachine | `take BoardNail IT2_Blades` (Zone02, the Mother's sleep window) → `usewith ShoeMachine IT2_Blades` → `await ShoeMachine 0` | PAID 0 |
| ElectricTap (NoticeWhenWalkNearby, no Rott use sequence) | `take Cable IT2_Cable` → `usewith ElectricTap IT2_Cable` → `await ElectricTap 0` | PAID 0 (the empty use still runs the stop flow) |
| Rake (NoticeWhenWalkNearby, bare hand) | `use Rake`, `use Fifi` → `await Rake 0` | PAID 0 — the Rott only enters Zone02 for the Fifi chain (Fifi tricked → the Mother's use injects MotherRott/TakeFifi/PutFifi, TrickItem.cs:1256-1260, ActionManager.AddInGameActions cs:814-842) and RakeBazarCrash rides that walk. Fifi itself is **not a scored trick**: TrickDone fires only from `Rottweiler.PlayAngryAnimation` (Rottweiler.cs:787) and no Rott action uses Fifi (Item.MotherUse only plays animations, Item.cs:1108-1137); the 7 of TotalTricksCount = pair(2)+ShoeMachine+ElectricTap+Rake+AngryElephant+ArmsBowl. |
| AngryElephant (rat + chalk) | `take Chalk`, `take Mouse IT2_Rat` (dexterity, unlocker IT_NONE), `prime AngryElephant IT2_Rat` (DoublePrimingItem arm, Item.cs:1573-1589), `usewith SafetyLine IT2_Chalk_sponge` → `await AngryElephant 0` | PAID 0 — plan note: the chalk must be drawn in the same visit, `Pawn.ElephantAnimations` (Pawn.cs:1536-1558) re-locks the SafetyLine when Woody leaves the primed elephant's zone (verified: `SafetyLine l=1` the moment he left) |
| ArmsBowl (snake) | `take Mouse IT2_Rat` (2nd) → `prime Snake IT2_Rat` → `usewith ArmsBowl IT2_Snake` → `await ArmsBowl 0` | **PORT** — the second rat never comes (see finding 1). The round itself works: run in isolation (Mouse → Snake → ArmsBowl) it PAID 0 (`/tmp/nfh-tricks-s2b/mtest`). Either rat round is reachable, not both. |
| DressingRoom (IT_Football), MotherRott/TakeFifi/PutFifi (IT_Chips/IT_Fuse/IT_Fartbag), Fence1-3 (knife) | — | unreachable by data (no source item gives those types; the fences ship disabled) |

### Level209 — total 7 / winning 5, reached 5/7 (0 restarts; WON)

| trick | leg | status |
|---|---|---|
| FireFakir (Rott action 0, IT_Cheese — no source) | `take ConstructionSet IT2_Fuel` → `usewith FireChannel IT2_Fuel` (KeepAfterUse, ActivateItemTrick → FireFakir, TrickItem.cs:323-327) → `await FireFakir 0` | PAID 0 |
| Coal (DexterityTrickItem, unlocker the bellows) | `take PairOfBellows IT2_Air_pump` → `unlock Coal IT2_Air_pump` (the done-pass, Item.cs:1462-1473) → `await Coal 0` | PAID 0 |
| Trough (LinkedItemTrick of the Coal) | `usewith Trough IT2_Fuel` → `await Trough 0` | PAID 0 (pair with the Coal, one LinkedTrick TrickDone) |
| HotShoe (RottweilerUseTogglesPrime, IT2_Pants_coal) | `take AsbestosNappies IT2_Pants` → `prime Coal IT2_Pants` → `usewith HotShoe IT2_Pants_coal` (after his prime visit, Item.cs:1520-1535) → `await HotShoe 0` | PAID 0 — plan note (DATA): the pants prime is `RequirePrimingOnlyWhenTricked && Tricked` (Item.cs:1598-1613), and the Rottweiler's next lap fixes the coal (CanFix); the first plan took the pants after the dexterity win, waited a lap for Zone03 and clicked a fixed coal (`Coal t=0` at the click, dbg39). Pants first, then the win and the prime in one visit. |
| Drain (LinkedItemTrick of the HotShoe) | `usewith Drain IT2_Match` → `await Drain 0` | PAID 0 |
| Cow (knife) | `prime Flowers IT2_Knife` (the knife pick, Item.cs:1421-1426) → `prime Cow IT2_Flowers` (CowBehavior, Item.cs:1760-1780) → `usewith Cow IT2_Knife` → `await Cow 0` | **PORT** — no knife (finding 6): every leg fails "IT2_Knife not in inventory" |
| IceCream (IT2_Crap) | `take CowCrap IT2_Crap` (collider on at frame 27 of the primed cow) → `usewith IceCream IT2_Crap` → `await IceCream 0` | **PORT** — downstream of the same gap (the cow never primes, the crap never appears) |
| TadjMahal (IT_Bowling), DressingRoom (IT2_Blades) | — | unreachable by data (no source item gives those types) |

### Level210 — total 8, reached 5/8 (0 restarts)

| trick | leg | status |
|---|---|---|
| (walk-in) | `entrance skip` | MANUAL — the walk-in ends in a catch at t=3.15 (finding 2) |
| TurbanShop | `usewith TurbanShop IT2_Hedgehog` → `await TurbanShop 0` | PAID 0 (the IT2_Oktopus alternative needs the valve chain below) |
| DogBasket | `take AlmsBowl IT2_Bone` → `usewith DogBasket IT2_Bone` (in the Mother's first sleep) → `await DogBasket 0` | PAID 0 — pays alone; the DivingBoard half of the pair and the ExtraCoin210 (Item.cs:2420-2427, empty pool) need a later Zone04 window |
| Elephant | `take CricketBat IT2_Bat` → `usewith Elephant IT2_Bat` → `await Elephant 0` | PAID 0 |
| DeckChair + Pylon (linked) | `take OlgaBra IT2_Bra` (during Olga's shower, OlgaBraBehavior), `prime WaterMelons IT2_Bra` (→ IT2_Bra_sling), `usewith Pylon IT2_Bra_sling`, `usewith DeckChair IT2_Hedgehog` → `await DeckChair 0`, `await Pylon 0` | PAID 0 + 0 (2 counts) — plan note: the Pylon first — the DeckChair is UseOnce without UseItemMultipleTimes, so its Fix keeps UseOnce and a second hedgehog is refused; the pair must be armed for one sit |
| DivingBoard | `take SuntanOil`, `usewith DivingBoard IT2_Sunoil` | **PORT** (finding 3): needs a Zone04 window after ~26 s; the Mother never sleeps again in the port |
| FishNet → ToolBelt (dexterity) → Valve (tongs) → ValveWaterPuddle / empty Pool | `take FishNet IT2_Brailer` … | **PORT** (finding 3), same room |
| FifiTurban, CallRTMother, DeckChairMother, Shower, PoolLadder, OlgaShower/OlgaMatBeach | — | no source for the required types (fartbag/knife/crayfish) or Olga's own actions — not tricks by data |

### Level211 — total 8, reached 7/8 (0 restarts)

| trick | leg | status |
|---|---|---|
| LifeJacket | `take CompressedAir IT2_Pressuretank` → `usewith LifeJacket` → `await LifeJacket 0` | PAID 0 |
| DivingGear | `take FireExtinguisher` (Zone03, the Mother's first sleep) → `usewith DivingGear` → `await DivingGear 0` | PAID 0 |
| Sweets (+ the toilet extra) | `take Urinal IT2_Pissballs`; the sign first: `take Plate IT2_Sausage` → `prime Dog IT2_Sausage` (the Plate's PrimingItem unlocks the Handbag, Item.cs:1548-1572) → `take Handbag IT2_Rasp` → `usewith ToiletSign IT2_Rasp` → `usewith Sweets IT2_Pissballs` → `await Sweets 0`; `await 8` | PAID 0; the extra `GameInfo.TrickDone` of `Toilet211Behavior` (Item.cs:2373-2384) came too (7 counted = 6 items + 1) — `await 8` fails only for the FishingRod |
| CabinPhone + OlgaChild (linked) | `usewith OlgaChild IT2_Pressuretank`, `take ChestDrawer IT2_Coin` → `usewith PayPhone IT2_Coin` (ActivateItemTrick + AlarmItem: he runs to answer) → `await CabinPhone 0`, `await OlgaChild 0` | PAID 0 + 0 |
| LifeBoat (DexterityTrickItem, unlocker rasp) | `unlock LifeBoat IT2_Rasp` → `await LifeBoat 0` | PAID 0 |
| FishingRod | `take MumPicture IT2_Bentnail` → `usewith FishingRod IT2_Bentnail` | **PORT** (finding 4): the click never reaches the rod |
| ToiletMen/ToiletWomen (knife, DependsOn ToiletSign), OlgaSeaView/OlgaStandStill (Olga's, no collider), Dog (IT_Egg), DeckChairMother | — | not tricks by data |

### Level212 — total 9, reached 9/9 (0 restarts)

| trick | leg | status |
|---|---|---|
| AztecThrone + AztecThrone2 (linked) | `take RubyThrone`/`take ParrotNest` (two rubies: the RubyThrone deactivates after its take, Item.cs:1939-1942), `usewith AztecThrone IT2_Ruby`, `usewith AztecThrone2 IT2_Ruby` → `await AztecThrone 0`, `await AztecThrone2 0` | PAID 0 + 0 — plan note: `ThroneBehavior212` (Item.cs:2450-2469, ported at world.py `_throne_behavior_212`) swaps the two colliders at Woody's use and his Fix swaps them back; both must be armed before one sit or the second throne pays never |
| Whip | `take Skeleton IT2_Dagger_rusty` → `prime RotatingStoneDisc IT2_Dagger_rusty` (RequirePrimingOnlyWhenTricked: the disc tricked by the throne's ActivateItemTrick, Item.cs:1599-1613) → `usewith Whip IT2_Dagger` → `await Whip 0` | PAID 0 |
| CigarBox | `take Crowbar` → `prime ClosedMine1 IT2_Crowbar` (Item.cs:1561-1566: crowbar → TNT + a fresh crowbar) → `usewith CigarBox IT2_Tnt` → `await CigarBox 0` | PAID 0 (the `prime` leg's own predicate was widened to see the type change; the port routes the click through the co-located ClosedMine search item — the TNT arrives) |
| SleepBench | `take PaintPot` → `usewith SleepBench IT2_Paint` → `await SleepBench 0` | PAID 0 |
| MechanicalBull | `take Resin` → `usewith MechanicalBull IT2_Resin` → `await MechanicalBull 0` | PAID 0 |
| ParrotLedge + BoatCoinSlot (linked) | `take Corn`, `take MechanicalBullCoins IT2_Coin` → `usewith BoatCoinSlot IT2_Coin`, `usewith ParrotLedge IT2_Corn` → both awaits | PAID 0 + 0 |
| PreAztecThrone, PreParrotLedge, Rock1, Fence*, ParrotCrap, LiveBull, BoatBase, BoatRent | — | knife/bowling/birdfood/cork: no source — not tricks by data |

### Level213 — total 9, reached 8/9 (0 restarts)

| trick | leg | status |
|---|---|---|
| CementBath | `take CementBag` → `usewith CementBath IT2_Cement` → `await CementBath 0` | PAID 0 |
| LiveBull | `take Flowers` (Zone05) → `usewith LiveBull IT2_Flowers` → `await LiveBull 0` | PAID 0 (its LinkedItemTrick is the Wasp *search item* — activated by his angry, Rottweiler.cs:583-590; it never has `Tricked`, so the bull pays 1) |
| PlantCarnivore | `take ChickenWings` → `usewith PlantCarnivore IT2_Chickenwing` → `await PlantCarnivore 0` | PAID 0 |
| Tortilla (+ compound extra) | `take Chili`, `take Skeleton IT2_Tequila` → `usewith Tortilla IT2_Chili`, `usewith Tortilla IT2_Tequila` (TrickItem.CanWoodyUse cs:509-529) → `await Tortilla 0` | PAID 0 + the ExtraCoinCompound (Item.cs:2398-2404) counted (8 = 7 items + 1) |
| BoatPicnic | `take Jar IT2_Jar_empty` → `prime Termite IT2_Jar_empty` (→ IT2_Termites) → `usewith BoatPicnic IT2_Termites` → `await BoatPicnic 0` | PAID 0 |
| MechanicalBullControls | `take StatueHand` → `usewith MechanicalBullControls IT2_Hand` → `await MechanicalBullControls 0` | PAID 0 |
| Pinata (DexterityTrickItem, unlocker beehive) | `take Wasp IT2_Beehive` (after the bull's angry) → `unlock Pinata IT2_Beehive` → `await Pinata 0` | PAID 0 |
| the 9th count (`await 9`) | — | not reachable by data: PlantCarnivore's second coin needs `Compound && CompoundTricked` (TrickItem.cs:824-826) and its `CompoundRequiredInventory` is IT_Antispot (enum 0) — no S2 source gives it; the level counts it in TotalTricksCount |

### Level214 — total 6, reached 2/6 (4 restarts, all downstream of finding 5)

| trick | leg | status |
|---|---|---|
| Shower (via the Washbucket) | `take HatchFish IT2_Fish` → `usewith Washbucket IT2_Fish` (ActivateItemTrick → Shower) → `await Shower 0` | PAID 0 |
| Hatch | `take Carpet` → `usewith Hatch IT2_Carpet` → `await Hatch 0` | PAID (his HatchCarpet angry at ~88 s counted: 2/6 in the log) — the leg's own await was cut by the catch below |
| Bouquet | `usewith Bouquet IT2_Fish` (tricked at 36 s) → `await Bouquet 0` | armed, never paid in a surviving run: Woody dies before his second Bouquet use — Zone04's exits are his shower room and the Mother's Zone03, which never opens (finding 5) |
| Pistol, CaptainDoor, CaptainMug/Captain, CaptainWheel | `take Handbag IT2_Pills`, `take Mat IT2_Code`, `usewith Pistol IT2_Ammo`, `usewith CaptainDoor IT2_Key` (Zone03), then Zone05 | **PORT** (finding 5): Zone03 has no IsSleeping window in the port — 'zone never clear' by construction |
| Glass (Olga's), Bird/BirdPerch/CaptainControls/Captain (knife), MotherWait, DeckChairMother | — | not tricks by data |

## PORT findings (evidence)

1. **Level208 — the Mouse's rat is never re-granted (InventoryToAdd unported).**
   C#: the snake round (`Item.cs:1554-1560`) and the elephant round
   (`Item.cs:1579-1589`) both call
   `AddInventoryToObject(InventoryToAdd, 1, IT2_Rat, …)` (`Item.cs:1791-1810`):
   with `Mouse.InventoryToAdd == Mouse` (data: pid 341 → 341) the emptied
   Mouse (`SearchItem.InternalUse` nulls InventoryItems, SearchItem.cs:192-206)
   gets a fresh rat, so with `TakeItemCount=20` both rat tricks are reachable
   in one game. Port: `world.py:7046` empties the item on the take and
   `world.py:6613` says "the InventoryToAdd rat grant rides the unported
   InventoryToAdd machinery"; nothing refills it. Trace: after
   `prime AngryElephant IT2_Rat` the second `take Mouse IT2_Rat` fails
   ("no IT2_Rat after take", results_208.json), and the isolated snake plan
   (`/tmp/nfh-tricks-s2b/mtest/s2/Level208.txt`) pays ArmsBowl but its
   second `take Mouse` fails the same way. Level208 caps at 6/7 in the port.

2. **Level210 — the walk-in ends in a catch at t=3.15 (input locked).**
   Data: `Level.StartZoneName=Zone02`, `EntranceZoneName=Zone01`
   (`Level.cs:199-208` computes EntranceLocation = Zone01's transform =
   (-2.97,-1.46)); `Woody.Update` starts the walk 0.5 s after CanStart
   (Woody.cs:223-229) and the neighbour's DelayStart is 1.5 s
   (Rottweiler.cs:153, 916-921), both from IntroAnimation.StartGame. Port
   trace (dbg21, 5/5 runs): Woody transfers into Zone01 at 3.12-3.15 s while
   the neighbour is still walking to the DeckChair (x=-4.41 at 3.12,
   arrives -4.49 at ~3.2, `IsSleeping` only once his sit sequence's bar
   window starts) → `can_rottweiler_see_woody` catches him before
   `OnFinishedEntrance` unlocks the input. A human cannot act during the
   walk-in, so the plan opens with `entrance skip` (driver: Woody starts at
   his StartLocation with the entrance finished — recorded MANUAL). Whether
   the original survives this by frame timing, by DonePassingToOtherZone
   (Pawn.cs:319-342) or by another gate is for the fix agents; the port
   makes the level unplayable as shipped.

3. **Level210 — the Mother sleeps only once per level: `MotherWakeSleepBehavior`'s
   ProgressBar restore is not ported.** C#: `ProgressBar.SetSleeping` clears
   `ExecutedOnce` (ProgressBar.cs:175-179) and only `RestoreVariables`
   (cs:291-301, from OnEnable or `ActionManager.StopMotherUrgentAction`)
   re-arms it; the L210 bar is `Mother210` (never deactivated) and the L210
   Mother has no urgent action, so the intended re-arm is
   `MotherWakeSleepBehavior.PlayAnimation` (MotherWakeSleepBehavior.cs:26-45:
   on `TargetAnimation=MotherLookLoop` → `Invoke("ProgressBarDelay", 2f)` →
   `ProgressBar.RestoreVariables()`, data pid 301: ProgressBar → go 86 = the
   DeckChairMother bar). Port: `behaviors.py:2079` MotherWakeSleepBehavior
   docstring "The ProgressBar restore rides the unported progress-bar
   system" — no `restore()` call. Trace (spectate L210): `MotherSleepSingle
   SLEEP` at 7-26 s, then `MotherSleepSingle` at 63-85 and 100-118 **without**
   IsSleeping. Consequence: Zone04 (DivingBoard, FishNet→ToolBelt→Valve→the
   empty pool and the octopus, DogBasket's second half, CallRTMother) has no
   safe window after 26 s: DivingBoard, ExtraCoin210 and the tongs chain are
   unreachable, Level210 caps at 5/8.

4. **Level211 — the FishingRod cannot be clicked: its collider lies inside
   the TransitionDownwards door box that the port's ray ranks nearer.**
   Data (Level211.json world boxes): FishingRod collider centre (-4.84,2.08)
   size 0.85×0.34, near face -0.05-4.00; the Zone04→Zone01 stairs door
   TransitionDownwards centre (-4.96,2.30) size 1.80×1.26, near face
   -0.02-4.45 — the rod's box is entirely inside the door's in XY and the
   door's near face is nearer. `viewer._hit_at` (viewer.py:190) picks the
   smallest near face, so every click on the rod is a door click (trace: no
   "use FishingRod" ever printed, Woody walks downstairs — dbg27). The
   original's `Physics.Raycast(MoveLocation, camera.forward)` (Pawn.cs:403)
   would order the same faces if the exported box z/dz are right; either
   the export of that door's collider depth is off or the original's door
   collider is not on the ray's layer — for the fix agents. The rod trick
   (and its OlgaStandStill activation) is unreachable in the port: 7/8.

5. **Level214 — the Mother's forced sleep never sets IsSleeping:
   `MotherSleepBehaviour.ForceSleep` does not stamp CurrentAnimationSequence.**
   C#: `ForceSleep` plays `MotherItem.GetMotherSecondUseAnimation()`
   (MotherSleepBehaviour.cs:73-83), which stamps
   `CurrentAnimationSequence = MotherSecondUse` (Item.cs:936-940; the extra
   variant `GetMotherExtraUseAnimation` stamps MotherExtraUse, cs:977-980);
   the DeckChairMother bar's windows are exactly `MotherSecondUse [0,10)` and
   `MotherExtraUse [2,11)`, 57.7 s (Level214.json ProgressBar go 19). Port:
   `behaviors.py:2057 force_sleep` / `_force_sleep_after_trick` play the
   sequences without setting `mother_item.current_sequence`, so
   `ProgressBarState._check_state` finds no window and `SetSleeping(True)`
   never runs. Trace (spectate L214): the pistol play at 49-60 s forces
   `MotherSleepSingle` from 62 s with **no** SLEEP marker, ever. Consequence:
   Zone03 (Handbag pills, Mat code, Shards, Pistol, CaptainDoor → the captain's
   cabin) has no window at all, and Zone04 becomes a trap whenever the
   neighbour showers (its other exit is Zone03) — the Bouquet's pay never
   happens in a surviving run. Level214 caps at 2/6.

6. **Level209 — the pre-serialized starting inventory is not loaded (the
   knife).** Data: the InventoryManager component (Level209.json
   `objects[271].data`) ships `InventoryItems = [{Type: IT2_Knife, NameString
   PENKNIFE2_NAME, PrimedNameString FLOWERS_NAME, NFH2Inventory: true}]`,
   `FirstInventoryItem: true` — Woody starts the level with the pen knife.
   C#: `InventoryManager.InventoryItems` is the serialized list
   (InventoryManager.cs:5-7); `HUD.OnGUI` initializes that first item on
   its first draw (`if (Woody.InvManager.FirstInventoryItem)
   InventoryItems[i].Initialize()`, HUD.cs:972-978); the level's knife
   chain hangs off it — the Flowers pick (`UsedInventory.Type == IT2_Knife`,
   Item.cs:1421-1426), `Cow.RequiredInventory = IT2_Knife` (the crap's
   controller wake, TrickItem.cs:319), IceCream (IT2_Crap). Port:
   `world.py:4597 self.inventory = InventoryState()` and `InventoryState.
   __init__` (`world.py:1639 self.items = []`) — nothing reads the
   component's list, so Woody starts empty. Trace: `inventory: []` at t=0
   in every Level209 run (run209.log) and the plan's `prime Flowers IT2_Knife`
   / `usewith Cow IT2_Knife` fail "IT2_Knife not in inventory". Cow and
   IceCream (2 of the 7) are unreachable; the level still WINs at 5/7
   (winning=5). Level209 is the only level (S1+S2 scan of every
   InventoryManager component) with a non-empty serialized list — Level208's
   Fence1-3 (knife) stay unreachable by data.

Data observations (not port bugs): Level208's Fifi is a mechanism, not a
scored trick (above); Level213's PlantCarnivore second coin is dead data
(CompoundRequiredInventory IT_Antispot); Level210's DeckChair is UseOnce
for good (no UseItemMultipleTimes) so the DeckChair/Pylon pair must be
armed for one sit; Level212's RubyThrone deactivates after its first take
(the ParrotNest is the second ruby) and the two thrones alternate colliders.

## KNOWN encountered

- The dexterity take (Level208 Mouse) failed at first ("dexterity win does
  not take the item") and worked after the fix agents' change; the L211
  LifeBoat and L213 Pinata dexterity trick items pass.
- The S2 sneak toggle crash surfaced through the driver's own auto-sneak
  (`Walk_Right` missing) — the driver now never sets Sneaking on the nfh2
  Woody.

## Driver changes (tests/run_tricks.py, this group)

- `eta_to_zone`: the S2 walk-through transitions — a `transfer` step flips
  the catcher's zone (the old model only saw `door` steps, so a neighbour
  crossing Level208's hub was invisible until he stood in it); a stair
  step's length is the hypotenuse (a same-x descent is not free); an
  in-progress use is not re-added as a pending action (the L208 platform
  read 47 s for a 15 s walk).
- `sleep_left(p)`: the remaining sleep of a catcher from his bar's
  `[AnimationStartIndex, AnimationEndIndex)` window and his player's
  sequence — a sleeping catcher counts by his wake, not by 0, in
  `eta_to_zone`, `_occupied`, the dodge's "ahead" check.
- `gate_open`: `in_use_now(item)` holds a leg whose target (or its
  ActivateItemTrick / LinkedItemTrick partner) is being used right now
  (Level208's seesaw was wiped by the platform's fix); the current zone's
  "leave" check; the `heading` catcher's `ESCAPE_MARGIN` (15 s: a room its
  owner is walking to must be left again); the way-round route
  (`find_path_avoiding`, `_route_via`) when the shortest route crosses a hot
  room — the leg then clicks the waypoint zone first (`_click_via`) and the
  item once there; the escape check is skipped when nobody reaches the room
  for 30 s (Woody can wait inside).
- `_dodge_tick`: keep walking when already on the way out of the hot room
  into a clear one; retry a click the transit guard swallowed; the flee
  target excludes rooms a catcher is heading to (slack < 10) and clicks the
  first hop of a detour route; `_flee_target`/`_safe_route` use
  `find_path_avoiding`.
- `_auto_sneak_tick` never touches the nfh2 Woody (S2 has no Walk_* sheets).
- `wait_until`: `_dex_tick` steers any enabled dexterity game to the win;
  a won game pokes at once (WinDexterity leaves DexterityDone up); a fire
  click swallowed mid-stairs/mid-climb or while the input is locked stays
  pending; `poke_every` 3 s; the waypoint poke.
- `leg_unlock`: click → steer → the follow-up click of the done-pass
  (Item.cs:1462-1473) → success = the pass consumed.
- `leg_take`: fires the click the moment a source turns clickable
  (Level210's OlgaBra comes with Olga's shower).
- `leg_prime`: success also when the held entry changed type / left the
  inventory / the source's PrimedInventoryType arrived (Level212's crowbar
  → TNT with the ClosedMine1 self-deactivation); the measured entry is the
  freshly selected CurrentInventory, not a stale UsedInventory an item path
  kept (Level209: the air pump stayed Used after the coal's dexterity win,
  so the pants prime landed — `IT2_Pants_coal` in the inventory line — while
  the leg still read the pump's source and timed out).
- `leg_await`: `await <N>` waits for CompletedTricksCount ≥ N (the extra
  TrickDones no item's AlreadyTricked explains); when every zone is on a
  routine or a corridor the parking spot is the nearest HideItem
  (`_hide_spot`, Level208's basket) and, while it is unreachable, Woody
  stages in the zone the catchers reach last; the parking spot is re-chosen
  at every poke; `safe_zone` skips corridor zones (`corridor_zones`) and
  unreachable ones (Level214's cabin).
- `entrance skip` prelude directive (`apply_prelude`, re-applied on
  restart): a MANUAL step for Level210's walk-in catch.
- `GATE_TIMEOUT` 160 s (a S2 lap is ~100 s), `in_use_now` by role (a
  neighbour ignoring Woody during a use still runs the stop flow).
