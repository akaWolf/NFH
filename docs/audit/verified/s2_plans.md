# s2_plans — the six PORT findings of plans_s2b (Level208 … Level214)

Source: `docs/audit/verified/plans_s2b.md` "PORT findings (evidence)" 1-6.
Plans re-run with `SDL_VIDEODRIVER=offscreen python3 tests/run_tricks.py
tests/plans/s2/Level2XX.txt --out=/tmp/s2p` (logs `/tmp/s2p/run2XX.log`,
`/tmp/s2p/s2_Level2XX/results.json`; the whole S2 set at the end with
`--jobs=4`, `/tmp/s2p/run_all_s2*.log`). Check module:
`tests/checks/s2_plans.py` (16 checks, all pass; the moment suite stays
ALL OK).

Claims received 6 — CONFIRMED-FIXED 5 (1, 2, 3, 5, 6; 2 turned out to be a
different port bug than the draft guessed) — REFUTED 1 (4: a data fact,
documented) — plus one follow-on port gap found on the way (L214's captain
cabin, fixed) and one driver gap (the dexterity search source's take).

## Findings

### 1. L208 `AddInventoryToObject` — CONFIRMED, FIXED

C#: the snake round (`Item.cs:1554-1560`) and the elephant round
(`Item.cs:1579-1589`) both call `AddInventoryToObject(InventoryToAdd, 1,
IT2_Rat, "MOUSE_NAME", "RAT2_DESC", "SNAKE_INV_NAME", "SNAKE_INV_DESC", "",
false, true)`; case 1 (`Item.cs:1795-1801`) refills
`UsedInventory.Item.InventoryToAdd.InventoryItems` when it is null — the
Mouse points at itself (Level208.json pid 341 → 341), and
`SearchItem.InternalUse` nulls its stock on the take (KeepFull false,
SearchItem.cs:158-165, 192-202), so each priming round hands the Mouse a
fresh rat; TakeItemCount 20 keeps its Dexterity flag (Item.cs:1466-1469).
The `invItems` parameter is unused; case 2 (own InventoryToAdd) has no
caller. Only the Mouse (L208) and L209's Flowers pair serialize an
InventoryToAdd; the Flowers never reach a call site.

Port before: `world.py` snake branch "the InventoryToAdd rat grant rides the
unported InventoryToAdd machinery"; nothing refilled the Mouse; the elephant
branch had no refill either. After: `runtime/scene.py:195, 470`
(`Item.inventory_to_add`), `runtime/world.py:15-16` (`_RAT_ENTRY_208`, the
Inventory ctor's fields in the port's entry shape), `world.py:6274-6295`
(`_add_inventory_to_object`, cases 1/2), calls at `world.py:6669` (snake,
cs:1559) and `world.py:6686` (elephant, cs:1582).

Plan: Level208 24/24 legs ok, `await ArmsBowl 0` paid, CompletedTricksCount
7/7, GameEnding (was 6/7). Check: `s2_plans: snake round refills the Mouse
with a rat`, `… elephant round refills the Mouse again`.

### 2. L210 walk-in catch at t≈3.15 — CONFIRMED (a different port bug), FIXED

The draft asked whether the original survives the walk-in. Traced first as
if the walk-in existed: at the Zone02→Zone01 transfer `ChangeZone` →
`CrabAnimations` clears `DonePassingToOtherZone` (Pawn.cs:1526-1528,
1560-1566), the next `Pawn.Update` sees `lastZone2 != Zone` with
`PassingComplexMove` still up → `CheckForNeighbour` →
`HasNeighborCaughtWoody` (Pawn.cs:291-313, 366-378): same zone, the
neighbour walking (no DeckChair animation is Blocking — ChairEnter/ChairSun/
ChairWakeup/ChairAwake/ChairLeave all serialize Blocking=false), IsSleeping
only from element 2 of his RottweilerUse ([2,6) window: ChairEnter 7 frames
+ ChairSun 22 frames at 8 fps ≈ 3.6 s after his ~3.2 s arrival, i.e. ~6.8 s),
Woody's flip at ~3.1 s (0.5 s timer + 4.9 units at the 2 u/s run) — the
original would catch too. But the walk-in itself is the port's invention:
**`Pawn.FinishedEntrance` is a serialized public field (Pawn.cs:119) and
every Season-2 level (and the S1 intros) ships it TRUE** (the 14 S1 levels
FALSE). With it true: `Woody.Start` leaves the input unlocked
(`InputLocked = !FinishedEntrance`, Woody.cs:191), `Woody.Update` never
starts the entrance walk (`!FinishedEntrance && EntranceTimer > 0 &&
CanStart`, cs:223-231), `TakeNextStep` never plays HelloAnimation
(Pawn.cs:1064-1067 — the S2 sheet has no `Hello`, only `Entrance`; a play
would throw "No animation found"), and `IntroAnimation.StartGame` locks the
NFH2Path Woody and plays `HelloAnimationNFH2` = `Entrance` (11 frames at
10 fps, not Blocking; IntroAnimation.cs:300-304, Pawn.cs:213), whose single
end unlocks (`Woody.OnSingleAnimationEnded`, Woody.cs:372-375). Consistent
with the S2 data: `EntranceLocationOffset.z = 0` (S1 puts the entrance
raycast origin on the camera plane, z = -9.5) and `StartZone ==
EntranceZone` on L201/L205/L206.

Port before: `world.py` Pawn init `self.finished_entrance = (role !=
'Woody')`, `spawn_pawn` always locked Woody and armed the 0.5 s
EntranceTimer, no Entrance greeting. After: `scene.py:2114, 2121`
(`hello_animation_nfh2`, `finished_entrance` in the pawn spec),
`world.py:476-477` (Pawn.finished_entrance from the spec),
`world.py:7303-7327` (`spawn_pawn`: InputLocked = !FinishedEntrance, the
timer only for an unfinished entrance, the NFH2 lock + Entrance play),
`world.py:6855-6858` (the Entrance end unlocks), `world.py:7791-7800`
(the fallback unlock now Season-1 only). Trace: L210 `Entrance` at 0-1.0 s,
unlocked at 1.02 s, Woody stays at StartLocation (4.39,-2.16) in Zone02, no
catch. Season 1 unchanged (moment suite: entrance/Hello/unlock all ok).

Plan: Level210's `entrance skip` (MANUAL) removed; 23/23 legs ok, 6/8.
Driver: `tests/run_tricks.py run_entrance` — a FinishedEntrance-true level
starts its plan when the Entrance greeting releases the input (~1.0 s)
instead of the S1 walk-in's 4.0 s (a human clicks when he can; the fixed
4 s wait made Level206's Pillows race lose by 0.1 s once Woody started at
StartLocation instead of the port's invented entrance point). Checks:
`s2_plans: S2 start plays Entrance, no walk-in, no catch`, `… the Entrance
end unlocks the input (~1 s)`, `… S1 Woody still starts unfinished and
locked`.

### 3. L210 `MotherWakeSleepBehavior` → `ProgressBar.RestoreVariables` — CONFIRMED, FIXED

C#: `MotherWakeSleepBehavior.PlayAnimation` (cs:26-44) on TargetAnimation
(MotherLookLoop) ends both arms in `Invoke("ProgressBarDelay", 2f)` →
`ProgressBar.GetComponent<ProgressBar>().RestoreVariables()` (cs:46-52;
ProgressBar.cs:291-301). The L210 bar (pid 362, go 86, Mother210) never
deactivates but `SetSleeping` clears `ExecutedOnce` (ProgressBar.cs:175-
179), so without the restore her second and later MotherUse windows never
`SetSleeping(true)`. Port before: `behaviors.py` MotherWakeSleepBehavior
"The ProgressBar restore rides the unported progress-bar system". After:
`behaviors.py:2097-2135` — `progress_bar_go`, `world.call_later(2.0,
_progress_bar_delay)`, `ProgressBarState.restore()` on the bar of that
GameObject. Trace (catchers IgnoreWoody, 140 s): IsSleeping 6.5-25.9,
64.9-84.3, 99.6-119.0; restores at 27.9, 86.3, 121.0 (2 s after
MotherLookLoop).

Plan: Level210 `usewith DivingBoard IT2_Sunoil` and `await DivingBoard 0`
paid; the tongs chain (FishNet → ToolBelt → Valve → the puddle's octopus)
runs; 23/23 legs, 6/8. Check: `s2_plans: L210 Mother sleeps (IsSleeping)
on the 2nd lap`.

Driver gap found here: `unlock ToolBelt IT2_Brailer` reported success at
the done-pass and the next leg fired at once, but a dexterity SEARCH source
hands its stock over only when the take animation ends (~1.4 s later,
SearchItem.OnFinishAnimationCompelted → InternalUse, SearchItem.cs:114-119,
156-212); the next leg's click cancelled the take. `leg_unlock` now waits
for the stock to land (`tests/run_tricks.py:2030-2046`).

### 4. L211 FishingRod inside the TransitionDownwards box — REFUTED (data fact)

Both colliders share the X-180°-about-(0,1,-1) rotation that turns the local
Y size into world depth: the rod (BoxCollider size (7,8,3), world scale
(0.121,1,0.112), position z=-0.05) is 0.847×0.336 in XY, z ∈ [-4.05, 3.95];
the Zone04→Zone01 TransitionDownwards (size (1.8,8,1.148), world scale
(1,1.1125,1.101), z=-0.016) is 1.80×1.264, z ∈ [-4.466, 4.434]. The rod's XY
box ([-5.268,-4.421]×[1.907,2.243]) lies entirely inside the door's
([-5.861,-4.061]×[1.664,2.928]). `Pawn.MoveToLocation` raycasts from
`ScreenToWorldPoint(mouse)` — the camera plane, z=-10 (Woody.cs:708,
Pawn.cs:403) — along +z and takes Physics.Raycast's nearest hit; both are
trigger colliders (562 of 702 item colliders, all 332 doors and 156 zones
are triggers, so `queriesHitTriggers` must be on or nothing would be
clickable) on raycastable layers (0 and 8, no mask). The door's near face
(-4.466) is 0.42 nearer than the rod's (-4.05): every click on the rod is a
door click in the original as in the port (`viewer._hit_at`). The FishingRod
(→ OlgaStandStill) is unreachable by data; Level211 caps at 7/8 (winning 6).
No `m_IsTrigger` question arises (the exporter carries `isTrigger`). Plan:
the rod's three legs dropped, `await 7`; 22/22 legs ok, 7/8. Check:
`s2_plans: FishingRod click resolves to TransitionDownwards` (regression of
the near-face ordering).

### 5. L214 `MotherSleepBehaviour.ForceSleep` stamp — CONFIRMED, FIXED (+ two follow-ons)

C#: `ForceSleep` (MotherSleepBehaviour.cs:73-83) plays
`MotherItem.GetMotherSecondUseAnimation()` (stamps
`CurrentAnimationSequence = MotherSecondUse`, Item.cs:936-940) when the
Pistol is untricked, else the raw `MotherUseTrickedAnimation` (no stamp);
`ForceSleepAfterTrick` (cs:85-88) plays `GetMotherExtraUseAnimation()`
(MotherExtraUse, Item.cs:977-981). The DeckChairMother bar (go 19) reads
MotherSecondUse [0,10) / MotherExtraUse [2,11), 57.7 s. Port before:
`behaviors.py force_sleep / _force_sleep_after_trick` played the sequences
without the stamp. After: `behaviors.py:2066, 2079`.

Follow-on A (same fix): the C# controller keeps its ActionManager, so the
forced sequence's end still runs `ActionManager.StopCurrentAction(true)`
(AnimationControllerBase.cs:242-246; ShouldStopAction raised at cs:289-292)
and her DeckChairMother action advances to MotherWait; the port's stand-in
for that stop is the use's pending `on_end` (Routine._finish), which a
plain `play_sequence(seq)` dropped — she stood "using DeckChairMother"
forever and the neighbour's Pistol WaitWatch (UnFreeze on her next
OnMotherSit) never ended. `behaviors.py:2085-2095 _resequence` carries the
pending on_end over. Trace (260 s): sleep 61-119 with IsSleeping,
MotherWait 129-144, sit 152, sleep 165-223 with IsSleeping (the bar's
object is re-activated by each MotherUse, `Item.MotherUse` →
`ProgressBarObject.SetActive(true)`, Item.cs:1108-1116 → OnEnable →
RestoreVariables — so the window repeats every lap; the plans_s2b/plan
header's "sits awake" is now "asleep 61-119, 165-223, …").

Follow-on B (the cabin): with Zone03 open, `usewith CaptainMug` never
walked — the port's `_build_graph` dropped the DisableOnStart DoorBack pair
(scene.py, "equivalent whichever Start() runs first") and
`_captain_door_behavior` only un-hid the sprites, so Zone05 was unreachable
for Woody and for the neighbour's retargeted CaptainControls action (his
routine skipped it: 'idle CaptainControls' → Pistol). C#: the pair ships
active and Door.Start deactivates it (Door.cs:63-66); ZoneController.Start
(cs:16-27) keeps the edge unless Door.Start ran first — the level needs it
(Item.CaptainDoorBehavior, Item.cs:2606-2623, re-activates both doors and
retargets the action into Zone05); Zone.Neighbors never changes; while the
pair is inactive `BuildPath → LinkNodes → GetDoorBetweenZones` finds no
active door (GetComponentsInChildren skips inactive objects,
Helpers.cs:194-205, 243-248) and FindPath is null. After: `scene.py:1845-
1877` (the edge stays), `scene.py:1879-1922` (find_path refuses a route
through a disabled door), `world.py:5898-5919` (`d.disabled = False` +
the sprite, on the door's AnimPlayer). Level214's captain cabin: Woody
walks Zone03 → DoorBack → Zone05 (door_climb/door_anim), the neighbour
uses the CaptainWheel there (SteeringCrash paid at 188.8 s).
`tests/checks/assets_refs.py` d2 (the find_path/Dijkstra parity) got the
same LinkNodes refusal on its reference so the 786-pair equality holds.

Plan: Level214 re-ordered for the first window (the Zone03 raid, the cabin,
then `hide DeckChair` while he crosses); 19/19 legs ok, 5/6 (was 2/6 with
4 restarts). The 6th count is dead by data: the CaptainMug (RequiredInventory
IT2_Pills, ActivateItemTrick + LinkedItemTrick Captain, no Rottweiler use
animation) is used by nobody after Woody, the Captain (IT2_Knife, no
source) neither, and the CaptainWheel's pay has no LinkedItemTrick — like
L213's 9th; the level wins at 4. Checks: `s2_plans: L214 pistol play puts the
Mother to sleep (bar)`, `… the forced sleep ends her DeckChairMother action`,
`… ForceSleepAfterTrick stamps MotherExtraUse`, `… cabin route refused
until the CaptainDoor trick`.

### 6. L209 serialized starting inventory — CONFIRMED, FIXED

C#: `InventoryManager.InventoryItems` (InventoryManager.cs:5) is a public
`List<Inventory>` Unity deserializes before any Start; Woody's `InvManager`
(Woody.cs:8) references the component (Level209.json 235 → 271); the list
holds `[IT2_Knife, PENKNIFE2_NAME, PENKNIFE2_DESC, primed FLOWERS_NAME/
FLOWERS_INV_DESC, NFH2]` with `FirstInventoryItem = true`, which HUD.OnGUI's
first draw feeds to `Inventory.Initialize` (HUD.cs:972-978: the icon
textures and the localized strings — the port resolves both at draw). No
`OnInventoryAdded` fires for it. Level209 is the only scene of 33 with a
non-empty list (all others `[]`, `FirstInventoryItem false`). Port before:
`InventoryState.__init__` empty for every level. After: `scene.py:1149-1150,
2262-2286` (`Level.inventory_items` / `first_inventory_item` from Woody's
InvManager component, the InventoryManager fallback), `world.py:4608-4615`.

Plan: the knife chain works (`prime Flowers IT2_Knife` → the held knife
becomes IT2_Flowers and a fresh knife lands, Item.cs:1421-1426; `prime Cow
IT2_Flowers` (CowBehavior); the crap at frame 27 (Level208Behaviors.
OnAdvanceFrame); `usewith Cow IT2_Knife`; `usewith IceCream IT2_Crap`).
Level209 21/21 legs ok, 7/7, GameEnding (was 5/7). Plan re-ordered — a data
fact found on the way: `Level208Behaviors.CowGetUpAux1` (cs:71-80, 112-115)
is set by the neighbour's first CowRide and never cleared; from then on
every animation switch of his (`SetAnimation → InitializeCurrentAnimation
→ BehaviorPlayAnimation`, AnimationControllerBase.cs:380-385) forces the
cow back to IdleNormal (PlayAnimationDirectly, unconditional re-init), so
a cow primed after his first ride keeps its 2.8 s primed pose only while
he holds one animation — the first plan's `prime Cow` at 177 s (he
switched to FixMid 0.2 s later) never reached frame 27; the knife chain now
runs first (his cow ride is at ~79 s). Checks: `s2_plans: L209 starts with
the serialized pen knife`, `… the knife picks the flowers, a knife lands
back`, `… L208 starts empty-handed`.

## Same-class sweeps

- AddInventoryToObject: the two C# call sites are the only ones; the
  L209 Flowers' InventoryToAdd (306) reaches no call. Nothing else in
  world.py/behaviors.py is still marked "unported" in the inventory/priming
  class except the IceBucket branch note (world.py `woody_prime`, ported in
  fact) and L102's `TrickProgressBarBehavior` "unported progress-bar HUD"
  (behaviors.py:594-598, S1 — a `ProgressBarTrick` object, not the
  ProgressBar component; flag).
- Serialized pawn flags the port hard-coded: `FinishedEntrance` was the
  one; `IsSleeping`, `IgnoreWoody`, `NFH2Path`, `AdjacentZonesEnabled` are
  read.
- Behaviour-started pawn sequences (the action-stop carry-over):
  MotherSleepBehaviour is the only C# behaviour that `PlayAnimationSequence`s
  a pawn (IndianPlatformBehavior re-sequences the Magician item). Sibling
  in another area: `Routine._use` drags Olga through
  `RottweilerUseOlgaAnimationSequence` with `olga.anim.play_sequence(oseq)`
  (world.py ~2572-2580, TrickItem.cs:911-914) — the C# would end Olga's
  current action at that sequence's end too; not touched (routine area).
- Get*Animation stamps: `_pick_use_sequence` stamps the routine's
  sequences; the two force sleeps were the unstamped ones; the
  MotherWakeSleep override changes no sequence.
- DisableOnStart doors: only L214's pair in all 33 scenes.
- Physics.Raycast near-face ordering: the assets_refs d7 check already
  guards it; the FishingRod is the one item whose XY box a door's box
  fully contains AND whose near face lies behind the door's — see the d7
  numbers (113 of 667 XY-overlapping pairs order by near face, not centre).

## Plan results (this run)

Level208 24/24 ok 7/7 · Level209 21/21 ok 7/7 · Level210 23/23 ok 6/8 (the
ExtraCoin210 pool half is not on the plan) · Level211 22/22 ok 7/8 (the rod
dead) · Level214 19/19 ok 5/6 (the mug dead). The whole S2 set re-run with
the fixed start and the driver's `run_entrance` (`/tmp/s2p/run_all_s2_b.log`,
results.json per level kept, the state.jsonl files removed — /tmp is
small): 201-204, 208-212, 214 all legs ok; 213 its documented dead 9th;
206 back to its s2a state (Pillows/Harpoon/LaunchPad paid, the Zone04
"sealed" seven); 207 its KNOWN crayfish three; 205 fails `usewith LionStatue`
(caught at 201.85 during his lap-2 WaterSkiis fix, 4 restarts) — identical
with the old walk-in emulated (a scratch run patching FinishedEntrance
false), so not a regression of this pass: the s2a plan's later legs meet
the neighbour's second lap, which the port now plays.

## README additions

- **Season-2 start.** `Pawn.FinishedEntrance` is serialized (Pawn.cs:119):
  every Season-2 level (and the S1 intros) ships Woody's TRUE, the 14 S1
  levels FALSE. With it true there is no entrance walk — `Woody.Start` leaves
  the input unlocked (`InputLocked = !FinishedEntrance`, Woody.cs:191),
  `Woody.Update` never arms the EntranceTimer (cs:223-231), `TakeNextStep`
  never plays HelloAnimation (Pawn.cs:1064-1067; the S2 sheet has no
  `Hello`). `IntroAnimation.StartGame` (cs:300-304) locks the NFH2Path
  Woody and plays `HelloAnimationNFH2` = `Entrance` (Pawn.cs:213; 11 frames,
  10 fps, not Blocking) whose single end unlocks him (Woody.cs:372-375).
  The port's Level210 "walk-in catch" was that invented walk-in
  (StartLocation Zone02 (4.39,-2.16) → EntranceLocation Zone01) meeting the
  neighbour's DeckChair walk; the S1 EntranceLocationOffset.z = -9.5 puts
  the entrance raycast on the camera plane, S2's 0 does not need it.
- **AddInventoryToObject** (Item.cs:1791-1810): the L208 snake and elephant
  rounds (cs:1559, 1582) refill the emptied Mouse (its own InventoryToAdd)
  with a fresh IT2_Rat when its InventoryItems is null; TakeItemCount 20
  keeps the dexterity game (cs:1466-1469); both rat tricks pay in one game.
- **InventoryManager.InventoryItems** (InventoryManager.cs:5): the serialized
  starting inventory — Level209 alone ships the pen knife
  (`FirstInventoryItem`, HUD.cs:972-978 initializes it on the first draw).
- **MotherWakeSleepBehavior.ProgressBarDelay** (cs:33/40, 46-52): 2 s after
  MotherLookLoop the L210 Mother210 bar's `RestoreVariables` re-arms
  `ExecutedOnce`, so her IsSleeping window opens every lap (6.5-25.9,
  64.9-84.3, 99.6-119.0 …); the bar's own end never deactivates a Mother210
  bar (ProgressBar.cs:164-172).
- **MotherSleepBehaviour.ForceSleep / ForceSleepAfterTrick**
  (cs:73-88): the Get* getters stamp CurrentAnimationSequence
  (MotherSecondUse / MotherExtraUse, Item.cs:936-940, 977-981) — L214's
  DeckChairMother bar window; the tricked arm reads the raw
  MotherUseTrickedAnimation (MotherSleepLoop) with no stamp. The forced
  sequence's end still stops her current action (AnimationControllerBase.cs:
  242-246: the controller's ActionManager, not the call's) — the port carries
  the routine's pending on_end over. Her bar object is re-activated by every
  MotherUse (Item.cs:1108-1116), so the L214 window repeats each lap
  (61-119, 165-223, …).
- **L214's captain cabin.** The DoorBack pair ships active with
  DisableOnStart (Door.cs:63-66); ZoneController.Start keeps the Zone03↔
  Zone05 edge (the level needs it: `Item.CaptainDoorBehavior`, Item.cs:
  2606-2623, re-activates both and retargets his CaptainDoor action at
  CaptainControls in Zone05); while inactive, LinkNodes finds no door and
  FindPath is null (Helpers.cs:194-205, 243-248) — `Level.find_path`
  refuses a disabled door the same way. The 6th L214 count (CaptainMug /
  Captain: no neighbour use, no linked pay) is dead by data; winning=4.
- **Level211's FishingRod** is unreachable by data: its whole XY box lies
  inside the Zone04 TransitionDownwards box and the door's near face
  (z -4.466) beats the rod's (-4.05) on the camera-plane raycast
  (Pawn.cs:403, Woody.cs:708); 7/8 (winning 6).
- **Level208Behaviors.CowGetUpAux1** (cs:71-80, 112-115) never clears after
  the neighbour's first CowRide: every animation switch of his forces the
  cow to IdleNormal (AnimationControllerBase.cs:380-385), so the crap window
  (frame 27 of the primed pose, cs:118-131) needs the prime before his first
  ride or a 2.8 s span without a switch.

## Coordinator flags

- `Routine._use` (world.py ~2572-2580): the neighbour's
  RottweilerUseOlgaAnimationSequence re-sequences Olga with `on_end=None`;
  by AnimationControllerBase.cs:242-246 Olga's current action would stop at
  that sequence's end (her controller's ActionManager) — the same class as
  finding 5's follow-on A; routine area, not touched.
- The FinishedEntrance start shifts every S2 plan's clock (~1.0 s start
  instead of 4.0 s; Woody at StartLocation, not the entrance point). With
  the old 4.0 s prelude Level206's Pillows race was lost by 0.1 s (Woody
  starts 0.19 units farther from the ToyBox); the driver's `run_entrance`
  (a human clicks when the Entrance greeting unlocks him) restores it —
  the S1 plans keep their 4.0 s. Level205's LionStatue failure predates
  this pass (see above); the s2a plan wants a re-tune for the neighbour's
  second lap.
- The dead-by-data counts to note in the score model: L211's 8th (rod),
  L214's 6th (mug/captain), L213's 9th (already noted).
- `tests/checks/assets_refs.py` d2: one small edit (the LinkNodes refusal on
  the reference path) so the parity check follows the kept DoorBack edge.
- L102's TrickProgressBarBehavior note ("unported progress-bar HUD") — a
  `ProgressBarTrick` object, S1, not the ProgressBar component; unverified.
