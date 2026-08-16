# Verified: pawn_woody (Pawn.cs / Woody.cs — movement, doors, hide, the click routing)

Source claims: docs/audit/raw/pass1_pawn_woody.md #1-#18 (per the coordinator's
list 1-12 + the per-field sweep) and pass4_twins.md F7. Port files touched:
runtime/world.py (class Pawn; World.woody_click / _wont_go / woody_see_alerter
/ hide_during_woody_anim / the Woody.Update block of tick; one line each in
_dexterity_gate and _woody_try_use), runtime/viewer.py (handle_click, the Tab
toggle), runtime/record.py (`key sneak`), runtime/scene.py (Door: 4 fields;
_add_sprite: 3 lines), tests/monkey.py (the sneak toggle input), and the new
tests/checks/pawn_woody.py (24 checks, all green).

## Counts

| received | CONFIRMED-FIXED | CONFIRMED-DOCUMENTED | REFUTED | already-documented / out of scope | extra (found while verifying) |
|---|---|---|---|---|---|
| 13 (12 listed + F7) | 9 (#1, #2 Woody side, #3, #4, #5, #8, #9, #10a-d, F7) | 3 (#2 take tail, #6-as-restated, #7) | 1 (#6 as stated) | 1 skipped (#12 → gameinfo agent) | 5 fixed + 2 documented (below) |

Validation: `python3 -c "import ast..." runtime/*.py` OK; the moment suite
(`tests/run_moments.py`) — every base moment and every check module green
except `sleep bar: the dog wakes early (<80%)` (L109's BedSleep now runs
30 s instead of 15 s; the working-tree scene.py change to `Anim.pattern` /
`UsePattern` gating is not mine — flagged below); monkey 60 s runs on
L101/L201/L211 seeds 1-2: no crashes, findings only `stuck-colored-tooltip`
(hud.py's MakePermanentTooltip latch, HUD agent) and L201's Rottweiler
`x-out-of-zone` at t=0.02 (start position, routine/data).

---

## 1. HIGH — S2 sneak toggle + click = crash — CONFIRMED, FIXED

- C#: Woody.cs:714-729 (`Sneaking = MbSneakToggle; if (NFH2Path) Sneaking = false`),
  ToggleSneak Woody.cs:1151-1168 (`MbSneakToggle && !NFH2Path`).
- Reproduced headless before the fix: Level201, toggle, click →
  `RuntimeError: No animation found !!! State: Walk_Right`.
- Port before: world.py `start_move_flags` copied the toggle unconditionally;
  viewer.py Tab and record.py `key sneak` wrote `sneaking` directly.
- After: `Pawn.start_move_flags` (world.py:608-618) — `if self.nfh2: sneaking =
  False`; new `Pawn.toggle_sneak()` (world.py:620-626) used by viewer.py's Tab
  (viewer.py ~447), record.py's `key sneak` (record.py:101) and
  tests/monkey.py's Tab input (the harness wrote the flag directly and crashed
  every S2 monkey run). hud.py's own button already gated (untouched, other
  agent) — it could call `toggle_sneak()` too.
- Check: tests/checks/pawn_woody.py `pawn: S2 sneak click survives / never
  sneaks / still walks` (a record.py script; the old code dies in record.py).

## 2. HIGH — dexterity win never auto-completes the take — CONFIRMED; Woody side FIXED, the take tail DOCUMENTED (item agent)

