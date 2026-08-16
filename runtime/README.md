# Runtime

A reimplementation of the game's rendering model, running off the exported level
JSON and the extracted PNGs. Python + PySDL2 over the system SDL2.

```sh
NFH_TEXTURES=/path/to/pngs python3 runtime/viewer.py levels/s1/Level101.json
```

Click to send Woody there. Keys: arrows pan · `F` follow camera · `[` `]`
previous/next level · `Z` zone overlay · `Space` pause · `S` screenshot ·
`Esc` quit. Add `--shot=out.png` to render one frame headless
(pair it with `SDL_VIDEODRIVER=offscreen`).

## What it reproduces

Two draw passes, because the game itself has two — see `docs/GAMEPLAY.md` §8.

**World-space quads** go first. The level backdrop and a handful of static item
overlays are ordinary Unity `MeshRenderer`s on the built-in 10×10 Plane, laid
into XY and scaled, so their world size is `10 × (scale.x, scale.z)`. Level101's
backdrop works out to 14.28 × 7.36 units with the `house01` texture.

**Screen-space sprites** go second. Every animated object blits a frame of its
sheet with `Graphics.DrawTexture`, positioned by projecting its world transform
and offset in design pixels:

```python
sx, sy = camera.world_to_screen(x, y)          # ortho size 3, then H - y
scale  = screen_h / 600.0                      # 800x600 design resolution
dst    = (sx + (ctrl.dx + anim.dx) * scale,
          sy + (ctrl.dy + anim.dy) * scale,
          anim.OriginalWidth  * scale / anim.SheetColumns,
          anim.OriginalHeight * scale / anim.SheetRows)
```

Ordering is the `GUIDepth` enum, not z-sorting: higher value draws further back.

## Coverage

All 31 levels of both seasons render with every sprite placed and no missing
sheet — 546 sprites in total:

```
Level101  drew 16/16 sprites; missing sheets: 0
...
Level214  drew 16/16 sprites; missing sheets: 0
total sprites drawn: 546, missing sheets: 0
```

(535 before the alerter pass; six sleeping pets have `IdleNormal == NONE` and
draw their `SleepSequence[0]` instead — see below. The seventh, Level109's
parrot, always had a normal idle. The 546th is Level210's dog basket, which
starts `Primed` and draws its `PrimedNormal` pose the way `Item.Start` →
`SetPrimed` does.)

Sprite counts vary a lot by design: Level113 has 27, while Level201 has 8
because that level paints most of its scenery into the backdrop instead.

## Things that bite

- **Transforms nest.** A door parented to a zone stores a local position;
  `tools/export_level.py` composes the chain and emits `world_position`.
- **Doors name their idle differently.** `Door` uses `IdleAnimation`, every other
  `Item` uses `IdleNormal`. Reading the wrong field silently selects animation 0,
  which for a door is "Woody walks through it" — the whole level then shows
  Woody standing inside every doorway. And every pass animation must end in
  `ReturnToIdleAnimation` (`Door.OnAnimationEnded`, Door.cs:155-197) — without
  it the door parks on the last stale frame of the walk-through.
- **Flat extraction collides on base names.** All three HUD face strips ship
  an `idle_0000`; `Resources.Load` disambiguates through the ResourceManager
  container (class 147: path → PPtr). `tools/extract_gui.py` walks the
  container and writes those textures with the full path flattened into the
  name, and the HUD loads faces by `HUD.LoadTextures`' base paths
  (HUD.cs:349-352) — before that, both portraits drew from one mixed pool and
  flickered through each other's frames.
- **Woody enters the level.** `Woody.Start` parks him at `Level.StartLocation`
  (the street zone named by `StartZoneName`) with input locked
  (Woody.cs:187-192); after the title cards (not modelled) the 0.5 s
  `EntranceTimer` runs out and he walks to `Level.EntranceLocation`
  (Woody.cs:223-229, Level.cs:199-208) — crossing the front door, which is
  the entrance the player sees. Arrival unlocks the input
  (`OnFinishedEntrance`). The `LevelLocations` teleport alone leaves him
  standing mid-room.
- **`IdleNormal == 'NONE'` means "not a sprite"** — except on an `Alerter`,
  whose `Start` plays the `SleepSequence` instead of an idle. Every other such
  object is drawn as a quad; giving it a sprite draws the wrong thing.
- **Sheet names are `Resources.Load` paths**, so some contain a subdirectory or
  a duplicate-asset suffix (`Closed/closeddoorback_ms`, `trashcan_ms (2)`). The
  texture cache tries the raw name, the flattened one, the basename, and the
  sanitised one.
- **The sheet is `BaseAnimationPath + TextureFileName`, and `TextureFileName`
  is sometimes empty** — then the base path *is* the asset, e.g.
  `Textures/NFH2/Items/WaterPuddle/W_Water_Puddle` + `''`. Only 76 of 12374
  animations do this (68 of them in Season 1), and treating an empty name as
  "no sheet" drops those objects silently: Level201 rendered 4 sprites instead
  of 8, and nothing reported an error.

## Movement

Speed is not a single number. `ProcessMovement` does
`position += Velocity * dt * Speed`, and `WalkOnPath` sets
`Velocity = direction * ForceMagnitude` for a mostly-horizontal move or
`* DoorForceMagnitude` otherwise, with the Running variants during an urgent
move and `SpeedSneaking` in place of `Speed` while sneaking. So Woody walks at
`1.25 x 0.8 = 1.0` units per second and the neighbour at `1.25 x 0.7 = 0.875`.

Walking limits are `Zone.PlayLeft` / `PlayRight`, set in `Level.Start()` from
`ZonesPlayLeft` / `ZonesPlayRight` as deltas either side of the zone's x — not
the collider box, which is only for containment. Zone03 of Level101 spans
[1.15, 6.25] as a box but only [1.70, 5.70] as walkable. `AdjustEndMoveInZoneArea`
clamps a free click to that range, but `BuildPathToItem` drops the clamped step
and appends the item's own `TargetLocation`, so routine targets are never
clamped — the binoculars at 6.30 stay reachable.

An action is "at place" per `Item.IsAtUseRange`: same zone, and within the
item's own `UseDistance` of `GetMoveLocation` — which offsets the stand-point by
`DeltaOlgaLocation` / `DeltaMotherLocation` for those two and is plain
`TargetLocation` for Woody and the neighbour. The `MaximumPawnDistanceToAction`
field on the action is not that check.

A door's animation controller is found the way `Item.Start` finds it —
`GetComponentInChildren`, so the door's own object or a child; 116 of the 354
doors keep it on a child, where matching by position would have guessed.

`world.py` adds the parts of §3 and §8 that make Woody walk. Click anywhere:

1. `zone_at(x, y)` finds the destination zone.
2. `find_path` is BFS over the door graph — the game's Dijkstra uses a flat cost
   of 1.0 per hop, so the two agree.
3. Each hop becomes a step: walk along x to the door, transit, continue.

A transit is the interesting part. The door sheets (`W_Door_Right_Enter` and
friends) already contain the walking character, so the game **hides the pawn and
animates the door**. Passing one is:

```
walk to door.x  ->  SetHidden(true)                     # every pawn hides
                    sourceDoor.play(<role>...Leave)     # both doors animate
                    farDoor.play(<role>...Enter)        # AT THE SAME TIME
  farDoor Enter ends:
                    warp to farDoor.position + DoorDistanceDelta
                    zone = farDoor.Zone, unhide
                    pawn.playLooping(farDoor.ExitAnimation)
  sourceDoor Leave ends:  nothing (frees the door)
```

