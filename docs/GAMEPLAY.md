# Gameplay specification

Behavioural spec recovered from the decompiled `Assembly-CSharp`, written for a
reimplementation. Every rule below cites the source it came from; anything not
cited is not established. Season 1 only (`GameMode.Classic`).

Naming trap: **`Rottweiler` is the neighbour himself**, not a dog. `Woody` is the
player. `Mother`, `Olga`, `Kid` are Season 2 characters that also appear in a few
Season 1 scenes.

---

## 1. Entities

```
MonoBehaviour
 └ Actor
    ├ ActionManager          the neighbour's routine engine
    ├ GameInfo               singleton: score, win/lose, per-level tuning
    ├ InventoryManager
    ├ Item                   anything Woody or the neighbour can interact with
    │  ├ Alerter             sleeping animal that wakes and raises the alarm
    │  ├ Door ── Transition  connects two zones
    │  ├ GroundItem          pick-up lying in the open
    │  ├ HideItem            wardrobe etc. Woody hides in
    │  ├ InspectItem
    │  ├ SearchItem          container Woody searches for inventory
    │  └ TrickItem           the trap; subclasses Drawing, Rake, Television, Toilet
    └ Pawn
       ├ Woody, Rottweiler, Mother, Olga, Kid
```

A level is a flat `GameObject` tree. Components carry all tuning as serialized
fields — see `tools/README.md` for how to read them.

---

## 2. Main loop and win/lose

`GameInfo.Update()`, in this order (`GameInfo.cs:212`):

1. `CanRottweilerSeeWoody()` → **lose**, `OnNeighborCaughtWoody()`
2. `CanMotherSeeWoody()` → **lose**, `OnMotherCaughtWoody()`
3. `CompletedTricksCount >= TotalTricksCount` → **win**, `WinGameOnCompleteAllTricks()`

Two distinct thresholds, both serialized on `GameInfo`:

- `WinningTricksCount` — on reaching it, `Won = true` and the HUD's *complete
  episode* button lights up (`GameInfo.cs:477`). The player may stop here.
- `TotalTricksCount` — reaching it wins immediately.

Losing freezes everyone and plays the caught animation; `gotCaught` guards
against firing twice.

### Catch conditions — there are two, and they differ

Detection is pure zone containment in both: **no line of sight, no distance
check**. But two separate predicates exist and they are not interchangeable.

**Continuous**, evaluated every frame in the main loop —
`GameInfo.CanRottweilerSeeWoody()` (`GameInfo.cs:181`):

- same `Zone`, neither `IsPassingDoor()`, neither `IsMovingToAdjacentZone()`
- neighbour not `IgnoreWoody`, not `IsSleeping`
- Woody not `Hiding`, not `DonePassingToOtherZone`, not `PassingComplexMove`
- `Rottweiler.CanSeeWoody()` — a hook delegating to the level's `ActorBehavior`
  (`Rottweiler.cs:1218`), so a scripted scene can blind him
- `(!Rottweiler.AnimController.IsPlayingBlockingAnimation() || !Woody.Sneaking)`

That last clause is inverted from what one might expect: **his blocking animation
only protects Woody while Woody is sneaking.** Walking normally past a busy
neighbour still gets you caught.

Special case: when the neighbour's current action item is named `Bed`, the
predicate drops `!IsSleeping` and the `PassingComplexMove` terms but adds
`Woody.Velocity.sqrMagnitude > 0f` — **while he is in bed, standing still is
safe and any movement is fatal.**

**Event-driven**, checked at discrete moments — `Pawn.HasNeighborCaughtWoody()`
(`Pawn.cs:366`). Same idea but a flat `!IsPlayingBlockingAnimation()` for both
parties, no `CanSeeWoody()` hook, no Bed case. Called when a non-Woody pawn
finishes walking through a door (`Pawn.cs:1668` — the neighbour walking in on
you), when `CheckForNeighbour` is flagged (`Pawn.cs:310`), and once per Woody
update (`Woody.cs:495`).

