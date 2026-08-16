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
sheet — 684 sprites in total over the 37 exported scenes (600 item
controllers, 84 pawn controllers):

```
Level101  drew 17/17 sprites; missing sheets: 0
...
Level214  drew 22/24 sprites; missing sheets: 0
```

39 of them have no CurrentAnimation after Start and 22 are hidden, so a
load-time shot legitimately draws fewer than it holds — L202 draws 18 of 19,
L207 27 of 29, L211 24 of 26 (see "IdleNormal == 'NONE'" below; the earlier
"546" counted only the controllers with a resting pose, and the six sleeping
pets that draw their `SleepSequence[0]` instead of an idle). Sprite counts
vary a lot by design: Level213 has 36, while Level201 has 8 because that
level paints most of its scenery into the backdrop instead.

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
  standing mid-room. Season 1 only: the S2 levels serialize
  `Pawn.FinishedEntrance` TRUE — no walk-in, `StartGame` plays the
  `Entrance` greeting in place (see "The final audit").
- **`IdleNormal == 'NONE'` means "no CurrentAnimation yet", not "not a
  sprite"**. Every active `ItemAnimationController` with loadable sheets is a
  sprite; one whose resting pose is NONE starts with no current animation
  (`Sprite.current is None`) — the controller exists from Start and OnGUI
  draws and refreshes nothing until the first play
  (AnimationControllerBase.cs:172-189; `Item.Start → PlayIdleAnimation →
  PlayItemAnimation(NONE)` is skipped, TrickItem.cs:1018-1050). 121 item
  controllers live that way: every S2 SearchItem's Full/Empty look, the
  ElectricTrap spark loop, the washing machine, the gramophone, L107's
  drawing... An earlier rule ("giving it a sprite draws the wrong thing")
  came from drawing frame 0 at load; the fix is the null current animation,
  which is also what keeps `SetObjectHidden(false)` from drawing anything on
  such an item. An `Alerter`'s `Start` plays the `SleepSequence` instead of
  an idle. `Sprite.hidden` is the other flag — `AnimationControllerBase.Hidden`
  (SetObjectHidden, HideWhenNotAnimating), which also freezes Refresh.
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
move and `SpeedSneaking` in place of `Speed` while sneaking. So the
neighbour walks at `1.25 x 0.7 = 0.875` units per second — and Woody, whose
plain click is an urgent move (`IsInUrgentMove = !Sneaking`, Woody.cs:858-861
→ the Running magnitudes, Pawn.cs:961-975), runs at `2.5 x 0.8 = 2.0`; only
the sneak toggle gives the `1.25 x 0.8 = 1.0` walk. (The reference footage
measures 1.99–2.06 u/s, docs/audit/verified/pass5_video.md.)

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
One lap is 47.9 seconds — the sofa sequence 17.0 s, the peep 7.2 s, two
transits and four walks (the reference footage measures 47.87 s between two
sit-downs; an earlier build ticked every pawn controller twice per frame and
read "about 35 s" — that number was the bug).

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
`AbortActiveMutex` (cs:127-134), which marks the parked action Finished and
calls `AdvanceToNextAction`, whose `StartAction(next)` stops the still-Active
mutex action first (ActionManager.cs:157-160) — its `OnActionStopped` runs
after all: the ignore-loop resets (cs:326-341), not the non-mutex block
(cs:342: OnUseEnded, the abort branch, the alarm checks). Level205's mat gets
its InfiniteLoop back the moment the neighbour is sprung. `HideOwnerDuringUse`
hides the owner while parked (cs:174-177) or for the span of the use
(cs:213-216), unhiding at the stop (cs:481-484) — and a hidden controller
does not animate at all: `AnimationControllerBase.OnGUI` runs `Refresh` only
when `!Hidden` (cs:177), so a pawn behind a door pass, under
`HideOwnerDuringUse` / `PawnToHideDuringUse` or in the wardrobe, and a hidden
item, stand on their frame and resume when shown. That is what the Level205
handshake is built on: Olga's mat use hides her, so her own `HitPawn` never
ends it; `TrickItem.PlayOlgaAnimation` plays the mat's `UseNormalSequence`
with `Olga.OnItemAnimationSequenceEnded` as the sequence delegate
(TrickItem.cs:964-975, 988; Olga.cs:154-158 — `CurrentAction.StopAction(
canPostponeStop: true)`), the neighbour's mat mutex releases the mat's
InfiniteLoop step on his arrival (`ItemToStopInfiniteAnimation`) and re-arms
it when he is sprung, so she sunbathes until he comes to watch (her use spans
his whole lap), the mat drains 11.4 + 4.4 + 1 s after he parks, her stop
springs him, and his tennis stop springs her; both cycle for the level
(400 s headless: 3 / 4 laps — before the item-side delegate both parked for
good after the first lap). Level210's mat is the second `PlayUseNormalSequence`
carrier; the two are the only non-mutex `HideOwnerDuringUse` actions in the
data.

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

