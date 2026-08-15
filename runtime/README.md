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
sheet — 545 sprites in total:

```
Level101  drew 16/16 sprites; missing sheets: 0
...
Level214  drew 16/16 sprites; missing sheets: 0
total sprites drawn: 545, missing sheets: 0
```

(535 before the alerter pass; six sleeping pets have `IdleNormal == NONE` and
draw their `SleepSequence[0]` instead — see below. The seventh, Level109's
parrot, always had a normal idle.)

Sprite counts vary a lot by design: Level113 has 27, while Level201 has 8
because that level paints most of its scenery into the backdrop instead.

## Things that bite

- **Transforms nest.** A door parented to a zone stores a local position;
  `tools/export_level.py` composes the chain and emits `world_position`.
- **Doors name their idle differently.** `Door` uses `IdleAnimation`, every other
  `Item` uses `IdleNormal`. Reading the wrong field silently selects animation 0,
  which for a door is "Woody walks through it" — the whole level then shows
  Woody standing inside every doorway.
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
  sneaking the slow one (0.52 u/s). Tab in the viewer.

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

Level112's dog is an *inactive* GameObject (a level script enables it later) —
no `Update`, no FSM; the port gates the FSM on the sprite's existence, which
only active objects get.

## Not implemented

From `docs/GAMEPLAY.md` §6–§7: the level scripts (`Level112Script` and kin)
that enable alerters mid-level, `SetIgnoreInfiniteLoop` /
`PawnToStopInfiniteAnimation` release of infinite animations, priming
(`RequirePriming`/`WoodyPrime`), the fixing-item run (`RunToFixingItem`),
`Mother`'s catch predicate, HUD.