This is `Pawn.MoveToDoor`'s portal branch verbatim: `PlayDoorLeaveAnimation(
TargetDoor)` and `PlayDoorEnterAnimation(TargetDoor.LinkTo)` fire together, and
the teleport hangs off `OnDoorEnterAnimationFinished` — the far door's Enter.
**Leave belongs to the departing side, Enter to the arriving side**, and
`PlayDoorLeaveAnimation` calls `SetHidden(true)` unconditionally, so the
neighbour hides during transit exactly like Woody (the `is Woody` guards touch
the same flag again). `ExitAnimation` is an `AnimationState` and loops on the
*pawn*; enter/leave are `ItemAnimationState` and belong to the doors. A door
occupied by another pawn (`IsOtherPawnPassing`, either side) makes the arrival
wait standing.

`AnimPlayer` mirrors `AnimationControllerBase`: an animation ending pulls the
next from the queue, and the queue draining fires the callback — which is what
ends the owning action. Walk direction comes from the dominant axis of the
movement vector, and the stand pose keeps the last facing, as `Pawn` and
`PawnAnimationController` do.

Every zone of all 28 playable levels is reachable from Woody's start. The three
intro scenes are not — they are cutscenes, and two declare no Woody zone at all.

## The neighbour's routine

`Routine` in `world.py` is `ActionManager` from §4: a cyclic list of actions,
each naming an item. Starting one walks the pawn to `item.TargetLocation`
(`position + DeltaLocation`) and then plays the item's use sequence on the pawn.
`Duration` is 0 almost everywhere, so **the animation sequence is the action** —
it ends when the sequence drains.

Level101's routine is two actions. The neighbour walks to the sofa, plays
`SitDown → SitLoop → SitRemote → SitLoop → SitRemote → SitLoop → SitUp`, crosses
through a door into the next zone, peeps through the binoculars, and comes back.
One lap is about 35 seconds.

Everything below was read out of `src/`, not inferred from behaviour:

- **The zone is passed explicitly, never derived from the target point.**
  `ActionManager` calls `MoveToGoal(item, item.Zone, item.TargetLocation, ...)`
  because an item's stand-point can sit just outside its zone's collider — the
  binoculars in Level101 are at x=6.30 while Zone03 ends at 6.25. Looking the
  zone up by position strands the routine there.
- **An action must never complete synchronously.** The game advances in
  `ActionManager.Update`, so a zero-length action costs a frame. Chaining
  directly from "finished" into "start the next" recurses without bound the
  moment two such actions sit at the same spot.

- **The owner is matched by component type, not object name.** Season 2 calls
  the neighbour's GameObject `Rottweiler2`; matching on the name skipped his
  routine on all 14 of those levels.
- **Each pawn type has its own use sequence** (`RottweilerUseAnimation`,
  `OlgaUseAnimation`, `MotherUseAnimation`). `Item.PlayAnimation` picks one array
  and plays it — there is no fallback, and an empty array means the item is not
  that character's to use.
- **`MutexAction` never finishes on its own.** `OnActionStarted` plays
  `MutexLoopingAnimation` and returns; the release comes from another action's
  `PawnToAbortMutexOnFinish`. Level205's neighbour legitimately waits at action 0
  forever until that fires.
- **`InfiniteLoop` and `Type == Looping` are different things.**
  `PlayNextSequenceAnimation` calls `PlaySingleAnimation`, which forces the type
  to Single, so inside a sequence only `InfiniteLoop` still loops. Conflating
  them stalls a routine on any animation merely marked Looping. Of 306 use
  sequences, exactly one of the neighbour's ends on an infinite loop; for Olga
  and Mother it is 11, and those are the deliberate waiting poses.

### Season 1 is faithful; Season 2 is not finished

Season 1 runs 9 to 31 uses per three minutes across all 14 levels. The
neighbour's routine also runs on 12 of Season 2's 14. What is still missing
there is the release machinery — `PawnToAbortMutexOnFinish`,
`SetIgnoreInfiniteLoop`, `PawnToStopInfiniteAnimation` — and the per-item
hardcoding in `ActionManager`, which is what lets Olga and Mother out of their
waiting poses.

## Verified in this pass (each read from the source)

- **Frame stepping is `Refresh` verbatim**: a time accumulator, at most one
  frame per tick, `+= 1/FrameRate` after each advance, `SlowAnimationsFactor`
  hook. `HoldOnLastFrame` parks on the end frame and never finishes its
  sequence. A missing animation **throws**, as `SetAnimation` does.
- **Frame-keyed sounds**: `AnimationSound {Frame, FileName}` fire as their index
  comes up; `runtime/audio_out.py` plays the extracted WAVs through SDL2_mixer.
- **Movement is 2D**: `Velocity = normalize(target - pos) * ForceMagnitude`
  (or `DoorForceMagnitude` when y dominates), `pos += Velocity * dt * Speed`,
  with `Walk_Up/Down` for the vertical-dominant case and `HasPassedTarget`
  ending a move when the pawn crosses the target x (without it, any step longer
  than `UseDistance` oscillates forever).
- **Walk-up doors** (`ShouldWalkUp`, 114 of 354): climb on `PortalUpAnimation`
  until `IsAtUseLocation` — a **y-only** check against the door's own transform
  — then Leave and Enter run *sequentially*, and the far side descends on
  `PortalDownAnimation` until `IsAtPortalTargetLocation`. Flat doors keep the
  parallel choreography.
- **Elevated items** (262): approach along the floor (`CheckMoveLocationY`
  forces step y to `GetItemZoneY`), with a plain floor step at the item's x
  first, then a vertical climb gated by the same y-only check.
- **`Actor.Start` repositions actors from `LevelLocations[i]`**, i =
  buildIndex − 5 (S1) / + 12 (S2). The serialized transform is not where an
  actor stands when the array has an entry for the level.
- **Stand poses come from the controller's `Stand*Animation` fields** and the
  pawn's `DefaultAnimation` — `Stand_Left` is not guaranteed to exist.
- **`PlayItemsZoneEnter/Leave`**: items with `EnterZone`/`LeaveZone` animations
  react when a pawn passes a door of their zone.
- Sheet lookup is case-insensitive, as `Resources.Load` is: the data asks for
  `O_workout`, the asset is `O_Workout`.

## The divergence that took three passes: zones are rebuilt at load

The climb runaways (seven levels' routines flying to y=100+) were not a
movement bug. `Level.Start` **rebuilds every zone from lists on the Level
component**, keyed by the number in the zone's name; the serialized zone
transforms are placeholders:

```csharp
zone.transform.position = new Vector3(x, ZonesY[i], z) + zoneController.position;
zone.HeightDelta        = ZonesHeightDeltas[i];
zone.collider.size      = ZonesSizes[i];
zone.SetPlayLeft(ZonesPlayLeft[i]);   // around the repositioned x
zone.SetPlayRight(ZonesPlayRight[i]);
```

With that, `GetDefaultZoneY = zone.y + HeightDelta + PlayerHeightDelta` lands on
the visible floor line and matches the pawns' spawn positions to within the
`IsPawnAtZoneY` tolerance (Level107: floor 2.411 vs spawn 2.495; Level211:
2.240 vs 2.290) — and every walk-up item is genuinely *above* it. Before this,
the floor computed from serialized zone data sat ~0.3–1.0 too high and the
y-only climb check could never be satisfied.

The same pass earlier established `Actor.Start`'s `LevelLocations[i]`
repositioning (i = buildIndex − 5 for S1, + 12 for S2). Together these mean:
**the scene's serialized transforms are not the runtime layout** — the Level
and Actor components carry the real one.

## The trick loop (§5)

Implemented from the source, method by method:

**Woody's side** — `Woody.TryUseItem` → `Item.Use` → `WoodyUse`:
`CanWoodyUse` gates on the held inventory (`RequiredInventory`, with
`SecondRequiredInventory` as the accepted alternative and the compound branch
from `TrickItem.CanWoodyUse`), on `Locked`, and on holding anything at a bare
item; failure is the `NoNo` animation and possibly `WrongTrick`. Success plays
the item's `Animation` on Woody, and the state change rides its end:
`TrickItem.OnUseAnimationCompleted` consumes the held inventory
(`UseCount--`, removal unless `KeepAfterUse`), handles `GrabDirectly` and
`CanUndoTrick`, arms the trap (`GetTricked`), propagates `ActivateItemTrick` /
`SetTrickedOnItem`, switches the idle, and Woody laughs unless
`DontLaughWhenTrickItem`. A `SearchItem` instead runs search → take →
`InternalUse`, handing over `InventoryItems` (or `WhatsUp` when empty).

**The neighbour's side** — `RoutineActionUse.StopAction(canPostponeStop:true)`:
a use that ends on a tricked item does not finish the action; the owner plays
the angry set first. `Rottweiler.PlayAngryAnimation` (Classic): meter at zero →
`AnimationAngryEasyUp`; meter still hot → `AngryCountTicks++`,
`AnimationAngryEasyDown + AnimationAngryHard`, a compound trick. Either way the
meter refills and stops decaying until the use ends. The fix animation rides the
same sequence's tail (`FixSequence` / `FixAnimation` per flags), and its end runs
`FixTrickedItem → TryFix`: `CanFix` disarms the trap and restores the idle, no
fix path marks it `FuckedUp`. `Item.OnTrickDone` pays `TrickScore` once
(`AlreadyTricked` guard, linked pairs pay both) into `GameInfo.TrickDone`, which
flips `Won` at `WinningTricksCount`.

Verified end-to-end on Level101: fridge → egg → microwave armed; drawer →
fart bag → sofa armed; the neighbour sits, the whoopee cushion fires, 25 points,
1/4 tricks, the sofa comes back fixed, and the meter decays from 100 at 4.23/s.
The locked first-aid kit correctly refuses to open.

In the viewer: click an item to use it, digits 1–9 select inventory, 0 clears.

## The infinite-loop release and the mutex handshake

`RoutineActionUse.OnActionStarted` (RoutineActionUse.cs:152-171) can release
"infinite" animations on named targets. It fires **on arrival**, not when the
routine step begins — `ActionManager.StartAction` interposes a `MoveAction`
first when the pawn is away (ActionManager.cs:146-171; the `SameZone` shortcut
is only the urgent Dog/Chili run). `ItemToStopInfiniteAnimation` and
`PawnToStopInfiniteAnimation[WhenTricked]` get `SetIgnoreInfiniteLoop(true)`,
letting a looping `InfiniteLoop` animation reach its end, and the
`...IgnoreInfiniteAnimationOnce` variants set the once-pair that auto-clears
the first time such an animation completes (AnimationControllerBase.cs:124-127,
213-217). `OnActionStopped` (cs:326-341) resets them and fires the on-end once
target. The tricked variants read the raw `Item.Tricked`, not the `IsTricked()`
chain. Six Season-2 levels use these — 205, 206, 207, 210, 213 in their action
lists, 208 via `ActionsToAddInGame`.

The stop side also carries the mutex handshake (cs:342-351): a non-mutex
action naming `PawnToAbortMutexOnFinish` unhides that pawn and calls its
`AbortActiveMutex` (cs:127-134), which finishes the parked action *without*
`OnActionStopped` — flags a mutex action set at its start deliberately leak.
Level205's beach mat keeps its infinite loop released forever, in the original
too. `HideOwnerDuringUse` hides the owner while parked (cs:174-177) or for the
span of the use (cs:213-216), unhiding at the stop (cs:481-484). Level205 runs
entirely on this: the neighbour parks on the mat's mutex while Olga uses it
hidden; her stop springs him, and his next use springs her parked mutex back —
before the handshake existed here, both routines sat parked forever.

Verified: Level205's cross-cycle loops both routines with Olga hidden for the
span of each use; Level206's Mother has her ignore flag flip exactly at the
neighbour's action[1]/action[3] start and stop. The pawn references are
component pids — JSON object keys are strings while the refs are ints, which
silently broke the first lookup.

## Priming (§7)

An item with `RequirePriming` has to be armed before its trick fires; 21
levels use it. Ported method by method:

**`Item.WoodyPrime`** (Item.cs:1246-1300): the held inventory changes type to
`PrimedInventoryType` (Level108's key becomes the poison this way — the locked
first-aid kit "contains" nothing), `SetPrimed(true)`, the inventory is consumed
when `RemoveInventoryAfterRequirePriming`, `ObjectToPrimeWhenPrimed` chains
recursively (with `UnlockObjectToPrime`), and `WoodyPrimeAnimation` plays on
Woody.

**`Item.SetPrimed`** (Item.cs:1169-1243) + the TrickItem override
(TrickItem.cs:996-1010): the `DontPrimeWhileTricked` guard, `DeltaLocation`
gaining/losing `DeltaPrimedLocation` (one nonzero case in the data, Level107's
1.3 x-shift — and `Item.Start`'s `SetPrimed(Primed)` means every *unprimed*
item subtracts it at load), the `ShowOnlyWhenPrimed` / `HideWhenPrimed`
visibility, and the primed idle (`PrimedTricked` when tricked, else
`PrimedNormal`; `PrimedFuckedUp` after a failed fix).

**The `CanWoodyUse` gates**, in the source order (Item.cs:1510-1688): holding
anything at a plain non-TrickItem that needs no priming is a flat no (1510); a
neighbour-primed (`RottweilerUseTogglesPrime`) item refuses Woody until primed
(1520); a held inventory whose *source item* is unprimed primes on its
designated `PrimingItem` and refuses everywhere else (1537, with the
`RequirePrimingOnlyWhenTricked` variant at 1599); an unprimed item Woody holds
something at primes by `PrimeWithInventory`, refuses with no `PrimingItem`, and
**falls through the whole `UseOnce`/required/locked cluster** when a
`PrimingItem` is designated elsewhere (1615-1641 — the block ends without a
return and the cluster sits in its `else`); an unprimed held source never
counts as the `RequiredInventory` (1671). The spent-`UseOnce` gate (1654) rides
along. Inventory entries carry their source item the way
`SearchItem.InternalUse` sets `inventory.Item = this` (SearchItem.cs:172).

**The neighbour's side** (`Item.Use`, Item.cs:1056-1095): a
`RottweilerUseTogglesPrime` item alternates — unprimed → `SetPrimed(true)` +
`RottweilerPrimeAnimation`, primed → `SetPrimed(false)` + the plain use;
`RequireUnprime` makes it three-phase (prime, use, unprime). No prime animation
means `StopCurrentAction(canPostponeStop: false)` — no angry postpone.
Level103's cake shows the cycle: visit one primes it, visit two plays
`BirthdayNormal`.

**After-use side effects** (`RoutineActionUse.OnActionStarted`, cs:262-301):
`GameObjectToPrimeAfterUse[Tricked]` toggles the target's `Primed` — at once on
a zero delay, else on a `GameInfo.Invoke` timer (Level206's Fifi chain uses
1.35 s) — and `GameObjectToTrickAfterUse` flips its `Tricked`.

The name-hack branches (hard-coded `name.Equals` sites in the source) are
ported for every item on the documented list, each against its lines:

- **FirstAid** + key (the only way Level108's kit opens; the `FirstAidPos`
  teleport stays unverifiable — the fields are not serialized).
- **ValveMain** — the Woody-click toggle owning the valve's state, the
  completion-arm exemptions, and the early-loop unprime animation swap
  (Item.cs:1335-1338).
- **Iron / Rope** — single-shot once tricked (TrickItem.cs:311), the Rope
  reset on Fix (416-420), `TakeOffIronPrimed`'s flags, the two routine jumps
  (ActionManager.cs:213, Rottweiler.cs:461), and Iron's `WrongTrick`
  exemption on a spent click (Item.cs:1665).
- **PigKeys / Pig / PigMilk** — the take marks `ItemRemoved`
  (SearchItem.cs:192-206, with `KeepFull` and `TrickAfterWoodyUse`), taken
  keys answer WhatsUp (Item.cs:1515), the neighbour's pass restores or takes
  them by `Primed` (1057-1063), the Pig's fix resets the keys
  (TrickItem.cs:426-429), and the primed-keys surprise gate (837-841).
- **Pipe** — the collider follows the neighbour's prime state
  (Item.cs:1085, 1331), honoured by the click hit-test.
- **Rake** — the compound lands only once tricked (TrickItem.cs:511).
- **GroundMarbles** — `MarblesNextAction` makes the urgent resume repeat the
  interrupted action (Item.cs:1384, ActionManager.cs:614, 642-646).
- **DirtyCarpet** — excluded from the generic notice run (Rottweiler.cs:188);
  its own urgent rides the unported Dog/Chili yell choreography.
- **WaterPuddle** — `SetPrimed` negates its `DeltaLocation` outright
  (Item.cs:1196-1200) and Fix re-primes it (2089-2092).
- **LionStatue** — accepts its priming inventory only once tricked
  (Item.cs:1544-1553).
- **ElectricTrapTatter** — primes bare-handed, skipping the gate cluster
  (Item.cs:1643-1651).
- **IceBucket** — the prime chain re-arms it for a bucket round and writes
  its target off as `FuckedUp` (Item.cs:1274-1281).
- **Cow** — flowers become a priming item and the cow primes at once
  (Item.cs:1760-1780).
- **Snake / Mouse / AngryElephant** — the held mouse arms by target and type
  (Item.cs:1385-1410), the snake round sets `SnakeAux208` and turns the
  mouse into a snake (1554-1560), and the `DoublePrimingItem` elephant arm
  primes and eats it (1573-1589). The `InventoryToAdd` rat grant rides that
  unported machinery.
- **DogFifi** — the first prime swaps the put animation in.
- **Beer** — `BbqDirty` 0.3 s after a fix (TrickItem.cs:472-480).
- **Plant / WateringCan** — the removal arms of `RemoveActionByItem`
  (ActionManager.cs:748-790) and the can's parked second round
  (ActionManager.cs:196-199).

Outside that list the source still carries one-off Season-2 scene hacks
(SandCastle, AztecThrone, MechanicalBull, CaptainDoor, PlantCarnivore, Hatch
and kin) living in flows this port does not model; the Rake→Kid crying and
the Dog/Chili yell choreography stay with the level behaviors.

## The fixing-tool run

Some tricks are cleaned with a fetched tool — Level111's dirty carpet and the
vacuum. Two triggers, both in the source:

- **`Item.RottweilerUse`'s head** (Item.cs:847-852): using a raw-`Tricked`
  item that names a `FixingItem`, with empty hands and `IsNeutral()` (the
  `Neutral` field on a TrickItem) or `ForceUseFixingItem`, calls
  `Rottweiler.RunToFixingItem` instead of the use. The urgent (notice/alerter)
  path reaches this too, because the urgent action is a `RoutineActionUse`.
  With the right tool already in hand the item is fixed outright and the tool
  used instead (cs:854-857).
- **`TrickItem.TryFix`** (TrickItem.cs:1115-1134): no `CanFix`, but a
  `FixingItem` named and hands empty — same fetch; otherwise `FuckedUp`. The
  `LetUntrickTrickedItem` tail rides along.

`RunToFixingItem` (Rottweiler.cs:1077-1082) shifts the tricked item's stand
spot by `DeltaFixLocation` and chains three urgent actions serialized on the
Rottweiler: `RoutineActionGrab` (the `GrabSequence`, then the tool hides and
he carries it as `Rottweiler.FixingItem`), `RoutineActionUseFixingItem` (a
tricked non-neutral tool fires its own trick first and the action redoes —
`RedoAction`; else `CanFix = true`, `TryFix`, and the `UseFixingItemSequence`),
and `RoutineActionReturn` when `ShouldReturnFixingItem` (the `ReturnSequence`,
the tool reappears). `GetTrickedItemToFix` resolves to `DependsOn` when
`FixDependsOn`.

Verified on Level111: the tricked carpet sends him to the vacuum (grab at
t≈6, the vacuum sprite hides), `VacuumLoop` plays at the carpet and it fixes,
the return leg puts the vacuum back and the routine resumes — 9.5 s
end-to-end. `TryFix`'s earlier port approximated this branch with the wrong
field (`FixItemTrick`); it now follows the source.

A dedicated verification pass exercised the rest and fixed four deviations
it exposed:

- **The tricked tool plays its own tricked use first** (`FixingItem.Use` →
  `RottweilerUse` → `PlayAnimation`), the angry flow riding its end — with
  a glued vacuum the order is `VacuumLoop`, `VacuumDustExplosion`,
  `AngryEasyUp`, `FixMid`, then the `RedoAction` re-entry cleans the carpet.
- **`GotTricked` marks at the top of `RottweilerUse`** (Item.cs:836-838, the
  raw flag) — not after the sequence check. Level113's invisible valves have
  no use animation at all, and the sink/radiator `DependsOn` chains hang off
  that mark.
- **An empty use sequence still runs the stop flow** — the sequence
  completes at once and `StopAction(canPostponeStop: true)`'s angry postpone
  fires; the earlier port skipped straight to the next action.
- **A fetch started from `TryFix` owns the resume** — the angry-completion
  path must not advance the routine over the running Grab/UseFixingItem
  chain; the interrupted action resumes from `StopUrgentAction` instead.

Level113's full circle now closes: Woody opens the main valve, the
neighbour's own valve turn marks it `GotTricked` (which is what starts the
sink spraying — `IsTricked` needs `DependsOn.Tricked && GotTricked`), the
sink use goes angry *at the sink* (`DependsOn.ForceFixOriginal`,
RoutineActionUse.cs:564 reads the dependency's flag), `TryFix` cannot fix it
and fetches the valve, and `FixMid` at the `GetTrickedItemToFix` target (the
valve, `FixDependsOn`) stops the spray — 11 s from the sink use. The
`RequireUnprime` trio cycles on all four items (Level111's machines,
Level114's gramophone): prime, use, unprime, repeat.

The raw-`Tricked` question is resolved. Nothing sets the sink's own flag —
that entry (Item.cs:847 with `ForceUseFixingItem`) really is dead data in
this build; the live circle runs through three pieces read out of the
source and now ported:

- **The ValveMain name-hack** (Item.cs:1714-1726, the `CanWoodyUse` tail):
  Woody's click toggles `MainValveOpen` — opening arms `Tricked` **and**
  `GotTricked` at once, which is what starts the sink spraying immediately.
  Both arms of `OnUseAnimationCompleted`'s trick toggle explicitly skip
  ValveMain (TrickItem.cs:305, 315) — the hack alone owns the valve's state.
- **`RemoveActionByItem`** (ActionManager.cs:748-774, minus the Plant and
  WateringCan hacks): `StopAction` removes spent actions
  (RoutineActionUse.cs:415-427) — the item's own when `ShouldDestroy()` and
  `IsTricked()`, every action of a `ShouldDestroy` raw-`Tricked` dependency,
  and `RemoveFromRoutineAfterFirstUse`. The sink's use-stop drops both valve
  actions this way (`RemoveFromRoutineAfterUseTricked` on the valve; the
  valve is `Neutral`, so its own-arm never fires — only the dependency arm
  does).
- The rest is the fetch already in place.

End-to-end on Level113: Woody's click sprays the sink at once; the sink use
goes angry and the routine loses its two valve visits (10 → 8 actions); the
fetch turns the valve back (`FixMid`) and the spray stops; a second Woody
click closes an already-fixed valve cleanly.

## Detection, catching, the two endings (§6)

`World.tick` runs `GameInfo.Update`'s Classic checks every frame: the detection
predicate, then the all-tricks win.

- **`CanRottweilerSeeWoody`** (GameInfo.cs:181-192) verbatim: same zone, neither
  warping through a door, neighbour not `IgnoreWoody`/`IsSleeping`, Woody not
  `Hiding`, `(!blocking || !sneaking)` on his side, no blocking animation on
  Woody's. The `Bed` case swaps the sleep term for "Woody is moving".
- **The catch** (`OnNeighborCaughtWoody` → `FinishGame` → `Rottweiler.HitWoody` →
  `RoutineActionHitWoody`): input locks, Woody plays `FearLeft/Right` facing the
  neighbour, the neighbour drops his routine and walks over, Woody's sprite
  hides, and one of the four serialized hit sequences plays — the beating is
  drawn in the neighbour's sheets. Its end is `FinishAnimationEnded`.
- **The win**: `CompletedTricksCount >= TotalTricksCount` waits the coroutine's
  2.5 s, then `PlayWinAnimations` — everything freezes and Woody plays
  `WinAnimation` (`WinGame`).
- **Hiding** (`HideItem.InternalUse` → `Woody.Hide`, `Woody.Unhide` →
  `HideItem.Leave`): using a wardrobe hides Woody at once and plays `Hide_In`;
  any new move leaves it, restoring the wardrobe idle and playing its
  `LeaveAnimation`.
- **Sneaking** is the port's toggle (`Woody.ToggleSneak`), applied at each move
  start — and `StartMoveToLocation` sets `InUrgentMove = !Sneaking`, so **a
  plain click is a running move** (`RunningForceMagnitude`, 2.0 u/s for Woody),
  sneaking the slow one (0.52 u/s). Tab in the viewer. Woody's walk animation
  override plays `Run_*` unless sneaking (Woody.cs:890-936) — Season 2's
  Woody sheet has no `Walk_*` frames at all, which is how the port's
  hard-coded `Walk_` was caught; every other pawn walks (Pawn.cs:1175-1188).
- **The Mother catches too** — `CanMotherSeeWoody` (GameInfo.cs:194-199) is
  the neighbour's non-Bed chain checked as the `else if` after his
  (GameInfo.cs:222-224), and `OnMotherCaughtWoody` mirrors the catch:
  `Mother.OnCaughtWoody` runs the same `HitWoody` (Mother.cs:108-111), and
  every Season-2 Mother carries all four hit sequences. Her
  `Mother.CanSeeWoody` defers to level behaviors (not ported, default true).

Standing in the open while the routine passes through your zone gets you caught;
19 of the 28 levels do exactly that to an idle Woody within three minutes.

## Alerters and the alarm plumbing (§6)

The sleeping pet is an `Alerter` item running a three-flag state machine
(`Alert`, `Awake`, plus "asleep" as neither) in `Alerter.Update` and its
coroutines; `runtime/world.py`'s `AlerterFSM` ports it method by method.

**Waking up.** `Alerter.CanSeeWoody` needs Woody in the pet's zone, not hidden,
and *not* "sneaking" — where `Woody.IsSneaking` is true both when the sneak
toggle is on **and when he stands still**, so only a moving, walking-openly
Woody wakes the pet. Seeing him starts `CoRoutineWoodySeeAlerter`: after
`AlerterDelay` seconds (re-checked at the end) the pet plays
`AlertSequenceStart` plus the directional bark (`AlertLeft`/`AlertRight` by
which side Woody is on), and the bark chains on itself while the alert holds.
The pet's sprite is the `SleepSequence[0]` frame at load, because
`Alerter.Start` plays the sequence instead of an idle — its `IdleNormal` is
`NONE`, which everywhere else means "no sprite" (six of the seven pets were
invisible until this).

**Woody flinches.** The same coroutine calls `Woody.PlayShortFearAnimation`:
`PauseMovement`, a blocking `FearShortLeft/Right`, and `RestartMovement` when
it ends — the path is kept, not dropped; Woody stalls mid-run and walks on.

**The neighbour investigates.** `CoRoutineRottweilerHearAlerter` (same
`AlerterDelay`) raises the alarm: `ActionManager.StartUrgentAction` aborts the
current step and runs him to the pet's target item; a `PostponeAlarm` action
parks the alarm until the action ends, and if he is mid-`MutexAction` the alarm
defers (`WasAlerted`) until he next moves. Arriving plays the surprise/search
set, then the routine resumes where it left off.

**Begging and going back to sleep** — `Alerter.OnAnimationSequenceCompleted`:
the neighbour entering the pet's zone plays `PoorSequence` (begging, no chain),
leaving plays `WakeSequence`; when a completed sequence finds Woody no longer
visible it drops `Alert`, and drops `Awake` into the `SleepSequence` **only if
the neighbour is out of the pet's zone too**. That guard is why the unit test's
pet "refused" to sleep: Level113's neighbour *starts* in the dog's zone. With
him elsewhere the full cycle closes — bark at t=0.0, alert dropped at t=3.1,
asleep again at t=11.2.

**`NoticeWhenEnterZone`** rides the same plumbing without a pet:
`TrickItem.Start` registers the item in `Zone.NoticeOnEnterItems`, and the
neighbour entering the zone of the tricked item runs `RunToTrickedItem` — a
startled look (`PauseMovement` + single animation), then the urgent run.
Verified on Level102's TV: 20 points and `FuckedUp`, since `CanFix` is false.

Level112's dog is an *inactive* GameObject and nothing in the level's data
references it — no `ActivateItemAfterFix`, no behavior, no script. It is dead
content in this build; the port gates the FSM on the sprite's existence,
which only active objects get.

## The HUD

`HUD.cs` (1491 lines) is serialized whole on every level — textures as
external PPtrs, layout as rects, the face strips as TextAsset file-name
lists. `tools/export_level.py` resolves all of it into a `hud` section
(re-exported with the rest of the JSON verified byte-identical), and
`runtime/hud.py` ports the drawing and the input:

- **Coordinates** are `Helpers.AdjustRectangleRelatizeSize`: a rect's x/y are
  screen fractions, its width/height design pixels over 800×600. The mouse
  test is `Helpers.PointInRect` (Unity's y is bottom-up; SDL's is already
  top-down).
- **`DrawHUD`'s order**: base bar (the Mother levels swap in the alternate
  art), inventory (real icons — `inventory/I_<type>_{hov,norm,pres}` for
  Season 1, `inventory2/<type>_{hovered,std,down}` for Season 2 — with
  selection, hover bubbles after 1 s, and paging arrows), buttons (power,
  complete-episode once `Won`, sneak with its toggle state, info), the angry
  meter (the full strip clipped bottom-up by `AngryMeter`, plus the whistle
  `HUDAnimation`), the trick coins (the `InitializeTricks` ladder layout with
  its count-dependent fudge factors, the celebration strip on a new trick,
  the statue), the clock, the faces (idle/laugh/sleep/angry strips driven by
  `HUDAnimation`), the think bubbles with the current action's item icon
  (`RoutineAction.BubbleIcon` → `Actor.BubbleIconPath`, a Resources string —
  the Alerter's mad icon included), the score screen, and the angry count.
- **The clock** is `GameInfo`'s: timed games count down from `TimeMinutes`
  and end the game at zero (`TimeUp` → the score screen), untimed ones count
  up; `NFH2Path` hides it.
- **The score screen** ports `CalculateScore` / `CalculateRating`: viewer
  rating = trick scores + completed × `CompoundTrickScore` (capped by the
  angry count outside tutorials, at 100 overall), the Season-2 formula
  `completed × 90 / total (+10 at exactly one angry tick)`, the
  EXCELLENT/GOOD/PASSED/FAILED/TIME UP bands, and working Restart / OK
  buttons.
- **`CheckClick`** consumes HUD clicks before the world sees them: icon
  selection, paging, the sneak toggle (`Woody.ToggleSneak` — Season 2 only
  flips the flag, it has no sneak sprites), power (the in-game menu is not
  modelled), complete-episode (`FinishGameOnHUDClick`), the faces.
- **Text** renders through SDL_ttf with the game's own faces:
  `tools/extract_strings.py` carves the Font assets' embedded TTFs (the
  acmesa and bluehigh families, 36 per season) and pulls the localization
  TextAssets (`Localization/Final/`, nine languages, `KEY<>VALUE` lines) into
  `fonts/` and `strings/`. Each `GUIStyle.m_Font` resolves to its face name
  in the hud section — the clock is acmesa22, tooltips bluehigh18 — with the
  design size baked into the name; `LocalizationManager.GetString` backs the
  rating messages, the Restart/Ok buttons, the `Use X with …` tooltip pieces
  (`Woody.UseString`/`WithString` keys off the pawn), inventory names and
  hover descriptions. A `MoveOnly` action's think bubble shows
  `MoveZone.BubbleIcon`, resolved by the exporter (four levels use it). Sizes
  still approximate `LevelDataGUIRenderer` by plain screen scaling.
  `HUDProgressBar` depends on the unported `ProgressBar` actions and is
  skipped.

## The level behaviors

`runtime/behaviors.py` ports every `ActorBehavior` / `RoutineBehavior` /
`SearchBehavior` subclass the scenes actually wire — 47 classes across both
seasons — plus the hook plumbing they hang from:

- **The hooks** come from the animation controller: `InitializeCurrentAnimation`
  fires `Owner.BehaviorPlayAnimation(name)` on *every* animation set, and
  `Refresh` fires `Owner.BehaviorOnAdvanceFrame(CurrentIndex)` right after each
  frame advance (AnimationControllerBase.cs:112-114, 384; Actor.cs:93-115).
  `AnimPlayer` exposes both as hook lists. The sequence-ended hook exists only
  on the Rottweiler (Rottweiler.cs:448, 514-524) and fires when a *real*
  `PlayAnimationSequence` drains — the `PlaySingleAnimation`-with-delegate
  wrappers (door passes, startled looks, fears, Woody's single-shot uses) pass
  `as_sequence=False` and stay silent. `CanSeeWoody`, `OnCaughtWoody` and
  `CanCheckSurpriseActionFar` gate detection, the catch and the zone-change
  alarm check (Rottweiler.cs:209-216, 1218-1239; Mother.cs:103-124), and
  `Pawn.RoutineBehavior` gets `OnMoveToRoutineAction` / `OnStartRoutineAction`
  from the two `StartAction` paths (ActionManager.cs:119-124, 165-168).
- **Wiring is data**: `Actor.Behavior` plus `SecondaryBehaviors` on the pawns,
  and on five items (the Vacuum, GroundSkates, PoolBoard, Bird perch, Mug) the
  *same component instance* rides the item's controller too, so both frame
  streams feed one state machine — the original relies on that.
  An inactive GameObject's component neither updates nor hooks.
- **`AnimationGUIDepth` is runtime state**: behaviors reshuffle draw depths
  constantly (Level201/211/213, SandCastle, ParrotLedge), so the viewer now
  re-sorts sprites by depth every frame instead of once at load.
- **The sequence model** grew `SetSequenceOverride` (redirects the next
  `PlayNextSequenceAnimation` pull; MotherWakeSleepBehavior and the Mother
  urgent both use it), `OnLastSequenceElementPlaying` (the `AlertNext` phone
  ring, Rottweiler.cs:256-263), and the two in-sequence name-hacks —
  ChairAssembly's hide at index 1 and Olga's `TowelSleep` turning itself
  infinite (AnimationControllerBase.cs:261-275).

Alongside the behaviors this pass ported the triggers they sit on:

- **The walk-nearby slip** (`Rottweiler.UpdateWalking`, cs:833-849 +
  `RoutineActionSurpriseNear`): a tricked `NoticeWhenWalkNearby` item within
  `NoticeWhenNearTrickedDistance` interrupts the walk with the facing-matched
  surprise set; a tricked one goes angry at the stop. This is what starts the
  Level112 skate ride.
- **The SameZone yell** (ActionManager.cs:442-481, Rottweiler.cs:485-510): an
  urgent run to *Dog* or *Chili* in the pawn's own zone starts the action at
  once, walks him over, yells the `SurpriseSequenceLeft` within 0.05 of the
  target, and a first element named `Angry` then fires the DirtyCarpet urgent
  that `OnChangeZone` always skips.
- **The phone alarm chain** (`Item.OnIconPressed` via HUD.cs:944,
  `RaiseAlarm`, `Rottweiler.OnAlarmRaised`, `PhoneBehavior`;
  Item.cs:2176-2209, 2429-2448): clicking the mobile's inventory icon stops
  Woody, plays `DirectUse`, and `ActionDuration` later the neighbour runs to
  the alarm item for a full use. `AlarmNextAction` (Level105RoutineBehavior's
  gate) re-checks the pending alarm when the routine advances
  (ActionManager.cs:39, Rottweiler.cs:897-901).
- **`ActionsToAddInGame`** (ActionManager.cs:814-842): the Mother's use of the
  tricked `ChangeActionsWhenTricked208` Fifi splices the serialized extras
  into both her and the neighbour's routines (TrickItem.cs:1253-1262).
- **KidActions and the Kid pawn** (ActionManager.cs:394-419, Kid.cs): the Rake
  visit starts the kid crying, Olga's mat hands him the remote, the bridge
  rail brings the submarine back — fired from `StartNextAction` only, which
  is why the port distinguishes `first`/`advance` (StartNextAction) from
  `skip`/`start` (bare StartAction) resumes; the urgent-skip resume never runs
  the extras (ActionManager.cs:608-648).
- **The walking props** (RoutineActionUse.cs:181-200, Rottweiler.cs:939-1030):
  `CakeAction` / `GiveFifi` / `GiveSkates` and their removals swap the whole
  walking set — pie, bowling, Fifi, ski and WC variants, including the portal
  climbs; Mother and Olga run in urgent moves (Mother.cs:183-234).
- **The SearchItem state switcher** (SearchItem.cs:214-244): each
  Tricked x Primed combination plays its Full/Primed/Tricked/Empty animation
  once — Level206's Fifi-harpoon poses ride on it.
- **A frozen manager swallows urgents**: `StartUrgentAction` and
  `StopUrgentAction` both return silently while `Frozen`
  (ActionManager.cs:604-606, 657-660) — the skate ride depends on the parked
  resume staying parked until `ScriptUnfreeze`.

### The pattern files: Season 2's frames and sounds lived in TextAssets

`AnimationInstance.SetupPattern` parses `PatternFile` — a TextAsset with the
frame indices *and* the sound keys — and 3917 Season-2 animations (plus one in
Season 1) carry their timing there rather than in the serialized
`Pattern`/`Sounds` fields. The exporter now resolves those files inline
(`tools/export_level.py`, `parse_pattern_file`), which changed every Season-2
level JSON: animations that played a raw 1-frame range now run their real
patterns — the ski slide is 116 frames long — and Season 2 gained its
frame-keyed sounds. Season 1's re-export is byte-identical. Every frame-index
check in the Season-2 behaviors (`FifiPutLeft` 12, `MotherPoolLadderLeave` 49,
`RiceToiletPaper` 100/120/180, the Mug's 25/57, the pistol's 65, the cow's 27)
was dead before this.

### Divergences this pass caught or documents

- **Pawns never actually hid.** `Pawn.SetHidden` sets `AnimController.Hidden`
  (Pawn.cs:1464-1467), and the transit code hides the controller for every
  pawn (Pawn.cs:1615-1635, 1661) — but the port kept a `Pawn.hidden` field the
  renderer never read. Door passes, `HideOwnerDuringUse` and the mutex parks
  now hide the sprite itself (`Pawn.set_hidden`; Woody's override still flips
  `Hiding` instead, Woody.cs:1086-1089).
- **The Level112 skate ride parks, by the source's own arithmetic.** The
  comeback run's arrival door sits at x=5.03 with `ExitAnimation Stand_Left`;
  `BreathLocation.x` is 5.0 and `MinXDelta` 0.3, so the door-exit stand
  triggers `Breath()` — which the very next `UpdateWalkingAnimation` kills.
  `Stand_Left` has 6 frames and `BreathEndFrame` is 29, so the Shout never
  fires and the manager stays frozen; only a caught Woody (`OnCaughtWoody ->
  End`) unparks him. The port reproduces exactly that. Also
  `SurpriseSequenceLeft` on the skates is empty — the original throws in
  `PlayNextSequenceAnimation` and parks the slip when he walks up leftward;
  the port's empty sequence completes at once instead (the same convention
  the invisible valves rely on).
- **Audio-only arms are noted, not faked**: Level105's phone-ring and
  Level114's gramophone toggles drive looping `AudioSource` objects, outside
  the port's frame-keyed sound model; their gate flags and counters are kept.
- **`TrickProgressBarBehavior` keeps state only** — the `ProgressBarTrick`
  overlay belongs to the unported progress-bar rendering.
- **`BirdMovementBehavior`'s cadence**: the original schedules one
  `Invoke(MoveTowards-step, DelayTimeToMove)` per Update; the port keeps a
  timer queue with one 1/60-s step per firing, which is the same movement at
  the same delay.
- **`GameObject.SetActive` is approximated** as sprite visibility plus the
  click collider (`World.set_active`, and by-name quad toggling for the bare
  wash-bucket objects).
- **Dead hooks stay dead**: `ActorBehavior.OnPlayAngryAnimation` has no caller
  in the build, `Level.LevelBehaviors` is empty in every scene (only the
  no-op `LevelNFH2TutorialBehavior` subclasses `LevelBehavior`), and
  `Level212Behavior`'s branches are empty in the shipped code.
- **`RottweilerUseTrickedLinkedAnimation`** joined `sequence_for` — the
  linked-pair head of `TrickItem.PlayAnimation` (TrickItem.cs:804-816) — since
  Level207/210's behaviors rewrite it at runtime.

## The use side-effects

The block `RoutineActionUse` and `Rottweiler.PlayAngryAnimation` hang their
flags on, ported end to end:

- **The started run** (RoutineActionUse.cs:201-307, in source order): the
  toilet flag, `TeleportRottweilerOnUse`, the tricked hide-after, the whole
  `HideObjectDuringUse` family (`...Tricked`, `...TrickedWithDelay` through
  the Invoke queue, `HideChildRendererDuringUse`, `ObjectToHideDuringUse[Tricked]`,
  `ObjectToActivateDuringUse`, `PawnToHideDuringUse`), the linked-tricked
  layer swap, the prime/trick-after-use tail, and the Bed mark
  (`IsRottweilerSleeping`, which also refuses Woody the bed —
  TrickItem.cs:537-541).
- **The stop run** (cs:386-535) fires on *both* stop calls of a tricked use,
  exactly as the original calls StopAction twice around the angry set: the
  door and item unlocks (`Door.Unlock` switches to the alternate idle and
  reopens the zone graph), the four exit deltas with their one-shot aux
  flags and the `DontUseOn` and `WasPriming` gates — the positive-component
  check on the item deltas is the original's quirk and is kept — the
  unhides, the after-use hide/show, the layer restore, and the Harpoon
  hand-off (cs:541-545) paired with the LaunchPad head
  (TrickItem.cs:896-902).
- **`PlayAngryAnimation` is now the whole method** (Rottweiler.cs:552-797):
  the `DontGetAngry` resets, `CheckFinalPosition` (with the
  `FinalDeltaLocation*` triple, the exact variants and the `NormalPosAux`
  one-shot — also run from `StartNextAction` for
  `UseFinalPositionsInBeginning` and the WaterPuddle), the Chef /
  ChairAssemblyBook / LiveBull / MumStatueFootStool name-hacks,
  `HideObjectDuringAnimation`, `ShowObjects`, `ChangeItemAnimationWhenAngry`,
  `ObjectToShowBeforeAngryAnimation`, `PlayBeforeAngry`, the compound
  double-count guard, the extra-angry insert with its sand-castle gate,
  `FixDirectly`, `AngryWithoutAnimations`, and `ReuseAfterFix` restarting
  the action instead of advancing.
- **The affected-pawn choreography** (Rottweiler.cs:737-753, 820-831;
  RoutineActionHitPawn / RoutineActionWaitInFear): a tricked
  `PawnToAffectWhenTricked` item parks the neighbour in his fear loop
  (`WaitInFearAction`, whose pose `ChangeHitPawnAnimation207` rewrites for
  the sand castle and shell), sends Olga or the Mother over — the hit
  sheets contain the neighbour, so the target hides — and
  `ContinueAngryAnimation` plays the parked angry afterwards, against the
  `ItemToIgnoreNextTime` re-entry gate. Olga's simultaneous tricked-use
  (`UpdatePawnToAffectAnimation`, Item.cs:868-882) and
  `ChangeItemAnimationWhenAffected` ride along.
- **The toilet run**: `CauseRushToToilet` → `MoveToToilet` → the serialized
  `ToiletAction` as an urgent full use, with `FeelSick` switching the walk
  and portal sets to `RunWC*` and the flags clearing on the use end
  (Rottweiler.cs:542-550, 863-892; TrickItem.cs:683-686). The `Toilet`
  subclass with its no-paper branch instantiates nowhere in either season's
  data.
- **Woody's side**: the use teleports (`TeleportWoodyOnUse`,
  `SetWoodyXOnUse`, `WoodyTargetY`, Olga's `SetOlgaXOnUse`), `PreUse`'s
  `HideBeforeUse` / `HideOtherObjectDuringWoodyAnim`, `InternalUse`'s
  `HideAfterUse` / `ShowAfterUse` / `HideDuringWoodyAnim` with the layer
  swap and the show-at-next-single restore, and `HideDuringWoodyUseAnim`'s
  per-frame watch (Woody.cs:237-250, 381-385, 520-533; Item.cs:1919-1953,
  2225-2235).
- **The items act their use**: `PlayUseAnimation` / `PlayTrickedAnimation`
  play the item's own `UseNormal` / `UseTricked` pose or sequence during
  the neighbour's use, `OnUseEnded` returns it to idle (or
  `AnimateAfterUse` does, via the controller's animation-ended delegate,
  which also serves the zone poses' return — TrickItem.cs:688-695,
  947-994, 1059-1079).

### The tricked overlays were drawing all along

93 items carry a `TrickedObject` — a separate quad whose `Renderer.enabled`
ships **off** and flips with the trick (`SetTrickedObjectHidden`,
TrickItem.cs:295-299, 400-410, 442). The exporter never read the renderer's
enabled byte, so all 125 disabled overlay quads (the dirty microwave, the
glued binoculars, the slippery floors...) drew from level start, under the
sprites. The exporter now emits `renderer_enabled` plus the GameObject id
per quad, the renderer honours it, and `SetObjectHidden` /
`SetActiveObjectHidden` toggle the quads too — the overlay appears on the
trick and vanishes with the fix, and `CheckDestroyWhenTricked` also drops
the notice registrations (TrickItem.cs:656-665).

An `Urgent` routine action is approached at a run
(RoutineActionMove.cs:68-75; the 206/208/210 Mother calls), its
`ContinueToNextAfterFinished` then matching the port's normal advance, and
`FreezeAfterCompletion` parks the manager (ActionManager.cs:539-543) — its
two data uses both sit behind the unported tutorial flows that also
unfreeze them. Still open here: `ChangeLayerInTricked`,
`IgnoreTrickedExitDelta` and `frozenDuration` are serialized but carry no
live data or code path; `KeepAnimationsInMemory` manages texture memory the
port does not model; the L211 Olga toilet-delay arm of the hit
(`DelayToiletBehavior211`) rides the unported Bouquet hack.

## Testing against the original

`runtime/record.py` drives the real `Viewer` deterministically — a fixed
60 Hz clock, scripted input, a numbered frame every 1/fps seconds and a JSON
state line every tick (Woody's position/state/animation/lock, active door
animations, the HUD face frames, routine states, the clock):

```sh
python3 runtime/record.py levels/s1/Level101.json /tmp/rec --seconds=8 --fps=2
# script lines: wait N | click X Y | clickworld WX WY | clickitem Name |
#               key sneak | inv N        (--script=file)
ffmpeg -pattern_type glob -i '/tmp/rec/f*.png' \
    -filter_complex 'scale=200:150,tile=6x3' -frames:v 1 /tmp/rec/sheet.png