`HasMotherCaughtWoody()` adds `Woody.IsPawnAtZoneY()` — the mother also checks
the floor.

Practical upshot: a doorway is a safe transit, and being mid-animation is a real
but conditional shield.

---

## 3. Zones and movement

Zones are boxes, not a mesh: extent comes from the `BoxCollider` on the zone's
GameObject. The adjacency graph is built at load by `ZoneController.Start()` and
is reconstructible offline — see `tools/zonegraph.py`.

`Helpers.GetShortestPath(start, end, pawn)` (`Helpers.cs:158`) is Dijkstra whose
edge cost is the constant `1f`, so it degenerates to BFS over the zone graph.
`Zone.Cost` / `Zone.Previous` are scratch fields reset on every query — they are
not level data.

Movement inside a zone is 1-D along x (`Zone.PlayLeft` / `PlayRight`,
`RoutineAction.IsAtActionLocation` compares only `position.x`). Levels are
side-on cutaway houses; the y axis selects the floor, and floors are joined only
through doors.

---

## 4. The neighbour's routine

`ActionManager` (`ActionManager.cs`) walks a cyclic list `Actions:
RoutineActionUse[]` — the neighbour's daily routine, authored per level.

```
ActiveActionIndex ──advance──▶ wraps to ActionStartIndex   (LoopFromStartIndex)
                                     or ActionSelectedIndex (LoopFromSelectedIndex)
                                     or 0
```

`StartAction(action)` (`ActionManager.cs:146`): if the pawn is not already at the
action's location, the action is wrapped in a shared `RoutineActionMove` whose
`NextAction` is the real one, so *walk there* and *do it* are one state machine.

`Update()` (`ActionManager.cs:421`) each frame:

| condition | effect |
|---|---|
| `MoveAction.Active` | keep walking; on arrival start `NextAction` |
| `ActiveAction.Finished` | `AdvanceToNextAction()` |
| `ActiveAction.Active` | `ActiveAction.Update()` |
| at location | `StartAction(ActiveAction)` |
| otherwise | `MoveToAction(ActiveAction)` |

An action finishes when its `Duration` elapses or `ForceFinished` is set
(`RoutineAction.Finished`).

### Interruptions

`StartUrgentAction(action, nextAction)` (`ActionManager.cs:651`) preempts the
routine and stores where to come back to in `action.OriginalAction`. The rules
for picking that resume point are explicit and worth copying verbatim
(`ActionManager.cs:679-719`) — e.g. a `RoutineActionGrab` interrupting a
`RoutineActionUse` resumes at that use, but interrupting a surprise resumes at
the surprise's own original.

`StopUrgentAction()` (`ActionManager.cs:586`) decides what happens after:

- `OriginalAction.Item.SkipAction` → advance past it
- **`OriginalAction.Item.GotTricked` → advance past it.** The neighbour does not
  retry a trap that already fired.
- `OriginalAction.Item.GoNextAction` → advance
- otherwise → resume `OriginalAction`

The routine is also mutable at runtime: `ActionsToAddInGame` splices actions in
(`AddActions`), `RemoveActionAfterUse` and `RemoveActionByItem` splice them out.

### Action kinds

`RoutineAction` subclasses: `Move`, `Use` (→ `UseFixingItem`), `Grab`, `Return`,
`HitPawn`, `HitWoody`, `MotherHitWoody`, `SurpriseFar`, `SurpriseNear`,
`WaitInFear`.

`RoutineActionUse` is where a trap fires: `OnActionStarted` calls
`Item.Use(ActionManager.Owner)` (`RoutineActionUse.cs:205`). Everything else in
that class is presentation bookkeeping — hiding objects during use, unlocking
doors, priming other items, mutex animations.

---

## 5. Trick state machine

State lives on `Item` / `TrickItem` as independent flags, not an enum:

| flag | meaning |
|---|---|
| `Primed` | Woody has set it up but it is not armed yet |
| `Tricked` | armed — will fire when used |
| `GotTricked` | has already fired |
| `AlreadyTricked` | has already been scored (double-score guard) |
| `FuckedUp` | broken past use |
| `WasPriming` | mid-priming, temporarily inert |
| `CompoundTricked` | second-stage trick applied |

