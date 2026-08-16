# Verified: `sprite_model` — the item-controller sprite model (the "IdleNormal == NONE" finding)

Scope: one HIGH finding, coordinator-assigned from `docs/audit/verified/items.md`
(Coordinator flag 2: "121 item controllers with sheets and playable strips get
no sprite in the port … the right model is a sprite with no current animation,
not 'no sprite'"), plus the render/anim side that hangs off it. Written from the
landed code (a previous instance implemented it and its check module and was
terminated before reporting); every C# reference below was re-read against
`src/Assembly-CSharp`.

**Counts.** claims received 1 / CONFIRMED-FIXED 1 / CONFIRMED-DOCUMENTED 0 /
REFUTED 0 / already-documented 0. Same-class sweep: 6 siblings checked, all
covered by the shipped data (numbers below).

Check module: `tests/checks/sprite_model.py` — 23 checks, all pass
(`SDL_VIDEODRIVER=offscreen python3 tests/checks/sprite_model.py`, and inside
`tests/run_moments.py`). Validation on the tree as of this report:
`SDL_VIDEODRIVER=offscreen python3 tests/run_moments.py /tmp/sm` →
`moments: ALL OK` (229 ok lines, 0 FAIL); `tests/monkey.py levels/s2/Level202.json
--seeds=1 --seconds=60` → 0 findings; `tests/monkey.py levels/s1/Level111.json
--seeds=1 --seconds=60` → 0 findings; `ast.parse` over `runtime/*.py` OK. My
only edit is a two-line comment fix in the check module (`Drawing.cs:45-46` →
`53-54`, the real lines of `Drawing.RottweilerUse`'s `Hidden = false;
PlayItemAnimation`); no runtime code was changed by this instance.

## The finding — CONFIRMED, FIXED

**C#.** An `ItemAnimationController` is born with `CurrentAnimation == null`
(`AnimationControllerBase.cs:13`), and `OnGUI` (`cs:172-189`) refreshes and
draws only `if (!Hidden && … Repaint)` **and** `CurrentAnimation != null`
(both `Refresh` arms, `cs:179-186`). Nothing gives it an animation but a
`SetAnimation` (`cs:350-371`), reached through `PlayAnimationDirectly` /
`PlaySingleAnimation` / `PlayLoopingAnimation` (`cs:326-348`). What plays at
Start is the owning Item's business: `Item.Start` (`Item.cs:677-719`) wires the
controller and calls `SetPrimed(Primed)` (`cs:697`); `TrickItem.SetPrimed`
plays the primed pose while `Primed` (`TrickItem.cs:996-1010` → `PlayPrimedAnimation`
`cs:483-493`); `TrickItem.Start` then plays `ReturnToIdleAnimation()` unless
`DontPlayIdleOnStart` (`cs:214-217`); `SearchItem.Start` plays
`PlayItemAnimation(FullAnimation)` (`SearchItem.cs:91-107`, the call at 106);
`HideItem.Start` plays `PlayAnimationDirectly(IdleAnim)` (`HideItem.cs:23-30`);
`Alerter.Start` plays the `SleepSequence` (`Alerter.cs:40-48`); `Drawing.Start`
sets `Hidden = true` over the null animation (`Drawing.cs:17-22`). All the item
plays go through `TrickItem.PlayItemAnimation` (`cs:1018-1050`) — a no-op
unless `Animating`, `NONE` only hides a `HideWhenNotAnimating` item, and the
type is `UseAnimationType` → `PlayAnimationDirectly` (the strip's own
serialized Type), else `Looping` → `PlayLoopingAnimation`, else
`PlaySingleAnimation` — or `SearchItem.PlayItemAnimation` (`SearchItem.cs:68-88`:
`SetObjectHidden(false)`, then Looping/Single by the flag; `NONE` hides a
`HideWhenNotAnimating` item). A pawn's controller gets `PlayLoopingAnimation
(DefaultAnimation)` (`Pawn.cs:224-238`), a door's `PlayLoopingAnimation
(IdleAnimation)` unless `IgnoreIdleAnimation` (`Door.cs:56-63, 209-222`).

**Port before (HEAD `dca965a`).** `scene.py _add_sprite` picked a resting pose
from the owner's `IdleNormal` / `IdleAnimation` (with Tricked/Primed/Alerter
special cases) and — for an `ItemAnimationController` whose pose came out
`None`/`'NONE'` — **returned without building a sprite** (`if want in (None,
'NONE') and o['type'] == 'ItemAnimationController': return`, HEAD scene.py
1525-1529, inside `_add_sprite` 1464-1536). So 100 active item controllers with loadable sheets had no
`Sprite`, no `AnimPlayer`, no `single_end_hook`: their played strips never
showed and `Item.OnItemAnimationCompleted` chains never fired (every S2
SearchItem's Full/Empty look, L111-114's ElectricTrap spark loop, L111's
WashingMachine/Drier, L114's Gramaphone/GoldCup/MouseHole, L105 Football/Phone,
L106 BathTub, L107 Drawing, L112 Mixer, L207 ElephantBucket/Pole, L209
CowCrap/FireChannel …), and the 8 S2 `IgnoreIdleAnimation` DoorBacks (L211-214)
had no sprite for their pass strips either. Every idle the loader did pick
started in the AnimPlayer's default `looping` mode regardless of the item's
dispatch (a Single-typed idle under `UseAnimationType` looped instead of
playing once). (The draft's "121" was its own count; the measured delta with
the loader's `_active` + loadable-sheet filters is 100 items + 8 doors = 108
new sprites: 576 → 684 in total, item controllers 492 → 600, pawns 84 → 84 —
`tests/checks/sprite_model.py` census: s1 327/327, s2 273/273 item controllers
are sprites.)

**Port after — the model.** `Sprite.current` may be `None` = "no
CurrentAnimation" (`scene.py:107-121`, docstring with the refs), distinct from
`Sprite.hidden` = `AnimationControllerBase.Hidden` (`cs:55`). While `None`:
`draw_sprite` draws nothing (`render.py:136-141`), `AnimPlayer.tick` refreshes
nothing (`world.py:290-302`, together with the `hidden` gate that was already
there), `AnimPlayer.anim` is `None` (`world.py:64-70`), `_set_start` leaves
`cur_frame = None` (`world.py:75-83`), `current_index()` is 0 (`92-100`),
`blocking` is False (`190-195`; the C# `IsPlayingBlockingAnimation`, `cs:398-401`,
would NRE on a null animation but its only callers are pawn controllers —
`GameInfo.cs:185-198`, `Woody.cs:652`, `Pawn.cs:368/382`), `waiting()` False
(`197-201`), `play_looping`'s abort-if-playing reads the animation only when it
exists (`138-148`, `cs:336-342`). The first play — any `_set` — sets `current`.
The loader names a pose only for a pawn (`DefaultAnimation`, first entry as
fallback) and for a door without `IgnoreIdleAnimation` (`IdleAnimation`);
every item controller starts at `None` (`scene.py:1942-1988`), and the Item
family's Start plays run in `World.__init__` through
`_start_item_animations()` (`world.py:4702-4705`, body `5398-5436`) using the
runtime's own dispatch — `play_item_anim` (`5565-5590`, `TrickItem.cs:1018-1050`),
`_return_to_idle` (`5438-5470`, `cs:696-731`), `_play_primed_animation`
(`5485-5492`), `search_play` (`5592-5604`, `SearchItem.cs:68-88`),
`AnimPlayer.play_directly` (`123-136`, first entry of that name —
`ItemAnimationController.cs:41-51`) — in the original's order: base-`SetPrimed`
visibility (`4694-4701`, `Item.cs:1219-1235`) → `_start_item_animations`
(primed pose, then TrickItem idle / SearchItem Full / HideItem IdleAnim) →
`Drawing.Start`'s hide (`4706-4709`). An Alerter's `SleepSequence` was and is
`AlerterFSM.__init__` (`4652-4654`), a door's idle the loader's; a controller
nothing plays — `IdleNormal NONE`, `Animating false` (`cs:1020`), the one
`DontPlayIdleOnStart` item (L109 Chili, whose controller the Alerter twin
shares and poses), a `NONE FullAnimation`, an `IgnoreIdleAnimation` door — keeps
`current None` and draws nothing, exactly as the original's. Also None-safe:
`World.on_mouse_hover` (`world.py:4729-4733`, `IsPlaying` `cs:403-410` — a
null animation is "not playing"), the viewer's draw loop (`viewer.py:364-368`),
the recorder's door state (`record.py:206-210`), the monkey's frame/pattern
invariants (`tests/monkey.py:339-343, 366-368`).

After `World.__init__` 39 of the 684 sprites are still without a
CurrentAnimation, each for a named C# reason: Intro102 MumPicture, L105
Phone/Football, L106 BathTub, L107 Drawing, L111 ElectricTrap/Drier/
WashingMachine, L112 ElectricTrap/Mixer, L113 ElectricTrap, L114 ElectricTrap/
Gramaphone/GoldCup, L202 Pond, L207 Pole/ElephantBucket, L208 TakeFifi, L209
FireChannel, L210 FifiTurban/ElephantCricketBat/FifiElephant (IdleNormal NONE);
L107 MumStatueDummy, L113 Aquarium, L206 DogFifi (Animating false); L206
FifiHarpoon/FifiWeights/FifiWeightsDrop/FifiWeightsGrab, L210
ValveWaterPuddle/OlgaBra (FullAnimation NONE); the 8 DoorBacks of L211-214
(IgnoreIdleAnimation). 22 sprites are hidden at load (HideWhenNotAnimating +
NONE, ShowOnlyWhenPrimed, Drawing.Start, DisableOnStart doors).

**Related landings by other agents that the model relies on** (documented in
their reports, not re-verified here beyond reading): the exporter's
`SheetTexture` resolution and the "keep an animation with an unloadable sheet"
rule (`scene.py:31-47, 1933-1937`; `assets_refs.md` F9); the past-the-end
frame drawn by the texture's wrap mode (`render.py:159-185`; `assets_refs.md`
"Coordinator item"), which is what a Single strip that ended with nothing set
after it draws once the controller has an animation; `_fix_idle_tail` /
`PlayPrimedAnimation` (`items.md` D8).

## The checks (`tests/checks/sprite_model.py`, 23)

| # | check | what it pins (C#) |
|---|-------|--------------------|
| 1 | `sprite: every active item controller is a sprite (s1 327/327, s2 273/273)` | census over all 37 exported levels; fails on HEAD (492/600) |
| 2 | `L202 RubbishBin: Rubbish_Full looping at load` | `SearchItem.cs:91-107` + Looping flag `68-88` |
| 3 | `L109 Chili: the shared controller shows the sleep loop` | `TrickItem.cs:214` (`DontPlayIdleOnStart`), `Alerter.cs:48` |
| 4-6 | `L111 WashingMachine: no CurrentAnimation at load` / `SetObjectHidden(false) draws nothing` / `the first play sets the animation` | `cs:13`, OnGUI `172-189` — hidden vs None; `Item.cs:1984-1995`; `PlayItemAnimation` Looping arm |
| 7-9 | `L111 ElectricTrap/WashingMachine: sprites, no animation, hidden` / `the trick shows the spark loop` / `the use plays WasherLoop` | HideWhenNotAnimating + NONE (`cs:1041-1044`); `ReturnToIdleAnimation` `697-720`; `PlayUseAnimation` `982-994` |
| 10-12 | `L114 Gramaphone: sprite, no animation at load` / `primed -> GramaphoneOpen` / `use -> GramaphonePlay` | `PlayPrimedAnimation` `483-493` |
| 13-14 | `L107 Drawing: sprite hidden, no animation at load` / `RottweilerUse shows Drawing1` | `Drawing.cs:20`, `53-54` |
| 15-17 | `Aquarium` / `MumStatueDummy` / `DogFifi: Animating=false -> no animation` | `TrickItem.cs:1020` |
| 18-20 | `L205 SandSculpture: Single idle plays once (36 s), parks on frame 7` / `L208 Snake: Single hold idle parks (no loop)` / `L202 Rake (TrickItem subclass): idle looping` | `PlayAnimationDirectly` keeps the serialized Type (`cs:326-329, 350-358`), the pattern's last entry (`AnimationInstance.cs:206-234`), Looping flag |
| 21 | `L211 IgnoreIdleAnimation doors: no animation, not hidden` | `Door.cs:209-222` |
| 22 | `render: current None draws nothing` | `draw_sprite` returns False (`render.py:140`) |
| 23 | `L202 RubbishBin: take -> Rubbish_Empty` (live, scripted click) | `SearchItem.OnFinishAnimationCompelted` `cs:114-119` — the hook that never fired without a sprite |

Not scriptable / not checked here: a real screenshot diff (the shots below
were compared by eye).

## Render regression (headless shots, current tree vs a detached worktree of HEAD `dca965a` with `NFH_TEXTURES` pointed at the extraction)

`SDL_VIDEODRIVER=offscreen python3 runtime/viewer.py levels/…json --shot=…`
(the shot lands ~0.4 s wall-clock into the level). Loader sprite counts are
HEAD's loader on HEAD's JSON vs the current tree (HEAD's loader on the current
JSON gives the same 576, so the whole delta is this change):

| level | sprites HEAD → now | drew (viewer) HEAD → now | newly visible at load, and why |
|-------|-------------------|--------------------------|--------------------------------|
| L101 | 17 → 17 | 17/17 → 17/17 | nothing — 3 idles now start via `_start_item_animations` instead of the loader; same poses |
| L109 | 24 → 24 | 24/24 → 24/24 | nothing — the pig sleeps in its cage (Alerter `SleepSequence`, `Alerter.cs:48`), the Chili TrickItem's `DontPlayIdleOnStart` leaves it |
| L201 | 8 → 8 | 8/8 → 8/8 | nothing (5 idles restarted through the dispatch, all Looping) |
| L202 | 13 → 19 | 13/13 → 18/19 | RubbishBin `Rubbish_Full`, SawFish sign, Sandbucket, CrayFish — `SearchItem.Start → PlayItemAnimation(FullAnimation)` (`SearchItem.cs:106`, unhide + Looping/Single `68-88`); the Rake — a `Rake` (TrickItem subclass) HEAD's owner-type list never matched, now `TrickItem.Start`'s idle (`cs:214-217`); the Pond (TrickItem, IdleNormal NONE) is the one undrawn sprite |
| L207 | 20 → 29 | 20/20 → 27/29 | red Moped (+Moped2), CrayFish (crab, `B_hide` 3x3 hold), the SeaUrchins, IceBucket, Whisky, BBQ — SearchItem Full looks; undrawn: the TrickItems Pole (NONE idle) and ElephantBucket (NONE + HideWhenNotAnimating) |
| L211 | 18 → 26 | 18/18 → 24/26 | Urinal (its `urinal` sheet is the open WC doorway with the urinal), Plate, FireExtinguisher, CompressedAir, Handbag, MumPicture — SearchItem Full; the 2 DoorBacks stay without an animation (`Door.cs:211`) until a pass |
| L212 | 22 → 31 | 22/22 → 29/31 | Skeleton, PaintPot, Crowbar, WhipStonePlate, Corn, ParrotNest, Resin — SearchItem Full; 2 DoorBacks undrawn |

Every newly drawn thing is a SearchItem's `FullAnimation` (the original plays
it in `SearchItem.Start`, so it is on screen from the first frame there too)
or, for the four `Looping=false` ones (L202/L207 CrayFish, L206
DentureAdhesive, L210 ToolBelt), a hold/infinite strip — none runs past its
sheet. Nothing that should stay invisible at load draws: every `current None`
sprite is skipped (viewer "drew" deficits above are exactly those), and the
`Hidden` items (ElectricTrap, WashingMachine, Drier, Mixer, Gramaphone,
FireChannel, ElephantBucket, Drawing…) are both hidden and animation-less.
Differences in the pairs that are NOT this change: the camera y offset and
the Level fences (L211/L201/L212 railings), the localized tooltip strings and
the trophy counter font, and the tooltip under the offscreen cursor at (0,0)
(HEAD's L202 shot shows "WOODY_EXAMINERUBBISH_BIN_NAME" because HEAD's
colliders were unscaled — RubbishBin 7.0×8.0 vs 0.94×1.14 now; the assets/
hit-test agents' work). Data checks done for the order-sensitive Start
sequence: no SearchItem carries `ShowOnlyWhenPrimed`/`HideWhenPrimed` with a
non-NONE `FullAnimation` (0), no TrickItem's idle play would undo a
`ShowOnlyWhenPrimed` hide (0), no door sprite has `IdleAnimation NONE` without
`IgnoreIdleAnimation` (0), no `Television` (whose `Start` loops `TVOn`,
`Television.cs:9-13`) exists in the shipped data (0), the only shared
controllers are L109 Chili (TrickItem+Alerter) and L209 Flowers
(SearchItem+TrickItem, both without `HideWhenNotAnimating`, so the play order
between the two Starts is irrelevant).

## Same-class sweep

- Every `.anim.<attr>` reader in `runtime/` was grepped for item players: the
  only ones are `world.py:4732` (None-guarded) and `behaviors.py:958`
  (`Level209Behavior.on_advance_frame`, `p.anim.name` on the Cow — the Cow has
  an idle at load and `current` never returns to `None`; the C# reads
  `CurrentAnimation.Name` there too). Pawn readers are safe by construction
  (pawns always load with a pose).
- `sprite.anims[sprite.current]` indexers: `viewer.py:367` and
  `tests/monkey.py:344` guarded; `tests/checks/assets_refs.py:358` runs on
  sprites it first checks (BeachChair/PoolBoard) which have a pose.
- `search_play` flips only `sprite.hidden` where `SetObjectHidden` would also
  flip the item's own Renderer: of the 33 SearchItems with an own quad none
  is `HideWhenNotAnimating` and none has its quad renderer disabled at load
  with a non-NONE Full, so the shipped data never sees the difference.
- `IsPlayingBlockingAnimation` NRE case: no item-controller caller in the C#
  (see above); the port's `False` is unreachable-equivalent.
- The `HideItem.Start` play uses `p.has()` where the C# would throw on a
  missing name — no data hit (every HideItem's `IdleAnim` resolves).

## README additions (runtime/README.md)

Note for the coordinator: the working tree's README already carries a version
of this bullet at lines 85-99 (uncommitted — someone merged it before this
report); the text below supersedes it (correct counts), and "Coverage"
(lines 39-58: "546 sprites", "Level113 has 27, Level201 8", the "535 before
the alerter pass" aside) needs the new numbers.

Replace the "Things that bite" bullet **`IdleNormal == 'NONE'` means "not a
sprite"** with:

- **`IdleNormal == 'NONE'` means "no CurrentAnimation yet", not "not a
  sprite".** Every active `ItemAnimationController` with a loadable sheet is a
  sprite (600 of them, plus 84 pawn controllers — 684 sprites over the 37
  exported scenes). A controller is born with `CurrentAnimation == null`
  (AnimationControllerBase.cs:13) and `OnGUI` draws and refreshes nothing
  until the first `SetAnimation` (cs:172-189, 350-371); the port's
  `Sprite.current is None` is that state, and `AnimPlayer.anim` is `None`
  with it. The loader names a pose only for pawns (`DefaultAnimation`) and
  doors (`IdleAnimation`, skipped under `IgnoreIdleAnimation`); the Item
  family's Start-time plays run in `World.__init__` →
  `_start_item_animations` in the original's order — `SetPrimed`'s primed
  pose (TrickItem.cs:996-1010), `TrickItem.Start`'s `ReturnToIdleAnimation`
  unless `DontPlayIdleOnStart` (cs:214-217), `SearchItem.Start`'s
  `FullAnimation` (SearchItem.cs:106), `HideItem.Start`'s `IdleAnim`
  (HideItem.cs:28), an `Alerter`'s `SleepSequence` (Alerter.cs:48) — through
  the same `PlayItemAnimation` dispatch as any later play (TrickItem.cs:
  1018-1050: `Animating` gate, `UseAnimationType` → the strip's own Type, else
  `Looping` → looping, else single; `NONE` only hides a `HideWhenNotAnimating`
  item), so L205's SandSculpture and L208's Snake play their Single-typed
  idles once and park. 39 controllers stay without an animation after Start
  (IdleNormal NONE, `Animating=false`, a NONE `FullAnimation`, the L109
  Chili's `DontPlayIdleOnStart`, the 8 S2 `IgnoreIdleAnimation` DoorBacks) and
  draw nothing — which is also why `SetObjectHidden(false)` shows nothing on
  such an item. `Sprite.hidden` is the other switch, `AnimationControllerBase
  .Hidden` (SetObjectHidden, HideWhenNotAnimating, Drawing.Start,
  DisableOnStart doors): it freezes `Refresh` too, and it can be true or false
  independently of the animation. The old rule ("giving it a sprite draws the
  wrong thing") came from drawing frame 0 of a made-up pose at load; the fix is
  the null animation, not the missing sprite — without it every S2 SearchItem's
  Full/Empty look, the ElectricTrap spark loop, the washing machine, the
  gramophone and L107's drawing were invisible and their
  `OnItemAnimationCompleted` chains never fired.

Coverage paragraph replacement (lines 41-58): "All 31 levels render with every
sprite placed and no missing sheet — 684 sprites in total over the 37 exported
scenes (600 item controllers, 84 pawn controllers; 39 of them have no
CurrentAnimation after Start and 22 are hidden, so a load-time shot draws
fewer — L202 draws 18 of 19, L207 27 of 29, L211 24 of 26). Counts vary by
design: Level213 has 36, Level201 8 because that level paints most of its
scenery into the backdrop."

## Coordinator flags

1. The README bullet is already in the working tree (lines 85-99) though the
   rules reserve README edits for you — verify who wrote it and prefer the
   text above (it fixes "121 item controllers live that way" → the measured
   100 items + 8 doors newly created; 39 without an animation after Start).
   The "Coverage" numbers (546 / L113 27 / L201 8 / "535 before the alerter
   pass") are stale.
2. `items.md` Coordinator flag 2 (this finding) and its D8.3 note ("a no-op
   today: the trap has no sprite … not scriptable until the sprite model
   changes") are now resolved: `_fix_idle_tail`'s ElectricTrap arm acts on a
   real sprite (checks 7-8 exercise the trap's sprite). `items.md`'s "the port
   already has `AnimPlayer.reveal_on_play`" refers to an intermediate
   working-tree stand-in that no longer exists.
3. `runtime/README.md` "Coverage" quotes viewer "drew N/N" lines; with the
   model, "drew" is legitimately below the sprite count on 18 of the 34
   scenes that have sprites (the `current None` and hidden sprites). If a CI-style check compares them, it
   should compare against `len([s for s in sprites if s.current is not None
   and not s.hidden])`.
4. Not addressed by anyone (data-verified no-ops, listed for completeness):
   `search_play` does not flip a same-GO quad renderer the way
   `Item.SetObjectHidden` does; `Television.Start`'s `TVOn` loop is not
   ported (no Television in any level).
