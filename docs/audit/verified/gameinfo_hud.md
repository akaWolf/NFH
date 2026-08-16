# gameinfo_hud — verified findings (GameInfo, HUD, the animation model, the endings)

Area: `runtime/world.py` GameState / AnimPlayer / World.tick's end-game section
(`_finish_game`, `_freeze_woody`, `_freeze_pawn`, `_finish_animation_ended`,
`_time_up`, `finish_game_on_hud_click`, `_play_finish_animation`, `_win`, the
detection predicates, `_catch`), `ProgressBarState`, `InventoryState`,
`runtime/hud.py` (whole), the two viewer/recorder gates the findings required.
Check module: `tests/checks/gameinfo_hud.py` (33 checks, ~8 s, all pass).

Counts: claims received **22** (D1–D21 + the deferred finish B) + 2 coordinator
items (empty patterns X3, the pattern-frame clamp X6) · CONFIRMED-FIXED
**19 + 2** · CONFIRMED-DOCUMENTED **3** (D8, D19, D21) · REFUTED **0** ·
already-documented **0** · extra findings from the same-class sweep **4**
(X1 pawn Freeze semantics, X2 the double tick — HIGH, mine —, X4 the own-zone
exit arm, X5 the per-frame OnIconPressed poll), all fixed.

The suite: `SDL_VIDEODRIVER=offscreen python3 tests/run_moments.py /tmp/gi-moments`
→ ALL OK (the sleep-bar moment's expectation was re-based by the coordinator
to the real timing, see X2 / flag 1).

---

## D1 (HIGH) — TimeUp forced a loss — CONFIRMED-FIXED
- C#: `GameInfo.Update` cs:241-249 `TimeUp = true; FinishGameOnHUDClick();`
  never touches `Won`; `FinishGameOnHUDClick` cs:382-389 picks the jingle by
  `Won`; `CalculateRating` cs:438-465 tests `Won` before `TimeUp`.
- Port before: `_time_up` set `won = False`, always `failed`, rating TIME UP.
  After: `_time_up` (world.py ~7309) = `time_up = True` + `finish_game_on_hud_click()`,
  whose jingle branches on `won` (success/success_perfect vs failed).
- Check: `gameinfo: TimeUp keeps Won -> success jingle`, `… -> a Won rating band`.

## D2 (HIGH) — GameEnding only at the end of the 2.5 s wait — CONFIRMED-FIXED
- C#: `WinGameOnCompleteAllTricks` cs:292-296 sets `GameEnding = true` and starts
  the `WinGameAnimations` coroutine (cs:298-302, 2.5 s, `PlayWinAnimations`).
  `Update`'s whole block is gated `!GameEnded && !GameEnding` (cs:212) — no
  catch, no clock; HUD.CheckClick's GameEnding branch (HUD.cs:1286-1308),
  MouseCursor.UpdateHover's early out (MouseCursor.cs:120-124). Woody's own
  clicks stay live: `CheckMouseClick` gates on `Frozen` (Woody.cs:637), and
  `Frozen` comes only with `FinishGame`'s `Woody.Freeze` at the wait's end.
- Port after: `World.tick` (~7556-7600) runs the coroutine timer outside the
  gate, sets `ending = True` the frame `all_done()` is seen (or `_win()` at once
  with `win_immediate`), and follows the original's branch order catch →
  Mother → win → clock (was clock first). `_finish_game` sets `woody.frozen`
  (`_freeze_woody`, Woody.cs:993-997); the click gates read `woody.frozen`
  instead of `game.ending`: viewer.py:261 (`handle_click`) and
  `World.woody_use` (~5957). The HUD's `ending` gates were already the C# reads.
- Numbers (Level101, last trick at t=4.00): ending at 4.02, clock frozen at
  296.00 through the wait, a click at 4.5 walks Woody (x 4.38 → 2.88),
  `_win` at 6.52, `frozen` from then on.
- Check: `gameinfo: GameEnding set on the all-tricks frame`, `the clock freezes
  during the win wait`, `PlayWinAnimations after the 2.5 s coroutine`, `Woody
  still walks during the wait (Frozen later)`.
- Left as documented (see flags): `door_exit_catch` and the stored-click
  replays (viewer.py ~449, record.py ~270) still gate on `game.ending`; C# would
  catch/replay inside the wait (Pawn.cs:366-378 has no GameEnding gate) and
  end up in a double ending.

## D3 (MED) — GameEnded before the finish pose — CONFIRMED-FIXED
- C#: the only `GameEnded = true` is `FinishAnimationEnded` cs:343-345,
  reached from `Woody.OnBlockingAnimationEnded` (Woody.cs:325-327) when the
  Win/Lose single ends; `HUD.DrawScore` gates on it (HUD.cs:731).