- C#: Woody.cs:218-222 (`DexterityDone && !DexterityAux → DexterityAux = true;
  TryUseItem()`), TryUseItem reads `MovePath.Steps[MoveIndex].Target`
  (Woody.cs:515); the done branch Item.cs:1445-1474 / 1482-1507 clears
  InDexterity/DexterityAux/DexterityDone, unlocks, spends the unlocker and
  falls to Item.cs:1710 → `return true` (nothing between 1508 and 1709 runs).
- Reproduced before: L202 CrayFish, reed held, `_win()`, 3 s: inventory
  `['IT2_Reed']`, `dexterity_done` latched, Woody looping GetCrayFishDexterity1.
- After: `Pawn.dexterity_aux` (world.py:375), `Pawn.use_target` (the item
  step's Target, stamped at the head of `_woody_try_use`, world.py:6579-6582,
  reset per route in `_route`), the retry in World.tick's Woody.Update block
  (world.py ~7437-7446), and the one-line `woody.dexterity_aux = False` in
  `_dexterity_gate`'s done branch (world.py:6487, Item.cs:1463/1496 — the only
  edit in that function; without it L207 CrayFish take 2 / L208 Mouse take 20
  never retry a second win). Now 1 s after the win: `dexterity_done False,
  in_dexterity False`, the reed spent, Woody's dexterity loop still playing.
- STILL OPEN (item agent, `_can_woody_use`, not mine to edit): after
  `dex == 'done'` the port keeps running the Item.cs:1520-1704 checks that the
  original skips; the CrayFish (RequiredInventory IT_Fuel placeholder) fails
  the `required` check at Item.cs:1671 (world.py `_can_woody_use`, the
  `not inv.is_using(required)` arm) and returns False silently, so the take
  animation and `_woody_search_step` never run and Woody stays in the
  dexterity loop. Exact fix: right after `if dex == 'armed': return False`
  add `if dex == 'done': return True` (Item.cs:1462-1474 → 1710; ValveMain is
  not a dexterity item, so the tail hacks do not apply). Also the win should
  end the looping dexterity pose — in the original the take animation
  replaces it through the same TryUseItem.
- Check: `pawn: dexterity arms / win retries the use / the retry spends the
  unlocker` (green); `pawn: dexterity take landed` prints `info False` until
  the item agent's line lands (not asserted).

## 3. MED — held transition pair not waited on first approach — CONFIRMED, FIXED

- C#: Pawn.cs:1002-1027 — `TransitionEnter = step.TargetTransition` before
  the claim test (1004, 1014); 1022-1027 parks the pawn standing.
- Port before: `_complex_arrival` set `transition_enter` only inside the
  successful claim → the wait arm compared None → walked in.
- After: world.py:1253-1263 assigns first, claims if either side is free,
  else `_stand()` + return True. Reproduced: L201 pair claimed for the
  Rottweiler, far-zone click → Woody stands at the stairs' foot 12 s
  (Stand_Right, zone unchanged); release → Zone03 in 2.2 s.
- Check: `pawn: held transition parks Woody / the release lets him through`.

## 4. MED — UseDoorAtOnce's general arms — CONFIRMED, FIXED

- C#: BuildPathToTarget Pawn.cs:744-780 (ShouldExitDoorNow Woody.cs:777-780;
  ShouldWalkDirectlyUpToDoor cs:785-788 with IsAtDoorLocation cs:802-809 —
  |x-door.x|<0.1), consumption Pawn.cs:1359-1364 (the wait), 1391-1396,
  1412-1416; WalkOnPath skips the walk on PortalMove (cs:957).
- Port before: only the direct same-door click shortcut (`woody_click`),
  transiting immediately (no IsOtherPawnPassing wait, no GoZone stamp); any
  other click routed back through the doorway walked down to the floor and
  re-climbed (reproduced on L101: DoorBack01 → far-zone click).
- After: `Pawn.portal_move` / `use_door_at_once` (world.py:325-334);
  `_route` pre-arms on a leading portal-door step (world.py:775-792 — the
  floor-step insert becomes the else, as in cs:746-765); the WALK head runs
  MoveToDoor at once (world.py:1302-1307); `_begin_transit` consumes the
  pre-arm and the flat at-once (world.py:1008-1029); the DOOR_CLIMB tick
  gained MoveToDoor's per-frame head wait (`_wait_for_passing`,
  world.py:998-1006, Pawn.cs:1359-1364), the per-frame climb-strip re-assert
  (cs:1400-1403) and `IsAtUseLocation || UseDoorAtOnce` (world.py:1385-1403).
  The `woody_click` shortcut is gone: the own-zone door click now goes
  through `_route` (`_capture_click` + on_arrive=None, so the coordinator's
  "pending use dies" stays; no zone pair in either season is linked by two
  doors, so BFS picks the clicked door exactly as before). Measured on
  L101: far-zone click from the doorway → `is_warping` after 0.02 s from
  y=1.30 (floor 0.76), 2.4 s to the far zone.
- Documented deviation: `UseDoorAtOnce` is reset per path in `_route`
  (world.py:748-754); the original never resets it outside consumption
  (InitializePath cs:491-498 drops PortalMove only), so a pre-arm abandoned
  during an IsOtherPawnPassing wait would ride into the next path and
  double-play a flat door (cs:1384-1385 + 1391-1396). Not reproduced; needs
  the neighbour mid-pass through Woody's doorway at the moment of the
  re-click, then a third click before the pass ends.
- Check: `pawn: arrives on the far doorway / far click passes the door at
  once` (asserts warping < 0.2 s with y unchanged).

## 5. MED — the DonePassing/GoZone/DoorClicked clears — CONFIRMED, FIXED

- (a) PawnAnimationController.cs:86-95: `Pawn._switch_to_stand`
  (world.py:460-471) is now the AnimPlayer stand hook and every explicit stand
  in Pawn (`_stand()`, world.py:473-477: the path end, the transition wait,
  the door waits) — Woody && DonePassing && NFH2Path → GoZone/DoorClicked/
  DonePassing drop. (b) Pawn.cs:1100-1104: the dead `if not self.steps` in
  `_next_step` (tested before the pop, under a guard that made it dead) is
  now `len(self.steps) == 1` (world.py:918-923). (c) Pawn.cs:1560-1566 via
  PassDoor→ChangeZone (cs:1598-1602): `_enter_played` drops DonePassing for
  Woody/Rottweiler on the door-pass zone change (world.py:1136-1140);
  `_transfer_zone` kept its clear. (d) DoorClicked: `woody_click` writes null
  per click (Pawn.cs:593) and the door before the gates (cs:624-627)
  (world.py:6031, 6062).
- Sweep: the two World-side stands in `_can_woody_use` (Item.cs:1663 →
  `self.woody._stand_name()` + play_looping, and Door.CanWoodyUse's literal
  Stand_Down loop) are the item agent's — the first is a SwitchToStandAnimation
  and would take the clears with `self.woody._stand()`; the second is a
  PlayLoopingAnimation(Stand_Down), correctly not one.
- Check: `pawn: the stand switch clears DonePassing/GoZone`, `pawn: entering
  the last step drops DonePassing`.

## 6. MED-LOW — LastMove* save/restore — REFUTED as stated; residual DOCUMENTED

- The draft says a failed re-route "restores the route and the use". Not so:
  a null FindPath goes ConstructLocationPath → `AdvanceToNextMove()` with
  MovePath == null → `OnPathFinished()` (Pawn.cs:1093-1132) → Woody's override
  runs `SetUsedInventory(null); ClearTooltip(); MoveLocationChanged = false;
  ClearMoveState()` (Woody.cs:356-368, 836-846) — and only then
  StartMoveToLocation's else `LoadMoveState()` (cs:736-741, 824-834) loads the
  freshly zeroed copies: MovePath = null, MoveIndex = 0. The original stops
  standing; the old route and its use are gone, not restored. (For a
  non-Woody pawn the base OnPathFinished is empty and the next WalkOnPath
  dereferences a null MovePath.) The GetMoveDestination-refusal failures
  (before InitializePath) do keep the old route — and the port's refusals
  keep `steps`/`on_arrive` untouched there too.
- Residual difference: on `_route`'s no-path returns the port keeps the old
  steps walking with `on_arrive` dropped, where the original stands. No
  live trigger: FindPath returns null only for a zone unreachable through
  `!Locked || TemporalLock` doors (ZoneController.cs:8-28, static at Start);
  every zone of every playable level is reachable, no runtime door lock
  exists in either season's data, and the port rebuilds its graph on unlock.
  Not changed.

## 7. MED-LOW — BlockWhenUsingPickupItem lock — CONFIRMED, DOCUMENTED (three areas outside mine)

- C#: Woody.cs:516-519 (BlockWhenPickupSpecialItemRef = target at TryUseItem's
  head), Item.cs:1539-1543 and 1645-1649 (the two priming arms of CanWoodyUse
  set `InputLocked = true; ClearStoreBlockedInput()`), unlock in
  CheckForTheBlockWhenUsedItem (Woody.cs:1170-1178) at OnPathFinished
  (cs:367) and at every SwitchToStandAnimation (PawnAnimationController.cs:95).
  A buffered click is dropped at the unlock; the port replays it after the
  prime pose (or processes it at once when the pose is not blocking).
- Data: 5 TrickItems — L113:414 ElectricTrapTatter (the cs:1643 arm),
  L202:239 EelBox, L204:227 OlgaKid, L208:234 Snake, L208:329 AngryElephant
  (the cs:1537 arm: a held unprimed source clicked on its PrimingItem).
- The port does not even load the field (scene.py Item has no
  `block_when_using_pickup`); the lock lines belong to `_can_woody_use`
  (item agent, off-limits to me). Exact patch: scene.py Item
  `self.block_when_using_pickup = bool(d.get('BlockWhenUsingPickupItem'))`
  (+slot); `_woody_try_use` head `if item.block_when_using_pickup:
  self.woody.block_when_pickup_ref = item`; in `_can_woody_use`'s
  `held_src.priming_item == item.pid` arm and the ElectricTrapTatter arm,
  before `woody_prime`: `if item.block_when_using_pickup: woody.input_locked
  = True; woody.stored_input = None`; and the unlock
  `if woody.block_when_pickup_ref is not None: input_locked = False;
  stored_input = None; block_when_pickup_ref = None` inside
  `Pawn._switch_to_stand` (Woody only) and `_next_step`'s path end. Not
  scriptable without the lock lines; no check.

## 8. MED — HideItem use skips InternalUse's layer/visibility choreography — CONFIRMED, FIXED (shared with the item agent)

- C#: HideItem.InternalUse → base.InternalUse (HideItem.cs:32-44,
  Item.cs:1929-1938: PawnToChangeLayerDuringHide → LayerDepth, ShowAfter
  FinishAnimation, SetActiveObjectHidden(true)); HideItem.Leave repeats the
  show-after + hide pair without the layer swap (HideItem.cs:64-70); the
  layer restores at Woody's blocking end (Woody.cs:304-307), the object at
  his single end (cs:381-385). Data: 11 S2 HideItems (incl. both
  StatueHidden) with HideDuringWoodyAnim + PawnToChangeLayerDuringHide, 7 S1
  Beds with HideDuringWoodyAnim alone.
- The item agent's concurrent `_item_internal_use` now runs the InternalUse
  half before `Pawn.hide` (world.py `_woody_try_use` HideItem branch); my
  side: `Pawn.unhide` runs the Leave repeat through the new
  `World.hide_during_woody_anim(item, layer=False)` (world.py:644-666,
  6498-6513) — the same helper the item agent's inline block duplicates
  (they may call it). Verified on L211 DeckChair: Woody's depth 16 → 72
  (BackItems) and the chair hidden at the dive; ChairIn is HoldOnLastFrame
  (never ends — the original holds too, Refresh AnimationControllerBase.cs:
  128-133), so both persist through the hide, as in C#; the leave hides the
  chair again during ChairOut and its blocking end restores depth 16 and the
  chair.
- Check: covered by the item agent's checks for the dive; my leave half is
  exercised in `pawn: he stays hidden after Hide_In` only indirectly (the S1
  wardrobe has no HideDuringWoodyAnim); not separately asserted.

## 9. LOW — sneak portal animations — CONFIRMED, FIXED

- C#: Woody.cs:952-968; PortalSneakUpAnimation = Walk_Up (cs:64),
  PortalSneakDownAnimation = default = AnimationState 0 = Walk_Down (cs:66,
  AnimationState.cs:3); both private, unserialized.
- After: `_portal_up_anim` / `_portal_down_anim` (world.py:515-547) — Woody
  sneaking climbs Walk_Up / Walk_Down (S1 only; S2 never sneaks).
- Check: `pawn: sneak portal strips`.

## 10. LOW — the four small ones

- (a) SeeAlerter `!Frozen` (Woody.cs:1040) — CONFIRMED, FIXED:
  `woody_see_alerter` returns on `w.frozen or self.game.ending`
  (world.py:5721-5725; Frozen = the dexterity snap DexterityComponent.cs:172
  and FinishGame's freeze GameInfo.cs:364, which the port carries as
  game.ending). Check: `pawn: a frozen Woody does not flinch`.
- (b) WrongZone tooltip on the door refusal (Pawn.cs:615 vs 633-638,
  Woody.cs:878-882) — CONFIRMED, FIXED as the field: `Pawn.wrong_zone_tooltip`
  (WrongZoneDescritionTooltip) set by the floor-item arm only, consumed by
  a non-empty bubble in `_wont_go` (world.py:6000-6015, 6056). Check:
  `pawn: door refusal speaks no WrongZone bubble`.
- (c) FlagAux from doors (Pawn.cs:594-595 with Helpers.cs:138-141 — a Door
  is an Item, `GetComponent("Item")` returns it; Pawn.cs:314-317) —
  CONFIRMED, FIXED: `woody_click` stamps `item_aux = item or door` at its
  head (world.py:6027-6032); the three `item_aux = None` door writes are
  gone. Residual: a floor item clicked bare-handed keeps ItemAux in C# while
  `Pawn.goto` nulls it — no floor item is walk-up in either season, so
  FlagAux never differs. Not scriptable (needs an off-floor Woody with a
  door-first path); no check.
- (d) Hide_In clicks buffered vs swallowed (Woody.cs:642-651) — CONFIRMED,
  FIXED: viewer.handle_click drops the click during the literal Hide_In
  (`'hide-in'`), the other dive poses (BedIn, ChairIn, ...) keep the
  unhide-and-store arm as the original does (viewer.py ~272-282). Check:
  `pawn: click during Hide_In is dropped / he stays hidden after Hide_In`.

## 11. F7 — every non-Woody role got the Rottweiler door strips — CONFIRMED, FIXED (+ a loader bug found)

- C#: Door.cs:18-24 (four pairs), Play<Role>Enter/LeaveAnimation
  Door.cs:85-139; overrides Woody.cs:452-463, Rottweiler.cs:363-373,
  Mother.cs:63-73, Olga.cs:94-104; the base Pawn plays nothing
  (Pawn.cs:1615-1635). Data: 98 doors carry MotherDoorBack*, Olga's fields
  ship NONE on all 354; the Kid never paths (no routine), so no other class
  ever passes a door.
- After: scene.py Door gains `mother_enter/leave`, `olga_enter/leave`
  (scene.py:953, 977-980); `Pawn._door_anims` picks by role, `(None, None)`
  for the base (world.py:979-996). Live effect: L213's Mother crosses
  DoorBack 56→50 (the only non-complex door any Mother/Olga route uses in
  S2) with M_disappear/M_appear — seen in a recording at t=13.7-16.7 s (the
  mother figure walks out of the temple doorway); Olga's Rottweiler-strip
  passes were never live (her routes are all complex transitions).
- Found while verifying: the port built no sprite at all for the 8 S2
  DoorBacks (IdleAnimation NONE + IgnoreIdleAnimation): `_add_sprite`
  returned on the NONE idle before the `hide_at_load` branch it had just
  taken — README's "IgnoreIdleAnimation doors (8) only exist on screen
  during a pass" was not happening; every S2 door pass, Woody's included,
  was an invisible instant warp. Fixed in scene.py `_add_sprite`
  (`pass_only`, scene.py:1892, 1915, 1956): the controller stays as a hidden
  sprite (its W_Disappear/W_Appear/N_*/M_* strips resolve), revealed by the
  pass and re-hidden by `_door_idle`. Woody's L213 DoorBack pass now shows
  him walking into the dark doorway (recording, 6.25-9.0 s). Side effect
  for the coordinator: record.py's `doors_active` lists these doors
  permanently (their idle is None, and both DoorBacks share one name), so
  that diagnostic is noisier on L211-214.
- Check: `pawn: S2 DoorBack has its pass sprite / Mother gets her own door
  strips / Olga gets her (NONE) strips`.

## 12. deferred finish (ShouldPlayFinish / IsPlayingFinish) — SKIPPED (gameinfo agent), as instructed.

---

## Extra entries (the per-field sweep and what verification turned up)

- E1 (#17, click gates) — FIXED: `LastInputTime` now stamps at
  handle_click's head past the gates (Woody.cs:641), so stored and hiding
  clicks reset the boredom timer; a paused game (`menu_open` or the viewer's
  Space) drops world clicks after the HUD had its look (`!(timeScale > 0)`,
  Woody.cs:637) — check `pawn: a paused game drops world clicks`. The
  Woody.cs:666 `InputLocked = false` else-arm remains a documented no-op; the
  port's stricter replay gate (no replay while ending/warping) stays as
  documented in the draft.
- E2 (found: the DonePassing click gate, Woody.cs:659-662) — FIXED: while
  DonePassingToOtherZone is latched the original drops the click; the port
  processed it, which is the only way its mid-stairs re-route shapes ever
  ran on a direct click. handle_click now returns `'passing'`; the shapes
  still run off the stored-click replay (OnBlockingAnimationEnded /
  OnDoorEnterAnimationFinished, Woody.cs:336-341, 484-488), exactly the
  original's only route to them. Check: `pawn: DonePassing swallows the click`.
- E3 (found: the Season-1 door-climb re-dispatch, Woody.cs:668-671) —
  FIXED: `!NFH2Path && itemAux is Door` re-runs ProcessMoveInput past the
  climb gate (itemAux = the current step's Target, cs:214-217, a Door
  during a door step), so an S1 click during a door climb is processed
  (EndPortalMove(abort), a new path; with FlagAux armed from the door
  click the new path inserts the walk-down floor step — the field's
  purpose). The port swallowed it as `'climb'`; now `s1_door_step`
  (viewer.py ~296-298) lets it through in S1's DOOR_CLIMB. Not scriptable
  deterministically in the suite (needs a click inside a 1 s climb window
  with the camera on it) — verified by reading; no check.
- E4 (#18, OnPathFinished's SetUsedInventory(null)+ClearTooltip,
  Woody.cs:361-362) — half FIXED, half DOCUMENTED: a finished walk with no
  use (door/zone/WasHiding paths; `cb is None`) drops the used inventory and
  the latched tooltip in `_next_step` (world.py:896-906). The item-path half
  fires in the original only after UseCompleted (Woody.cs:443,
  Pawn.cs:1752-1788), i.e. at the end of the use chain's last single —
  including a refusal's NoNo (a wrong-inventory refusal ends deselected in
  C#, the port keeps it selected) and never for the stand-refusals
  (Item.cs:1533/1663/1680 leave UseCompleted false; the path finishes at
  the next click's path end). The port's path ends at arrival, before the
  use, so that half belongs to the use tail (`_woody_try_use`'s
  `anim_ended` / the refusal returns — item agent). Note hud.py's new
  `promote()` (every world click sets `used = current`, dropping a stale
  used) already hides most of the visible difference.
- E5 (#13 RottLastDoor / RoutineActionMove.cs:108-125) — OUT OF SCOPE
  (routine agent): the Dog/Chili urgent-run door-relative arrival test is
  the routine's IsFinished, not Pawn's; noted only.
- E6 (#14 ElephantAnimations, Pawn.cs:1528-1557 — L208 only) — DOCUMENTED,
  not fixed by me: it is `Pawn.ChangeZone`, but the item agent's checks
  (`items: elephant zone watch locks the line once / is one-shot`) show
  they ported it in the zone-change hook this session; verified green in the
  suite; nothing left for the Pawn side.
- E7 (#15 in the draft = my #8 above) and #16 (= my #10d) — see there.

## Same-class sweep

- Sneak writes: `sneaking` is written in start_move_flags, toggle_sneak,
  hud.py:1340-1342 (gated) — nothing else in runtime/ or tests/ (monkey.py
  fixed).
- Stand switches in Pawn: `_next_step` end, `_wait_for_passing`
  (`_begin_transit`, DOOR_CLIMB), `_complex_arrival` — all `_stand()`; the
  World-side stands listed under #5.
- DonePassing clears: `_switch_to_stand`, `_next_step` last step,
  `_enter_played`, `_transfer_zone` — the four C# sites (PawnAnimation
  Controller.cs:92, Pawn.cs:1104, 1566 ×2 paths).
- `item_aux = None` writes: only `Pawn.goto` remains (a zone click's null,
  Pawn.cs:595) — the WasHiding arm and the door arms no longer null it.
- `_door_anims` callers: `_transit_animations` (both sides) only.
- Door-strip data: every Mother/Olga field read in one place
  (scene.py Door.__init__); no other reader of `rott_leave/rott_enter`
  besides `_door_anims`.

## README additions

- Movement, after the transit description: "Standing on the door he just
  came through (AtDoorLocation + LastExitDoor), any click whose path starts
  back through it passes at once from the doorway — ShouldExitDoorNow +
  UseDoorAtOnce (Woody.cs:777-780, Pawn.cs:744-780, 1391-1396, 1412-1416);
  a pawn off the floor at a door's x climbs to it directly
  (ShouldWalkDirectlyUpToDoor, Pawn.cs:785-788). Both ride the path build in
  `Pawn._route`; MoveToDoor's per-frame IsOtherPawnPassing wait
  (Pawn.cs:1359-1364) covers the climb too. UseDoorAtOnce is reset per path
  here; the original only ever consumes it — an arm abandoned mid-wait would
  ride into the next path (and double-play a flat door, cs:1384-1396). Not
  reproduced."
- The walk-through stairs: "A pair held by another pawn parks the arriving
  pawn standing on the first approach — TransitionEnter is assigned before
  the claim (Pawn.cs:1004/1014, 1022-1027). Every stand switch while
  DonePassingToOtherZone && NFH2Path drops GoZone/DoorClicked/the flag
  (PawnAnimationController.cs:86-95), entering a path's last step restamps
  the y-thresholds and drops it (Pawn.cs:1100-1104), and CrabAnimations
  drops it on door passes too (Pawn.cs:1566 via PassDoor). While the flag is
  latched, clicks are swallowed (Woody.cs:659-662): the mid-stairs re-route
  shapes only ever run off a replayed stored click, in both games."
- Input, HUD, and timing — the click contract: "The S2 sneak toggle only
  flips MbSneakToggle (ToggleSneak, Woody.cs:1151-1163) and
  StartMoveToLocation forces Sneaking off on the NFH2 path (cs:717-720) —
  the S2 sheets have no Walk_* strips. A click during the literal Hide_In is
  dropped, not stored (Woody.cs:642-651); the other dive poses unhide and
  replay. A paused game drops world clicks after the HUD (timeScale gate,
  cs:637); LastInputTime stamps past the gates (cs:641). Season 1 re-runs
  ProcessMoveInput when the current step's Target is a Door (cs:668-671),
  which is how a click during a door climb gets processed there. The
  WrongZone bubble speaks only for the floor-item refusal
  (WrongZoneDescritionTooltip, Pawn.cs:615), the door refusal is a bare
  NoNo. Sneaking Woody climbs with Walk_Up/Walk_Down (PortalSneak*,
  Woody.cs:64-66, 952-968)."
- The dexterity minigame: "The frame after the win Woody.Update re-runs
  TryUseItem on the same step (DexterityDone && !DexterityAux, Woody.cs:
  218-222); CanWoodyUse's DexterityDone branch then unlocks, spends the
  unlocker (unless the keep flags say otherwise), clears the three flags and
  falls straight to `return true` (Item.cs:1462-1474 → 1710) — the take
  follows without a second click." (Once the `_can_woody_use` line lands.)
- Door strips: "Each pawn class plays its own Door pair — Woody, the
  Rottweiler, the Mother, Olga (Door.cs:85-139; Mother.cs:63-73,
  Olga.cs:94-104); Olga's ship NONE everywhere, the base Pawn plays none.
  The 8 S2 DoorBacks serialize IdleAnimation NONE + IgnoreIdleAnimation and
  keep their pass strips (W_Disappear/W_Appear, N_*, M_*): the controller
  is a hidden sprite between passes." (Replaces the loader note that
  claimed this already.)
- Documented divergences: the #6 restatement (a null FindPath stops the
  original outright; no reachable trigger), the #7 lock (5 items, patch
  above), the #18 item-path half, the UseDoorAtOnce reset.

## Coordinator flags

1. `_can_woody_use` (item agent): `if dex == 'done': return True` after the
   'armed' return — required for #2's take to land (Item.cs:1462-1474 skip
   to 1710). My retry is in place and verified up to that line.
2. `_can_woody_use` + scene.py Item + `_woody_try_use` head: the
   BlockWhenUsingPickupItem lock (#7) — exact patch under #7; my unlock
   half (`_switch_to_stand` / `_next_step`) waits for the field.
3. `_woody_trick_done`'s inline HideDuringWoodyAnim block and the item
   agent's `_item_internal_use` duplicate the new
   `World.hide_during_woody_anim(item)`; either can call it.
4. hud.py's SneakRect could call `Pawn.toggle_sneak()` (same semantics today).
5. The moment suite's `sleep bar: the dog wakes early (<80%)` fails: L109's
   BedSleep runs 30 s (elements ~1.03 s) instead of the README's 15 s —
   the working-tree change to `Anim.pattern` (`UsePattern` gating,
   scene.py Anim.__init__) is the likely cause; not mine.
6. record.py `_state`'s `doors_active` now lists the 8 S2 DoorBacks
   permanently (idle None; both share one name) — the diagnostic wants
   `d.sprite.sprite.hidden` in the predicate if anyone asserts on it.
7. The item agent's `_can_woody_use` stand refusal (Item.cs:1663) could use
   `self.woody._stand()` for the DonePassing clear (#5 sweep).