The predicate that decides whether a use fires the trap
(`TrickItem.IsTricked()`, `TrickItem.cs:258`):

```csharp
return ((Tricked && !UseAtOtherPlace && !Neutral)
        || (DependsOn != null && DependsOn.Tricked && DependsOn.GotTricked
            && (!UseDependsOnWhenTricked || Tricked)))
       && !WasPriming && !FuckedUp;
```

So a trap is live either directly, **or** because the item it `DependsOn` has
already fired. That second branch is the chain mechanic: soap the floor, and the
thing at the end of the slide becomes live without being touched.

### Woody arming a trap

`Item.CanWoodyUse` rejects in this order (`Item.cs:1671-1700`):

```csharp
// wrong item held, or the held item still needs priming
if (RequiredInventory != IT_NONE
    && (!Woody.IsUsingInventory(RequiredInventory)
        || (UsedInventory.Item.RequirePriming && !UsedInventory.Item.Primed))
    && !GrabDirectly)
{
    if (UsedInventory != null) { PlayCantUseAnimation(); WrongTrick = true; }
    return false;
}
if (RequiredInventory == IT_NONE && UsedInventory != null) return false;  // holding
if (Locked) return false;                                                 // something
```

`SecondRequiredInventory` acts as an accepted alternative: holding it swaps the
two fields so the rest of the code sees it as the required one (`Item.cs:1736`).

`WrongTrick` set here makes `OnUseAnimationCompleted` bail out before any state
changes (`TrickItem.cs:270`) — the animation plays, nothing happens.

On success the flow is `OnUseAnimationCompleted()` (`TrickItem.cs:268`):

1. `UseItem()`
2. decrement `UsedInventory.UseCount`; at zero, and unless `KeepAfterUse`, remove
   `RequiredInventory` from the inventory
3. `GrabDirectly` → the item adds *itself* to the inventory
4. `GetTricked(true)` — or `GetTricked(false)` when `CanUndoTrick && Tricked`,
   which is how a trap gets disarmed again
5. propagate: `ActivateItemTrick.Tricked = true`, `SetTrickedOnItem.Tricked = true`

`Compound` items take a second, different inventory item
(`CompoundRequiredInventory`) for a bigger payoff (`TrickItem.cs:509`).

### The neighbour springing it

`TrickItem.RottweilerUse` (`TrickItem.cs:566`) plays the tricked animation,
honours `DestroyAfterUseTricked` (which also unregisters the item from its zone's
notice lists), and hands off to scoring.

`Item.RottweilerUseTogglesPrime` makes a use alternate prime/unprime instead —
that is how repeatable props work (`Item.cs:1065`).

---

## 6. Alerters

`Alerter` is the sleeping pet. Three states from two bools: asleep
(`!Awake && !Alert`) → awake → alert.

Visibility (`Alerter.cs:79`):

```csharp
CanSeeWoody() = Zone == Woody.Zone && !Woody.IsPassingDoor()
                && !Woody.Hiding && (!Woody.IsSneaking() || Awake);
```

**Sneaking hides Woody from a sleeping alerter but not from an awake one.**
`Woody.IsSneaking()` is true when holding sneak *or* when barely moving
(`Woody.cs:1075`: `Sneaking || Velocity.sqrMagnitude < MinimumVelocitySquared`).

Two triggers (`Alerter.cs:52`):

- visible **and moving** → directional alert (`AnimationType = 1`)
- same zone, already awake, **standing still**, not hiding → repeat alert (`AnimationType = 0`)

Plus an unconditional `AlertOnStartTimer` countdown for scripted alarms.

On alert, after `AlerterDelay` (default `1f`) two things happen independently:
`Woody.SeeAlerter(this)` if still visible, and
`Rottweiler.HearAlerter(this, triggeredByWoody)`.