- Port after: `_time_up` and `finish_game_on_hud_click` no longer set `ended`;
  it comes from `_finish_animation_ended` alone (`_play_finish_animation`'s
  `on_end`; a missing pose — no data — ends at once). Numbers: TimeUp at 4.52,
  ended at 6.85 (WinGame 23 frames / 10 fps = 2.3 s).
- Check: `gameinfo: GameEnded only after the finish pose`.

## D4 (MED) — DisableProgressBar unported — CONFIRMED-FIXED
- C#: `FinishAnimationEnded` cs:346 → `DisableAllProgressBars` cs:535-541 →
  every subscribed bar's `DisableProgressBar` (ProgressBar.cs:303-307):
  `SetSleeping(false)` + `enabled = false`; only an active bar is subscribed
  (OnEnable/OnDisable cs:108-121).
- Port after: `ProgressBarState.disable()` (~4373: skips inactive bars,
  `set_sleeping(False)`, `disabled = True`; `tick` honours `disabled`);
  `_finish_animation_ended` calls it on every bar. Verified L109 (bed bar up
  when the clock ran out): after the pose `disabled=True, visible=False,
  is_sleeping=False, hud_disable_think=False`.
- Check: `gameinfo: DisableAllProgressBars at FinishAnimationEnded`.

## D5 (MED) — UsedInventory survived extra clicks — CONFIRMED-FIXED
- C#: `HUD.CheckClick` cs:1319-1322 runs `Woody.SetUsedInventory(CurrentInventory)`
  on EVERY non-icon click; `Woody.SetUsedInventory` (Woody.cs:1062-1073) assigns
  unconditionally — Current null ⇒ Used null. Confirmed against
  `ShouldAbortMove` (Woody.cs:786-792): that arm only handles the same-click
  bare-zone abort; the per-click reset is CheckClick's.
- Port after: `InventoryState.promote` (~1619) is unconditional and
  `Hud.check_click` (~1319) does `inv.used = inv.current` before the button
  rects. `InventoryState.select` (~1627, the viewer digits / recorder `inv N` /
  the harnesses) now stages `current` — the icon click — instead of writing
  `used`, so the next click promotes it exactly like the original; the one
  harness reader that needed it (`tests/run_tricks.py leg_prime`) reads
  `used or current`.
- Check: `hud: the world click promotes Current -> Used and latches`, `hud: a
  click with nothing selected drops UsedInventory`.

## D6 (MED) — pressed-icon draw wrote the tooltip raw — CONFIRMED-FIXED
- C#: `DrawInventory` HUD.cs:942-955: only `CurrentInventory` draws pressed and
  its line is `SetTooltip(UseWith, name, HoverItem == null ? EmptyUseString :
  HoverItem.GetNameString())` — hover-aware, latch-gated (cs:1024-1027);
  `UsedInventory` has no draw state.
- Port after: `_draw_inventory` (hud.py ~831): `inv.current is entry` only,
  `set_tooltip('UseWith', …)` with the hovered Item's GetNameString (a Door's
  NameString), else EmptyUseString. `set_tooltip` (~541) is the SetTooltip
  port: latch gate, GoTo renders empty, `tooltip_state` = CurrentTooltipState
  (enum default `Examine`).
- Check: `hud: the pressed icon line names the hovered item`, `hud: the icon
  stage speaks "Use X with <hover>"`.

## D7 (MED) — the latch only after a promotion — CONFIRMED-FIXED
- C#: `UpdateTooltip` cs:1062-1067 on every non-icon click: `ClearPermanentTooltip`
  → `UpdateHover(tooltipOnly)` (Current still set) → `MakePermanentTooltip`
  (`CurrentTooltipState != GoTo`, cs:1069-1075); then `SetCurrentInventory(null)`,
  a second `UpdateHover`, and `if (HoverItem == null) ClearPermanentTooltip()`
  (cs:1323-1327). A Door is an Item, so door taps count as hovered.
- Port after: `check_click` mirrors the six steps; `update_hover` keeps
  `_hover_item/_hover_door/_hover_zone` (Woody.HoverItem).
- Check: `hud: a bare tap on an item latches the colored line`.

