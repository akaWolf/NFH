# Flag-lifecycle audit — pass 1: Pawn (Pawn.cs) + Woody (Woody.cs)

Source: src/Assembly-CSharp/{Pawn,Woody}.cs. Port: runtime/world.py (class Pawn ~266,
World.woody_click ~5270, _woody_try_use ~5771, tick ~6376), runtime/viewer.py
(handle_click ~218). Every divergence below was read from both sides; the marked ones
were additionally reproduced headless (scripts run against levels/s1/Level101,
s2/Level201/202/211).

## Counts

| total | OK | DIVERGENCE | NOT-PORTED | OUT-OF-SCOPE | CONFIG | DEAD |
|-------|----|------------|------------|--------------|--------|------|
| Pawn 90 | 38 | 8 | 1 | 4 | 22 | 17 |
| Woody 84 | 25 | 5 | 14 | 13 | 21 | 6 |
| **174** | **63** | **13** | **15** | **17** | **43** | **23** |

(A NOT-PORTED field belongs to a numbered finding below when it breaks a live flow;
the 13+15 field verdicts collapse into 15 distinct findings.)

---

## DIVERGENCES

### 1. HIGH — Season-2 sneak toggle + click = crash (missing `Sneaking = false` NFH2 override)
- C#: `Woody.StartMoveToLocation` (Woody.cs:714-729): `Sneaking = MbSneakToggle; if (NFH2Path) Sneaking = false;` then the SneakFlag pair (721-728). `ToggleSneak` (Woody.cs:1151-1163) has the same `!NFH2Path` gate.
- Port: `Pawn.start_move_flags` (world.py:538-543) does `self.sneaking = self.sneak_toggle` with **no nfh2 override**. The HUD button (hud.py:1226-1230) gates correctly, but the *next click* re-copies the toggle into `sneaking`.
- Consequence: S2 Woody sheets have no `Walk_*` frames (README documents that); `_walk_anim` returns `Walk_Right` → `AnimPlayer._set` raises. **Reproduced**: Level201, press sneak (HUD or viewer Tab), click → `RuntimeError: No animation found !!! State: Walk_Right`. Viewer dies. viewer.py:401-405 (Tab) has the same hole.
- Scenario: any S2 level, tap the sneak button, click anywhere → crash.

### 2. HIGH — dexterity win never auto-completes the take (`DexterityDone`/`DexterityAux` retry missing)
- C#: `Woody.Update` (Woody.cs:218-222): `if (DexterityDone && !DexterityAux) { DexterityAux = true; TryUseItem(); }` — one frame after `WinDexterity` (DexterityComponent.cs:369-373 sets `DexterityDone`), the use re-runs and Item.cs:1445-1464/1482-1497 falls through to the unlock/take, clearing both flags.
- Port: `DexState._win` (world.py:3665-3671) sets `dexterity_done`/`mouse_click_after_dexterity`, but **nothing ever calls `_woody_try_use` again** — the only caller is `woody_use`'s on_arrive (world.py:5256). `mouse_click_after_dexterity` is write-only (no reader anywhere in runtime/).
- **Reproduced**: Level202 CrayFish — held reed, use, `ds._win()`, 3 s of ticks: inventory still `['IT2_Reed']`, item still full, `dexterity_done` latched True. In C# the crayfish is taken next frame.
- Consequences: the reward needs a second manual click; `dexterity_done`+`in_dexterity` stay latched meanwhile, so a click on a *different* dexterity item would fall straight through `_dexterity_gate`'s 'done' branch (world.py:5683, 5700-5708) and unlock it without playing its minigame.

### 3. HIGH — the finish deferral (`ShouldPlayFinish` / `IsPlayingFinish`) is not ported
- C#: `Woody.PlayFinishAnimation` (Woody.cs:1104-1128): `IsPassingDoor() → ShouldPlayFinish=true; return`, `Hiding → ShouldPlayFinish=true; Unhide(); return`; the deferred play fires at `OnBlockingAnimationEnded` (Woody.cs:331-334) or `OnDoorEnterAnimationFinished` (Woody.cs:490-493). `IsPlayingFinish` (1119, read 325-327) routes the blocking end into `GameInfo.FinishAnimationEnded`.
- Port: `World._play_finish_animation` (world.py:6332-6346) plays the win/lose sequence immediately, wiring `on_end` directly; no is_warping / hiding checks anywhere (`should_play_finish`, `is_playing_finish` do not exist in runtime/).
- **Reproduced**: Level101, all tricks done, win timer expiring while Woody passes a door: `WinGame` plays with `sprite.hidden=True` and `is_warping=True` — the entire win animation is invisible inside the door pass; the score screen appears over a doorway. In C# the pass completes first, then the visible win pose.
- Additional risk: `AnimPlayer.play_looping` clears `on_end` (world.py:119); if `_enter_played` reaches its `play_looping(d.exit_anim)` (world.py:995-996) while the finish sequence is pending, `_finish_animation_ended` is dropped. On the `_win` path (`game.ended` comes only from that callback, world.py:6361-6362) that is a **soft-lock** whenever the door Enter animation outlasts the finish animation. (`_time_up` and `finish_game_on_hud_click` set `ended` directly, so they only lose the pose.)
- Related cosmetic order swap: on an exit-door departure C# plays `ExitAnimation` first (Pawn.cs:1652) and the finish after (1662-1665) — the win pose is visible; the port calls `finish_game_on_hud_click` at world.py:968-971 *before* the exit-anim `play_looping` at 995, so Woody's win/lose pose is replaced by `Stand_*` one frame later.
- Hiding variant: time-up while hidden — C# unhides then plays; port plays the lose pose on a hidden sprite (invisible).