`Rottweiler.HearAlerter` (`Rottweiler.cs:265`) ignores the alarm if already
walking to one (`MovingToAlarm()`), postpones it if passing a door or if the
current action postpones alarms, and otherwise starts a `SurpriseFar` action.

The alerter calms down when the neighbour arrives (`OnRottweilerEnter` → "poor"
animation) and sleeps again once he leaves and Woody is out of sight.

---

## 7. Anger and scoring

`Rottweiler.AngryMeter` decays continuously at `AngryMeterDecay` per second
(`Rottweiler.cs:910`), capped at `AngryMeterMaximum`.

Classic mode, when a trick fires (`Rottweiler.cs:595`):

| meter at that moment | result |
|---|---|
| `<= 0` | anger level 1, medium audience laugh |
| `> 0` | `AngryCountTicks++`, anger level 3, big laugh, **compound trick** |

Either way the meter is reset to maximum. So the combo is: **land the next trick
before the meter drains**. `AngryCountTicks` is the multiplier the HUD shows as
`xN` (`HUD.cs:669`).

Scoring (`GameInfo.CalculateScore`, `GameInfo.cs:392`):

```
CompoundTrickScore   = min(serialized CompoundTrickScore, AngryCountTicks)
FinalCompoundTrickScore = CompletedTricksCount * CompoundTrickScore
FinalViewerRating    = min(100, FinalTrickScore + FinalCompoundTrickScore)
```

`FinalTrickScore` accumulates each trap's `TrickScore` via `GameInfo.TrickDone`
(`GameInfo.cs:467`). `Item.OnTrickDone` (`Item.cs:2121`) guards with
`AlreadyTricked` so a trap scores once, and pays both items when a
`LinkedItemTrick` pair fires together — with an extra payout if
`ExtraCoinLinkedTrick`.

### Per-level tuning, read from the shipped data

| level | tricks | to win | compound cap | anger decay |
|---|---|---|---|---|
| Level101 | 4 | 2 | 5 | 4.23 |
| Level102 | 6 | 4 | 3 | 4.23 |
| Level103 | 6 | 4 | 4 | 4.23 |
| Level104 | 7 | 5 | 4 | 4.23 |
| Level105 | 8 | 6 | 3 | 4.23 |
| Level106 | 9 | 7 | 4 | 4.23 |
| Level107 | 7 | 5 | 3 | 4.23 |
| Level108 | 6 | 4 | 3 | 4.23 |
| Level109 | 7 | 5 | 3 | 4.23 |
| Level110 | 6 | 5 | 3 | 4.23 |
| Level111 | 8 | 5 | 2 | 3.70 |
| Level112 | 10 | 7 | 2 | 4.23 |
| Level113 | 8 | 6 | 3 | 4.23 |
| Level114 | 9 | 7 | 3 | 4.23 |

`AngryMeterMaximum` is 100 everywhere. Level111 is the only one with a slower
decay, i.e. a wider combo window.

---

## 8. Rendering and animation

This is the part least like a normal Unity game, and the most useful to know
before writing a runtime.

**Nothing is drawn by Unity's renderer.** Every character and item draws itself
in `OnGUI` via `Graphics.DrawTexture` in *screen* space
(`AnimationControllerBase.DrawAnimation`, `AnimationControllerBase.cs:153`):

```csharp
Vector3 p = Camera.main.WorldToScreenPoint(Owner.transform.position);
Rect dst = new Rect(p.x + (DeltaLocation.x + anim.DeltaLocation.x) * anim.Height / anim.OriginalHeight,
                    Screen.height - p.y + (…y…),
                    anim.Width / anim.SheetColumns, anim.Height / anim.SheetRows);
Rect src = new Rect(1f/SheetColumns * (CurrentFrame % SheetColumns),
                    1f - 1f/SheetRows * (CurrentFrame / SheetColumns + 1),
                    1f/SheetColumns, 1f/SheetRows);
Graphics.DrawTexture(dst, anim.SheetTexture, src, 0, 0, 0, 0);
```

The `MeshFilter`/`MeshRenderer` objects in the scenes are backgrounds; the world
transform of an actor is used only to derive a screen position.