## D8 (MED) — Hidden freezes Refresh — CONFIRMED-DOCUMENTED (flag)
- C#: `AnimationControllerBase.OnGUI` cs:172-189: `if (!Hidden && Repaint)
  Refresh()` — a hidden controller neither draws nor advances (no frame step,
  no PlaySound cs:110, no sequence progress, no end delegates). Writers:
  `StopSingleAnimation` cs:226-229 (HideOwnerOnAnimationEnd), `Pawn.SetHidden`
  (Pawn.cs:1464-1467), the transits (Pawn.cs:1615-1661), `Item.SetObjectHidden`
  (Item.cs:1984-1995 — items too), `RoutineActionUse` cs:174-177/213-216/481-484.
- Port: `AnimPlayer.tick` advances regardless of `sprite.hidden`
  (render.py:106 only skips the draw), and its frame-keyed sounds play hidden.
- Why not fixed here: the port ends Olga's `HideOwnerDuringUse` uses (Level205
  and Level210 `OlgaMatBeach`: `HideOwnerDuringUse=True, MutexAction=False,
  Duration=0`) on HER hidden sequence's drain (`Routine._use` →
  `play_sequence(seq, on_end=self._finish)`, her `OlgaUseAnimation=['HitPawn']`,
  6 frames at 10 fps = 0.6 s), whereas the original ends that action from the
  ITEM's `UseNormalSequence` through the alternate delegate
  `Olga.OnItemAnimationSequenceEnded` (TrickItem.cs:964-975 → `PlayUseAnimation(
  olga.OnItemAnimationSequenceEnded)`, Olga.cs:154-158 → `StopAction`) — the
  mat's `N2TrickItemExtra1 → N2TrickItemUseNormal (InfiniteLoop) → Extra3 →
  Extra2`, released by the neighbour's mutex `ItemToStopInfiniteAnimation`.
  Freezing hidden AnimPlayers today would park Olga forever (her HitPawn never
  drains) and break the Level205 handshake the README verified; the freeze must
  land together with the item-driven action end (Routine.*, pawn agent's area).
  Live guards added: `routine: Level205 cycles both routines (D8 guard)`,
  `pawn: Level101 door pass completes visible (D8 guard)` — both pass before
  and after this pass. Also relevant once fixed: the finish deferral (B) keeps
  Woody's WinGame off a hidden controller.

## D9 (MED) — PrevAnimState is never written — CONFIRMED-FIXED
- C#: `PawnAnimationController.PlaySingleAnimation` cs:165-172 writes
  `PrevAnimState` only when `CurrentAnimation.Type == Looping`, but
  `SetAnimation(state, Single)` → `GetAnimation` cs:137-151 returns a
  Type==Single instance (strict filter) — the write is dead, `PrevAnimState`
  stays `default(AnimationState)` = `Walk_Down` (AnimationState.cs:3), and
  `SwitchToStandAnimation` cs:99-134 uses it whenever a Single is current
  (`IsPlayingSingleAnimation`) → `StandDownAnimation`; a Looping current
  resolves by AnimState (Walk/Stand/Run/RunWC → the facing stand, WaitWatch /
  WaitInFear stay themselves, anything else throws "Stand with nothing").
- Port after: `Pawn._stand_name` (~444, the one allowed class-Pawn function):
  `anim.mode == 'single'` → `stand['Down']`; looping → the direction parsed off
  the current name's family (was `self.facing`), WaitWatch/WaitInFear kept;
  other loops keep the port's facing fallback (documented: the original throws
  there — pie/fifi/ski/bowling walks — a pawn-agent matter). Every stand site
  goes through it (the AnimPlayer stand hook, `_stand`, `_next_step`, the item
  refusals), exactly as the original decides by the current instance's type.
- Numbers: Hello (a Single) → Stand_Down after the entrance; WinGame → Stand_Down;
  NoNo after a leftward walk → Stand_Down (was Stand_Left).
- Check: `anim: a bare single stands Down (PrevAnimState default)`,
  `gameinfo: Woody stands Down after the pose (PrevAnimState)`.

## D10 (LOW) — OnInventoryAdded auto-scroll — CONFIRMED-FIXED
- C#: HUD.cs:898-914 + InventoryManager.cs:15-23, 47-58 (Removed fires BEFORE
  the RemoveAt — the clamp reads the pre-removal count).
- Port after: `InventoryState.on_added/on_removed` hooks (called per added
  item / before the deletion), `Hud.on_inventory_added/on_inventory_removed/
  _check_displayed_begin` (~808-829); the draw-time clamp is gone (it papered
  over the missing hooks and hid the original's one-empty-slot quirk).
- Check: `hud: OnInventoryAdded pages to the newest item`.

## D11 (LOW) — FinishGame cleanup partial — CONFIRMED-FIXED
- C#: `FinishGame` cs:358-371: `Rottweiler.SetHoldCake(false)`, `Woody.Freeze`,
  `InputLocked`, `HUD.ShowDescription = false`, GameEnding, camera snap +
  freeze, `CalculateScore`.
- Port after: `World._finish_game` (~7243) does all of it and is shared by
  `_catch`, `_win`, `finish_game_on_hud_click` (and so `_time_up`); the score
  is now computed at FinishGame time (was `_finish_animation_ended`).
- Covered by the D1/D2 checks (score/rating available at ending).

## D12 (LOW) + B (HIGH) — the finish deferral — CONFIRMED-FIXED
- C#: `Woody.PlayFinishAnimation` Woody.cs:1104-1128: `IsPassingDoor()` →
  `ShouldPlayFinish = true` (replayed at `OnDoorEnterAnimationFinished`
  Woody.cs:490-493); `Hiding` → `ShouldPlayFinish = true; Unhide()` (replayed
  at `OnBlockingAnimationEnded` Woody.cs:331-334 when the leave single ends —
  every HideItem's LeaveAnimation is Blocking in the data); else
  `IsPlayingFinish = true` and the pose, whose blocking end is
  `FinishAnimationEnded` (Woody.cs:325-327). `ShouldPlayFinish` is never
  cleared in the original (harmless: `IsPlayingFinish` wins afterwards).
- Port after: `World.should_play_finish / is_playing_finish` (World attrs, the
  Woody fields), `_play_finish_animation` (~7339) with both deferral arms (the
  hiding one rides `w.anim.on_end` after `unhide()`), and — the third arm —
  `Pawn._enter_played` (~1180-1197, tiny edit) runs the exit-door
  `finish_game_on_hud_click` AFTER `play_looping(ExitAnimation)` and
  `_next_step` (Pawn.cs:1652-1665) and then the deferred replay (Woody.cs:490).
  Its old `not game.ending` guard is gone: the original re-runs
  FinishGameOnHUDClick at an exit-door arrival even during the wait.
  `play_looping` clearing `on_end` can no longer clobber the finish (nothing
  loops on Woody after FinishGame: frozen + paused; the alerter flinch's
  `!Frozen` gate is the pawn agent's #9 and reads the `frozen` this sets).
- Numbers: Level101 forcewin mid-pass — WinGame frames all `hidden=False,
  is_warping=False`, ended afterwards; hiding: `Hide_Out → WinGame → ended`.
- Check: `finish: deferred through the door pass, played visible`, `finish:
  hiding -> Hide_Out first, then the win pose`.

## D13 (LOW) — zone graph rebuilt on unlock — CONFIRMED-FIXED (no shipped effect)
- C#: `ZoneController.Start` cs:8-28 builds `Zone.Neighbors` once from
  `(!Locked || TemporalLock)`; `Zone.AddNeighbor` has no other caller;
  `Door.Unlock` Door.cs:198-207 never touches it.
- Port after: `unlock_door` (~5509) no longer calls `level._build_graph()`.
  Data: the playable levels' only `DoorsToUnlock` (L201 ×3 → TransitionDownwards)
  target a door that ships `Locked=false` (Unlock is a no-op both sides);
  TemporalLock doors exist only in the three Intro scenes (unported tutorial
  layer) — the port's `_build_graph` has no TemporalLock term (`temporal_lock`
  is not exported); noted, Intro-only.
- Check: `zones: Door.Unlock adds no path edge (ZoneController.Start)`.

## D14 (LOW) — the CurrentAction gate — CONFIRMED-FIXED
- C#: both predicates require `ActionManager.CurrentAction != null`
  (GameInfo.cs:183, 187, 196); `ActiveAction` is first assigned by
  `StartAction` after DelayStart (ActionManager.cs:103-110, 146-171) and never
  nulled.
- Port after: `can_rottweiler_see_woody` / `can_mother_see_woody` return False
  while `routine.delay_start > 0` or the routine has no actions.
- Check: `gameinfo: detection needs CurrentAction (DelayStart)`.

## D15 (LOW) — angry-meter 0.1 s throttle — CONFIRMED-FIXED
- C#: HUD.cs:1240-1248 recomputes the fill rect / UV only when
  `Time.time - LastUpdateAngryMeterTime > 0.1`.
- Port after: `_draw_angry_meter` caches `_angry_rects` and `_last_angry_update`
  (world.time). Check: `hud: DrawAngryMeter recomputes at most every 0.1 s`.

## D16 (LOW) — stale tooltip over the ending — CONFIRMED-FIXED
- C#: `DrawHUD` HUD.cs:646-649 clears the unlatched line after each draw; with
  GameEnding `UpdateHover` writes nothing (MouseCursor.cs:120-124).
- Port after: `Hud.draw` (~769) empties the unlatched line when no SetTooltip
  pass ran that frame (`_hover_updated`), before drawing — the recorder still
  logs the drawn line. Check: `hud: the unlatched tooltip clears once GameEnding`.

## D17 (LOW) — cursor/hover read `used` — CONFIRMED-FIXED
- C#: `UpdateMouseOver` MouseCursor.cs:189-198 and `UpdateCursor` cs:362-373
  read `CurrentInventory` only.
- Port after: `update_hover` `held = inv.current`, `update_cursor`
  `inv.current is not None`. Check: `hud: after the promotion the cursor reads
  Current only`, `hud: the icon stage shows the use-inventory cursor`.

## D18 (LOW) — hover-bubble details — CONFIRMED-FIXED
- C#: HUD.cs:962-967 (an unselected icon under the cursor with nothing selected
  → "Use X with nothing"), cs:991 (the 1 s bubble needs a non-empty
  DescriptionString — no name fallback).
- Port after: `_draw_inventory`. Check: `hud: an unselected icon under the
  cursor speaks "with nothing"`.

## D19 (LOW) — Invoke slot vs closures — CONFIRMED-DOCUMENTED
- C#: GameInfo.cs:513-533 stores the target in the single `ObjectToPrime` /
  `ObjectToHide` field; two overlapping delayed invokes both act on the last
  stored item. Port: `call_later` closures capture their own item
  (RoutineActionUse arms, Routine.* — pawn agent's area). No data has two
  overlapping delayed primes/hides; latent. Not changed here.

## D20 (LOW) — forcewin ≠ ForceWinGame — CONFIRMED-FIXED
- C#: `ForceWinGame` cs:315-321 (`Completed = Total; FinalTrickScore = 100;
  Won; WinImmediate`), consumed at Update cs:228-235 (no coroutine).
- Port after: `GameState.force_win()` (+ `win_immediate`, `final_trick_score`
  accumulated by `trick_done` and used by `calculate_score`); record.py's
  `forcewin` calls it. Check: `gameinfo: ForceWinGame plays the win at once,
  rating 100`.

## D21 (LOW) — the ShouldStopAction stale latch — CONFIRMED-DOCUMENTED
- C#: `PlayLoopingAnimation` cs:344-348 nulls the sequence but leaves
  `ShouldStopAction` (set at the last element's pull, cs:289-292) latched; the
  next bare single's end runs `ActionManager.StopCurrentAction(true)` on
  whatever action is current then (cs:234-247). Port: `play_looping` clears
  `on_end`, so the stale stop cannot fire. Reproducing it needs Routine.* to
  accept a stop in any state (a `_finish` on a MOVING/next action) — the port's
  `on_end` also carries the delegate-style callbacks the latch must not touch.
  Left as a documented, "saner" divergence in the interrupt-during-last-element
  window (numbers: only pawn controllers with an ActionManager; only when a
  use sequence's LAST element is cut by a PlayLoopingAnimation and a bare
  single later ends).

## X1 (extra, HIGH) — the game-end freezes were ActionManager.Freeze — FIXED
- C#: `Rottweiler.Freeze` / `Mother.Freeze` (Rottweiler.cs:1095-1099,
  Mother.cs:136-140) = `SwitchToStandAnimation(); PauseMovement()` — the pawn's
  own freeze; `ActionManager.Freeze` (cs:792-795) is HitWoody's, not the
  endings'. `PlayWinAnimations` cs:308-311 freezes the neighbour only;
  `FinishGameOnHUDClick` cs:377-381 him and the Mother; `FinishAnimationEnded`
  cs:347-355 all three.
- Port before: `r.frozen = True` (the routine) — the neighbour kept walking his
  steps and finished his use element under the win pose. After:
  `_freeze_pawn` (~7277: stand switch by the D9 rule + `movement_paused`),
  `_freeze_woody` (~7263: `frozen`, `movement_paused`, the path dropped unless
  mid-pass — documented: the original keeps the path and resumes it through
  SwitchToStandAnimation's ContinueMovement, PawnAnimationController.cs:97).
  Numbers: forcewin while the neighbour sits (SitDown, a Single) → Stand_Down
  at once (was: SitLoop/SitRemote/SitUp for 8 more seconds).

## X2 (extra, HIGH) — every pawn animation ran at twice its FrameRate — FIXED
- C#: one `Refresh` per controller per frame (OnGUI Repaint,
  AnimationControllerBase.cs:172-189, 102-142).
- Port before (since commit 2b16218): the pawn's `AnimPlayer` is in
  `World.players` AND `Pawn.tick` advances `self.anim` — two `tick(dt)` per
  frame. Measured: Woody's Hello (frames 15-22, 10 fps) stepped every 0.05 s,
  0.42 s total; WinGame (23 frames) 1.12 s. After: `World.tick` (~7506) skips
  the pawn players in the item pass — Hello steps every 0.10 s, WinGame 2.3 s.
- Consequences the README got backwards: "the dog wakes at ~50% of the L109 bar
  in the original too" — the original's `Refresh` runs `ResetAnimationTime`
  AFTER `StopSingleAnimation` switched to the next element (cs:137-141), so a
  2-frame 2 fps element lasts a full 1.0 s (only a sequence's very first
  element shows frame 0 for one dt); 29 BedSleep elements ≈ 29.0 s against
  the bar's Duration 29.3 → the bar reaches ~0.99 and the neighbour wakes on
  the last element (index 31 leaves the [2,31) window). The port now matches;
  the moment `sleep bar: the dog wakes early (<80%)` asserts the old 2× bug.
- Check: `anim: a pawn animation steps at its FrameRate (one tick)`.

## X3 (coordinator) — UsePattern with an empty Pattern — FIXED
- C#: AnimationInstance.cs:66-76, 186-234: `ReachedEndFrame` = `0 >= 0` at
  once, `UpdateCurrentFrame` writes nothing → `CurrentFrame` stays the instance
  default 0. 36 instances (14 × Woody's PutEel with a GUID-stub PatternFile the
  build never shipped, 21 × Olga's `OlgaStand{Down,Right}Infinite`, L101
  SitSurprise).
- Port after: `scene.Anim.empty_pattern`; `AnimPlayer._set_start / _loop_to_start`
  (frame 0), `_reached_end` (True), `_advance` (index only), `current_index`
  (the pattern index), the hold branch (`!UsePattern` only). A single ends on
  its first step, a loop holds sheet frame 0.
- Check: `anim: an empty-pattern single ends on its first step`, `anim: an
  empty-pattern loop holds sheet frame 0`.

## X6 (coordinator, HIGH) — the pattern frame clamped to EndFrame — FIXED
- C#: `AnimationInstance.UpdateCurrentFrame` cs:228-234 sets `CurrentFrame =
  Pattern[CurrentFrameIndex]` with no clamp, and leaves the last entry standing
  past the end; a range animation steps `CurrentFrame` one past EndFrame
  (cs:206-215) and `Refresh` (AnimationControllerBase.cs:102-142) settles the
  end — loop / next element / hold / stand — in the same call, so that frame
  is drawn only when nothing switches, and then the original draws it too
  (DrawAnimation cs:153-170: no clamp either).
- Port before: `AnimPlayer._advance` ended with `sprite.cur_frame = min(frame,
  a.end)` — 4557 of the 6260 pattern animations serialize EndFrame below their
  entries (L209 FireFakir's 127-entry idle with EndFrame 0 sat on sheet frame
  0; L101's neighbour `ShitNormal` 4..10 / EndFrame 0; `SlipLeft` 8..12 /
  EndFrame 7). After: `cur_frame = self.frame` (~200); the range clamp is
  gone too (the port, like the original, handles the end in the same tick;
  the delegate-handled no-switch corner then shows the same overrun frame).
- Check: `anim: a pattern animation draws Pattern[index], not <= EndFrame`
  (FireFakir animates: 15 distinct frames in 3 s, max > EndFrame 0).

## X4 (extra, LOW) — the bare-zone hover arm — FIXED
- C#: MouseCursor.cs:333-347: Woody's OWN zone → GoTo (empty), another exit
  zone → End, another zone → GoTo. Port spoke End in the own exit zone; now exact.

## X5 (extra, LOW) — OnIconPressed polled per frame — FIXED
- C#: `DrawInventory` HUD.cs:942-960 polls the Current item's `OnIconPressed`
  every frame (a phone raises the alarm and deselects); `CheckClick` cs:1311-1316
  selects unconditionally; `Item.OnIconPressed` cs:2178 is gated
  `!IsPassingDoor() && !DonePassingToOtherZone`. Port: the poll moved from
  click time to `_draw_inventory`; `icon_pressed` gained the DonePassing term.

---

## Same-class sweep
- `won` writes: `_catch` (=false, cs:325/335), `trick_done` (cs:479),
  `force_win` (cs:319); the HUD's redundant `won = True` in the complete arm
  removed (C# relies on TrickDone).
- `ending` writes: `_finish_game` and the win-wait arm only; `ended`:
  `_finish_animation_ended` only.
- `used` writes: `check_click` (every non-icon click), the path end (pawn
  agent), the ShouldAbortMove miss, `remove`.
- Every `_stand_name` caller (AnimPlayer hook, `_stand`, `_next_step`, the
  transition wait, the item refusals) now resolves by the C# type rule.
- `hud.tooltip` is written only through `set_tooltip` and the per-frame clear.
- The two `game.ending` gates deliberately left (`door_exit_catch`, the
  stored-click replays) are listed under flags.

## README additions

- **Detection, catching, the two endings** — replace the win/lose paragraph:
  `GameInfo.Update` runs in the original's order — the neighbour's catch, the
  Mother's, the all-tricks win, then the clock — behind `!GameEnded &&
  !GameEnding` (GameInfo.cs:212). The moment `CompletedTricksCount >=
  TotalTricksCount` is seen, `GameEnding` is set and the 2.5 s
  `WinGameAnimations` coroutine starts (cs:292-302): the clock stops, no catch
  can fire, the HUD answers only the power button and the cursor sits on the
  default arms — but Woody's own clicks stay live (`CheckMouseClick` gates on
  `Woody.Frozen`, Woody.cs:637), so he can walk and even use an item during
  the wait. `PlayWinAnimations` then runs `FinishGame` (cs:358-371: the
  neighbour drops the cake, `Woody.Freeze` + `InputLocked`, the description
  bubble closes, the camera snaps and freezes, `CalculateScore`), Woody's
  `WinAnimation`, `Rottweiler.Freeze` — the pawn's own freeze:
  `SwitchToStandAnimation` + `PauseMovement` (Rottweiler.cs:1095-1099), not the
  routine's — and `PlaySuccess(perfect: true)`. `GameEnded` (the score board)
  comes only from `FinishAnimationEnded` (cs:343-356) at the end of the pose:
  the sleep bars are disabled (`DisableAllProgressBars` → `SetSleeping(false)`
  + `enabled = false`, ProgressBar.cs:303-307) and Woody, the neighbour and
  the Mother freeze. The clock running out is `TimeUp = true` +
  `FinishGameOnHUDClick` (cs:241-249, 373-390) — `Won` is untouched: a player
  past `WinningTricksCount` still gets the success jingle and the
  EXCELLENT/GOOD/PASSED band; TIME UP is the `!Won` band (cs:438-465).
  `Woody.PlayFinishAnimation` (Woody.cs:1104-1128) defers mid-door-pass until
  the arrival (Woody.cs:490-493) and, hiding, leaves the spot first and rides
  the leave animation's blocking end (Woody.cs:331-334); an exit-door pass
  finishes AFTER the ExitAnimation loop (Pawn.cs:1652-1665). `ForceWinGame`
  (`forcewin` in the recorder) is the tutorial's immediate win: all tricks,
  `FinalTrickScore = 100`, `WinImmediate` (cs:315-321).
- **The HUD** — the tooltip line: every write is `SetTooltip` (HUD.cs:1024-1060,
  latch-gated, GoTo renders empty), and `DrawHUD` clears an unlatched line
  after every draw (cs:646-649). Every non-icon click runs
  `SetUsedInventory(CurrentInventory)` unconditionally (cs:1320, Woody.cs:1062-
  1073) — the used inventory lives for exactly one click — then `UpdateTooltip`
  latches the current arm in yellow unless it is GoTo, dropped again when
  nothing (Item or Door) sits under the cursor (cs:1321-1327). Only
  `CurrentInventory` draws pressed and drives the use-inventory cursor
  (MouseCursor.cs:362-373); its line is "Use X with <hovered item's name>"
  (cs:942-955); an unselected icon under the cursor speaks "Use X with nothing"
  (cs:962-967); the 1 s bubble needs a DescriptionString (cs:991).
  `OnInventoryAdded` pages to the newest item, `OnInventoryRemoved` clamps
  with the pre-removal count (cs:898-914, InventoryManager.cs:20, 53). The
  angry meter repaints at 10 Hz (cs:1240-1248). The recorder's `inv N` and the
  viewer's digit keys stage `CurrentInventory` (the icon click); the next
  world click promotes it.
- **The sleep bars** — correct the duration paragraph: `Refresh` runs
  `ResetAnimationTime` after `StopSingleAnimation` has switched to the next
  element (AnimationControllerBase.cs:137-141), so every element after the
  first lasts frames/FrameRate — the bed's 2-frame 2 fps `BedSleep` a full
  1.0 s, 29 of them ≈ 29.0 s against Duration 29.3: the bar fills to ~99% and
  the neighbour wakes on the last element (its post-increment stamp 31 leaves
  the [2,31) window). The old "~50%" came from the port ticking every pawn
  controller twice per frame (fixed).
- **Divergences / animation model** — `PrevAnimState` is never written in
  the original (PawnAnimationController.cs:165-172 sits behind a
  `Type == Looping` test the strict Single lookup cannot pass), so
  `SwitchToStandAnimation` after any bare single (idles, NoNo, Hello, the
  win/lose pose) plays `StandDownAnimation`; a Looping current resolves by its
  own name (Walk/Stand/Run/RunWC families, WaitWatch, WaitInFear), and the
  original throws "Stand with nothing before" on other loops (pie/fifi/ski/
  bowling walks) — the port keeps the last facing's stand there. UsePattern
  with an empty Pattern (36 instances: PutEel, Olga's stand-infinite poses,
  L101 SitSurprise) ends a single on its first step and holds sheet frame 0
  when looping (AnimationInstance.cs:66-76, 186-234); a pattern animation
  draws `Pattern[index]` unclamped — 4557 of 6260 pattern animations ship an
  EndFrame below their entries (L209 FireFakir's idle: 127 entries, EndFrame
  0), which the port used to clamp to (cs:228-234). Every pawn controller
  now refreshes once per frame (it was ticked twice — 2× speed on all pawn
  animations, AnimationControllerBase.cs:172-189). Detection needs
  `ActionManager.CurrentAction` (GameInfo.cs:183-196): none during the 1.5 s
  DelayStart. `Door.Unlock` never changes the zone graph (ZoneController.cs:
  8-28 builds it once; the playable levels' DoorsToUnlock hit an unlocked
  door anyway).
- **Not reproduced (documented)**: `AnimationControllerBase.Hidden` freezing
  `Refresh` (cs:172-189) — waits for the item-driven action end of Olga's
  hidden uses (TrickItem.cs:964-975, Olga.cs:154-158); the ShouldStopAction
  stale latch (cs:344-348); the Invoke slot overwrite (GameInfo.cs:513-533);
  the frozen Woody's path resuming after the finish pose
  (PawnAnimationController.cs:97); a door-exit catch or a stored-click replay
  inside the 2.5 s wait (Pawn.cs:366-378 has no GameEnding gate) — the
  original then plays two endings over each other.

## Coordinator flags
1. **X2 re-based the sleep-bar moment** (already done in
   `tests/run_moments.py`: fills > 0.95, 29 × 1.0 s window): the L109 bar
   fills to ~0.99–1.0 (29 × 1.0 s vs Duration 29.3) and the dog wakes on the
   last element (AnimationControllerBase.cs:137-141). The README's "wakes at
   ~50%… in the original too" paragraph needs the correction above.
2. **X2 is a global timing change** (all pawn animations now at their real
   FrameRate): the trick harness plans/timeouts (`tests/run_tricks.py
   LEG_TIMEOUT`, per-level plans) and any timing thresholds in other agents'
   checks may need re-tuning; the moment suite otherwise passes.
3. **`tests/monkey.py` `stuck-colored-tooltip`** ("ColoredTooltip latched with
   no held inventory", >1 s) encodes the old latch model; under HUD.cs:1062-
   1075 (D7) a bare tap on an item latches until `Woody.ClearTooltip`
   (OnPathFinished / the use tail / a refusal) — legit for the length of a
   walk. Suggest: latch allowed while Woody moves or a stored click waits.
4. **D8 (Hidden freezes Refresh)** needs the pawn agent's port of the
   item-driven action end (`Olga.OnItemAnimationSequenceEnded`,
   TrickItem.cs:972) first — Level205/210 `OlgaMatBeach`; then a one-line
   gate in `AnimPlayer.tick` (`if self.sprite.hidden: return`) plus the
   `reveal_on_play` case. The Level205 / Level101 guards are in my module.
5. Files touched outside my area (all tiny, all cited): `Pawn._enter_played`
   (the exit-door finish order + the deferred replay), `Pawn._stand_name`
   (allowed), `World.woody_use` (frozen gate), `World.unlock_door`,
   `World.icon_pressed`, `World.tick`'s player pass (X2), `runtime/viewer.py:261`
   (frozen gate), `runtime/record.py forcewin`, `runtime/scene.py` (Door
   `with_string`, Anim `empty_pattern`), `tests/run_tricks.py leg_prime`
   (`used or current`).
6. Pre-existing heuristic seen while testing (not mine): `World.tick`'s
   entrance `elif` (~7456) unlocks `woody.input_locked` on ANY idle frame with
   no steps — it also defeats FinishGame's `InputLocked = true` (unobservable
   after `frozen`, but `BlockWhenItemPick`'s lock during a pick may be
   affected). Pawn agent's call.
7. `door_exit_catch` and the stored-click replays keep their `game.ending`
   gates (see D2) — the original's double-ending corner is not reproduced.