### 4. MED — a transition pair held by another pawn is not waited on (first approach walks in)
- C#: `MoveTransitionNFH2` (Pawn.cs:996-1030) assigns `TransitionEnter = step.TargetTransition` **before** the claim test (1004, 1014); when the claim fails, the 1022-1027 arm (`TransitionEnter.PassingPawnTransitionNFH2 != this → Velocity=0, stand, return true`) parks the pawn until the pair frees.
- Port: `Pawn._complex_arrival` (world.py:1070-1091) sets `self.transition_enter` **only inside the successful claim** (1082); the wait-arm (1085-1091) tests `self.transition_enter`, which is still None on a first approach → falls through, `passing_complex = True`, and the pawn enters the occupied stairs.
- **Reproduced**: Level201, claim the pair for the Rottweiler, route Woody through → he walks onto the claimed transition (C# stands).
- Scenario: Woody and the neighbour (both `adjacent_zones`) converge on one staircase → overlap on the steps; the mutual exclusion the flags exist for fails on the approach side. Writes/releases (Pawn.cs:1007-1008, 1017-1018, 300-305, 1240-1246, 1262-1268 ↔ world.py:1078-1084, 1014-1021, 1060-1067) are otherwise ported.

### 5. MED — `UseDoorAtOnce`'s general arms are missing (only the direct re-click on the same door is ported)
- C#: `BuildPathToTarget` (Pawn.cs:744-780): **(a)** `ShouldExitDoorNow(path)` (Woody.cs:777-780 — first step targets `LastExitDoor` while `AtDoorLocation`) fires for *any* destination whose route starts back through the door Woody stands on → `PortalMove=true; UseDoorAtOnce=true; MovingUp=ShouldWalkUp` → `MoveToDoor` passes at once (flat: 1391-1397; climb arm: `IsAtUseLocation || UseDoorAtOnce` at 1412-1416). **(b)** `ShouldWalkDirectlyUpToDoor` (785-788, off the floor at the door's x): `PortalMove=true; MovingUp=ShouldWalkUp; UseDoorAtOnce=!MovingUp` — climbs (or flat-passes) from the current height without walking to the floor first.
- Port: only the direct door-click shortcut exists (`woody_click` world.py:5326-5336: `at_door_location and last_exit_door is door` → immediate `_transit_animations`). Any *other* click routed through that door (a far-zone or item click from the top of a ladder door) builds a normal walk step → Woody walks **down to the floor and climbs back up** before passing; arm (b) has no equivalent at all (`use_door_at_once` does not exist in runtime/).
- Scenario: stand at the top of a walk-up door (arrived by clicking it), then click into the far zone (not the door itself) — original passes immediately from the top, port descends and re-climbs. README documents only the direct-click case (its exact wording), not the general path-head one.

### 6. MED — the NFH2 `DonePassingToOtherZone` / `GoZone` / `DoorClicked` clears are missing
- C# clear sites with no port equivalent:
  - `PawnAnimationController.SwitchToStandAnimation` (PawnAnimationController.cs:86-95): every stand while `DonePassingToOtherZone && NFH2Path` → `GoZone=null; DoorClicked=null; DonePassingToOtherZone=false` (this is what disarms the y-tracker after every path).
  - `AdvanceToNextMove` last step (Pawn.cs:1100-1104): the equivalent port code is **dead** — world.py:787-790 tests `if not self.steps ...` under a guard (768) that guarantees steps is non-empty, so the last-step `done_passing=False`/y-restamp never executes.
  - `CrabAnimations` (Pawn.cs:1560-1566) clears on **every** zone change incl. door passes; the port clears only in `_transfer_zone` (world.py:1110) — `_enter_played`'s door-pass zone change goes through `world.crab_animations` (5110-5137), which has no clear.
  - `DoorClicked` is never written in the port at all (only init world.py:315; C# writes at Pawn.cs:593 (null per click), 626).
- Empirics: exhaustive zone-to-zone sweeps on Level201/211 end with `done_passing=False` — each hop's transfer step clears it and the sign-split tracker rarely re-arms after the last transfer, so the *common* arrivals match the original. The residual exposure: (a) a stand mid-route (e.g. the held-transition wait, or a use interposed while the flag rides) leaves `done_passing`/`go_zone` set where C# clears them → the next click takes `FindPath`'s `done_helper` reroute shapes (world.py:643, 654-657, 717-753) from stale state; (b) both catch predicates read `not done_passing` (world.py:5091, 6151 ↔ GameInfo.cs:189/198, Pawn.cs:368/382) — any window where the flag out-lives its C# clear is a window where Woody cannot be caught.
- Severity med: no player-visible stuck case found empirically, but three of the original's four clear sites are absent and one port clear is dead code.

### 7. MED-LOW — the `LastMove*` save/restore family is absent; a failed re-route drops the pending use
- C#: `ProcessMoveInput` → `SaveMoveState` (Woody.cs:707, 812-822); a refused/failed move → `LoadMoveState` (Woody.cs:740, 824-834) restores MoveLocationChanged/MoveLocation/MoveIndex/PortalMove/ItemMove/MovePath — including the item step whose arrival performs the use; `ClearMoveState` at `OnPathFinished` (Woody.cs:365, 836-846).
- Port: no equivalent. The abort paths that keep the old route do so by not touching `woody.steps` — equivalent for same-click aborts — but `Pawn._route` (world.py:636-686) overwrites `self.on_arrive` at 649 *before* it can fail (hops None → 660-662 sets it to None and returns False). The old route keeps walking with its callback gone.
- Scenario: Woody en route to an item (on_arrive = `_woody_try_use`), player clicks a zone with no path (behind a locked transition — S2 has locked Transitions, Pawn.cs:628-632): original restores the route *and* the use; port walks the rest of the route and silently never uses the item.

### 8. MED-LOW — the `BlockWhenUsingPickupItem` input lock is not ported (5 items)
- C#: `TryUseItem` head stores `BlockWhenPickupSpecialItemRef` (Woody.cs:516-519); `CanWoodyUse`'s priming branches lock: `InputLocked=true; ClearStoreBlockedInput()` (Item.cs:1539-1543, 1645-1648); `CheckForTheBlockWhenUsedItem` unlocks at `OnPathFinished` (Woody.cs:367, 1170-1178) and at every `SwitchToStandAnimation` (PawnAnimationController.cs:96).
- Port: `block_when_using_pickup` appears nowhere in runtime/ (only `block_when_item_pick` = the *other* flag, ported at world.py:5818-5824). Data: `BlockWhenUsingPickupItem=true` on 5 TrickItems (L113:414, L202:239, L204:227, L208:234+329).
- Scenario: during those items' priming animation the original hard-drops clicks (lock + buffer clear); the port buffers and replays them → an extra queued move/use fires after the prime.

### 9. LOW — `SeeAlerter`'s `!Frozen` gate is missing
- C#: Woody.cs:1040: the flinch requires `!Frozen && alerter.Zone == Zone`; `Woody.Frozen` is set by `GameInfo.FinishGame` (GameInfo.cs:364) and `DexterityComponent.StartDexterity` (cs:172).
- Port: `woody_see_alerter` (world.py:5017-5056) checks the zone but not `frozen`. A `_see_delay` armed just before the dexterity snap (or before a catch, if the pet is already awake — `can_see_woody`'s `(not sneaking or self.awake)` arm, world.py:1278) delivers a movement-pause + FearShort over the frozen pose. Narrow window; the AlerterFSM's end-of-delay re-check (world.py:1312) covers the commonest cases.

### 10. LOW — Woody's sneak portal animations are not ported
- C#: `Woody.GetPortalUpAnimation`/`GetPortalDownAnimation` (Woody.cs:952-968): sneaking climbs with `PortalSneakUpAnimation` (=Walk_Up) / `PortalSneakDownAnimation` (enum default 0 = Walk_Down) instead of the serialized `Run_Up`/`Run_Down`.
- Port: `_portal_up_anim`/`_portal_down_anim` (world.py:455-477) branch only for the Rottweiler; Woody always climbs with `portal_up`/`portal_down` (= Run_Up/Run_Down in the data). A sneaking S1 Woody climbs ladders with the running strip. Cosmetic; the climb-click swallow lists both names so input is unaffected.

### 11. LOW — the WrongZone tooltip fires on a refusal where the original stays silent
- C#: `WrongZoneDescritionTooltip` is set only in `GetMoveDestination`'s floor-item arm (Pawn.cs:615) before `PlayWontGoAnimation`; the door-with-held-inventory refusal (Pawn.cs:633-638) calls `PlayWontGoAnimation` *without* it, so Woody.cs:878-882 shows no bubble there — just NoNo.
- Port: `_wont_go` (world.py:5258-5268) always shows the held inventory's `wrong_zone` text; it is called from both the floor-item (5304) and the door (5316) refusals. The door refusal gains a bubble the original never shows.

### 12. LOW — `FlagAux` never arms from walk-up-door clicks
- C#: `ItemAux = Helpers.GetItemFromCollider(...)` (Pawn.cs:595) is the raw collider item — doors included; Pawn.cs:314-317 arms `FlagAux` when `ItemAux.ShouldWalkUp` and same zone, and `BuildPathToTarget` (761-764) then inserts Woody's walk-down-to-floor step.
- Port: the door branches of `woody_click` set `item_aux = None` (world.py:5341, 5366), so `flag_aux` (world.py:1031-1034) arms only from walk-up *items*. After interacting near a walk-up door, the original's next-path floor-step insert can differ from the port's. Also feeds the `not flag_aux` gate of the D6 tracker.

### 13. LOW — `RottLastDoor`'s alternative Dog/Chili arrival test is unported
- C#: Pawn.cs:1647 stores the neighbour's last exit door; `RoutineActionMove.IsFinished` (RoutineActionMove.cs:108-125) ends the urgent Dog/Chili run when he crosses `RottweilerLastDoor.RottweilerExitLocation + RottPos`.
- Port: `last_exit_door` exists but only Woody's shortcut reads it (world.py:5330); the SameZone yell uses the 0.05-of-target check only (per ActionManager.cs:442-481). The door-relative arrival variant of the urgent run has no equivalent. Rottweiler-side; listed because the field is declared on Pawn.

### 14. MED-LOW — `ElephantAnimations` (the L208 zone-change elephant hack) is unported
- C#: `Pawn.ChangeZone` → `ElephantAnimations` (Pawn.cs:1528, 1536-1557): when Woody leaves the zone of `Woody.ItemBehavior` (serialized non-null **only on Level208**, the AngryElephant) while it is Primed, the elephant plays `PrimedTricked→IdleTricked` / `PrimedNormal→IdleNormal`, one-shot via `ElephantBehaviorAux`, and **locks `ObjectToPrimeWhenPrimed`**.
- Port: no equivalent anywhere (`ItemBehavior`/elephant zone-change logic absent; only the CanWoodyUse-head Mouse toggles at world.py:5419-5432 and the DoublePrimingItem arm at 5577-5589 exist).
- Scenario (L208): prime the elephant, walk to another zone — original swallows the pose into idle and locks the chained object; port leaves the primed pose standing and the chained object unlocked.

### 15. MED — the HideItem use skips `Item.InternalUse`, losing the S2 hide-spot layer/visibility choreography
- C#: `HideItem.InternalUse` calls `base.InternalUse()` (HideItem.cs:31-44) → the `HideDuringWoodyAnim` family (Item.cs:1929-1938): swap Woody's `AnimationGUIDepth` to `LayerDepth`, `Woody.ShowAfterFinishAnimation(this)`, `SetActiveObjectHidden(true)` — and `HideItem.Leave` repeats the show-after/hide pair (HideItem.cs:63-70). The layer restores at every blocking end through the serialized `Woody.HideItemToChangeLayer` (Woody.cs:304-307) — non-null on **9 S2 levels** (206 Pipe, 207 BeachChair, 208/209 Basket, 210 Bin, 211/214 DeckChair, 212/213 Lorry), all with `HideDuringWoodyAnim=true`.
- Port: `_woody_try_use`'s HideItem branch (world.py:5802-5808) goes straight to `woody.hide()` + `Hide_In`; `Pawn.hide`/`unhide` (545-570) handle `hide_woody`/`hide_anim`/`leave_animation` only. The layer-swap/show-after machinery exists solely on the TrickItem path (`_woody_trick_done` world.py:5908-5918), which HideItems never reach.
- Scenario (any of the 9 spots): Woody dives into the DeckChair — the chair item keeps drawing under/over the `ChairIn` sheet (which already contains the chair), and Woody's depth is never moved to `BackItems`/`Items` — double image and wrong layering during hide/leave; C# hides the object for the span and swaps the depth.

### 16. LOW — clicks during `Hide_In` are buffered instead of swallowed
- C#: `CheckMouseClick` (Woody.cs:642-651): while `Hiding && HidingItem != null`, a click during `Hide_In` returns without storing anything (the unhide+store arm requires `AnimState != Hide_In`).
- Port: viewer.py:244-249 implements the unhide arm; a click *during* `Hide_In` falls through to the blocking-buffer (252-254) and replays after the dive → Woody pops back out. Original drops the click.

### 17. LOW — small input-flag deltas around `InputLocked`/`LastInputTime`/replay gating
- Woody.cs:666 (`InputLocked = false` in the climb-click else-arm) has no port write — near no-op in C# (nothing re-locks there), noted for completeness.
- C# replays buffered input at any blocking end regardless of `InputLocked`/`GameEnding` (Woody.cs:336-341); the port's replay (viewer.py:432-438) additionally requires `not input_locked`, `not is_warping`, `not game.ending` — strictly safer, can only *suppress* a C# replay that would move Woody during a game-over.
- `LastInputTime` stamps: C# at `CheckMouseClick` head (641) — even buffered clicks reset the 30 s boredom timer; the port stamps in `woody_click` (5279) — buffered clicks don't. One extra idle stretch possible.
- Clicks are dispatched while the port's pause/menu is open (viewer run loop has no `paused`/`menu_open` gate on `handle_click`; C# `timeScale` gate at Woody.cs:637) — adjacent to the documented unported menu, noted only.

### 18. LOW — `OnPathFinished`'s inventory/tooltip tail is partial
- C#: every finished path runs `SetUsedInventory(null)` + `ClearTooltip` (Woody.cs:361-362).
- Port: `_next_step`'s path end (world.py:766-776) plays the stand and fires the callback only. Same-click aborts match (the miss-with-held-inventory clear, world.py:5375-5379 = ShouldAbortMove Woody.cs:786-792), but an inventory *without a source item* (grab_directly grants) held through a door walk survives arrival in the port where C# deselects it at path end.

---

## Per-field table — class Pawn (declaration order)

| field | verdict | evidence (C# ↔ port) |
|---|---|---|
| Speed | CONFIG | ctor Pawn.cs:203; runtime write only BirdMovementBehavior.cs:56 (ported behavior) ↔ world.py:281, 838 |
| SneakFlag | **DIVERGENCE #1** | writes Woody.cs:723/727/1156/1161; reads Pawn.cs:871/876 ↔ merged into `sneaking` (world.py:301, 838); the NFH2-false write missing |
| SpeedSneaking | CONFIG | Pawn.cs:204, read 879 ↔ world.py:282, 838 |
| MinDistToNextMove | OK | writes Pawn.cs:1114/1118/1123, read 957/1125 ↔ `_min_dist` world.py:823-832, used 1161 |
| RoutineBehavior | OK | reads ActionManager.cs:119-124/165-168 ↔ world.py:6119-6123, Routine.routine_behavior |
| AdjacentZonesEnabled | CONFIG | read Pawn.cs:983 ↔ world.py:311, 1165 (Olga ships without — documented) |
| ForceMagnitude | CONFIG | Pawn.cs:205, 963 ↔ world.py:283, 1194 |
| DoorForceMagnitude | CONFIG | Pawn.cs:206, 974/1324/1406/1432/1773 ↔ world.py:284, 1199/1216/1222/1229 |
| RunningForceMagnitude | CONFIG | Pawn.cs:207, 967 ↔ world.py:383, 1194 |
| RunningDoorForceMagnitude | CONFIG | Pawn.cs:208, 978/1328/1410/1436/1777 ↔ world.py:384, 1199 |
| DoorDistanceDelta | CONFIG | Pawn.cs:209, 1522 ↔ world.py:285, 954-955 |
| DebugPath | DEAD | debug OnGUI only (Pawn.cs:910); no live writer |
| DebugPathTexture | DEAD | debug texture |
| DebugMoveLocationTexture | DEAD | debug texture |
| ShouldLogPath | DEAD | LogPath gate only (Pawn.cs:511/549); no writer |
| PortalMove | OK (see #5) | writes 495/750/770/1371/1493/1513 + Woody 831 ↔ the DOOR_CLIMB/DOOR_ANIM/DESCEND states + `_route` reset; the BuildPath-time arming rides finding #5 |
| MovingUp | OK | writes 751/774/778/1288/1293/1374/1473/1483/1491/1634/1747/1782 ↔ states + `should_walk_down` (world.py:1176-1180, 1223-1229) |
| MovingDown | OK | incl. ActionManager.cs:467 (SameZone yell — ported per README) ↔ DESCEND state, world.py:997-1002 |
| ItemMove | OK | writes 496/1485/1740/1787 + Woody 832; reads incl. IsUsingItem (dead) ↔ ITEM_CLIMB + on_arrive callbacks (world.py:1171-1180) |
| TransitionMove | OK | writes 497/1283/1472; reads 1137/1281/1299/1714 ↔ `moving_to_adjacent_zone` world.py:495-501; detect at 6146-6147 |
| MoveIndex | OK (see #6) | writes 210/494/1095 + Woody 830 ↔ `_move_index` world.py:323, 683, 780; FlagAux clear at 785 = Pawn.cs:1096-1098; the last-step arm world.py:787-790 is dead code (finding #6) |
| MoveLocation | OK | UpdateMoveLocation/CheckMoveLocationY (1150-1155, 1135-1148 + Woody 939-950) ↔ `_step_target` world.py:797-821 incl. transition walk-deltas |
| MovePath | OK | Build* (729-853) ↔ `steps` list + `_route`/`_link_steps` world.py:636-763 |
| MoveLocationChanged | OK | writes 256/493/1072 + Woody 363/828 ↔ state machine (WALK vs IDLE) |
| UseCompleted | OK | write 1749, Woody 443; read 1754 ↔ callback ordering (`ITEM_CLIMB → _next_step → on_arrive`); C# reader `IsUsingItem` (Woody.cs:447-450) has **no caller** |
| SearchingItem | OK | Woody.cs:547 set, 386-411 branch ↔ `searching` local world.py:5812, `_woody_search_step` 5943-5958 (SearchItem.cs:64 / Item.cs:1380 / MouseCursor.cs:255 are *Item.SearchingItem*, a different field) |
| TrickItem (bool) | OK | Woody.cs:548 set, 412-437 branch ↔ `_woody_trick_done` world.py:5838-5935 (laugh, BeerMat, name-hack run, UseItemMultipleTimes all present) |
| SearchAnimation | OK | Woody.cs:409/438-441 ↔ take-sequence callback world.py:5948-5956 (PawnAnimationController.cs:13/54… is its own debug field) |
| InUrgentMove | OK | writes 432/446/453/460 + Rott 885 + Woody 729 ↔ world.py:541, 1928, 2894, 3052, 3327, 6228/6256; Woody's `IsInUrgentMove()=!Sneaking` (Woody.cs:858-861) ≡ port `in_urgent = not sneaking` |
| FeelSick | OK | Pawn.cs:466, Rott 884; reads Rott 400/417 ↔ world.py:326, 436-471, 3058, 3380 |
| AdvanceToUrgentMove | OK | Rott 350/502, consume 985-988 ↔ routines rebuild paths on urgent interpose (README's urgent machinery); no double-step observed |
| AnimController | OK | the controller ↔ AnimPlayer (world.py:12-259) |
| PortalDownAnimation | CONFIG | read 1456 ↔ world.py:291 (Woody sneak override — finding #10) |
| PortalUpAnimation | CONFIG | read 1461 ↔ world.py:290 |
| PlayerHeightDelta | CONFIG | ParrotLedgeBehavior writes (ported class) ↔ world.py:286, 483 |
| MovementPaused | OK | writes 261/266/271; read 867 ↔ world.py:304, 1124; pause/unpause sites 3004/3284/3310/3578/3701/4241/4260/5033/5041; the stand-switch `ContinueMovement` (PawnAnimationController.cs:97) is redundant in the port's structure |
| TestAnimationTime | DEAD | test harness (232) |
| TestAnimationInterval | DEAD | test harness |
| TestAnimationState | DEAD | test harness |
| TestAnimationType | DEAD | test harness |
| PawnZ | CONFIG | z only (211, 759-763); port is 2D |
| Velocity | OK | WalkOnPath/transitions ↔ per-tick vx/vy world.py:1184-1229; magnitude reads via state |
| ZoneLevelThreshold | CONFIG | read 1612 ↔ world.py:287, 1219 |
| ItemUseHeightThreshold | CONFIG | reads 1702-1704, Woody 752 ↔ world.py:288, 515, 527-534 |
| Toilet | DEAD | only Toilet.cs/ToiletBehavior read it; the Toilet subclass instantiates nowhere (documented) |
| MinimumVelocitySquared | CONFIG | reads 871, Woody 1077 ↔ state-based `_woody_moving` world.py:1266-1269 (equivalent: paused-mid-walk cases agree) |
| HelloAnimation | CONFIG | read 1066 ↔ world.py:367, 6404-6419 |
| HelloAnimationNFH2 | OUT | IntroAnimation.cs:303 only (intros unported, documented) |
| DefaultAnimation | CONFIG | 214, 237 ↔ world.py:392, 405-408 |
| FearAnimationLeft | CONFIG | 215, 1829 ↔ world.py:363, 6213-6216 |
| FearAnimationRight | CONFIG | 216, 1833 ↔ world.py:364 |
| FinishedEntrance | OK | write Woody 311 ↔ world.py:6414/6424/6429; reads 1064 (Hello) ↔ 6404-6419; 1378 OUT (confirmation); 1662 ↔ 968; Woody 191 ↔ 6044; 223 ↔ 6396; 471/484 ↔ 964 |
| CanStart | OUT | IntroAnimation writes; port starts the entrance timer immediately (title cards documented as not modelled) |
| HitPawnAction | CONFIG | serialized action ↔ `hit_pawn_action` world.py:345 (affected-pawn choreography ported per README) |
| WaitInFearAction | CONFIG | serialized ↔ world.py:344 |
| IsWarping | OK | writes 1631/1649 ↔ world.py:875, 982; readers: IsPassingDoor ↔ is_warping in detect (6145), catch (5088), alerter (1278/1296/1350); Woody.cs:1030 IsInZone ↔ same flag |
| WaitingforExitConfirmation | OUT | ExitConfirmation dialog documented as unported |
| ExitConfirmationShown | OUT | same (Rottweiler.cs:151 is its own reset) |
| WasMovingLeft | OK | write 1109, read HasPassedTarget 1041 ↔ `_step_sign`/`_step_sign_y` crossing machinery world.py:1137-1160 |
| OldZone | OK | write 1531 ↔ old_zone params world.py:5058-5072 (Rottweiler.cs:181 consumer ported via on_zone_changed) |
| AtDoorLocation | OK | writes 1060/1643 ↔ world.py:783, 985; read Woody 779 ↔ 5330 |
| UseDoorAtOnce | **DIVERGENCE #5** | writes 752/771, consume 1391-1396/1412-1414 ↔ only the direct-door-click shortcut world.py:5326-5336 |
| LastExitDoor | OK | writes 1061/1644 ↔ world.py:784, 986; read Woody 779 ↔ 5330 |
| ExitingDoor | OK | writes 1471/1490/1601; reads 1330/1334 ↔ the transit/DESCEND state split (climb-side pass at world.py:1205-1216) |
| WarpDoor | DEAD | only BugTest.cs:13 reads |
| WaitWoodyGoToRott | DEAD | write Woody.cs:269 inside `OnGetCaughtByNeighbour` — **no caller anywhere**; read only its decl |
| WrongZoneDescritionTooltip | **DIVERGENCE #11** | set Pawn.cs:615 only; consume Woody.cs:878-882 ↔ `_wont_go` shows unconditionally (world.py:5258-5268) from both call sites |
| AnimationsInProgress | OK | set Item.cs:1858 (WoodyUse head, incl. refusals), clear Woody.cs:376-380 (TrickLaugh/WhatsUp/TakeInventory) ↔ world.py:5776, 5716-5718; reads Woody 232/1036 ↔ 6432-6433, 5028; the DontLaugh latch quirk preserved on both sides |
| RottLastDoor | **NOT-PORTED #13** | write 1647; read RoutineActionMove.cs:119 (Dog/Chili door-relative arrival) — no port equivalent |
| GoZone | **DIVERGENCE #6** | writes 606/647/662/677/702 ↔ `_capture_click` world.py:575-578; the PawnAnimationController.cs:90 null-clear missing |
| DonePassingToOtherZone | **DIVERGENCE #6** | writes 327/335/339 ↔ world.py:1040-1048; clears 1104 (dead port code 787-790), 1566 (only `_transfer_zone` 1110), PawnAnimationController.cs:92 (missing); reads: predicates ↔ 5091/6151, FindPath ↔ 643/654, Woody.cs:659 climb gate ↔ viewer 256 |
| cont | OK | Level211Behavior storage (behaviors.py ports the class with its own state) |
| DoorClicked | **DIVERGENCE #6** | writes 593 (null per click)/626 — never written in the port (world.py:315 init only); the tracker gate rides go_zone alone |
| WoodyPositionY | OK | 217/321 ↔ inline `y` world.py:1040 |
| NewWoodyPositionYNegative | OK | 218/608/649/664/679/704/1102 ↔ `y_neg` world.py:579, 788 (dead), 1042-1046 |
| NewWoodyPositionYPositive | OK | 219/611/652/667/682/707/1103 ↔ `y_pos` world.py:581, 1047 |
| Interval | CONFIG | 0.15 (220) ↔ the literal world.py:579-581, 788-789 |
| GoingDown | DEAD | writes 326/334, read only decl |
| DoorAux | DEAD | write Helpers.cs:244, read only decl |
| ItemAux | OK (see #12) | write 595 ↔ world.py:587, 606, 5295/5341/5366; consumer 314-317 ↔ 1031-1034 — doors excluded in the port (finding #12) |
| FlagAux | **DIVERGENCE #12** | set 316 ↔ 1031-1034 (items only); clear 1098 ↔ 785-786; reads 319/761 ↔ 1039, 668 |
| IsSleeping | OK | writes Mother.cs:25/ProgressBar.cs:180/Rottweiler.cs:154 (sleep bars ported) ↔ world.py:354; reads GameInfo/Pawn predicates ↔ 5090/5101, 6178/6193 |
| AuxFlag | DEAD | no writes |
| PassingComplexMove | OK | writes 297/1234/1247/1256/1269 ↔ world.py:312, 1013, 1068, 1097; predicate reads ↔ 5092/6152-6153 |
| TransitionEnter | **DIVERGENCE #4** | writes 306/1004/1014/1246/1268 ↔ world.py:1021, 1082, 1067; the assign-before-claim missing → the held-pair stand never fires first-approach |
| lastItem | DEAD | no writes |
| lastZone2 | OK | 318/291 ↔ `_last_zone2` world.py:322, 1010, 1035 |
| CheckForNeighbour | OK | 295/312, read 308 ↔ world.py:321, 1011-1012, 1022-1028 (door-exit predicate, no sneak escape — matches Pawn.cs:366-388) |
| originalZone | DEAD | read only in the no-op `if` Pawn.cs:738-740 |
| auxZone | DEAD | decl only |

## Per-field table — class Woody (declaration order)

| field | verdict | evidence (C# ↔ port) |
|---|---|---|
| InvManager | OK | ↔ `InventoryState` world.py:1364-1407 |
| Action | OK | writes 1053/1057 + MouseCursor ↔ hud cursor verbs (hud.update_cursor; two-stage inventory per README) |
| State | OK | writes 1067/1071 ↔ `inv.used is None` ≡ Hover (hud.py promote/CheckClick); tutorial/skater writes OUT |
| HoverItem | OK | MouseCursor writes ↔ viewer `_hit_at` + `hud.update_hover` (viewer.py:342-352) |
| MouseOverHUD | OK | read 637 ↔ the HUD-strip swallow viewer.py:235-237 |
| HUD | OK | ↔ world.hud |
| Lives | DEAD | decl-only read |
| IdleAnimations | CONFIG | read 621 ↔ world.py:368, 6445-6449 |
| IdleThreshold | CONFIG | read 616 ↔ world.py:369, 6443 |
| UseString/WithString/EmptyUseString/LookAtString/OpenString/ExamineString/HideString/GoToString/EndString | CONFIG (9) | LoadLocalizationData 195-207 ↔ the hud strings section (README text pipeline) |
| ExtraDeltaHeight | CONFIG | read 752 + Item.cs:2288 ↔ world.py:289, 517, 530-531 |
| ExitConfirmMessage | OUT | ExitConfirmation documented |
| EntranceClap | CONFIG | MusicPlayer reads (ported clap) |
| EntranceVolume | DEAD | zero reads |
| TutorialScriptCamera | OUT | tutorials documented |
| TutorialScriptCamera3 | OUT | tutorials documented |
| WinAnimation | CONFIG | read 1122 ↔ world.py:365, 6338 |
| LoseAnimation | CONFIG | read 1126 ↔ world.py:366, 6338 |
| SearchBehavior | OK | OnSearchItemUsed 985-991 ↔ world.py:6124-6126, 5965-5968 |
| LastInputTime | OK (note #17) | writes 187/614/618/641, read 616 ↔ `_last_input_time` world.py:3846, 5279, 6441-6444; buffered-click stamp missing (cosmetic) |
| PortalSneakUpAnimation | **NOT-PORTED #10** | read 965 — no sneak-climb branch in `_portal_up_anim` (world.py:455-464) |
| PortalSneakDownAnimation | **NOT-PORTED #10** | read 956 (enum default Walk_Down) — same |
| InGameMenu | OUT | menu widgets documented; the pause half ported (hud power button) |
| Frozen | **DIVERGENCE #9** | writes 995/1001 (+GameInfo.cs:347/364, DexterityComponent.cs:172/395) ↔ world.py:361, 3578/3701 (dexterity) and `game.ending` gates (viewer 238); the SeeAlerter `!Frozen` read (1040) missing at world.py:5031; CheckMouseClick read (637) covered by is_dexterity_on/ending |
| InputLocked | **DIVERGENCE #8** (core OK) | Start 191 ↔ 6044; trick-camera 253/258 OUT; entrance 276/374 ↔ 6413/6421-6428; transit 460 ↔ 881; arrival 473/483 ↔ 964-965; pick 536 + Item.cs:1945 ↔ 5819/5824; unhide 647 ↔ viewer 247; GameInfo.cs:365 ↔ `game.ending` gate; **missing**: Item.cs:1541/1647 + 1170-1178 (finding #8), climb-arm 666 (note #17) |
| Sneaking | **DIVERGENCE #1** | writes 716/719/1157/1162 ↔ world.py:540 (NFH2 override missing → crash), hud.py:1227-1230, viewer.py:403-404; reads: predicates ↔ 6149, walk anims ↔ 450, portals (#10), IsSneaking 1077 ↔ 1277 |
| Hiding | OK | write 1088 (SetHidden override) ↔ world.py:419-426, 547, 559; reads: Alerter ↔ 1278/1297/1350, GameInfo/Pawn predicates ↔ 5089/6148, boredom 616 ↔ 6442, click 642 ↔ viewer 244, move 730 ↔ 542, finish 1112 → finding #3; transit-Hiding compensated by is_warping everywhere |
| HidingItem | OK | writes 1083/1099 ↔ world.py:548, 562; reads 642 ↔ viewer 244, Leave chain ↔ unhide 557-570 |
| LastHidingItem | OK | writes 803/1083/1095 ↔ world.py:5289, 549, 563; read 801 ↔ 5288 |
| StoredMousePosition | OK | 689/698 ↔ `stored_input` tuple world.py:372, viewer 248/253/437 |
| StoredMouseButton | OUT | the right-button path is the touch long-press alternative click (mobile); port is left-click only |
| HasMouseInputStored | OK (note #17) | 688/697, clear 338/486 ↔ viewer replay loop 432-438; ClearStoreBlockedInput 693-700 ↔ `stored_input=None` 5820; replay gating differences note #17 |
| IsPlayingFinish | **NOT-PORTED #3** | write 1119, read 325-327 — replaced by direct on_end wiring; the deferral half missing |
| ShortFearAnimationRight | CONFIG | read 1023 ↔ world.py:5035 |
| ShortFearAnimationLeft | CONFIG | read 1019 ↔ 5035 |
| FearLeftRepeat | CONFIG | read 346 ↔ 5044-5046 |
| FearRightRepeat | CONFIG | read 349 ↔ 5044 |
| ShouldPlayFinish | **NOT-PORTED #3** | writes 1108/1114, reads 331/1182 (+ door arrival 490) — absent; verified invisible finish mid-pass |
| LastMoveLocationChanged | **NOT-PORTED #7** | SaveMoveState/LoadMoveState/ClearMoveState family absent |
| LastMoveIndex | **NOT-PORTED #7** | same |
| LastPortalMove | **NOT-PORTED #7** | same |
| LastItemMove | **NOT-PORTED #7** | same |
| LastMovePath | **NOT-PORTED #7** | same |
| LastMoveLocation | **NOT-PORTED #7** | same |
| WasHiding | OK | set 1101 ↔ world.py:561; consume 798-808 ↔ 5286-5299 (floor conversion order, ClearTooltip, TargetLocation walk all match) |
| EntranceTimer | OK | decrement 225, gate 223 ↔ world.py:6045, 6396-6399 (CanStart immediate — documented) |
| MouseCursor | OK | ↔ hud cursor pipeline |
| ItemToShowAfterAnim | OK | set 1137 (`ShowAfterFinishAnimation`), restore+clear 381-385 ↔ `_woody_show_after` world.py:5917, 5719-5721 |
| ShouldUpdateWalkingAnimation | OK | set 1025, consume PostWalk 283-287 ↔ per-tick walk-anim refresh (world.py:1197-1202) makes the flag unnecessary; `restart_movement` ≡ RestartMovement's inert-move + FearRepeat loop (5037-5050 = Woody.cs:317-320, 343-353) |
| SignalScriptOnLocation | OUT | LevelScript tutorials documented |
| ScriptLocation | OUT | same |
| ScriptLocationThreshold | OUT | same |
| SignalScriptDoor | OUT | same |
| SignalScriptZone | OUT | same |
| TouchStarted | OUT | touch-only input path documented |
| TouchStartedTime | OUT | same |
| BlockMouse | DEAD | zero writes, decl-only read |
| OldZoneAux | DEAD | decl-only |
| Rott | OK | ↔ pawns registry (`pawns['Rottweiler']`) |
| WrongZoneItem | DEAD | write-only (877); TrickItem.cs:160 declares TrickItem's *own* `WrongZoneItem` — Woody's is never read |
| DeltaDescriptionLocation | CONFIG | read 880; serialized (0,0,0) on Woody → the port's omission at world.py:5265 is a data no-op |
| PostponeAlert | OK | set 1038, release 232-236 ↔ `postponed_alerter` world.py:5028-5030, 6432-6435 |
| Alerter | OK | set 1035 ↔ merged into postponed_alerter; the neighbour-side readers ride `rott_hear_alerter` (world.py:5010-5015) |
| NFH2Path | CONFIG | ↔ `nfh2` world.py:310/387 (one missing gate = finding #1) |
| WoodyGameOverPosition | DEAD | only inside the dead `OnGetCaughtByNeighbour` (no caller) |
| DexterityDone | **DIVERGENCE #2** | set DexterityComponent.cs:373 ↔ world.py:3671; consume Item.cs:1445-1464/1482-1497 ↔ 5683-5708; the Woody.cs:218-222 auto-retry missing (verified) |
| DexterityAux | **NOT-PORTED #2** | the retry one-shot — absent |
| ItemBehavior | **NOT-PORTED #14** | reads Pawn.cs:1536-1557 (ElephantAnimations) — live via L208's serialized ref; no port equivalent |
| HideItemToChangeLayer | **NOT-PORTED #15** | reads Woody.cs:304-307 (blocking-end layer restore); serialized on 9 S2 levels; the whole HideItem-side swap family missing (world.py:5802-5808 bypasses InternalUse) |
| HideAux | OK | 243/248, watch 237-250 ↔ `_woody_use_anim_hidden` world.py:6453-6461 |
| itemAux | OK | write 216 ↔ `_woody_use_anim_item` (world.py:5780-5781; C# checks HideDuringWoodyUseAnim inside the watch — same set); the 668-671 door re-dispatch collapsed to one call (documented in viewer.py:258-260, same result) |
| MbSneakToggle | OK | write 1153 ↔ `sneak_toggle` world.py:302, hud.py:1227; read 716 ↔ 540 (see finding #1 for the gate) |
| MouseClickAfterDexterity | **DIVERGENCE #2** | set DexterityComponent.cs:371 ↔ world.py:3670; the Item.cs:1948-1951 consume (clear + unlock) has no port reader — write-only |
| InDexterity | OK | writes Item.cs:1443/1462/1480/1495 ↔ world.py:5680-5682, 5700; reads 1438/1440/1477 ↔ 5669; latch-leak noted under finding #2 |
| BlockWhenPickupSpecialItemRef | **NOT-PORTED #8** | set 516-519, consume 1170-1178 — absent with the whole BlockWhenUsingPickupItem lock |
| UnlockOneTime | OUT | trick-camera relock/unlock (251-260) — trick camera documented as unimplemented |

## Method notes (non-field checks made along the way)

- `OnGetCaughtByNeighbour` (Woody.cs:263-271) is dead — the live catch is GameInfo.OnNeighborCaughtWoody → PlayFearAnimation → Rottweiler.OnCaughtWoody, which the port follows (world.py:6195-6258).
- `Pawn.IsUsingItem` (888) and its Woody/Rottweiler overrides have no caller — dead virtual.
- `ClickCanceled` (Pawn.cs:197) is written only by CameraMover's touch-drag pan (CameraMover.cs:403/416) — touch-only, OUT.
- `GameInfo.FinishGame`'s `Woody.Freeze()+InputLocked=true` (GameInfo.cs:364-365) maps to the port's `game.ending` input gate + steps-clear; equivalent for input, see finding #3 for the animation half.
- The C# blocking-end replay of buffered input during GameEnding (Woody.cs:336-341, no ending gate) is deliberately *not* reproduced — the port's stricter gate can only suppress a move-during-game-over glitch of the original (note #17).