**Draw order is an explicit enum**, not z-sorting. Lower value draws in front
(`GUIDepth.cs`, applied by `Helpers.SetGUIDepth` → `GUI.depth`):

```
BackItems 72 · BackDoors 64 · Items 32 · ItemsFront 24 · Doors 22 · Alerters 20
FrontDoors 19 · Rottweiler 18 · Woody 16 · LevelFenceBack 14 · LevelFence 13
BackHUD 12 · HUD 11 · MainMenu 10 · Menu 9 · MainMenuControl 8 · MainMenuFont 7
ConfirmMessage 2 · MouseIcon 1
```

That enum is the whole render stack of the game.

**Resolution model.** Everything scales off a fixed design resolution of
**800×600** (`Helpers.BaseResolutionHeight/Width`), by height only, preserving
aspect (`AnimationInstance.SetDimensions`):

```csharp
Height = OriginalHeight * Screen.height / 600f;
Width  = OriginalWidth * Height / OriginalHeight;
```

(`DexterityComponent` inconsistently hardcodes 1280×800 for its own ratios —
`DexterityComponent.cs:245`.)

### Frame model

`AnimationInstance<T>` is one sprite sheet plus playback data: `SheetColumns` ×
`SheetRows`, `StartFrame`, `EndFrame`, `FrameRate`, `DeltaLocation`,
`OriginalWidth/Height`, and flags `Blocking`, `HoldOnLastFrame`, `InfiniteLoop`,
`HideOwnerOnAnimationEnd`.

Two frame-advance modes:

- default: `CurrentFrame++` from `StartFrame`, ends when `> EndFrame`
- `UsePattern`: frames come from an `int[] Pattern` — arbitrary order, repeats,
  ping-pong — parsed at load from a `PatternFile` TextAsset whose format is
  `<header line> / <count> / <blank> / count× frame index / <blank> / <sound
  count> / "frame, filename"` lines (`AnimationInstance.SetupPattern`)

Timing accumulates rather than resets, so it does not drift
(`AnimationControllerBase.ResetAnimationTime`):

```csharp
animationTime += 1f / FrameRate;
if (Owner.ShouldSlowAnimations) animationTime *= Owner.SlowAnimationsFactor;
```

Sounds are keyed to frame numbers: `AnimationSound { int Frame; string FileName }`,
fired in `PlaySound` as each frame is entered, loaded from `Sound/sfx_hi/`
(or `Sound/NFH2/sfx/` when `UseNFH2Sounds`).

### Sequencing

`PlayAnimationSequence(T[] seq)` walks the array; each animation ending pulls the
next (`StopSingleAnimation` → `PlayNextSequenceAnimation`). When the last element
*starts*, the sequence is cleared and `ShouldStopAction` is set, so when it
finishes the routine action ends — this is the link between animation and the
`ActionManager` state machine.

Callback order when a single animation ends (`AnimationControllerBase.cs:219`):

1. `OnAnimationEnded(name)` — truthy result consumes the event
2. else if `Blocking`, `OnBlockingAnimationEnded(name)`
3. else `SwitchToStandAnimation()`

and when a sequence ends: `AlternateOnSequenceEnded()` → `OnAnimationSequenceEnded()`
→ `ActionManager.StopCurrentAction(true)`.

`InfiniteLoop` is a *runtime-mutable* flag, and `SetIgnoreInfiniteLoop` /
`SetIgnoreInfiniteLoopOnce` override it. Much of the per-item special-casing in
`ActionManager` exists purely to toggle these on other characters' current
animations.

### Loading

Textures load lazily by name through `Resources.Load(BaseAnimationPath +
TextureFileName)`. `TaskScheduler` (`TaskScheduler.cs`) is a queue that runs
**exactly one task per frame**, and async texture load/unload go through it —
that is the game's entire strategy for avoiding hitches.

---

## 9. UI, camera, and the dexterity minigame