- **FirstAid** + key (the only way Level108's kit opens). `FirstAidPos` is
  not level data but internal initializers in the class body —
  `(-5.98, -2.544, -0.001)`, Item.cs:640-646, assembled in `Start` — and
  Level108's kit transform already sits exactly there, so the ported
  teleport is a verified no-op on the shipped scene.
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
port does not model. The L211 `DelayToiletBehavior211` arm of the hit
(RoutineActionHitPawn.cs:23-27) is dead in the shipped build — it compares
`GameInfo.Instance.Olga` with the hit's `Target`, and the only callers of
`RunToHitPawn` (Rottweiler.cs:741, 752) pass the Rottweiler; the port keeps
the writer (`StopOlgaInfiniteLoop`) and the live `else` arm.

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
fill-rate denominator. `Refresh` runs `ResetAnimationTime` after
`StopSingleAnimation` has switched to the next element
(AnimationControllerBase.cs:137-141), so every element after the first lasts
frames/FrameRate — the bed's 2-frame 2 fps `BedSleep` a full 1.0 s, and the
bar's [2, 31) window of 29 elements ≈ 29.0 s against Duration 29.3: the bar
fills to ~99% and the neighbour wakes on the last element. (An earlier build
ticked every pawn controller twice per frame — 0.5 s per element and a bar
at ~50% when he woke; that was the bug, not the design.)

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

The y-axis arrival guard, closed with numbers: an urgent (running) vertical
approach steps `RunningDoorForceMagnitude/60 = 1.6/60 = 0.0267` per tick
against an item step's arrival window of `2*ItemUseHeight = 0.02` — under a
fixed 1/60 clock the position oscillates around the target forever (walking
speed, `0.8/60 = 0.0133`, always lands). The original runs the same
arithmetic in `Update` under a *variable* `Time.deltaTime`, whose jitter is
the only thing that ever breaks the loop; its resting error is anywhere up
to `MinDist = 0.01`. The port extends the existing x crossing guard to y —
cross, snap to the target, arrive — which rests at error 0, inside the
original's envelope, on the first crossing. Not an open question: the
outcome is the original's converged behavior, reached deterministically.

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

## The parity audit (docs/PARITY_AUDIT_PROMPT.md)

Four passes over the decompile, the engine contracts it leans on, the level
data and the reference footage. Everything found was either fixed against a
named method or written down here.

### Fixed in the audit, each against its source lines

Rendering and data:

- **Click hitboxes ignored the transform.** BoxCollider sizes are local:
  the binoculars' box is (10, 4, 14.37) with scale (0.023, 1, 0.037), and
  most items rotate X by 90° so the screen height is the local z. The port
  used the raw x/y — the binoculars' hitbox covered half the level and ate
  the fridge's clicks. Colliders now go through the world matrix
  (`Level._world_box`); the binoculars land at 0.23 x 0.53.
- **Quad textures resolved by bare name.** Four L201 chests all serialize a
  texture literally named `ms_0000`; the cache landed them on L211's deck
  rail and drew rails instead of the deck chair and chest (S1's workbench
  had the same silent swap). The exporter now replicates the extraction's
  collision numbering for quads, the Level fences and the item tip icons
  (`ms_0000~3`...).
- **`Level.OnGUI` fences** (Level.cs:322-341, LoadFenceSize cs:244-252):
  L201/206/211/214 draw garlands and deck rails between the pawns and the
  HUD (GUIDepth.LevelFence); 208/209 serialize `DisableFences`.
- **`Item.OnGUI` interaction icons** (Item.cs:2740-2760) behind the HUD
  info button's touch-hold (`ShowInteractionIcon`, HUD.cs:835-895) — 7-29
  items on every level carry `ItemTipIcon`, drawn at `ItemTipIconDepth`
  in the same depth-ordered pass as the sprites.
- **`HideOwnerOnAnimationEnd` / `ShowChildRenderersOnEnd`**
  (StopSingleAnimation, AnimationControllerBase.cs:226-233): 88 + 14
  animations. Woody now actually disappears into the wardrobe at the end
  of `Hide_In` — before this every HideItem (all 32 ship `HideWoody=false`)
  left him standing visible next to it.
- **The catch, the score screen and the outcomes**: `LoseAnimation`
  (Woody.cs:1120-1127), the exit-door finish (Pawn.cs:1662-1665, gated on
  the real `FinishedEntrance`), score-style text colors from the
  serialized styles, the statue resting grey on frame 0
  (InitializeHUDAnims starts only the three idle strips, HUD.cs:415-436).

Movement and world state:

- **`Door.DeltaExitLocation`** (Woody.cs:476) and
  `DeltaMotherExitLocation` (Mother.cs:60): 196 doors place Woody at their
  own exit offset over the base `DoorDistanceDelta` warp.
- **`WoodyDeltaUseHeight`** (Pawn.cs:1690-1705) + `UseWoodyExtraDeltaHeight`
  (Woody.cs:744-755, Item.cs:2286-2288): Woody's climb-arrival window on 77
  items.
- **Transition walk deltas** (Woody/Mother/Olga `CheckMoveLocationY`):
  61 transitions shift the ComplexMove step per pawn.
- **`Passable`** gates the end-of-step snap (Pawn.cs:1032-1035, 1725-1728);
  `DisableOnStart` kills L214's captain-door pair; `IgnoreIdleAnimation`
  doors (8) only exist on screen during a pass (Door.cs:157-160, 210-213).
- **`MainValveOpen` is serialized TRUE** on L113's ValveMain: the
  neighbour's first prime closes it (Item.cs:1352-1355), his use re-opens
  it (TrickItem.cs:570-573) — the port had hard-coded False.
- The crab zone reactions play INVERTED strips through
  `Pawn.CrabAnimations` (Pawn.cs:1560-1596, SearchItem.cs:275-293), with
  the NFH2 TrickItem pass gated on `!Primed`; the plain door-pass channel
  stays TrickItem-only.
- The Coal walk-in swap (Item.cs:988-1002), the CabinPhone urgent alarm
  (Rottweiler.cs:869-877), `GoNextAction` read from data (L113's valves),
  `PrimedMouseOverIconName` (Item.cs:1215-1218),
  `TakeItemMultipleTimes` + `DoNothingWhileBeeingUsed` gates
  (Item.cs:1415-1437), `SearchItem.OpenObject` (61 items visibly open for
  1.5 s/1 s, SearchItem.cs:125-152, 250-268), `UseFixedStrings`
  (Item.cs:2113-2118), and the Mother beats from where she stops —
  RoutineActionMotherHitWoody never calls MoveToEmptySpace.

Input, HUD, and timing:

- **The full click contract** (Pawn.GetMoveDestination, Pawn.cs:556-714 +
  the Woody overrides): own-zone doors are crossed (the cut-tail
  StopAtExitDoor path), locked Transitions swallow the click, locked doors
  refuse with Stand_Down and their description, floor items follow
  CheckTargetItem/ShouldGoToItem with `WrongZoneTooltip`, a missed click
  with a held inventory clears it and keeps the old route, and blocked
  input buffers and replays (StoreBlockedInput, Woody.cs:642-656, 336-341;
  `BlockWhenItemPick` locks without buffering on 181 items).
- **The description bubble** (Item.ShowItemTooltip → HUD.DrawDescription,
  HUD.cs:673-709): every refusal speaks — descriptions, InventoryTooltips,
  NotPrimedTooltip, locked doors — cleared by MoveToGoal and FinishGame
  (the occupied-bed and empty-wall lines cannot show: `TrickItem.CanWoodyUse`
  refuses the slept-in bed and `Drawing.CanWoodyUse` the hidden drawing
  before `base.CanWoodyUse` reaches `CheckDescriptionTooltip`,
  TrickItem.cs:537-542, Drawing.cs:81-88 — `ItemInUseString` /
  `EmptyDrawingString` are dead strings). 218 items carry tricked variants;
  the Fuckedup/Compound/CheckDependsOn name overrides ride
  TrickItem.cs:1164-1225.
- **The two-stage inventory** (Current → Used, HUD.CheckClick
  1309-1322) with the colored latched tooltip (UpdateTooltip /
  MakePermanentTooltip, yellow 0.86/0.86/0) and door/exit-zone hover
  tooltips (MouseCursor.cs:302-347).
- **The Hello greeting** ends the entrance and its blocking end unlocks
  the input (Pawn.cs:1064-1067, Woody.cs:304-312); the 30-second boredom
  poses (Woody.FindInput, cs:612-623); the routines' 1.5 s DelayStart;
  the postponed alerter flinch during a use (Woody.cs:1033-1044, released
  in Update cs:232) and the FearRepeat loop after it (Woody.cs:343-353).
- **Season 2's anger ladder** (Rottweiler.cs:613-693): the meter
  accumulates `AngerAmount` (10..80 in data) with the extra-coin hacks,
  levels pick the sets, and only overflow costs a tick — with
  RottFreakoutHead (Random.Range(0,1) is always 0), the statue strip and
  the whistle. Classic keeps the old two arms plus the audience laughs
  (`Medium/BigLaughs`, Rottweiler.cs:805-818) and the HUD anger faces by
  level (PlayRottweilerAngry), idling again when the strip ends.
- **Sound**: MusicPlayer is ported — the entrance clap at load, the level
  track after the 15 s first-run delay (MusicPlayer.cs:88-98), the caught
  / success (perfect at a 100 rating) / failed jingles
  (GameInfo.cs:304-390). `tools/fsb_to_ogg.py` rebuilds the FMOD-Vorbis
  banks (40 clips; python-fsb5). The whistle sound rides
  PlayWhistle (HUD.cs:1473-1481) from the compound tricks and S2 statues.
- **The camera is free**, per the desktop contract (UpdateWindowsInput,
  CameraMover.cs:110-165 — dead code on Android, but the desktop original
  is the reference): 5 px edge scroll and arrows at Speed*(Sensibility*3)
  with SpeedX aspect-scaled, HUD face clicks interpolate over
  (MoveVelocity 0.5/s), FinishGame snaps to Woody and freezes
  (GameInfo.cs:368-369), and the dexterity snap sits exactly on Woody
  (CameraMover.cs:468-471 — no +0.6). The viewer's follow camera is off by
  default; `F` re-enables it as a convenience.
- Dexterity: the margin drain boost is dead in the original (FillSpeed is
  unconditionally reset to 1 before the drain reads it,
  DexterityComponent.cs:237-243) and the port no longer keeps it; the
  DexterityRunOtherAnimation win plays the literal `N2TrickItemUseNormal`
  (cs:374-379) — both carriers serialize UseNormal as NONE.
- The whistle frame breathes: WhistleRects[i] averages the adjusted rect
  with each frame's own pixels (HUD.cs:353-357). DescriptionStyle's
  serialized ContentOffset (y=-10), Padding (4/4) and WordWrap now apply,
  long descriptions use the big bubble (HUD.cs:995-1008), the Mother
  levels park the tooltip in TooltipMotherRect (HUD.cs:611-614), and the
  world progress bars draw beneath the HUD strip (BackHUD=12 vs HUD=11).

### Documented divergences and dead data (with numbers)

- **Trick camera**: a whole sleeping subsystem (Level.IsTrickCameraEnabled,
  SnapToRottweilerImmediate, the HUD frame, the camera-shaped cursor). The
  PlayerPrefs setting defaults off and `ForceTrickCamera` is false in all
  28 levels; the settings menu is not modelled, so the port leaves it
  unimplemented.
- **The ExitConfirmation dialog** before an exit door is a menu widget
  (Control*); the port ends the level directly on the pass.
- **Dead fields with data but no reader in any .cs**:
  `AlternateStartFrame` (11644 values), `OverridesTransformation` (56; its
  only reader Pawn.cs:893 has no caller), `SlowAnimationsFactor` (=100
  everywhere; nothing sets ShouldSlowAnimations), `AnimationAngryCollapse`
  / `FixAnimationExtra` (on every Item), `PrimedOffset` /
  `ChangeScaleWhenPrimed`, `MouseOverLockedIconName` /
  `MouseOverSystemForTutorial` (no data), `Alerter.PoorSequenceSkates`,
  `ArrowSignDepth` (0 scenes), `AudioInstantiate` (empty class),
  `StatueAchieved` (set, never read), and ~35 more listed in the audit
  notes (`docs/audit/pass{1,2,3}_*.md` — the raw pass reports).
- **GameMode is Classic in all 31 scenes** — DrawLives and the Modern
  scoreboard are dead; `HasFingerPressed`'s double-tap click gate and the
  touch-only skip of the finale (GameInfo.cs:257-289) are touch-input
  paths the desktop reference never hits.
- The exporter now reads the built-in Camera and AudioSource payloads:
  every playable scene serializes an orthographic camera of size 3.0 (the
  four size-100 perspective ones are menu scenes) and every
  LevelMusicSource ships loop=true — both asserted across the data and
  consumed instead of the old hard-codes. The last FSB bank
  (`na2_shout3pool`, PCMFLOAT) decodes to a float WAV in
  `tools/fsb_to_ogg.py`, so all 41 clips play.
- The click raycast picks the collider nearest the camera: hitboxes carry
  their world z and items compete with doors on it, as Physics.Raycast
  orders hits. Dexterity rects use the original's integer division
  (600*190/800 = 142, not 142.5); the clipped styles (the clock, the
  score fields, both tooltips ship m_TextClipping=1) crop their glyphs to
  the rect.
- The ProgressBar-vs-HUD Start order is settled: the bar's GameObject
  ships inactive, so its Start — which copies HUD.RottweilerFaceRect into
  PawnHUDRect — runs at the first in-game activation, long after
  HUD.Start's AdjustRectangles. The port's adjusted rect is correct.
- `Item.IsAtUseRange`'s walk-up arm skips its y-check for the DontUseOn
  pawn — kept, as the original does.
- Woody's transit locks the input for the span of a door pass
  (PlayDoorLeaveAnimation, Woody.cs:459-463) and the arrival unlocks and
  replays the buffered click (Woody.cs:471-488) — without the lock a
  mid-pass click built a second route and the pass animation played
  twice. Clicking the door he is standing on — the one he just came
  through — passes it at once (ShouldExitDoorNow + UseDoorAtOnce,
  Woody.cs:777-780, Pawn.cs:769-777, 1391-1397), and the first click
  after leaving a hiding spot re-targets the wardrobe as a plain walk
  (the WasHiding arm, Woody.cs:798-808). The door-exit frame runs the
  stricter catch predicate — no sneaking escape, no Bed arm
  (Pawn.HasNeighborCaughtWoody, Pawn.cs:366-388, wired at Woody.cs:495
  and the zone-crossing watch). The four hit sequences pick at the
  original's 26/25/25/24 thresholds, and the win freezes only the
  neighbour until FinishAnimationEnded (GameInfo.cs:304-313).
- The prime family closed out: PrimedMaterial swaps the first-aid quad to
  'firstaid_open' (Item.cs:1236-1239), DisableColliderWhenPrimed /
  DisableMesh kill the tatter's clicks and sprite (cs:1253-1261),
  EnableColliderAfterPrime wakes L104's shelf pair (cs:1326-1329), and
  the Flowers-with-knife pick converts the held knife and hands a fresh
  one back (cs:1421-1426). The idle sequences play where flagged
  (TrickItem.cs:698-731 — the Pig, the Airer, the bull, the carnivore,
  the parrot ledge), DontPlayIdleOnStart keeps L109's Chili invisible
  until first played (cs:214), IgnoreDependsOnWhenFixed frees the fixed
  Pig's idle, BlockValveAfterFix re-arms L113's valves to demand a
  balloon (cs:421-425), AnimateDependant echoes every PlayItemAnimation
  onto the Dependant (cs:1046-1049), TrickItem.KidActions plays the
  kid's sand-castle reactions (cs:632-653), and the Mother's think
  bubble honors SpecialBubbleForMother (RoutineAction.cs:59-70).

### The recorder and the moment suite

`runtime/record.py` now drives a virtual mouse as real input (hover art,
tooltips, the info-button hold), glides it between targets or on a
`mousetour` across every item and door, and adds `pause/resume`, `dex`,
`forcewin`, `follow` and `cam`. `tests/run_moments.py` replays seven
moments — entrance, tooltips, the refusal bubble, the catch, the sleep
bar, the forced win, the pause — and asserts each guarded class over
`state.jsonl` (16 checks). Reference stills from the mobile walkthrough
footage matched the port's anchors on the entrance, the held-inventory
tooltip line, and the whole right edge (the grey statue, the x0 counter,
the coin ladder) — the last after the statue-frame fix above.

## The final audit (docs/FINAL_AUDIT_PROMPT.md)

Six passes over what happens *in time* — the flag lifecycles, an input monkey
with invariants, the trick matrix, name twins and silent defaults, the frame
timings against the footage, and the reverse audit of runtime/ — after the
parity audit above had checked what was written. Counters and the per-pass
verdicts are in `docs/audit/FINAL_AUDIT.md`; the verified per-area reports
(every claim with its C# lines, the port lines before/after and its check)
are `docs/audit/verified/*.md`; the drafts they were verified from are
`docs/audit/raw/`. The regressions: `tests/run_moments.py` (the moment suite
plus every `tests/checks/*.py` module), `tests/monkey.py --all` (the monkey,
28 levels × seeds × 180 s), `tests/run_tricks.py --all` (28 trick plans).
What the passes fixed, by area — each against its lines:

### The animation core

- **Every pawn controller refreshes once per frame** — the port ticked a
  pawn's AnimPlayer twice (once in the players pass and again from
  `Pawn.tick`), so every pawn animation ran at 2× its FrameRate: the sofa
  sequence in 8.5 s instead of 17.0, the sleep in 14.7 s instead of 29, the
  lap in 35.8 s instead of 47.9 (AnimationControllerBase.cs:172-189).
- **`UsePattern` gates the pattern** (AnimationInstance.cs:66-76, 186-234):
  262 instances carried a stale `Pattern` next to `UsePattern=false` (L113
  LadderTestTransition: 15-16 vs a 40-frame pattern) that the original never
  reads. `UsePattern` with an empty Pattern (36 instances: PutEel ×14 whose
  PatternFile is a GUID stub the build never shipped, Olga's stand-infinite
  poses, L101 SitSurprise) ends a single on its first step and holds sheet
  frame 0 when looping. A pattern animation draws `Pattern[index]` unclamped —
  4557 of 6260 pattern animations ship an EndFrame below their entries (L209
  FireFakir's idle: 127 entries, EndFrame 0), which the port used to clamp to
  (cs:228-234).
- **A frame past its sheet.** `DrawAnimation` never checks `CurrentFrame`
  against the sheet; a Single that ends with nothing set after it keeps
  advancing, and `Graphics.DrawTexture` samples the out-of-range source rect
  by the texture's wrap mode — Repeat wraps the row back onto the sheet, Clamp
  smears the texture's bottom edge row over the cell (cs:153-170).
  `draw_sprite` emulates both from `textures/<season>/wrap.json` (each PNG's
  `m_WrapMode`, written by `tools/extract_textures.py`; `--wrap-only`
  refreshes an old extraction): S1 1253 clamp / 325 repeat, S2 1743 / 692.
- **StopSingleAnimation's two tails** (cs:234-246): a real
  `PlayAnimationSequence` ends in `OnAnimationSequenceEnded` /
  `StopCurrentAction` and never stands; a single ends in
  `SwitchToStandAnimation` in the same Refresh unless a delegate returned
  true — the arms that do all start something (an animation, the stored
  click's move, the finish, the FearShort→FearRepeat loop, Woody.cs:330-353).
  The port used to skip the stand whenever a callback was attached and drew
  the past-the-end cell for 1/FrameRate (the Hello's Stand_Down came 0.083 s
  late against the footage). `PrevAnimState` is never written in the original
  (PawnAnimationController.cs:165-172 sits behind a `Type == Looping` test the
  strict Single lookup cannot pass), so the stand after any bare single
  (idles, NoNo, Hello, the win/lose pose) is `StandDownAnimation`; a Looping
  current resolves by its own name (Walk/Stand/Run/RunWC families, WaitWatch,
  WaitInFear), and the original throws "Stand with nothing before" on other
  loops (pie/fifi/ski/bowling walks) — the port keeps the last facing's stand
  there.

### The clock, the finish and the HUD

- **`GameInfo.Update`** runs in the original's order — the neighbour's catch,
  the Mother's, the all-tricks win, then the clock — behind `!GameEnded &&
  !GameEnding` (GameInfo.cs:212). The moment `CompletedTricksCount >=
  TotalTricksCount` is seen, `GameEnding` is set and the 2.5 s
  `WinGameAnimations` coroutine starts (cs:292-302): the clock stops, no catch
  can fire, the HUD answers only the power button — but Woody's own clicks
  stay live (`CheckMouseClick` gates on `Woody.Frozen`, Woody.cs:637), so he
  can walk and even use an item during the wait. `PlayWinAnimations` then runs
  `FinishGame` (cs:358-371: the neighbour drops the cake, `Woody.Freeze` +
  `InputLocked`, the bubble closes, the camera snaps and freezes,
  `CalculateScore`), Woody's `WinAnimation`, `Rottweiler.Freeze` — the pawn's
  own freeze, `SwitchToStandAnimation` + `PauseMovement` (Rottweiler.cs:
  1095-1099), not the routine's — and `PlaySuccess(perfect: true)`. `GameEnded`
  (the score board) comes only from `FinishAnimationEnded` (cs:343-356) at the
  end of the pose: the sleep bars are disabled (`DisableAllProgressBars`,
  ProgressBar.cs:303-307) and Woody, the neighbour and the Mother freeze. The
  clock running out is `TimeUp = true` + `FinishGameOnHUDClick` (cs:241-249,
  373-390) — `Won` is untouched: a player past `WinningTricksCount` still gets
  the success jingle and the EXCELLENT/GOOD/PASSED band; TIME UP is the `!Won`
  band (cs:438-465). `Woody.PlayFinishAnimation` (Woody.cs:1104-1128) defers
  mid-door-pass until the arrival (cs:490-493) and, hiding, leaves the spot
  first and rides the leave animation's blocking end (cs:331-334); an
  exit-door pass finishes AFTER the ExitAnimation loop (Pawn.cs:1652-1665).
  `ForceWinGame` (`forcewin` in the recorder) is the tutorial's immediate win:
  all tricks, `FinalTrickScore = 100`, `WinImmediate` (cs:315-321).
- **The tooltip line**: every write is `SetTooltip` (HUD.cs:1024-1060,
  latch-gated, GoTo renders empty), and `DrawHUD` clears an unlatched line
  after every draw (cs:646-649). Every non-icon click runs
  `SetUsedInventory(CurrentInventory)` unconditionally (cs:1320,
  Woody.cs:1062-1073) — the used inventory lives for exactly one click — then
  `UpdateTooltip` latches the current arm in yellow unless it is GoTo, dropped
  again when nothing (Item or Door) sits under the cursor (cs:1321-1327); the
  latch clears when the walk ends (`Woody.OnPathFinished`, cs:361-362) or the
  item use runs its tail (`Item.UseItem`, Item.cs:1916) — a silent refusal
  (no NoNo, only the bubble) never sets `UseCompleted`, so the item step stays
  open and the latch survives until the next click. Only `CurrentInventory`
  draws pressed and drives the use-inventory cursor (MouseCursor.cs:362-373);
  its line is "Use X with <hovered item's name>" (cs:942-955); an unselected
  icon under the cursor speaks "Use X with nothing" (cs:962-967); the 1 s
  bubble needs a DescriptionString (cs:991). `OnInventoryAdded` pages to the
  newest item, `OnInventoryRemoved` clamps with the pre-removal count
  (cs:898-914, InventoryManager.cs:20, 53). The angry meter repaints at 10 Hz
  (cs:1240-1248). The recorder's `inv N` and the viewer's digit keys stage
  `CurrentInventory` (the icon click); the next world click promotes it.
- **Font sizes come from the screen, not the face**: `HUD.Start` sizes each
  style by `LevelDataGUIRenderer.CalculateFontSize` — `((W/1024)+(H/768))*10`
  truncated, minus the style's adjust (HUD.cs:335-342, cs:177-191); at 800×600
  the clock is 18, the tooltips and score fields 13, the rating 15, the
  description bubble `W/1024*13` = 10, the sleep bar's percentage `+3` = 18
  (ProgressBar.cs:79). The size baked into the face name (acmesa22,
  bluehigh18) is the asset's, which the runtime overrides — the port drew
  22/18 px.
- **The music anchor**: the clap and the 15 s `Invoke("PlayMusic")` start at
  the scene load (MusicPlayer.Start cs:43-51, Level.Start → LoadSettings,
  Level.cs:295-297), and the `IntroAnimation` title cards run for the seven
  serialized stage times — 7.79 s on Level101 — before `StartGame`, the
  port's t=0 (IntroAnimation.cs:86-112, 278-315). The port resumes the clap
  7.79 s in and arms the track at 15 − 7.79 s; the reference measures 7.08 s
  from StartGame to the track — the seven `WaitForSeconds` add the device's
  frame latencies (~0.14 s at 30 fps), which a fixed 60 Hz clock does not.
  `StartGame` also plays the `EntranceSound` (levelstart, 7.78 s) on its own
  `EntranceSoundSource` (`PlayEntranceMusic`, MusicPlayer.cs:122-135) — the
  level track starts under it; the port gives it a second reserved channel.
  Detection needs `ActionManager.CurrentAction` (GameInfo.cs:183-196): none
  during the 1.5 s DelayStart. `Door.Unlock` never changes the zone graph
  (ZoneController.cs:8-28 builds it once).

### Woody's input and movement

- Standing on the door he just came through (AtDoorLocation + LastExitDoor),
  any click whose path starts back through it passes at once from the doorway
  — ShouldExitDoorNow + UseDoorAtOnce (Woody.cs:777-780, Pawn.cs:744-780,
  1391-1396, 1412-1416); a pawn off the floor at a door's x climbs to it
  directly (ShouldWalkDirectlyUpToDoor, Pawn.cs:785-788). Both ride the path
  build in `Pawn._route`; MoveToDoor's per-frame IsOtherPawnPassing wait
  (Pawn.cs:1359-1364) covers the climb too. A door click still runs
  `GetMoveDestination` + `MoveToLocation`: `ItemAux = null` (Pawn.cs:595) and
  `InitializePath` replaces the path (cs:480-498) — the pending item use of
  the previous route dies with it (the monkey caught a wardrobe click,
  overridden by a door click, firing its hide + `SetWoodyXOnUse` teleport at
  the end of the door pass, across half of Level105). UseDoorAtOnce is reset
  per path here; the original only ever consumes it — an arm abandoned
  mid-wait would ride into the next path (and double-play a flat door,
  cs:1384-1396). Not reproduced.
- The walk-through stairs: a pair held by another pawn parks the arriving pawn
  standing on the first approach — TransitionEnter is assigned before the
  claim (Pawn.cs:1004/1014, 1022-1027). Every stand switch while
  DonePassingToOtherZone && NFH2Path drops GoZone/DoorClicked/the flag
  (PawnAnimationController.cs:86-95), entering a path's last step restamps
  the y-thresholds and drops it (Pawn.cs:1100-1104), and CrabAnimations drops
  it on door passes too (Pawn.cs:1566 via PassDoor). While the flag is
  latched, clicks are swallowed (Woody.cs:659-662): the mid-stairs re-route
  shapes only ever run off a replayed stored click, in both games.
- The click contract: the S2 sneak toggle only flips MbSneakToggle
  (ToggleSneak, Woody.cs:1151-1163) and StartMoveToLocation forces Sneaking
  off on the NFH2 path (cs:717-720) — the S2 sheets have no Walk_* strips (the
  port crashed on a sneaking S2 walk). A click during the literal Hide_In is
  dropped, not stored (Woody.cs:642-651); the other dive poses unhide and
  replay. A paused game drops world clicks after the HUD (timeScale gate,
  cs:637); LastInputTime stamps past the gates (cs:641). Season 1 re-runs
  ProcessMoveInput when the current step's Target is a Door (cs:668-671),
  which is how a click during a door climb gets processed there. The
  WrongZone bubble speaks only for the floor-item refusal
  (WrongZoneDescritionTooltip, Pawn.cs:615), the door refusal is a bare NoNo.
  Sneaking Woody climbs with Walk_Up/Walk_Down (PortalSneak*, Woody.cs:64-66,
  952-968). A `BoxCollider`'s size is its half-extents in magnitude — the
  serialized negative sizes (L106's Pudding height, L210's ElephantCricketBat
  width) still hit; and `BoxCollider.enabled` ships off on 221 items (every
  SlipperyGround strip, L104's ApplePie until its round trip, L105's Football
  until alerted, L114's Pipe until primed, the S2 fences and props) —
  `Physics.Raycast` never hits them, `Item.clickable` starts from that byte.
- The dexterity minigame: the frame after the win `Woody.Update` re-runs
  TryUseItem on the same step (DexterityDone && !DexterityAux, Woody.cs:
  218-222); CanWoodyUse's DexterityDone branch then unlocks, spends the
  unlocker (unless the keep flags say otherwise), clears the three flags and
  falls straight past the refusal cluster to the tail (Item.cs:1462-1474 →
  1704-1730) — the take follows without a second click.
- Door strips: each pawn class plays its own Door pair — Woody, the
  Rottweiler, the Mother, Olga (Door.cs:85-139; Mother.cs:63-73,
  Olga.cs:94-104); Olga's ship NONE everywhere, the base Pawn plays none. The
  8 S2 DoorBacks serialize IdleAnimation NONE + IgnoreIdleAnimation and keep
  their pass strips (W_Disappear/W_Appear, N_*, M_*): the controller is a
  hidden sprite between passes — before this every S2 door pass was an
  invisible warp for everyone.

### The neighbour's routine, urgents and alarms

- The two parked runs are separate slots, as in the original: the
  alerter/notice run (`Rottweiler.ShouldStartSurpriseActionFar` +
  `SurpriseActionFar.Item`, cs:88/271/305; `Routine.pending_surprise`) and the
  phone alarm (`PendingAlarm`/`PendingAlarmItem`, cs:96-98/1043;
  `Routine.pending_alarm`). `CheckSurpriseActionFar` (cs:1139-1148) releases
  the first — from `ContinueAlarm`, from `OnChangeZone` behind
  `CanCheckSurpriseActionFar` (`IsFixingBlockingItem`: a Grab/UseFixingItem
  step or the walk toward one with PostponeAlarm), and from every non-mutex
  Rottweiler use stop (RoutineActionUse.cs:358-362); `CheckPendingAlarm`
  (cs:231-240: not postponed, not passing a door) releases the second as
  `MoveToAlarm` — the AlarmAction's full use — from the same use stops, the
  SurpriseFar/SurpriseNear stops, `OnChangeZone` and the AlarmNextAction gate.
  Both stops fire from inside `StartAction(next)` (ActionManager.cs:157-160),
  so a released run interrupts the action that was about to start and resumes
  it afterwards. `IsAlarmPostponed` (cs:1047-1070) is the whole six-arm
  predicate over the running template: SurpriseNear always; SurpriseFar and
  Grab by their PostponeAlarm; the interposed move by the target action's own
  bare PostponeAlarm; a use by `PostponeAlarm || PostponeAlarmDuringUseOnly ||
  Item.IsTricked()` — Level105's four actions ship PostponeAlarmDuringUseOnly,
  and every tricked use postpones. Two quirks kept as the code has them:
  `HearAlerter`'s tricked-item exception (cs:272) dereferences the
  MoveAction's Item, which is never set (ActionManager.cs:23), so a bark heard
  while *walking toward* a postponed action throws out of
  `Alerter.CoRoutineRottweilerHearAlerter` and is lost; and `!PortalMove`
  postpones a bark heard on the walk-up climb/descend, not just the door pass.
- Urgents nest as the original's `OriginalAction` chain (ActionManager.cs:
  679-718): a run landing on a running one stashes it (`Routine._urgent_stack`)
  and `StopUrgentAction`'s `StartAction(OriginalAction)` (cs:647) replays it —
  a Grab replays its GrabSequence, a UseFixingItem its TryUseFixingItem, the
  Return leg its ReturnSequence, an alerter run or toilet run its whole run;
  the exceptions are the running SurpriseNear (cs:681-691), the chain
  hand-overs (692-710), a ForceUseOriginalAction carrier (711-714 — L110's
  UseFixingItemAction: the chain is abandoned with the tool in hand and the
  next visit fixes with it, Item.cs:854-857), and the same template restarted
  on itself (cs:679). Before this the port collapsed every nested urgent onto
  the routine action, and a bark during the L110 fetch left `_fix_tool` set
  for good. Not reproduced: the original loses a parked alerter run when the
  resumed action needs no walk (ActionManager.cs:161-170), a bark parked
  during a tricked toilet-rush use fires *before* the toilet run there
  (cs:157) but after it here, and a phone alarm during the WaitInFear
  interrupts it there and replays the fear loop for good (cs:715-718 + 647) —
  the port parks it and resumes the routine.
- The urgent templates run or walk by their own `Urgent` flag
  (RoutineActionMove.cs:68-75 → `MoveToGoalUrgent`, Pawn.cs:444-448):
  SurpriseActionFar and ToiletAction run in every scene, the AlarmAction walks
  (the CabinPhone hack sets its Urgent for good, cs:872-875), the fetch runs on
  L110/L113 and walks on L111, the Return leg walks everywhere, Olga runs to
  her hit and the Mother walks to hers except on Level210. Level102's
  ToiletAction carries `ContinueToNextAfterFinished`: its end is a plain
  advance (ActionManager.cs:530-538). A `Duration` that runs out (L110's Beer,
  1.0 s) is a bare `Finished` — but its `TakeGround` drains in 4/7 s first, so
  the branch never fires in the shipped data.
- The Dog/Chili run is watched by `RoutineActionMove.SameZone()` on every
  `ActionManager.Update` (ActionManager.cs:442-448; RoutineActionMove.cs:105-
  128): the first frame he stands in the pet's zone off a door latches
  `RottPos` and `RottLastDoor` (Pawn.cs:1644-1647), and — every door of the
  Dog/Chili levels serializing `RottweilerExitLocation` (0,0,0) — that same
  frame switches the run: the surprise plays where he landed, `Finished &&
  SameZone` walks him (the plain MoveToGoal) to the pet, and within 0.05 the
  "Angry" yell of `SurpriseSequenceLeft` runs, whose end (Rottweiler.cs:
  485-510) sends him to a raw-tricked DirtyCarpet in the zone — the fetch of
  the vacuum (Level111's Vacuum trick was unreachable while the port only
  took the shortcut for a neighbour already in the pet's room). A neighbour
  who has never passed a door has no `RottLastDoor`: cs:121 throws in Update
  each frame and the manager is dead — he walks to the pet and stands — until
  the next StartUrgentAction retargets the MoveAction (Level113's neighbour
  starts in the dog's zone; the port reproduces the stall). `UpdateWalking`
  (Rottweiler.cs:833-849) runs on every walk, urgent runs included: the toilet
  rush past a tricked NoticeWhenWalkNearby item starts the near surprise,
  which chains the run as its OriginalAction and resumes it; the
  ToiletAction / AlarmAction stop angers at `GetTrickedItem`
  (RoutineActionUse.cs:548) — Level102's loo visit pays the toilet on the way
  and the ToiletPaper on the seat.
- `AdvanceActionIndex` (ActionManager.cs:566-584) wraps to the start index,
  else to `ActionSelectedIndex` only with `LoopFromSelectedIndex`, else 0 —
  Level206's Mother (LoopFromSelectedIndex false, ActionSelectedIndex 3)
  replays her whole lap; `StopOlgaInfiniteLoop` clears the flag (Item.cs:2602).
- Season 2's anger ladder: `Item.Fix` opens by clearing `Rottweiler.TrickedAux`
  (Item.cs:2065), so a re-angry on a fully scored linked pair (cs:650-652) only
  latches the meter until the next fixed trick; `CanDecreaseAngryMeter=false`
  is Classic-only (cs:793-796, and ActionManager.cs:588-591's release) —
  Season 2's meter keeps decaying through the angry set; the compound
  statue/whistle of cs:702 is `!NFH2Path`-gated. `RoutineActionUse.StopAction`'s
  angry gate is `Item as TrickItem` (cs:419) — the Drawing (L107) and the Rake
  (L202) go angry like any TrickItem (the port's `kind == 'TrickItem'` test
  missed the subclasses; every such test is `TRICK_KINDS` now). The animated
  angry never rushes to the toilet: `OnAnimationSequenceEnded` runs
  `FixTrickedItem` (cs:460, nulling `TrickedItem`) before `CheckRushToToilet`
  (cs:478-484); only `AngryWithoutAnimations` items rush (cs:721) — every
  `RushToToilet` carrier ships it.

### The items

- Two kinds of use. Only a TrickItem or SearchItem defers `UseItem` to the end
  of Woody's animation (`ShouldUseAfterAnimationFinishes`, TrickItem.cs:
  263-266, SearchItem.cs:121-124); every other kind runs it at once
  (Item.cs:1865-1871) and the animation ends into nothing (Woody.cs:412-444) —
  GroundItem and InspectItem never get that far: their `CanWoodyUse`
  overrides stand, show the description (InspectItem's primed variant once
  `ItemThatChangesTooltip.GotTricked`) and refuse (GroundItem.cs:3-8,
  InspectItem.cs:5-22) — the port used to trick every SlipperyGround and the
  carnivorous plant on a click. `Item.UseItem` (Item.cs:1879-1917) is one
  shared body — the Dove/CowCrap/Rabbit hacks, `Used`, `InternalUse`
  (HideAfterUse/ShowAfterUse, HideDuringWoodyAnim, the RubyThrone drop, the
  BlockWhenItemPick unlock with its buffer clear, the post-dexterity unlock),
  `ClearTooltip` — and the SearchItem take runs it too
  (SearchItem.OnFinishAnimationCompelted, cs:114-119), through
  `SearchItem.InternalUse` (cs:156-212): the KeepFull/TakeItemCount head, the
  source stamps (`AssignFirstInventoryOnly` stamps the first entry alone —
  L112's SportsBag, L114's DeskDrawer), the hand-over, `DisableColliderAfterUse`
  (41 S2 items), the IceBucket re-arm, `AcquiredInventoryCount`, the emptying
  (`!DontRemoveInventoryItem && !DexterityKeepItem`, else `ItemRemoved`),
  `TrickAfterWoodyUse`, then the empty pose through SearchItem's own
  `PlayItemAnimation`. The empty re-click runs the same tail after WhatsUp
  (Woody.cs:409). `SetCloseTime` runs only on a `SearchingItem`
  (SearchItem.cs:143): the 19 `SearchingItem=False` openers — the pin boards,
  the toilet-paper holders, the bins, the mobile, the soil bag, L201's soap
  chest — open and never close; a searching drawer re-closes after 1.5 s, or
  1.0 s once a take has landed. The trick tail's idle switch is
  TrickItem.cs:357-379, not `ReturnToIdleAnimation`: a compound item plays its
  tricked idle until CompoundTricked, then `CompoundDoubleTrickedAnim`; else
  the raw `Tricked` flag picks the tricked idle — a Neutral item too (L104's
  deodorant shows its hair). `OnTrickDone` pays through the virtual
  `GetTrickScore` (a compound-tricked compound item pays `CompoundTrickScore`,
  L114's Shotgun 13 over 10) and a fresh linked pair with
  `ExtraCoinLinkedTrick` pays a second time (Item.cs:2143-2146; L207's
  SandCastle counts three). `ActivateItemTrick`'s target plays
  `PlayIdleTrickedAnim` outright and the ElephantBucket rewrites its normal
  idle (TrickItem.cs:326-331); `ActivateItemAfterUsingObject` retargets every
  routine action on "CaptainControls" and activates after
  `DelayActivateItemAfterUsingObject`, dropping the LinkedItemTrick
  (cs:333-351, 382-389 — L214's grog: the CaptainWheel 11 s later).
- Priming: `WasPriming` (Item.cs:398) is the flag that keeps a prime/unprime
  visit from counting as a tricked use: `RottweilerPrime` /
  `RottweilerUnprime` raise it (Item.cs:1330, 1361), every `RottweilerUse` head
  clears it (cs:835), `IsTricked()` ends in `&& !WasPriming` (TrickItem.cs:260),
  `OnUseEnded` keeps the primed pose after a prime leg (cs:691) and StopAction
  picks `RottweilerPrimeExitDelta` over the use delta (RoutineActionUse.cs:
  458-480) — the port never wrote it. L111's washing machine tricked while
  unprimed: the prime visit ends calmly, the use visit (`IsUsing`) pays the
  angry, the unprime visit resets the idle at its start (TrickItem.cs:
  1052-1057). `DoNothingWhileBeeingUsed` reads `IsUsing` itself
  (Item.cs:1429) — L114's gramophone refuses Woody for the whole use→unprime
  stretch. `TrickItem.SetPrimed` and `ReturnToIdleAnimation` play through
  `PlayItemAnimation` (UseAnimationType → PlayAnimationDirectly, so a Looping
  strip loops; NONE hides a HideWhenNotAnimating item — L113's FuseBox drops
  its FusePlaced strip while primed). `TrickItem.Fix`'s pose tail
  (cs:457-471) replays the primed pose of a still-primed item and disables the
  ElectricTrap's controller for good. `Pawn.ElephantAnimations`
  (Pawn.cs:1536-1558) is ported: with L208's primed AngryElephant
  (`Woody.ItemBehavior`), Woody's first zone change to another zone plays the
  elephant's primed-then-idle pair and locks the SafetyLine again, once, until
  the Mouse arm re-arms it (Item.cs:1581). The L210 Valve's `N2TrickItemExtra1`
  ends into `WaterPuddleBehavior` (TrickItem.cs:1240-1251): the puddle's
  collider comes on and it shows `N2TrickItemIdleNormal`. The WaterPuddle
  name-hack negates `DeltaLocation` and `FinalDeltaLocationNormal` at every
  SetPrimed — including `Item.Start`'s, so L201's serialized +0.6 is -0.6
  from the first frame.
- Zones and crabs: `SearchItem.PlayItemAnimation` (SearchItem.cs:68-89) is
  the crabs' own twin — no Animating gate (that field is TrickItem-only), an
  unconditional unhide, the Looping flag — and `Pawn.CrabAnimations` uses it
  (L202/L207's crab strips never played before); the TrickItem lists ride
  `PlayZoneEnter` (IsTricked gate) / `PlayZoneLeave` (raw Tricked, unhide
  first), both through `TrickItem.PlayItemAnimation` so L110's BBQFullSmoke
  keeps its Looping type. `TrickItem.KidActions`' SandSculpture arm animates
  `Item.Kid` — the L205 OlgaKid TrickItem with its item-side sequences — while
  the SandCastle arm animates the Kid pawn (the port bound both to the pawn).

### Assets, data and defaults

- Every texture and clip the runtime draws is named after the file the
  extraction wrote, and the extraction numbers repeated `m_Name`s `name~2`,
  `name~3` in serialized-file order. PPtr fields resolve through the pointer
  in the exporter; animation sheets are `Resources.Load` strings and are
  resolved through the ResourceManager container into `SheetTexture` (null
  when the container has no such path — S1's Mother door strips, L213
  BoatPicnic's boat_rent/boat_unmount: the original loads nothing there
  either, the animation still runs and draws nothing). 23 Season-2 sheet
  references (18 level/sheet pairs) landed on a same-named twin before —
  L212's live bull drew the 109x72 `bull` bubble icon instead of `bull~2`,
  L202's rocks took L211's deck rail (`ms_0000` for `ms_0000~8`); the Mother's
  face, the sleep-bar strips and the camera icon had the same twins.
  Details and counts: tools/README.md, docs/audit/verified/assets_refs.md.
- Silent defaults: the exporter writes every serialized field, so a port
  default only ever bites when an `or` replaces a serialized 0/false/''.
  543 default-bearing reads audited; the ones that masked data are fixed —
  `ItemUseHeight` (532 zeros; Pawn.cs:1118 reads it raw) and
  `RoutineAction.MaximumPawnDistanceToAction` (81 zeros) are taken as
  serialized, `Door` carries `WoodyDeltaUseHeight` / `UseWoodyExtraDeltaHeight`
  / `CanUse` / `DontUseOn` like the Item it is (six L212-L214 DoorBacks widen
  Woody's climb window by 0.2-0.4, Pawn.cs:1330/1412 → 1690-1705), field
  defaults equal the C# initializers (Item.cs:220/236/246/392/432, Pawn.cs:
  203-209, CameraMover.cs:21-27, GameInfo.cs:43, Level.cs:38-40). Open, with
  0 carriers: `FrameRate = -1f`/`0` (AnimationControllerBase.cs:146: -1 =
  advance every Refresh, 0 = frozen) never occurs in the data (0 of 12374).
- Zone graph and paths: the graph is `ZoneController.Start()` minus the
  `|| TemporalLock` arm: 22 TemporalLock doors exist, all in the three S1
  intros (20 of them Locked), none in the 28 playable levels; there `LinkNodes`
  refuses the Locked door anyway, so every intro zone pair yields the same null
  path. `find_path` is a BFS: the route LENGTH equals `Helpers.GetShortestPath`
  on all 786 reachable ordered zone pairs; 66 S2 pairs (the opposite corners
  of the 4-cycles) have two shortest routes and the original's pick depends on
  `FindGameObjectsWithTag` order plus Mono's unstable `List.Sort` — the port
  takes the first door in scene order. The click raycast orders items and
  doors by the near face of their world box (`z - dz`), which is what
  `Physics.Raycast`'s hit distance ranks; 113 of the 667 XY-overlapping
  collider pairs would order differently by centre.
- Reference shorthand: comments cite the original three ways — the full
  `File.cs:NN-MM`; the short `cs:NN` (the file is the one named by the
  enclosing class/def docstring); or by member name
  (`AnimationInstance.SetStartFrame`). A grep for `\.cs:\d` alone undercounts
  by an order of magnitude.

### Season 2's start and the last plan findings

- **Season-2 start.** `Pawn.FinishedEntrance` is serialized (Pawn.cs:119):
  every Season-2 level (and the S1 intros) ships Woody's TRUE, the 14 S1
  levels FALSE. With it true there is no entrance walk — `Woody.Start` leaves
  the input unlocked (`InputLocked = !FinishedEntrance`, Woody.cs:191),
  `Woody.Update` never arms the EntranceTimer (cs:223-231), `TakeNextStep`
  never plays HelloAnimation (Pawn.cs:1064-1067; the S2 sheet has no
  `Hello`). `IntroAnimation.StartGame` (cs:300-304) locks the NFH2Path Woody
  and plays `HelloAnimationNFH2` = `Entrance` (Pawn.cs:213; 11 frames,
  10 fps, not Blocking) whose single end unlocks him (Woody.cs:372-375). The
  port's Level210 "walk-in catch" was that invented walk-in (StartLocation
  Zone02 → EntranceLocation Zone01) meeting the neighbour's DeckChair walk.
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
- **MotherSleepBehaviour.ForceSleep / ForceSleepAfterTrick** (cs:73-88): the
  Get* getters stamp CurrentAnimationSequence (MotherSecondUse /
  MotherExtraUse, Item.cs:936-940, 977-981) — L214's DeckChairMother bar
  window; the tricked arm reads the raw MotherUseTrickedAnimation
  (MotherSleepLoop) with no stamp. The forced sequence's end still stops her
  current action (AnimationControllerBase.cs:242-246: the controller's
  ActionManager, not the call's). Her bar object is re-activated by every
  MotherUse (Item.cs:1108-1116), so the L214 window repeats each lap
  (61-119, 165-223, …).
- **L214's captain cabin.** The DoorBack pair ships active with
  DisableOnStart (Door.cs:63-66); ZoneController.Start keeps the
  Zone03↔Zone05 edge (`Item.CaptainDoorBehavior`, Item.cs:2606-2623,
  re-activates both and retargets his CaptainDoor action at CaptainControls
  in Zone05); while inactive, LinkNodes finds no door and FindPath is null
  (Helpers.cs:194-205, 243-248) — `Level.find_path` refuses a disabled door
  the same way. The 6th L214 count (CaptainMug / Captain: no neighbour use,
  no linked pay) is dead by data; winning=4. Level211's FishingRod is
  unreachable by data too: its whole XY box lies inside the Zone04
  TransitionDownwards box and the door's near face (z -4.466) beats the
  rod's (-4.05) on the camera-plane raycast (Pawn.cs:403, Woody.cs:708);
  7/8 (winning 6). `Level208Behaviors.CowGetUpAux1` (cs:71-80, 112-115)
  never clears after the neighbour's first CowRide: every animation switch
  of his forces the cow to IdleNormal (AnimationControllerBase.cs:380-385),
  so the crap window (frame 27 of the primed pose, cs:118-131) needs the
  prime before his first ride or a 2.8 s span without a switch.

### The quads' texture window

A quad's material carries `_MainTex_ST` — the Plane's 0..1 UVs sample
`uv * scale + offset` — and 41 of the 267 quads use it: L101's Binoculars
shows the (0.625..0.70, 0.34..0.52) window of a 256×256 sheet (the port
drew the whole texture into 23×37 px — a speck), the Open_Chest 0.95×1,
L103-106's MumSmeared 1×2.5 from v=-0.9, L102's Beer 1.2×1.5. The exporter
now emits the window as the quad's `uv` (tools/export_level.py
`_quad_texture`, tools/assets.py `read_material_maintex_st`) and
`draw_quad` blits that source rect; the six windows that leave the texture
all sample Clamp textures, so the outside bands repeat the edge row/column
(3×3 bands at most). Viewer conveniences added at the same time (viewer
decisions, no game counterpart): a single level on the command line —
run.sh's default — still gets `[` `]` over its season's siblings, and the
score screen's OK opens the next level of the list (the original goes to
the level selection menu, LevelLoader, not modelled).

### Documented, not reproduced

- `AnimationControllerBase.Hidden` freezing `Refresh` IS reproduced (see the
  Level205 paragraph); still open: the ShouldStopAction stale latch
  (cs:344-348), the Invoke slot overwrite (GameInfo.cs:513-533), the frozen
  Woody's path resuming after the finish pose (PawnAnimationController.cs:97),
  a door-exit catch or a stored-click replay inside the 2.5 s win wait
  (Pawn.cs:366-378 has no GameEnding gate — the original then plays two
  endings over each other), the UseDoorAtOnce carry-over, the parked-run
  edge cases above, and the two hidden-use timings of the routine section.
- Dead by the data, confirmed by the plans: L112's GroundSkates 14 (both
  `OnTrickDone` paths die in the parked ride — README above), L113's
  ElectricTrap 8 (its collider sits inside and behind the basement door's,
  the raycast always hits the door), L114's Gramaphone and Pipe (primable only
  while the neighbour is in the room, no hide there), L108's ToothBrush (a
  ~0.1 s window under perfect input), L206's Weights/DynamiteBox (Zone04
  sealed by the awake Mother's infinite poses); the level's TotalTricksCount
  counts them, the win comes at WinningTricksCount.

## The menus and the flow (runtime/app.py, runtime/menu.py)

`runtime/app.py` is the whole game: the scene machine the original wraps
around the levels. `CoreFrameworkController` loads "Entry"
(CoreFrameworkController.cs:24-27); the port's `App` builds the Entry
scene's `Menu` (runtime/menu.py) over `levels/s1/Entry.json`, and a level
start swaps in the `Viewer` sharing the same SDL window, renderer, texture
cache and mixer. `./run.sh` starts it; `./run.sh <name>.json` still opens
the bare level viewer.

What runs, each class against its file:

- **The splash** — `GameIntroAnimation`: Company (2 s) → Company2 (2 s) →
  Game (1.5 s) → "tap to start"; any click/Esc enters the menu
  (`EnterGame`, cs:97-103); the static `Finished` keeps it one-shot per
  process, so returning from a level skips it.
- **The widgets** — `Control` / `ControlButton` / `ControlWindow` /
  `ControlToggle` / `ControlSlider` / `ControlRadioButton(+Group,
  Initializer)` over the exported GameObject tree with its active flags;
  `Control.SetObjectActive` toggles the object and its direct children
  (Control.cs:305-322). A click is the mouse-up over the control
  (Control.LateUpdate, cs:243-250); the pointer-over state shows the hover
  texture (the PC look; the mobile CheckTextureIndex only knows pressed).
  A widget whose window a click just activated does not see that same
  click — Unity schedules a freshly activated behaviour's LateUpdate for
  the next frame, and `OnHouseButtonStart` shares `MenuButtonStart`'s
  exact rect, so without this the season selection would fall through.
- **The level pages** — `LevelDataGUIRenderer` under the 1024×768
  `GUI.matrix`: the `L{i}T/H/D/B` strings, the Duration / MinRating /
  Record / TricksPlayed format strings, the trick coins stepping ×1.5
  width from `StartTrickRect`, the NFH2 variant (the world map with the
  season-2 totals via `CalculateTricks`, the shipped `i + 18` slots).
- **The tiles** — `ControlRadioButton`: textures rebuilt per progress
  (`_normal`/`_passed`/`_perfect` + hover/pressed), the rating percentage
  label, `LastLoadedLevel(2)` written on select, the 0.25 s double-click
  start, the group initializer re-selecting the last level on window open
  (`ControlRadioButtonInitializer.OnEnable`; out-of-range → 0).
- **The settings** — `Level.LoadSettings` defaults (Level.cs:278-307):
  Music/AudioEnabled 1, Music/AudioLevel 10, TimedGame 1, TrickCamera 0,
  Language 0, Sensibility 0.5; the sliders write `value = |mouse.x -
  rect.x| / rect.width`, the toggles flip ints, ApplySettings re-reads and
  re-applies the audio. PlayerPrefs is `runtime/prefs.py` — one JSON at
  `$XDG_DATA_HOME/nfh/prefs.json` (`NFH_PREFS` overrides).
- **The languages** — the flag buttons stage `Control.SelectedLang`; the
  options' OK (`SetLanguage`) writes the pref and reloads Entry
  (`LocalizationManager.SetCurrentLanguage`, cs:189-206); Back
  (`UnsetLanguage`) reverts. The strings come from
  `strings/<season>/<Lang|NEW_LANG_*>.txt`; the level HUD reads the same
  language (hud.load_strings).
- **The credits** — `Credits`: the names/entries XML TextAssets, the
  styles by name, the −40 px/s scroll after the 1.5 s pause, the window
  force-closing 1.5 s after the last entry crosses the top. The original
  mutates the entry rects inside OnGUI; the port moves them in `tick` so
  a headless frame advances identically.
- **The loading screens** — `LevelLoader.OnGUI` out of Entry,
  `LevelTransition` (the Transition scene) out of a level. The original
  loads async and fills the bar with `LoadingOperation.progress`; the
  port's load is blocking, so the screen draws once with the Transition's
  fixed 0.8 fill and holds `LoadTimer` (0.1 s).
- **The title cards** — `IntroAnimation`: the seven-state coroutine with
  the serialized stage times and the px/s slides (`IncrementWithCap`),
  "IN" + `L{n}T`, sizes `CalculateFontSize+5/+6`; a click/Esc skips
  (`StopIntroAnimation`). The camera parks on the neighbour for the span
  (`SnapToRottweilerImmediate`, cs:259-262) and `StartGame` glides it back
  (`SnapToWoody`). During the cards the port ticks only the ambient
  AnimPlayers (`World.tick_ambient`) — the actors wait for `CanStart`,
  the clock for `IntroAnimation.Finished` — and the world clock starts at
  StartGame, the port's t=0 (the audit's convention); the music picks up
  the elapsed card time (`World.start_music(elapsed)`), so the clap
  resumes mid-jingle exactly as the always-running original sources do.
- **The in-game menu** — `InGameMenu` over the level's own widget scene:
  Esc / the power button toggle it (`Woody.FindInput`, cs:583-586;
  `InGameMenu.Toggle` gated on the exit dialog), Enable freezes time and
  shows the `IsInGameMenu` renderer page, Continue/`DisableInGameMenu`
  resumes, Restart is `samesame`, Quit "Entry", SelectEpisode "Entry" +
  `ReturnToLevelSelection`. The score screen's Restart reloads and OK
  raises `Level.OpenLevelSelection` (HUD.cs:1287-1299); the Entry scene's
  `Level.Update` arm then opens the selection window `MenuLoader` picked —
  stamped 1/2 by Woody's path at HUD build (HUD.cs:358-368).
- **The confirmations** — `ExitConfirmation` (+`DirectorAnimation`'s
  face strip at `DirectorFaceInterval`): the destructive buttons'
  `RequireConfirmation`, the first window's Esc-to-quit
  (`ShowQuitGameConfirmation` + `EscapeAux`), and the exit door:
  a finished-entrance pass through an `ExitDoor` parks the pawn
  (`Pawn.cs:1378-1383`, `ShowExitConfirmation` → `PauseMovement`) and asks;
  Yes runs `ContinueExit`, No `AbortExit` (Woody.cs:558-568,
  Pawn.cs:1500-1515). The bare viewer has no dialog and passes straight
  through, as before.
- **The score save** — `GameInfo.CalculateScore`'s tail
  (`Level.SaveScore(GetGameOnlyLevelIndex(), ...)`, GameInfo.cs:429-435):
  tricks/rating only rise, completion sticks, Perfect is the ≥100 arm.

Port decisions, each documented in place:

- **One process, one Entry.** The original shipped two apps that launch
  each other (`ControlButton.CanLaunchApplication` /
  `BuildSettings.AppToLaunch`, ControlButton.cs:153-160); the port hosts
  both seasons and always returns to Season 1's Entry, whose
  GameSelection already carries both level selections. `levels/s2/
  Entry.json` stays unused.
- **The packs are unlocked.** `LevelUnlocker`/`LevelPackUnlocker` lock
  tiles by the store's purchase state (LevelUnlocker.cs:82-93); there is
  no store here, so every tile is open (the `TestMode` arm's outcome).
- **The Level112/113 index swap is kept.** The build order ships
  Level113 as `level16` and Level112 as `level17` (the exports'
  `unity_scene` fields), so `GetGameOnlyLevelIndex` = loadedLevel−2
  computes 15 for Level112 and 14 for Level113 — while their menu tiles
  serialize LevelIndex 14/15 and the Entry tables (`TricksTotal[14]`=10 =
  Level112's count) follow the tile order. The original therefore shows
  the *other* level's title card and writes its progress into the other's
  slot for this pair; the port reproduces it rather than fix it.
- **Fullscreen is the port's own toggle** (the PC build had one; the
  Android decompile has no SettingKey for it): a synthesized
  `ControlToggle` in both options windows, the `Fullscreen` pref,
  SDL fullscreen-desktop over the 800×600 logical size.
- **The sliders' first run looks shipped.** `ControlSlider.LoadValue`
  reads the raw default 10 into a [0,1]-ranged control
  (ControlSlider.cs:47-70: `CalculatedScreenRect.width *= FloatValue`,
  `ScreenUVRect.width = FloatValue`), so until first dragged the fill
  rect is 10× the slider and the clamp-wrapped texture smears across the
  screen — the original data does this; the port draws the same bands.

`tests/run_menu.py` drives the whole flow headless (the splash, the
window graph, the tiles and prefs, the cards, the in-game menu, the
confirmations, both score exits, season 2, the exit door, the language
reload, the fullscreen pref) — 70 checks.

## The tutorial layer (runtime/tutorial.py)

`LevelScript` / `LevelScriptAction` run the three Intro scenes and the two
Season-2 tutorial levels (`GameInfo.ShowTutorialTextAfterIntro` activates
the inactive LevelScript object at StartGame, IntroAnimation.cs:305-307).
Each action arms one completion signal (`LevelScriptAction.Initialize`) and
the world raises it from the original's sites:

- an Item's use — `Used = true`'s tail (Item.cs:1894-1897) — or its
  look-at when `CompleteOnLookAt` (CheckDescriptionTooltip's arm,
  cs:1817-1819);
- a Door pass — Woody.OnDoorEnterAnimationFinished compares the far half
  (Woody.cs:477-480);
- a Zone entry (Pawn.ChangeZone, Pawn.cs:1592-1595);
- Woody within `Threshold` of the x-location (Woody.Update, cs:288-291).

`CompleteCurrentAction` (LevelScript.cs:148-166) unlocks/locks the listed
doors and items, stops Woody on the door/location kinds, unfreezes the
neighbour's manager (`ActionManager.Unfreeze` with the ForceAdvance pair),
re-arms the director faces, and past the last action calls `ForceWinGame`.
The message box, the `DescriptionMobile` strings (the alternate pair
latched by the neighbour's trick / action — Rottweiler.cs:789-792,
RoutineActionUse.cs:405-407), the world-anchored arrow/sign HUDAnimations
(64 px design cells) and `DirectorAnimation.DrawFaces`' two-loop ping-pong
all follow their files.

The four `TutorialScriptCamera*` scene scripts are ported state machine by
state machine: Intro102's film-overlay rides on the MumSmeared/Marble
tricks; Intro103 wakes the dog-frozen manager (the port's
`Routine.freeze_neighbour` / `stop_dog_action` mirror the ActionManager
flags) and releases the marble walk; Level201 (NFH2) stages the neighbour
with synthetic MoveOnly steps (`AddAction`/`RemoveAction`), the
stair/transition locks and the water-puddle field surgery, closing 35 s
after the last message; Level206 (NFH2206) runs the pillow lesson with the
Mother's action-table rewrites. `GameCamera.SnapTo*Immediate` maps to the
viewer camera.

Two departures this layer surfaced, both fixed by code:

- **TemporalLock is now modelled** (Door.cs; ZoneController.Start's
  `!Locked || TemporalLock` edge): the Intro doors keep their zone edges
  while locked and `find_path` refuses a route through a locked door
  (Helpers.GetDoorBetweenZones wants `!Locked`) — the audit-era note that
  the arm had no observable effect stopped holding the moment the tutorial
  unlocks doors at runtime.
- **A MoveOnly step's stop side-effects run** (RoutineActionUse.cs:386-412:
  only the tricked unlocks sit behind `Item != null`) — Intro103's dog
  walk is a MoveOnly step whose `ItemsToUnlock` opens the Drawer.

`tests/run_tutorial.py` drives all five scenes (Intro101 start to the
forced win; Intro102/103 through every signal kind and both cameras;
the L201/L206 openings) — 39 checks.

## Not implemented

From `docs/GAMEPLAY.md` §6–§7: the trick-camera *behaviour* (the setting
and its toggle exist; `Level.IsTrickCameraEnabled`'s snap-to-neighbour arm
stays unwired); and the name-hack branches listed at the end of the
priming section.
