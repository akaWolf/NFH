# Verified: `defaults` — pass 4, "тихие дефолты" (silent defaults)

Scope: every default-bearing read in `runtime/*.py`, `tools/export_level.py`,
`tools/scene.py` — `getattr(x, 'f', default)`, `d.get('F') or default`,
`d.get('F', default)`, `(x or {}).get(...)`, bare `or <literal>` fallbacks —
checked against the C# field initializer (`src/Assembly-CSharp`) and against
the shipped data (`levels/s1|s2/*.json`).

**Counts.** 543 pattern hits (scan script below; 2 are false positives —
hud.py:691 `or -0.6 <= ...` is arithmetic, world.py:5222 is a docstring) /
MATCH ≈405 / MISMATCH-fixed 23 sites (10 findings) / MISMATCH-documented 16
sites / MASKING-fixed 6 sites (4 findings) / INFRA ≈91.

Check module: `tests/checks/defaults.py` (data-level; 20 asserts, all pass
on the fixed code; on the pre-fix code 15 of them fail — verified in a scratch
copy with only my edits reverted: 296 Items, 354 Doors, 260 Anims and 16
levels' routine actions differ from the raw JSON there).
Validation: `SDL_VIDEODRIVER=offscreen python3 tests/run_moments.py` → the
final run is `moments: ALL OK` (16 core moments + assets_refs + defaults +
routine); `python3 tests/monkey.py levels/s1/Level113.json --seeds=1
--seconds=60` → 0 findings; `ast.parse` over `runtime/*.py` OK. Two earlier
suite runs showed transient FAILs in other agents' checks (assets_refs "no
sprite anim", routine D7/D10, one tooltips moment) — each re-checked with my
edits reverted in a scratch copy of the then-current tree and found
independent of this work; all passed on the retry.

## Method — what can actually go wrong

`tools/export_level.py:219-225` writes **every** node of the MonoBehaviour's
serialization layout (`Layouts.class_layout`, `tools/monodeser.py:220-239`:
public non-static/non-readonly/non-`[NonSerialized]` fields plus
`[SerializeField]` privates; nested `[Serializable]` classes inline). It never
filters zeros/defaults. So for a serialized field the "key absent" path of a
port default is dead; the live trap is `d.get('F') or X` replacing a
serialized `0 / 0.0 / false / '' / []` with a nonzero X the C# would not use.
The exceptions where the port default IS load-bearing: fields the C# does not
serialize (SkiBehavior's `protected StartX/EndX/RightVelocity/LeftVelocity`,
`Item.InvUsed`) — there the C# constructor/initializer value must be the port
default. Two C# classes carry their initializers in an explicit constructor
rather than on the field: `Pawn` (Pawn.cs:203-220: Speed 1.25, SpeedSneaking
0.65, ForceMagnitude 300, DoorForceMagnitude 80, Running* 300/80,
DoorDistanceDelta (0,-0.3,0), Hello, Stand_Down, FearLeft/FearRight, Interval
0.15) and `MouseCursor` (MouseCursor.cs:39-40: TextureDeltaLoc, MinMouseY 100).

Data verified (python one-liners over all 37 level JSONs): every Item/Door
field below is present on all 1086 Item-derived objects; every AnimationInstance
(12374) has FrameRate/Sheet*/Start/EndFrame/UsePattern/Pattern; every Level's
`Zones*` lists have 10 entries ≥ max zone index 9; every gameplay scene has
GameInfo/HUD/MouseCursor/CameraMover/MusicPlayer with all fields.

## Findings — fixed

| # | site (≈line, moves as others edit) | C# field = initializer | port default before | carriers of the falsy value | verdict | action |
|---|---|---|---|---|---|---|
| F1 | scene.py:70→77 `Anim.pattern = d.get('Pattern') or None` | `AnimationInstance.UsePattern` gates Pattern: CurrentIndex/SetStartFrame/AdvanceFrame/ReachedEndFrame (AnimationInstance.cs:66-76, 186-234); `int[] Pattern`, no init | truthiness of Pattern stood in for UsePattern | **262 instances** with UsePattern=false and a Pattern that differs from StartFrame..EndFrame (e.g. L113 `LadderTestTransition` 15-16 vs a 40-frame [39..0] pattern, `DogSleepStart` 56-63 vs 30 frames, L201 `TakeOneFrameNFH2*` 3-3 vs [3,3]); 260 reach a port sprite | MISMATCH | `pattern = (Pattern or None) if UsePattern else None`; AnimPlayer's `if a.pattern` sites (world.py:72,79,174,180,191,254) follow. Check `defaults: Pattern ignored while UsePattern is false`, `shipped Anims: Pattern only with UsePattern` |
| F2 | scene.py:324→349 `Item.item_use_height = ... or 0.03`; :940→974 Door same | `Item.ItemUseHeight = 0.01f` (Item.cs:220); Pawn.cs:1112-1119 sets `MinDistToNextMove = Target.ItemUseHeight` raw on a walk-up step | 0.03 (also ≠ initializer) | **532** objects serialize 0.0 (238 TrickItem, 120 Door, 116 Transition, 41 SearchItem, 9 Alerter, 7 HideItem, 1 Drawing) — 0 of them ShouldWalkUp, so no behaviour changed | MISMATCH | `d.get('ItemUseHeight', 0.01)` (Item + Door). Check `Item keeps serialized 0 / false`, `shipped Items keep their radii...` |
| F3 | scene.py:321→346 `Item.use_distance = ... or 0.01`; :939→973 Door | `Item.UseDistance = 0.03f` (Item.cs:246; Item.cs:2292, Pawn.cs:1114) | 0.01 | 0 objects serialize 0.0 (values 0.01…0.5) | MISMATCH (dead: default ≠ init) | `d.get('UseDistance', 0.03)` |
| F4 | scene.py:809→839 `tip_dimensions = ... or 0.0` | `Item.TipIconDimentions = 0.7f` (Item.cs:236) | 0.0 | 0 zero carriers (1071×0.7, 15×0.5) | MISMATCH (dead) | `d.get('TipIconDimentions', 0.7)` |
| F5 | scene.py:483 `self.anger = d.get('AngerAmount') or 0` (+ slot) | `Item.AngerAmount = 20` (Item.cs:392) | 0 — an unused twin of `anger_amount` (:669 `d.get('AngerAmount', 20) or 0`, which is right) | 0 zero carriers | MISMATCH (dead duplicate) | deleted line + slot |
| F6 | scene.py:1598→1658 `'max_distance': ... or 0.03` (routine actions) | `RoutineAction.MaximumPawnDistanceToAction = 0.03f` (RoutineAction.cs:25); RoutineActionMove.cs:39 compares raw | 0.03 | **81** actions serialize 0.0 (71 item actions — irrelevant, they arrive by Item.IsAtUseRange; 7 MoveOnly — use MoveThreshold; 3 blank actions in L203); the port never consumes this key | MISMATCH (masked, unused) | `a.get('MaximumPawnDistanceToAction', 0.03)`. Check `routine actions keep a 0 MaximumPawnDistance` |
| F7 | scene.py:1874-1881→1950-1957 pawn spec `Speed/SpeedSneaking/ForceMagnitude/DoorForceMagnitude/Running*` `or 0.0`, `DoorDistanceDelta.y` `.get('y', 0.0)` | Pawn ctor: 1.25 / 0.65 / 300 / 80 / 300 / 80 / (0,-0.3) (Pawn.cs:203-209) | 0.0 | 0 zero carriers (all pawns serialize their own) | MISMATCH (dead) | `pd.get('Speed', 1.25)` … `.get('y', -0.3)` |
| F8 | scene.py:1237-1238→1285-1286 `cm.get('MinX') or 0.0` ×4 | CameraMover.cs:21-27 `MinX=-7 MaxX=7 MinY=-3.5 MaxY=3.5` | 0.0 | 0 zero carriers | MISMATCH (dead) | `cm.get('MinX', -7.0)` … |
| F9 | scene.py:1256-1259→1306-1308 `lvl.get('EntranceZoneName')`/`StartZoneName` (no default) | Level.cs:38-40 `"Zone05"` / `"Zone01"` | None→'' (no zone) | all 37 levels serialize non-empty names | MISMATCH (dead) | `lvl.get('EntranceZoneName', 'Zone01')`, `('StartZoneName', 'Zone05')` |
| F10 | scene.py:1531→1588 `'compound_trick_score': ... or 0` | GameInfo.cs:43 `CompoundTrickScore = 4` | 0 | 0 zero carriers (2/3/4/5) | MISMATCH (dead) | `d.get('CompoundTrickScore', 4)` |
| F11 | world.py:4104→4499 `num = angry_meter / float(item.anger_amount or 20)` | Rottweiler.cs:664 divides by `Item.AngerAmount` raw: 0 → +Infinity (0/0 NaN), neither `<= 1f` nor `<= 2f` → falls to the `AngryMeter < Max` test | 20 (an invented divisor) | 0 items serialize AngerAmount 0 | MISMATCH (0 carriers, trivial) | `meter/anger if anger else float('inf')` — same branch outcomes as the C# Infinity/NaN |

MASKING (a `getattr` default hiding a field the C# class has):

| # | site | C# | data | action |
|---|---|---|---|---|
| M1 | world.py:527-533→573-579 `getattr(obj, 'delta_use_height'/'use_woody_extra'/'woody_delta_use_height', …)` in `Pawn.at_use_location` — `obj` is a Door on the DOOR_CLIMB step and the port's Door lacked two of the three | Door : Item; `IsAtUseLocation(TargetDoor)` (Pawn.cs:1330, 1412 → cs:1690-1705, Woody.cs:744-755) adds `WoodyDeltaUseHeight` / `ExtraDeltaHeight` for Woody | **6 walk-up `DoorBack` doors** serialize WoodyDeltaUseHeight: L212 0.3, 0.4; L213 0.4, 0.4; L214 0.2, 0.2 (+ L214 one carries DeltaUseHeight 0.5, already honoured) — Woody's door-climb arrival window was 0.2-0.4 units too narrow there | Door gains `woody_delta_use_height`, `use_woody_extra` (scene.py Door.__slots__/__init__ ≈979-980); the three getattr's became plain reads. Check `Door keeps serialized 0 / false and its widenings`, `shipped Doors keep radii/WoodyDeltaUseHeight` |
| M2 | hud.py:652→680 `getattr(cand, 'can_use', True)` — cand may be a Door | `Item.CanUse = true` (Item.cs:314), read for doors too (MouseCursor.cs:374) | 0 doors serialize false (14 items do) | Door gains `can_use` (explicit None-check, default true); hud reads `cand.can_use` |
| M3 | world.py:511→555 `getattr(it, 'dont_use_on', None)` | `Item.DontUseOn` (Item.cs:2270-2293 y-arm skip); `it` is always an Item here (`it.move_x`) — redundant, but Door lacked the field | 0 doors serialize DontUseOn | Door gains `dont_use_on`; plain read |
| M4 | world.py:5717→6254 `getattr(self, '_dex_inv_used', None)` — never declared in `World.__init__` | `Item.InvUsed` (Item.cs:628; set 1442/1479, consumed 1472/1505) | — | `self._dex_inv_used = None` in `World.__init__` (≈4302) + plain read. Check `World._dex_inv_used declared` |

## Findings — documented (not fixed), with the numbers

| site | C# | port default | data | why not fixed |
|---|---|---|---|---|
| scene.py:52 `fps = FrameRate or 10.0`; world.py:260 `fps = anim.fps or 10.0` | `AnimationInstance.FrameRate = -1f` (cs:12); Refresh does `animationTime += 1f / FrameRate` (AnimationControllerBase.cs:146) — **-1 means "advance every Refresh"** (negative time ≤ 0), **0 means frozen** (+Infinity). Nothing substitutes 10 | 10.0 | **0 of 12374** instances have FrameRate ≤ 0 (values 0.72…20; 8.0 ×6205, 10.0 ×3873) | dead; a faithful port of -1 needs a per-Refresh path in AnimPlayer (its frame_at is time-based); flagged |
| scene.py:48-51 `SheetColumns/SheetRows or 1` (+max(1,·)), `StartFrame/EndFrame or 0` | initializers -1 (cs:14-22) | 1 / 0 | 0 instances ≤ 0 columns/rows; 0 with -1 frames | dead sentinels; `or 0` on 0 is identity |
| Anim: UsePattern **true** with an **empty** Pattern | SetStartFrame/UpdateCurrentFrame keep CurrentFrame (0 on a fresh instance), ReachedEndFrame is immediately true → an InfiniteLoop one shows frame 0 forever | port falls back to StartFrame..EndFrame | **36 instances**: OlgaStandDownInfinite ×10 (L214 uses it in 6 OlgaUseAnimation entries + BirdPerchBehavior — C# static frame 0, port animates 0-5), OlgaStandRightInfinite ×11, PutEel ×14 (PatternFile external #355 unresolved by the exporter → Pattern empty), SitSurprise ×1 | pre-existing, needs an empty-pattern model in AnimPlayer; flagged |
| scene.py:716 `DexterityUnlocker or 'IT_NONE'` | `InventoryType DexterityUnlocker` no init → 0 = `IT_Antispot` (InventoryType.cs:3); Item.cs:1388 compares `ToString()` with "IT_NONE" | 'IT_NONE' | value always a name string; the `or` never fires | dead |
| world.py:344→359 `wait_in_fear_anim or 'WaitInFear'` | `RoutineActionWaitInFear.FearAnimation` no init → 0 = `Walk_Down`; the port's default is `PawnAnimationController.WaitInFear = WaitInFear` (cs:29) — a different field | 'WaitInFear' | 0 NONE carriers; the Rottweiler serializes WaitInFear ×13, WaitInFear2 ×1, **Walk_Down ×16** — passed through as-is (the C# plays Walk_Down there too) | dead |
| scene.py:1279→1333 `lmd.get('loop', True)`; world.py:6396 `music.get('loop', True)` | `AudioSource.loop` Unity default false | True | all 33 LevelMusicSources serialize loop=true | dead (tools/scene.py r_audiosource always writes the key) |
| hud.py:677-678→706-707 `cursorSize .get('width', 0.03)/.get('height', 0.04)` | `MouseCursor.cursorSize` Rect, no init (0) | 0.03/0.04 | all 31 cursors serialize 0.0313×0.0417 | dead; hud.py is another agent's file |
| scene.py:1893→1979 `angry_decay = AngryMeterDecay or 0.0`; :1925→2010 `min_door_distance = MinDistanceToNearestDoor or 0.0` | Rottweiler.cs:54 `= 6f`, :74 `= 0.6f` | 0.0 | 30/30 Rottweilers serialize nonzero; the keys are Rottweiler-only and the spec dict is shared by all roles (0 for Woody/Olga/Mother/Kid, who have no such field) | dead; a class-default there would invent a value for roles without the field |
| scene.py:351 `can_fix = bool(d.get('CanFix'))`; :1675→1740 `'loop_from_start': bool(d.get('LoopFromStartIndex'))` | Item.cs:286 `CanFix = true`; ActionManager.cs:27 `LoopFromStartIndex = true` | implicit False when absent | always present (39 CanFix=false items, all managers carry the flag) | dead |
| world.py Pawn.__init__ mirrors `spec.get('angry_max') or 100.0` (:297), `notice_near_distance or 0.03` (:349), `idle_threshold or 30.0` (:369), `fear_left/right or 'FearLeft'/'FearRight'` (:363-364), `hit_pawn_action.get('max_distance') or 0.03` (:3329) | Rottweiler.cs:56 100f, :38 0.03f, Woody.cs:24 30f, Pawn.cs:215-216 FearLeft/FearRight, RoutineAction.cs:25 0.03f — all equal | equal | 0 zero/NONE carriers | MATCH by value; the second `or` layer is INFRA (the scene side already resolves them, `notice_near_distance` with an explicit None-check) |

## MATCH — the bulk, by class (no action)

- `d.get('F') or []` (110), `or {}` / `(x or {}).get('path')` (130), `or ''` (56), `or 0`/`or 0.0` on zero-initialized C# fields (61), `or None`/`or False` (9): Unity deserializes null arrays/strings as empty, null PPtrs → None; a serialized falsy value round-trips identically. Includes every `use_anim` sequence table, all string/description fields, `TrickScore`, `DeltaUseHeight`, `WoodyDeltaUseHeight`, `AlertOnStartTimer`, `ActionDuration`, `TakeItemCount`, `ExtraCoinAngerAmount`, `HeightDelta`, `TimeMinutes` (17 levels serialize 0.0 → 0.0), the delays.
- `.get('x'/'y'/'width'/'height', 0.0)` on inline Vector2/3/Rect structs (72): always present.
- Explicit initializer matches: `AngerAmount` (`d.get('AngerAmount', 20) or 0` = 20 absent, raw otherwise), `Passable` (`.get('Passable', True)`; 2 false kept), `CanUse` (None-check → true; 14 false kept), `CauseAlarmInterval` (None-check → 2f, Item.cs:326; 2 zeros kept), `AlerterDelay` (None-check → 1f, Alerter.cs:24), `ItemTipIconDepth` (`GUI_DEPTH.get(…, 24)` = ItemsFront, Item.cs:230), `AnimationGUIDepth` (`GUI_DEPTH.get(…, 32)` = Items, AnimationControllerBase.cs:47), `FenceDepth` (LevelFence, Level.cs:50), `HideObjectOnStartIndex` (`.get(…, True)`, AnimationSequenceControl.cs:11; 6 false kept), `MinMouseY or 100` (MouseCursor.cs:40; all 100), HUD `MaxInventoryItemsDisplayed or 5` (HUD.cs:195; 4/5), `TotalTrickHeight or 53.0` (HUD.cs:55; all 38), `InventoryTooltipHoverInterval or 1.0` (HUD.cs:243; all 1.0), `MaximumPawnDistanceToAction or 0.03` on HitWoodyAction/HitPawnAction (RoutineAction.cs:25; all nonzero), the stand poses `or 'Stand_Left'…` (PawnAnimationController.cs:19-25; every pawn controller serializes its own — Kid KidPlay/KidAnnoyedRemote, L2xx Rottweiler WaitWatch variants), `renderer_enabled` default True (Renderer.m_Enabled; exporter always writes it), `notice_near_distance` (scene side, None-check → 0.03f).
- behaviors.py `value(field, default)` / `anim_name(field, default)` (explicit None/NONE checks): MinXDelta 0.3 (RollerSkaterBehavior.cs:29), FallWindow/Breath (:33-35), TimeToStopAnimation 3 (BirdPerchBehavior.cs:9), StartFallIndex 40/13 (ParrotLedgeFall/Jump), CliffCrash/CliffJump, OlgaShowerPutBra/TakeBra (OlgaBraBehavior.cs:5-7), RepeatSleep true (MotherSleepBehaviour.cs:27), Speed 1.8 (BirdMovementBehavior.cs:56), FifiSpeed 1 (FifiBehavior.cs:29), Ski/SkiNail/SkiHandleReturn + **StartX -10.5 / EndX 7 / ±2.4 velocities — `protected`, NOT serialized, so the port default is the live value** (SkiBehavior.cs:17-23, 47-54). All serialized ones present and non-NONE.
- Zone arrays `ZonesY/Sizes/PlayLeft/PlayRight/HeightDeltas` (`or []` + `if i < len`): Level.Awake indexes unconditionally (Level.cs:186-190); every level's lists have 10 entries ≥ max index 9 → the guards never fire.
- `GUI_DEPTH.get(a.get('layer_to_change'))` (world.py:2515): 22 actions serialize `GUIDepth(0)` (not an enum member) → None → no layer change; none of the 22 has ChangeLayerInLinkedTricked or a target (RoutineActionUse.cs:249-261 never runs for them).
- Redundant `getattr` on classes that define the field (left as is): hud.py `door.exit_door`, `zone.exit`, `self.mouse_down`, `world.dex_states`; render.py `sprite.hidden`; scene.py `sprite.go`; world.py `d.walk_deltas`, `target.passable`, `Routine._angry_target/_toilet_run/_hit_target` (declared at Routine.__init__ ≈1524-1527), `World._entrance_hello` (≈3847), `item.animate_dependant` (TrickItem-only field, TrickItem.cs:48; only TrickItem.PlayItemAnimation (cs:1018-1050) and SearchItem's (cs:68) exist, Item/Door have none — a Door legitimately lacks the field and the False default is the right non-TrickItem behaviour).

## INFRA (no C# counterpart)

record.py:239/242 `getattr(w, 'progress_bars', ())`, `dex_states` (World declares both) and :320-321 CLI opts; render.py:106; tools/export_level.py:36-38, 230, 264/481/503 (`PPtr` dicts always carry file/path), tools/scene.py:102-103; world.py Pawn.__init__ reading the port's own spec dict (32 sites: keys always present), `s.get('y', floor_y())` on the port's path steps, `tpl.get('urgent', True)`, `spec.get('loop_from_selected', False)`, `hit_pawn_action.get('sequence', ())`, `level.objs.get(...).get('data', {})`, `music.get('delay')`, `pawns.get(role) or {}`, GameState `info.get('total', 0)`; hud.py string/asset-array fallbacks (`InventoryPrevious or [None, None]`, `entry.get('name') or ''`, `hover_started or 0.0`, `_style_color` default white for HUD-less scenes); scene.py `raw.get('unity_scene') or raw['scene']`, `tr.get('world_position') or tr['position']`, `ow.get('type') or ow.get('name')`, `IdleTricked or want`.

## Same-class sweep

- Every `or <nonzero literal>` in the port was enumerated (scan: 7 bare + 24 `.get() or <literal>` + 40 `.get('F', <nonzero>)`); each is in a table above.
- Every `bool(d.get('X'))` over a C# field with a `true` initializer: CanFix, LoopFromStartIndex (documented above); RenderGizmos unused; RepeatSleep goes through `value(…, True)`.
- Every enum read through `_anim_name(...) or 'X'`: stand poses (MATCH), fear (MATCH), wait-in-fear (documented).
- Door vs Item field parity for the fields the pawn code reads on both: use_distance, item_use_height, delta_use_height, woody_delta_use_height, use_woody_extra, passable, can_use, dont_use_on — now all on Door. Remaining Item-only reads on a possible Door: `animate_dependant` (legit, TrickItem-only).

## README additions

- **Silent defaults (pass 4).** The exporter writes every serialized field, so a
  port default only ever bites when an `or` replaces a serialized 0/false/''.
  Audited: 543 default-bearing reads; fixed the ones that masked data —
  `AnimationInstance.UsePattern` now gates `Pattern` (262 instances carried a
  stale Pattern next to UsePattern=false, e.g. L113 LadderTestTransition 15-16
  vs a 40-frame pattern; the original ignores it, AnimationInstance.cs:66-76,
  186-234), `ItemUseHeight` (532 zeros; Pawn.cs:1118 reads it raw) and
  `RoutineAction.MaximumPawnDistanceToAction` (81 zeros) are taken as
  serialized, and Door carries `WoodyDeltaUseHeight`/`UseWoodyExtraDeltaHeight`
  /`CanUse`/`DontUseOn` like the Item it is (six L212-L214 DoorBacks widen
  Woody's climb window by 0.2-0.4, Pawn.cs:1330/1412 → 1690-1705). Field
  defaults now equal the C# initializers (Item.cs:220/236/246/392/432, Pawn.cs:
  203-209, CameraMover.cs:21-27, GameInfo.cs:43, Level.cs:38-40).
- **Open (0 carriers, kept):** `FrameRate = -1f`/`0` (AnimationControllerBase.cs:
  146: -1 = advance every Refresh, 0 = frozen) never occur in the data (0 of
  12374); the port would show 10 fps. `UsePattern` with an empty Pattern (36
  instances — OlgaStandDownInfinite ×10 [L214 uses it], OlgaStandRightInfinite
  ×11, PutEel ×14 [external PatternFile unresolved], SitSurprise ×1) holds
  frame 0 in the original; the port plays StartFrame..EndFrame.

## Coordinator flags

1. **UsePattern=true + empty Pattern (36)** — a visible divergence for L214's
   `OlgaStandDownInfinite` (C#: static frame 0; port: frames 0-5 looping).
   Modelling it needs AnimPlayer to distinguish "no pattern" from "empty
   pattern" (world.py:72-191, the animation agent's area). Decide: model or
   accept.
2. **PutEel** (L201-L214, 14 instances): `PatternFile = {external: 355, path: 1}`
   is not resolved by `resolve_pattern_files` (the asset file is not in the
   index) → Pattern empty though UsePattern is true; a real pattern probably
   exists in the build. Exporter/assets side.
3. **UsePattern=false with a PatternFile (29 instances)**: the file's pattern
   is loaded (SetupPattern) but ignored (UsePattern) in the C#, and now in the
   port too — its Sounds are still used (LoadSoundClips reads Sounds regardless).
4. FrameRate -1/0 semantics (see above) — dead in the data; if the animation
   agent wants strictness, `fps = -1` should mean one frame per tick.
5. `LayerToChange = GUIDepth(0)` on 22 season-2 actions (RoutineActionUse) —
   inert (no ChangeLayerInLinkedTricked/targets); noted for the data pass.
6. hud.py:706-707 cursorSize fallbacks 0.03/0.04 (C# 0) — dead; cosmetic, in
   the HUD agent's file.
7. Door now carries `with_string` too (added concurrently by the HUD agent,
   scene.py Door.__slots__) — consistent with the Item-parity sweep above.

## Scan script (for the counts)

```
python3 - <<'EOF'
import re, glob
files = sorted(glob.glob('runtime/*.py')) + ['tools/export_level.py', 'tools/scene.py']
P = [re.compile(r"\.get\([^()]*(?:\([^()]*\))?[^()]*\)\s*or\s+(\S+)"),
     re.compile(r"\.get\(\s*['\"][A-Za-z_.0-9]+['\"]\s*,\s*([^)]+)\)"),
     re.compile(r"getattr\([^,]+,\s*'([A-Za-z_]+)'\s*,\s*([^)]+)\)"),
     re.compile(r"\bor\s+(-?\d+(?:\.\d+)?|'[A-Za-z_]+')\b")]
n = 0
for f in files:
    for line in open(f):
        if line.strip().startswith('#'): continue
        n += sum(len(p.findall(line)) for p in P[:3])
        if not P[0].search(line) and 'get(' not in line: n += len(P[3].findall(line))
print(n)
EOF
```
