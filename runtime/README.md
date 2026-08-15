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
sheet — 535 sprites in total:

```
Level101  drew 16/16 sprites; missing sheets: 0
...
Level214  drew 16/16 sprites; missing sheets: 0
total sprites drawn: 535, missing sheets: 0
```

Sprite counts vary a lot by design: Level113 has 27, while Level201 has 8
because that level paints most of its scenery into the backdrop instead.

## Things that bite

- **Transforms nest.** A door parented to a zone stores a local position;
  `tools/export_level.py` composes the chain and emits `world_position`.
- **Doors name their idle differently.** `Door` uses `IdleAnimation`, every other
  `Item` uses `IdleNormal`. Reading the wrong field silently selects animation 0,
  which for a door is "Woody walks through it" — the whole level then shows
  Woody standing inside every doorway.
- **`IdleNormal == 'NONE'` means "not a sprite".** Those objects are drawn as
  quads instead; giving them a sprite draws the wrong thing.
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

`world.py` adds the parts of §3 and §8 that make Woody walk. Click anywhere:

1. `zone_at(x, y)` finds the destination zone.
2. `find_path` is BFS over the door graph — the game's Dijkstra uses a flat cost
   of 1.0 per hop, so the two agree.
3. Each hop becomes a step: walk along x to the door, transit, continue.

A transit is the interesting part. The door sheets (`W_Door_Right_Enter` and
friends) already contain the walking character, so the game **hides the pawn and
animates the door**. Passing one is:

```
walk to door.x  ->  pawn.hidden = True
                    door.play(WoodyEnterAnimation)
  on end:           pawn moves to door.LinkTo, zone = LinkTo.zone
                    LinkTo.play(WoodyLeaveAnimation)
  on end:           pawn.hidden = False, next step
```

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

Two details that took a debugging pass each:

- **The zone is passed explicitly, never derived from the target point.**
  `ActionManager` calls `MoveToGoal(item, item.Zone, item.TargetLocation, ...)`
  because an item's stand-point can sit just outside its zone's collider — the
  binoculars in Level101 are at x=6.30 while Zone03 ends at 6.25. Looking the
  zone up by position strands the routine there.
- **An action must never complete synchronously.** The game advances in
  `ActionManager.Update`, so a zero-length action costs a frame. Chaining
  directly from "finished" into "start the next" recurses without bound the
  moment two such actions sit at the same spot.

Each pawn type has its own use sequence (`RottweilerUseAnimation`,
`OlgaUseAnimation`, `MotherUseAnimation`). An empty one means the item is not
that character's to use, not that the action is instantaneous.

### Season 1 works; Season 2 does not, yet

Season 1 routines run at a believable pace — 12 to 33 uses per three minutes
across all 14 levels, none stuck. Season 2 still produces implausible rates on
some levels (Level204, Level206, Level207): those routines interleave Olga,
Mother and Kid and go down the `NFH2Path` branches, which this does not model.
A guard freezes a routine whose every action is unplayable so it cannot spin.

## Not implemented

The rest of `docs/GAMEPLAY.md` §5–§7: the trick state machine, inventory,
detection and catching, alerters, anger and scoring. Woody walks and the
neighbour keeps house; nothing either of them does has consequences yet.