```

The contact sheet gets eyeballed, `state.jsonl` gets asserted on. For the
reference side, pull the original's gameplay video (yt-dlp + ffmpeg), cut a
coarse grid to locate the moment, then a fine one, and hstack a frame pair.
This loop caught two real bugs the flag-level tests had passed over:

- the texture cache tried every candidate exact-case before its
  case-insensitive pass, so the base-name candidate kept hitting the old
  colliding flat faces and the portraits sampled a third character's strip
  (the flat `idle_0003` hash-matches neither Woody's nor the neighbour's);
- the camera showed the void past the house — `CameraMover` clamps the
  viewport corners into its serialized `[MinX,MaxX]×[MinY,MaxY]`
  (CameraMover.cs:378-394), now applied after the follow. The reference
  frame and the port's, side by side at the entrance moment, agree on
  layout, clock, HUD and the door pass; the original's wider slice is the
  phone's 16:9 against the design 800×600.

## The sleep bars

`ProgressBar`/`HUDProgressBar` are ported whole (ProgressBar.cs,
HUDProgressBar.cs). The bar's GameObject ships inactive; `Item.Use` turns on
the Rottweiler-actor bar at its head and the Mother-actor bar at its tail,
`MotherUse` and `RottweilerPrime` their own (Item.cs:831-834, 861-864,
1110-1113, 1322-1325). The fill runs while the item's
`CurrentAnimationSequence` matches an entry and `CurrentSequenceIndex` sits
in `[start, end)` — both stamped from the use dispatch and the sequence step
hook (AnimationControllerBase.cs:277-284) — and `SetSleeping` drives
`Pawn.IsSleeping` (a detection gate), the HUD sleep/blind faces, the
think-bubble disable and the face drain overlay. A `CanSee`/urgency latch
kills a non-`Mother210` bar for the level (ProgressBar.cs:125-142).

A data observation, not a divergence: the serialized `Duration` is only the
fill-rate denominator. The bed's 29 sleep elements play ~0.52 s each
(2 frames at 2 fps, `animationTime` starting at 0 and `ReachedEndFrame`
being strictly greater — AnimationControllerBase.cs:103-141), so the dog
wakes at ~50% of the L109 bar in the original too.

`Item.OnSequenceIndexChanged` (Item.cs:2693-2726) rides the same step hook:
the six `AnimationsToControl` tables hide/show the item — or another item —
at their start/end element indices, including the shipped quirk of showing
the *hide* target on the last item index (cs:2722-2725).

## The walk-through stairs

All 116 Season-2 transitions are `ComplexMove`, and the original never warps
them: `Helpers.LinkNodes` (Helpers.cs:225-357) expands each hop into walk
steps — `NFH2Stairs` pairs walk the pawn diagonally to the far side's
per-pawn `GetTargetLocation` (Item.cs:2010-2050), flat pairs walk through at
`TargetLocation`, and a `TransferToZone` step runs `ChangeZone` with the
zone search reactions. Woody's mid-stairs re-click shapes consume the
`Helpers.StepIndex`/`FirstStepIndex`/`DonePassingHelper`/`OriginalStartZone`
statics verbatim, and `FindPath` starts from `GoZone` when he is already
crossing (Helpers.cs:86-106). Pawns claim both sides of a transition while
passing (`PassingPawnTransitionNFH2`, Pawn.cs:996-1030) and stand when the
pair is held; `PassingComplexMove` and the `DonePassingToOtherZone`
y-tracker (Pawn.cs:319-342) now sit in both catch predicates as themselves
(GameInfo.cs:189, 198). `AdjacentZonesEnabled` is per-pawn data — Season-2
Olga ships without it and walks the stairs unclaimed, as shipped.

One deliberate divergence, documented in the walking loop: the original's
variable `Time.deltaTime` breaks up the y-axis approach, but a fixed 1/60
step can oscillate forever around a target narrower than one velocity step
(the arrival window `2*MinDist = 0.02` against a `0.0267` step). The port
extends the existing x crossing guard to y — cross, snap, arrive.

## The dexterity minigame

`DexterityComponent` is ported whole (DexterityComponent.cs): the GUI rects
anchor at the component's screen position after `SnapToWoodyImmediate`, the
pick drifts on a once-a-second random vector (`Dificulty` 2) against the
player's touch/mouse delta, the margin clamp swaps in the alarm field and
boosts the drain to 1.2, and the fill follows the center-distance sway
(cap 25, win 85, lose 10 with the `DexterityCannotLose` floor at 12).
`CanWoodyUse`'s chain (Item.cs:1438-1507) arms the search and trick-item
branches — Woody loops his `DexterityAnimation`, the component enables, the
use is refused — and the `DexterityDone` pass unlocks, spends the unlocker
(unless the keep flags say otherwise) and falls through to the normal take.
Losing plays `DexterityFailed`, restarts the game and alerts the
Rottweiler: at once if he is walking, else deferred through
`RottInAnimation` to the item Update watchers (SearchItem.cs:245-251,
TrickItem.cs:243-249). The viewer feeds mouse deltas, freezes the camera
and mutes clicks while `IsDexterityOn`.

## Not implemented

From `docs/GAMEPLAY.md` §6–§7: the tutorial layer — `LevelScript` /
`LevelScriptAction` (the arrows, message boxes and `DirectorAnimation` of the
three intro scenes and the two NFH2 tutorial levels), the
`TutorialScriptCamera*` scripts and the `SignalScript*` completion hooks that
feed them; the in-game menu's widget tree (`LevelDataGUIRenderer`, the
save/quit buttons) — the power button runs the pause half of
`Woody.ToggleMenu` (time freeze + the HUD fill hide) without the widgets;
and the name-hack branches listed at the end of the priming section.