**`Control`** is an immediate-mode widget: a `ScreenRect`, a `Texture[]` indexed
by state, a `GUIStyle`, a `GUIDepth`, and a hit test in `LateUpdate` on mouse-up
(`Control.cs:353`). Subclasses: `ControlButton`, `ControlToggle`, `ControlSlider`,
`ControlRadioButton(Group)`, `ControlWindow`, `ControlLabel`.

Two mobile-isms that a desktop port must undo: both hover (`IsMouseHovering`) and
click require `Input.touchCount == 1`, so with a mouse and no touch device
neither ever fires.

**`HUD`** draws inventory, the trick counter, the anger multiplier as `xN`, item
descriptions, and the clock. The clock is cosmetic: `Level.TimedGame` is a saved
player *setting* (`SettingKey.TimedGame`, default on) and shows `--:--` when off.
`GameInfo`'s `TimeScore`, `StartTimeScore`, `CoinScore`, `LifeScore`,
`StatueScore` and the matching `Final*` fields are **declared but never read or
written** — dead scoring machinery inherited from the PC original.

**`CameraMover`** lerps toward a target with separate Windows and mobile input
paths, clamps to level bounds, and yields to two overrides: `Woody.IsScriptCameraEnabled()`
for scripted shots and `GameInfo.IsTrickCameraOn` for the trap cutaway (the
`TOGGLETRICKCAM` player setting).

**`DexterityComponent`** is a steadiness minigame that suspends normal movement
while active (`Pawn.cs:351`). Two rects — a drifting `ForegroundRect` the player
nudges, and a fixed `BackgroundRect` target:

```csharp
sway = Mathf.Clamp(MaxSway - (|Δcentre.x| + |Δcentre.y|), -MaxSway, MaxSway);
PercentageDone += sway * FillSpeed * Time.deltaTime;
```

Starts at 20, wins at `CompletedPercentage` (85), loses at ≤10 unless the
alerter has `DexterityCannotLose`, which floors it at 12. Drifting into the
margin clamps the rect, swaps in `BackgroundTextureWrong` and raises `FillSpeed`
to 1.2 as a penalty (`DexterityComponent.cs:273`).

---

## 10. What resists a clean reimplementation

The engine is genuinely data-driven, but there is a tail of per-item
special-casing keyed on `GameObject.name` string comparisons. `ActionManager`
alone branches on `WaterPuddle`, `Iron`, `WateringCan`, `GroundMarbles`,
`Sweets`, `LifeBoat`, `FishingRod`, `Tortilla`, `Pinata`, `MechanicalBullWait`,
`CaptainDoor`, `Shower`, `Bouquet`, `Glass`, `BridgeRail`, `OlgaMat`, `Rake`,
`Submarine`, `DynamiteBox`, `ValveHot`, `ValveMain`, `Plant`, `PigKeys`, `Pipe`,
`Cow`, `Bed`, `Flowers`, `Mouse`, `Snake`, `AngryElephant`, `FirstAid`,
`SandCastle`, `SandSculpture`, `ChairAssembly`.

Most of those are Season 2 items. A Season 1 reimplementation can skip them, but
each needs checking rather than assuming.

Beyond that, bespoke logic lives in `ActorBehavior` subclasses — 43 of them,
including `Level101Behavior`, `Level105Behavior`, `Level108Behavior`,
`Level109Behavior`, `Level110Behavior`, `Level113Behavior`, `Level114Behavior`
for Season 1. These are per-level scripted set pieces and have to be ported one
by one.

## 11. Not yet examined

- `MusicPlayer` (177 lines) beyond its call sites, `AudioController`
- `LocalizationManager` / `XMLMerge` string pipeline — mechanically simple, the
  data is the 111 localization TextAssets
- `MouseCursor`, `LevelDataGUIRenderer`, `IntroAnimation`, `Credits`
- the 43 `ActorBehavior` subclasses, individually
- Season 2 (`Level2xx`): code ships in the assembly but the scenes are not in
  this OBB — they are IAP-gated (`NFH.IAP.Purchaser`, `LevelPackUnlocker`)
