# Verified: routine (ActionManager / Rottweiler urgents, alarms, angry, fixes)

Source draft: `docs/audit/raw/pass1_rott_actionmgr.md` (D1–D16 + the per-field
tables). Port area: `runtime/world.py` class `Routine`, `World.play_angry` /
`_start_wait_in_fear` / `continue_angry_animation` / `_try_fix` / `_fix` and
the fix behaviors, `World._raise_alarm`; the routine/pawn spec readers in
`runtime/scene.py` (`_find_routines`, `_find_pawns`).

**Counts**: claims received 16 (+6 extras from the tables/traces and the
plan agents) · CONFIRMED-FIXED 17 (D1, D2, D3, D4, D5, D6, D7, D8, D9,
D10, D11, D15, D16, extras: L102 `ToiletAction.ContinueToNextAfterFinished`,
the interrupted-urgent replay, the abort's OnActionStopped, the Dog/Chili
SameZone re-check, UpdateWalking during urgents + the template use's
GetTrickedItem) · CONFIRMED-DOCUMENTED 3 (D13, D14, extra: parked-run edge
cases) · REFUTED 1 (D12) · already-documented 0.

Check module: `tests/checks/routine.py` (26 checks, all in-process over a
headless `World` — no SDL — each poking the exact state the original's
method reads; every check targets a line changed by its fix and would fail on
the pre-fix code by construction: the old predicate/branch/attribute did not
exist or returned the other value. The pre-fix working tree no longer exists
as a file — other agents edit the same files concurrently, and HEAD predates
the S2 ladder — so "fails on the old code" is stated by construction, not by
an executed baseline).

Validation: `python3 -c "import ast..." runtime/*.py` OK;
`SDL_VIDEODRIVER=offscreen python3 tests/run_moments.py /tmp/rt-moments` —
all `routine:` checks (mine, `tests/checks/routine.py`) ok; the suite's two
remaining failures are other agents' checks whose scenarios assume the
pre-fix hidden-controller behavior (see Coordinator flags 6). Single-level monkeys
(seed 1/2, 90 s) on L102/103/105/107/110/111/113/114 run clean of routine
exceptions (their one finding is the HUD's `stuck-colored-tooltip`, not
mine); the S2 monkeys crash in Woody's sneak walk (see Coordinator flags).

---

## Claims

### D1 — `Rottweiler.TrickedAux` never cleared — CONFIRMED, FIXED
- C#: set `Rottweiler.cs:652` (NFH2 branch, both halves of a linked pair
  already scored); cleared as the **first statement of `Item.Fix()`,
  `Item.cs:2065`** (`GameInfo.Instance.Rottweiler.TrickedAux = false`); read
  `cs:655-658` (the only meter-accumulation arm for a plain trick).
- Port before: set at `play_angry` (now world.py:4670), read 4672, never
  cleared; comment at world.py:300 said "never reset".
- Port after: `World._fix` opens with `rott.tricked_aux = False`
  (world.py:4943-4946); the field comment (world.py:300-301) cites cs:652 /
  Item.cs:2065. S2 consequence: after a re-angry on a fully scored pair the
  next fixed trick lets the meter accumulate again (before: frozen for the
  level → no Level2/3, no freakout/statue).
- Check: `routine: TrickedAux set by the scored pair` /
  `TrickedAux cleared by Item.Fix` (L206 LaunchPad+Harpoon).

### D2 — `kind == 'TrickItem'` misses the subclasses — CONFIRMED, FIXED
- C#: `RoutineActionUse.StopAction` — `TrickItem trickItem = Item as
  TrickItem` (`RoutineActionUse.cs:419`) and the angry gate `trickItem !=
  null && trickItem.IsTricked()` (`cs:546-549`); `Drawing : TrickItem`
  (Drawing.cs:3), `Rake : TrickItem` (Rake.cs:1), `Toilet`/`Television` too.
  `Item.kind` in the port is the concrete component type
  (`scene.py:_add_item`, `o['type']`) — hence `TRICK_KINDS`.
- Port before: `_finish` `if it.kind == 'TrickItem' and it.is_tricked(...)`.
- Port after: `if it.kind in TRICK_KINDS and it.is_tricked(...)`
  (world.py:3007-3009). Live: L107 action 0 (Drawing), L202 action 2 (Rake)
  — the tricked use now ends in `PlayAngryAnimation` → score, `TryFix`
  (`Drawing.Fix` → `SkipAction`).
- Check: `routine: tricked Drawing goes angry` (L107, `_finish` with the
  Drawing tricked → `play_angry('Drawing')`).
- Same-class sweep of every `kind` test in world.py: 1656, 2256, 2265,
  2546, 2678, 2826, 2957, 2987, 3125, 3176, 3930, 3939, 4066, 4128, 4143,
  4154, 4794, 5129, 5134, 5143, 5192, 5523, 5535, 5761, 5803 use
  `TRICK_KINDS` (= `is TrickItem`) ✓; 2120 `== 'Rake'` / 2131, 3925, 4335,
  5518, 5765 `== 'Drawing'` are the subclass-specific arms (Rake.cs,
  Drawing.cs) ✓; 2864/2972/3879 `== 'Alerter'`, 5119/5123/5681/5800/5822/6504
  `== 'SearchItem'`, 5812 `== 'HideItem'` are leaf classes with no
  subclasses ✓; 5823 `item.kind in ('TrickItem','GroundItem','HideItem',
  'InspectItem') or not searching` — the `or not searching` covers the
  subclasses ✓. **One suspect outside my area**: world.py:~5499
  (`_can_woody_use`, Flowers/knife pick) `item.kind != 'TrickItem'` stands
  for `!TrickedItem` in Item.cs:1421 — that is the **bool field**
  `Item.TrickedItem` (Item.cs:524; set only for LionStatue at cs:1546,
  cleared cs:1593), not a type test; on L209 the Flowers GameObject carries
  both a TrickItem and a SearchItem component. Flagged below (item agent).

### D3 — parked alarms not released at the use stop — CONFIRMED, FIXED
- C#: `RoutineActionUse.OnActionStopped` (`cs:358-362`) runs
  `CheckSurpriseActionFar(NextAction)` + `CheckPendingAlarm(NextAction)` at
  every non-mutex Rottweiler use stop; `RoutineActionSurpriseFar.
  OnActionStopped` (`cs:66-71`) runs `CheckPendingAlarm()`; SurpriseNear's
  stop runs `ContinueAlarm` + `CheckPendingAlarm` (`cs:39-45`). OnActionStopped
  fires from inside `StartAction(next)` (`ActionManager.cs:157-160`), so the
  released run interrupts the action about to start and resumes it after.
- Port before: both parked runs merged into `pending_alarm`, released only at
  `continue_alarm`, zone change and the AlarmNextAction tick gate.
- Port after: two slots (`pending_surprise` = ShouldStartSurpriseActionFar,
  `pending_alarm` = PendingAlarm/PendingAlarmItem, world.py:1735-1740);
  `_check_surprise_far` (3580) / `_check_pending_alarm` (3589) are the two
  C# checks; `_check_parked_runs` (3036) runs both after a routine use stops
  — from `_finish`, `_angry_done`, the two no-animation stops in `_use` and
  the Duration timeout — after `_pending` is set, so `start_urgent`
  materializes the advance and the run resumes at the chosen action;
  `_release_at_urgent_stop` (3556) runs the template's checks at
  `_urgent_finished` (SurpriseFar → pending alarm; the use templates and the
  Return leg → both), evaluating IsAlarmPostponed over the stopping template
  as the original does; `_surprise_near_stopped` (3830) now chooses the
  resume first and checks after (before, `continue_alarm()` ran before
  `_urgent_finished()`, which then clobbered a just-released run).
- Check: `routine: use stop releases the parked run` (L114 Polish,
  PostponeAlarm=True: `_finish` with a parked pet → `urgent_item is pet`).
- Documented residue (see README additions): the original loses a parked
  alerter run when the next action needs no walk (`ActionManager.cs:161-170`
  stops the run's MoveAction and starts the use over it) — the port keeps it;
  the same trace shows the UseFixingItem stop's release surviving behind the
  Return leg only when the resumed action is away.

### D4 — `is_alarm_postponed` had 1 of 6 arms — CONFIRMED, FIXED
- C# `Rottweiler.IsAlarmPostponed` (`cs:1047-1070`): SurpriseNear → true;
  SurpriseFar by PostponeAlarm; a Move by `NextAction.IsAlarmPostponed()`
  (the action's own virtual: bare PostponeAlarm for a Use,
  `RoutineActionUse.cs:573-576`, and a Grab, `RoutineActionGrab.cs:26-29`;
  false otherwise, `RoutineAction.cs:163-166`); Grab by PostponeAlarm; a Use
  by `PostponeAlarm || PostponeAlarmDuringUseOnly || Item.IsTricked()`.
- Data: `PostponeAlarmDuringUseOnly` **is already in the level JSON**
  (L105's four actions) — no exporter change was needed; the reader is the
  spec key `postpone_alarm_during_use_only` (`scene.py:_find_routines`).
- Port after: `is_alarm_postponed` (world.py:3152-3179) +
  `_template_postponed` (3181) over `_urgent_action` — the running urgent
  template's `{kind, name, postpone_alarm, postpone_alarm_during_use_only}`
  set by every starter (`start_urgent`, `_on_surprise_near`,
  `run_to_hit_pawn`); the MOVING state is the interposed Move. `hear_alerter`
  (3745) reproduces cs:272's exception path: with IsAlarmPostponed true
  while the CurrentAction is the MoveAction, `ActionManager.CurrentAction.
  Item.Tricked` dereferences the MoveAction's Item, which nothing ever sets
  (`ActionManager.cs:23`, `protected ... = new RoutineActionMove()`, MoveAction
  serializes null in all 50 managers) — the coroutine
  `Alerter.CoRoutineRottweilerHearAlerter` (Alerter.cs:116-120) dies with
  the bark: neither started nor parked. `_raise_alarm` keeps its gate.
- The L110 stuck-flag chain (D4c): with the Grab arm the bark during the
  fetch is parked (grab step) or dropped (the walk, the NRE); and an urgent
  that does interrupt a chain step now stashes it (`_stash_interrupted_
  urgent`, 3284; replayed at 3503) — see the extra below — so `_fix_tool`
  can no longer stick. `_can_check_surprise_far` (3979) is now the exact
  `IsFixingBlockingItem` (Grab/UseFixing with PostponeAlarm, or the walk
  toward one; the Return leg does not block).
- Checks: `routine: PostponeAlarmDuringUseOnly arm` (L105), `the walk toward
  a PostponeAlarm use` (L114 MOVING), `Item.IsTricked() arm` (L101 Sofa),
  `L110 Grab.PostponeAlarm arm` (L110 fetch in flight).

### D5 — `LoopFromSelectedIndex` conflated with the index — CONFIRMED, FIXED
- C# `AdvanceActionIndex` (`ActionManager.cs:566-584`): wrap → start index
  if LoopFromStartIndex, else selected index **only if LoopFromSelectedIndex**,
  else 0. Data: **the field is already in the level JSON**; L206 Mother
  serializes LoopFromStartIndex=false, LoopFromSelectedIndex=false,
  ActionSelectedIndex=3 → the original wraps to 0; L206 Rottweiler (Sel=4,
  LoopSel=true), L214 Olga (Sel=1, LoopSel=true), L210 Olga (Sel=0) coincide.
- Port before: `_advance` `elif self.selected_index:` (truthiness); the same
  wrap open-coded in `_on_last_seq_element`; `_stop_olga_infinite_loop`
  emulated `LoopFromSelectedIndex=false` (Item.cs:2602) as `selected_index=0`.
- Port after: spec key `loop_from_selected` (`scene.py:_find_routines`),
  `Routine.loop_from_selected` (world.py:1721), `_next_index` (1872) used by
  `_advance` and `_on_last_seq_element` (GetNextAction, cs:112-117);
  `_stop_olga_infinite_loop` sets `ort.loop_from_selected = False` (5146).
- Check: `routine: L206 Mother wraps to 0`.
- Coordinator note: no exporter change and no re-export were needed (both
  fields ship in `levels/*.json`; the port's `scene.py` reads the raw dump).

### D6 — the toilet rush walked — CONFIRMED, FIXED (+ siblings)
- C#: `RoutineActionMove.OnActionStarted` (`cs:68-75`) picks
  `MoveToGoalUrgent` (Pawn.cs:444-448, InUrgentMove=true) from
  `NextAction.Urgent`. Data: `ToiletAction.Urgent` true in all 30 scenes;
  `SurpriseActionFar.Urgent` true/30; `AlarmAction.Urgent` false/30 (the
  CabinPhone hack `Rottweiler.cs:872-875` sets it for good); **`GrabFixing-
  ItemAction`/`UseFixingItemAction.Urgent` true on L110/L113 only, false on
  L111** (its fetch walks); `ReturnFixingItemAction.Urgent` false/30 (the
  return leg walks); Olga's `HitPawnAction.Urgent` true/11, the Mother's
  false on 8 of 9 (true on L210 only) — she walks to the hit on L206/207/214.
- Port before: `start_urgent` `in_urgent = (not alarm_use) or CabinPhone`
  → toilet walked, fetch/return ran everywhere; `run_to_hit_pawn` always ran.
- Port after: `start_urgent(..., urgent=)` takes the template's flag
  (world.py:3209-3261); readers in `scene.py`: `toilet_action.urgent /
  postpone_alarm / postpone_alarm_during_use_only / continue_to_next`,
  `grab_action.urgent / force_use_original`, `use_fixing_action.urgent /
  postpone_alarm / force_use_original / return_urgent`, `hit_pawn_action.
  urgent`, and the new pawn-spec dicts `surprise_far_action` / `alarm_action`
  (read into `Pawn.surprise_far_action` / `alarm_action`, world.py:355-358);
  callers: `move_to_toilet` (3906), `move_to_alarm` (3601, sticky CabinPhone
  flag `_alarm_urgent`), `run_to_fixing_item` / `grabbed()` / `_fixing_done`
  (kinds grab / use / return with their flags), `run_to_hit_pawn` (3846).
- Checks: `routine: the toilet rush runs` (L103), `L111 fetch walks
  (Grab.Urgent=false)`, `L206 Mother walks to the hit`.

### D7 — a parked phone alarm lost `alarm_use` — CONFIRMED, FIXED
- C#: `CheckPendingAlarm` → `MoveToAlarm(PendingAlarmItem)` (`cs:236,
  869-877`) → the AlarmAction is a RoutineActionUse: arrival = `Item.Use`.
- Port after: `_check_pending_alarm` → `move_to_alarm` (world.py:3589-3610)
  → `start_urgent(alarm_use=True, kind='use', name='alarm', ...)`; every
  release site (use stop, urgent stops, zone change, AlarmNextAction gate)
  goes through it. `_raise_alarm` calls `rt.move_to_alarm` (5573).
- Check: `routine: parked phone alarm keeps alarm_use` (L105).

### D8 — `CanDecreaseAngryMeter=false` without the `!NFH2Path` gate — CONFIRMED, FIXED
- C#: `Rottweiler.cs:793-796` (`Woody != null && !Woody.NFH2Path`);
  `ActionManager.cs:588-591` (StopUrgentAction's true-write, gated too).
- Port after: the three writes in `play_angry` gate on `not nfh2`
  (world.py:4747 rush, 4775 affect, 4796 animated); the AWA rush write moved after the stop
  (the original's OnUseEnded release fires inside `StartUrgentAction(Toilet)`
  before cs:795 latches false, so the latch holds through the run);
  `_urgent_finished`'s release gates `kind == 'use' or not nfh2` (3461 —
  a use template's stop sets it through OnUseEnded, Rottweiler.cs:891).
- Check: `routine: S2 keeps CanDecreaseAngryMeter` (L206 play_angry).

### D9 — S2 compound blew the whistle — CONFIRMED, FIXED
- C#: `Rottweiler.cs:702` `Compound && CompoundTricked && !Woody.NFH2Path`.
- Port after: `if item.compound and item.compound_tricked and not nfh2:`
  (world.py:4711). Check: `routine: S2 compound skips OnCompoundTrickDone`
  (L213 PlantCarnivore).

### D10 — Duration timeout ran the full stop — CONFIRMED (latent), FIXED
- C#: `RoutineAction.Finished` (`cs:91-98`) → `AdvanceToNextAction` →
  `StartAction(next)` → only `OnActionStopped` (`ActionManager.cs:157-160`);
  no `StopAction(bool)`. Data: L110 action 1 (Beer, Duration 1.0) —
  its `TakeGround` is 4 pattern frames @ 7 fps = 0.571 s < 1.0 s, so the
  sequence's `StopAction(true)` always precedes the timeout: the branch is
  latent. `_finish` now zeroes the timer (world.py:2984) so the two paths can
  never both fire.
- Port after: the timeout runs `_action_stopped(); _pending='advance';
  _check_parked_runs()` (world.py:4053-4062). Check: `routine: Duration
  timeout skips the angry`.

### D11 — animated angry could rush to the toilet — CONFIRMED (latent), FIXED
- C#: `OnAnimationSequenceEnded` runs `FixTrickedItem()` (`cs:460`, nulls
  `TrickedItem`) before the `IsPlayingAngryAnimation` arm's
  `CheckRushToToilet()` (`cs:478-484`, needs `TrickedItem != null`, cs:544)
  — dead; the live rush is the AngryWithoutAnimations branch (`cs:719-721`).
  Data: every RushToToilet carrier ships AngryWithoutAnimations=true; the
  only `DependsOn.RushToToilet` carrier without it is L102's Sofa (dep Beer),
  and no code path reaches `PlayAngryAnimation(Sofa)` (GetTrickedItem
  returns the Beer, `ForceFixOriginal=false`; the Sofa is no notice item).
- Port after: `after_run` no longer rushes (world.py:4717-4728); the AWA
  branch is in source order (CheckRushToToilet, TryFix, stop, FixDirectly,
  OnTrickDone, latch — cs:721-796; `FixDirectly` was missing there, inert:
  no item ships both flags), a fetch from TryFix owns the resume.
- Check: `routine: animated angry does not rush` (L102 Sofa via the tricked
  Beer, 20 s of ticks: no `_toilet_run`, Sofa fixed).

### D12 — `DelayToiletBehavior211` consumer missing — REFUTED (dead code)
- `RoutineActionHitPawn.OnActionStarted` (`cs:23`) gates the branch on
  `GameInfo.Instance.Olga == Target`; `Target` is set only by
  `Pawn.RunToHitPawn(p)` (`Pawn.cs:1837-1841`), whose only callers are
  `Rottweiler.PlayAngryAnimation` `cs:741` and `cs:752` passing `this` — the
  Rottweiler. So `Olga == Target` never holds: `InvokeWCBehavior211` /
  `Olga.targetPawn` / `WCBehavior211` (Olga.cs:160-169) and the
  `Actions[0].Item.SetObjectHidden(false)` reveal are unreachable in the
  shipped build; the live arm is the `else` (`Target.AnimController.Hidden =
  true`, cs:29-31), which `_hit_pawn_arrived` does. The port's write of
  `delay_toilet_211` (StopOlgaInfiniteLoop, ported) is as dead as the
  original's. README's "rides the unported Bouquet hack" is stale — see
  README additions.

### D13 — `MovingToHitWoody` global gate — CONFIRMED, DOCUMENTED
- `ActionManager.StartUrgentAction` (`cs:657`) returns on
  `GameInfo.Instance.Rottweiler.MovingToHitWoody` in **every** manager;
  set at `Rottweiler.HitWoody` (`cs:1092`), never cleared. The port's `_catch`
  freezes only the catcher's routine (owned by the end-game agent). Exposure:
  a bark/notice/alarm landing during the catch walk on another manager —
  input is locked, the pet's coroutine may still complete: with the numbers,
  `AlerterDelay` = 1 s (Alerter default) vs the catch walk. Fix would need a
  `World.moving_to_hit_woody` written by `_catch` and read by
  `Routine.start_urgent` / `run_to_hit_pawn` — flagged.

### D14 — `StartSurpriseActionFar` unfreezes — CONFIRMED, DOCUMENTED
- `Rottweiler.cs:1150-1154`: `ActionManager.Unfreeze(!triggeredByWoody)`
  (Frozen=false, no StartNext) then `StartUrgentAction`; the port's
  `start_urgent` returns when frozen (world.py:3231). Live freezes outside
  the end game: `FreezeAfterCompletion` on Intro103 action 0 and L201 action
  5 (tutorial flows, unported), and the port's own `frozen` doubling as the
  MovingToHitWoody stand-in during the catch — unfreezing there would break
  the catch, so D13 must land first. The `animal_tutorial` arm unfreezes
  explicitly (3773). Not fixed.

### D15 — `hear_alerter` missed `PortalMove` — CONFIRMED, FIXED
- C#: `Rottweiler.cs:272` `!IsPassingDoor() && !PortalMove`; PortalMove
  spans the portal step from `Pawn.cs:1369-1371` (climb) through the pass to
  `EndPortalMove` (`cs:1488-1493`, `1659`).
- Port after: `_passing_or_portal` (world.py:3200-3207): `is_warping` or the
  pawn state in `DOOR_CLIMB / DOOR_ANIM / DESCEND`. Check: `routine: bark
  mid-climb parks` (L114, pawn state DOOR_CLIMB → `pending_surprise`).

### D16 — `Olga.OnItemAnimationSequenceEnded` not wired — CONFIRMED, FIXED (follow-up)
- C#: `TrickItem.PlayOlgaAnimation` (`cs:964-975`) plays the item's own
  sequence first — `PlayUseAnimation(olga.OnItemAnimationSequenceEnded)`
  (`cs:972`, wired only for `PlayUseNormalSequence`, cs:988:
  `AnimController.PlayAnimationSequence(UseNormalSequence, delegate)` =
  the controller's `AlternateOnSequenceEnded`, AnimationControllerBase.cs:
  312-316, consumed at cs:243) — then her own set (`base.PlayOlgaAnimation`,
  Item.cs:1144-1167). `Olga.OnItemAnimationSequenceEnded` (Olga.cs:154-158):
  `ActionManager.CurrentAction.StopAction(canPostponeStop: true)`.
- Why it is the release and not a curiosity: **`AnimationControllerBase.
  OnGUI` runs `Refresh` — the whole time/frame step — only for a controller
  that is not `Hidden`** (`cs:177`: `!Hidden && Event.current.type ==
  Repaint`). Olga's mat action carries `HideOwnerDuringUse` (RoutineActionUse.
  cs:213-216 → `Pawn.SetHidden` → `AnimController.Hidden`, Pawn.cs:1464-
  1467), so her own `HitPawn` (42 frames @ 10 fps) never advances while she
  lies on the mat: her use can only end through the item's sequence. Data:
  the only non-mutex `HideOwnerDuringUse` actions in both seasons are Olga's
  OlgaMatBeach on L205 and L210 — exactly the two `PlayUseNormalSequence`
  carriers. On L205 the mat's `N2TrickItemUseNormal` is InfiniteLoop (91 @
  8 fps) and the neighbour's mat mutex action carries
  `ItemToStopInfiniteAnimation = OlgaMatBeach` (SetIgnoreInfiniteLoop at his
  arrival, RoutineActionUse.cs:152-155; reset at his stop, cs:326-329): she
  stays on the mat until he comes to watch, the loop drains, Extra3/Extra2
  play (4.4 + 1 s), the delegate stops her use, and her OnActionStopped's
  `PawnToAbortMutexOnFinish` springs him — the second half of the handshake.
- Port before: `play_use_item_anim` took no callback; hidden pawns kept
  animating, so her 4.2 s HitPawn ended the use, `TrickItem.OnUseEnded`'s
  ReturnToIdle interrupted the mat's sequence, and from lap 2 on the
  neighbour parked on the mat (WaitWatch) with Olga parked on the tennis
  table (EatChinese) — dead-lock at t≈102-129 s (the plans_s2a trace).
- Port after: `AnimPlayer.tick` returns while `sprite.hidden` (world.py:
  255-266, the OnGUI gate); `World.play_use_item_anim(item, on_end=)`
  (5302-5317); Olga's non-tricked item play passes
  `Routine._olga_item_seq_ended` (2568-2577), which does `CurrentAction.
  StopAction(true)` on whatever runs: her use → `_finish()`; a walk → no-op
  (the Move's base `Finished` restarts it at the next Update, ActionManager.
  cs:449-457); her HitPawn urgent → `_hit_pawn_done()` (base `Finished` →
  StopUrgentAction resumes the use). `_action_stopped` now skips the
  non-mutex block for a MutexAction (cs:342 gate) and `_abort_parked_mutex`
  runs the aborted action's OnActionStopped (see Extra C).
- Verified headless (Woody parked out of the way): L205 400 s → the
  neighbour wraps 3 times, Olga 4 (before: both parked from 102 s); her mat
  use spans his whole lap (29.6 → 126.9 s, hidden), the mat loops with
  `ignore_infinite` False between his visits and drains 11.4 + 4.4 + 1 s
  after he parks; L210 300 s: Rottweiler 2 / Olga 8 / Mother 3 laps.
- Checks: `routine: hidden Olga does not animate` (her frame/accumulator
  frozen for 2 s on the mat), `routine: L205 handshake cycles (>=3 laps/400s)`.

### Extra C — `AbortActiveMutex` runs the aborted action's OnActionStopped — CONFIRMED, FIXED
- C#: `RoutineActionUse.AbortActiveMutex` (`cs:127-134`) sets `Finished` and
  calls `AdvanceToNextAction` → `StartNextAction` → `StartAction(next)`,
  which stops the still-`Active` mutex action first (ActionManager.cs:157-
  160 → `RoutineAction.StopAction`, cs:116-120) — so `OnActionStopped`
  DOES fire: the ignore-loop resets of cs:326-341 (`ItemToStopInfinite-
  Animation` → `SetIgnoreInfiniteLoop(false)`), while the cs:342 non-mutex
  block (OnUseEnded, the abort branch, the alarm checks) is skipped. The
  README's "finishes the parked action *without* OnActionStopped — flags set
  at its start deliberately leak" is wrong: Level205's mat gets its
  InfiniteLoop back the moment the neighbour is sprung, and it drains only
  on his next visit.
- Port before: `_abort_parked_mutex` set `_pending='advance'` only — the
  mat's `ignore_infinite` stayed True for the level; `_action_stopped` ran
  the OnUseEnded block for mutex actions too.
- Port after: world.py:3173-3195 / 3154-3156. Covered by the L205 lap check.

### Extra A — `ToiletAction.ContinueToNextAfterFinished` (L102) — CONFIRMED, FIXED
- Data: L102's ToiletAction serializes it true (the only one). C#
  `AdvanceToNextAction` (`ActionManager.cs:530-538`): an urgent with the flag
  clears `UrgentAction` and advances normally (`AdvanceActionIndex` +
  `StartNextAction`) — `StopUrgentAction` (after-toilet angry, skip arms,
  the OriginalAction replay) never runs. Port after: `_urgent_finished`
  (world.py:3463-3494) → `_pending='advance'`. Check: `routine: L102 toilet
  end advances`.

### Extra B — an urgent landing on a running urgent — CONFIRMED (D4c's stuck chain), FIXED
- C# `StartUrgentAction` (`cs:679-718`): the running action becomes the
  newcomer's `OriginalAction` and `StopUrgentAction` restarts it (`cs:647`);
  exceptions: a running SurpriseNear (cs:681-691), the chain steps handing
  over (692-710), a `ForceUseOriginalAction` carrier (711-714; data: L110's
  UseFixingItemAction, L107's SurpriseActionNear), and the same template
  restarted on itself (`action != ActiveAction`, cs:679 — a second alerter
  run, the carpet run of Rottweiler.cs:504). The port collapsed nested
  urgents onto the routine action, so an alerter run or phone alarm during
  a fetch dropped the Grab/UseFixing/Return step: `_fix_tool` stayed set
  (L110: every later zone-change release dead, the carpet never fixed), and
  a re-fetch would re-add `DeltaFixLocation` (Rottweiler.cs:1078).
- Port after: `_stash_interrupted_urgent` (world.py:3284-3317) pushes the
  interrupted template (item, arrival handler, flags, Urgent, toilet state)
  on `_urgent_stack`; `_urgent_finished` pops and replays it (3503-3521) —
  a Grab replays its GrabSequence, a UseFixing its TryUseFixingItem, the
  Return its ReturnSequence, a SurpriseFar/Alarm/Toilet its whole run (a
  stashed toilet has had its OnUseEnded, Rottweiler.cs:879-892). The FUOA
  carrier drops the chain with the tool in hand (the next visit fixes with
  it, Item.cs:854-857). Cleared on the CTN and frozen exits (no replay in
  the original either).
- Check: `routine: interrupted Grab replays after the run` (L111 fetch,
  alerter run lands, ends → the Grab is current again).

---

### Extra D — the Dog/Chili SameZone re-check on every Update — CONFIRMED (plans_s1c "PORT #1"), FIXED
- C#: `ActionManager.Update` asks `MoveAction.SameZone()` on every frame the
  urgent MoveAction is active (`cs:442-448`); `RoutineActionMove.SameZone`
  (`cs:105-128`): `NextAction.Item.Zone == Owner.Zone && !IsPassingDoor() &&
  (Dog|Chili) && IsUrgent()` latches `RottPos` and `RottweilerLastDoor =
  Owner.RottLastDoor` (Pawn.cs:1644-1647, the door he last entered) on the
  first such frame and returns true once `pos >= RottLastDoor.
  RottweilerExitLocation + RottPos` — (0,0) on every door of the eight
  Dog/Chili levels (L112's 0.2/0.3 doors serve a dead dog), i.e. on that very
  frame; then `StartAction(SurpriseActionFar)` skips the MoveToAction (cs:
  152), the surprise plays where he landed, `Finished && SameZone` walks him
  to the pet with the plain `MoveToGoal` (cs:461-469, InUrgentMove drops)
  and `RottweilerPositionToDog < 0.05` yells `SurpriseSequenceLeft` ["Angry"]
  (cs:470-480), whose end (Rottweiler.cs:485-510) starts the raw-tricked
  DirtyCarpet's urgent → `RunToFixingItem` → the glued Vacuum's tricked use
  pays its 15. `RottLastDoor` is null before the first door pass: cs:121
  throws inside Update every frame — the manager is dead (he walks to the
  pet and stands) until the next `StartUrgentAction` retargets the
  MoveAction (Level113's neighbour starts in the dog's zone).
- Port before: `start_urgent` took the SameZone shortcut only when already
  in the pet's zone at the start; a run arriving from another zone went
  through the plain arrival — no yell, no carpet run, the Vacuum's 15
  unreachable (the L111 plan's `await Vacuum 15`).
- Port after: `start_urgent` arms `_sz_watch` (item Dog/Chili and the
  template's Urgent, world.py:~3352-3360); `_same_zone_check` (~3565)
  runs from `tick` while the urgent MoveAction is active, latching
  `_sz_pos` / `_sz_door = pawn.last_exit_door` and switching to the
  SameZone choreography (`_urgent_arrived` with `_same_zone`, the MoveAction
  stopped: steps cleared, PauseMovement); a null door sets `_manager_dead`
  (`tick` and `_urgent_arrived` return; `start_urgent` revives);
  `_same_zone_walk` walks (`in_urgent = False`, Pawn.cs:428-433).
- Verified: `python3 tests/run_tricks.py tests/plans/s1/Level111.txt` — 35
  legs, 0 failed: the alarm run lands in Zone02 (Search at the landing spot,
  the walk, `Angry` at t≈176), the carpet run, the grab, `VacuumLoop`,
  `VacuumDustExplosion`, `AngryEasyUp` → the 15 pays (t≈187).
- Checks: `routine: SameZone latches on landing, away from the dog` (L111
  from Zone06 through the walk-up door), `the yell starts the carpet run and
  the vacuum fetch`, `L113 null RottLastDoor stalls the manager`.

### Extra E — UpdateWalking runs during urgents; the template use angers at GetTrickedItem — CONFIRMED (plans_s1c "PORT #2"), FIXED
- C#: `Rottweiler.UpdateWalking` (`cs:833-849`) is `WalkOnPath`'s hook on
  every walk (Pawn.cs:981) — an urgent run included; the near surprise's
  `StartUrgentAction(SurpriseActionNear)` makes the running urgent its
  OriginalAction (ActionManager.cs:715-718; a Move is unwrapped, cs:662-
  667) and `StopUrgentAction` replays it (cs:647); no `break` — every item
  in range fires. The ToiletAction/AlarmAction are RoutineActionUse: their
  stop angers at `GetTrickedItem(trickItem)` (RoutineActionUse.cs:548,
  556-571) — the dependency for a use tricked only through it.
- Port before: `_update_walking` returned while an urgent ran; `_alarm_use_
  done` passed the item itself to `play_angry`. Level102's loo visit paid
  the toilet only (5/6).
- Port after: `_update_walking` (~3933) runs on every walk (no break);
  `_on_surprise_near` stashes the interrupted urgent (a toilet run caught on
  its way keeps FeelSick — only an Active use gets its OnUseEnded, cs:157-
  160 / Rottweiler.cs:879-892); `_alarm_use_done` (~3498) angers at
  `_tricked_item(it)`.
- Verified: `python3 tests/run_tricks.py tests/plans/s1/Level102.txt` — 16
  legs, 0 failed, 6/6: `FindRight` on the way (t≈98.6), the toilet's 10
  (100.2), the run resumes (`RunWCLeft`), `ShitNormal`/`ShitNoPaper`, the
  ToiletPaper's 10 (117.0).
- Check: `routine: L102 loo visit pays the toilet and the paper`.

## Same-class sweep

- `kind` tests: listed under D2 (one flag outside my area).
- The `selected_index or 0` conflation: `_advance`, `_on_last_seq_element`,
  `_stop_olga_infinite_loop` — all three fixed.
- `in_urgent` writers: `_start_action` (routine action's Urgent ✓),
  `start_urgent` (now the template's), `run_to_hit_pawn` (now the
  template's), `_urgent_finished` (False), `_catch` (HitWoody Urgent=false,
  end-game agent ✓). **Outside my area**: `Pawn.tick`'s DOOR_CLIMB / DESCEND
  use `door_force` regardless of `in_urgent`; the original picks
  `RunningDoorForceMagnitude` when InUrgentMove (Pawn.cs:1404-1411 up,
  1430-1436 down) — flagged.
- `pending_alarm` sites: `hear_alerter`, `_raise_alarm`, `on_zone_changed`,
  `continue_alarm`, the AlarmNextAction tick gate, `_surprise_near_stopped`,
  `continue_angry_animation` (now the stop order: resume → ContinueMovement
  → ContinueAlarm), `_finish` / `_angry_done` / the no-animation stops in
  `_use` / the timeout, `_urgent_finished` — all on the split slots.
- `can_decrease_angry=False`: the three `play_angry` sites (gated), the AWA
  rush site (gated, after the stop); no others.
- `nfh2` gates in the angry/urgent code: D8, D9, the StopUrgentAction
  release; the Classic/NFH2 ladder selection unchanged.

## Observations not in the claims (not fixed, for the coordinator)

- `_use`'s no-prime-animation path (world.py:~2062-2067) runs only
  `_action_stopped`; the original's `Rottweiler.ActionManager.StopCurrent-
  Action(canPostponeStop: false)` (Item.cs:1350) is the full
  `RoutineActionUse.StopAction(false)` body (unlocks, deltas, unhides) — and
  it fires from inside `Item.Use`, i.e. before OnActionStarted's own side
  effects (RoutineActionUse.cs:205-306). No routine item ships an empty
  RottweilerPrimeAnimation with side-effect flags that I found; left as is.
- `hear_alerter`'s `state == MOVING` stands for `AnimController.IsMoving()`
  (walking/running animation playing, PawnAnimationController.cs:197-200);
  a neighbour waiting at a door for another pawn (stand pose) is "not
  moving" to the original — his bark then reaches the WasAlerted arm with
  `CurrentAction.Item == null` (the MoveAction) and is dropped silently.
  Edge, unchanged.
- During the WaitInFear the port's `is_alarm_postponed` reads the routine
  action (tricked → true); the original's `RoutineActionWaitInFear` is in no
  arm (false), so a phone alarm during the affected choreography interrupts
  the fear wait there (and, after the alarm, `StartAction(WaitInFear)`
  replays the fear loop for good — a softlock, ActionManager.cs:715-718 +
  647); the port parks the alarm and releases it after the parked angry.
  Left as documented.

---

## README additions (ready to paste)

**Under "Alerters and the alarm plumbing":**

The two parked runs are separate slots, as in the original: the alerter/
notice run (`Rottweiler.ShouldStartSurpriseActionFar` + `SurpriseActionFar.
Item`, cs:88/271/305; `Routine.pending_surprise`) and the phone alarm
(`PendingAlarm`/`PendingAlarmItem`, cs:96-98/1043; `Routine.pending_alarm`).
`CheckSurpriseActionFar` (cs:1139-1148, no gate of its own) releases the
first — from `ContinueAlarm`, from `OnChangeZone` behind
`CanCheckSurpriseActionFar` (`IsFixingBlockingItem`: a Grab/UseFixingItem
step or the walk toward one with PostponeAlarm), and from every non-mutex
Rottweiler use stop (RoutineActionUse.cs:358-362); `CheckPendingAlarm`
(cs:231-240: not postponed, not passing a door) releases the second as
`MoveToAlarm` — the AlarmAction's full use — from the same use stops, the
SurpriseFar/SurpriseNear stops, `OnChangeZone` and the AlarmNextAction gate.
Both stops fire from inside `StartAction(next)` (ActionManager.cs:157-160),
so a released run interrupts the action that was about to start and resumes
it afterwards; the port sets the resume (`_pending`) before the checks and
`start_urgent` materializes it. `IsAlarmPostponed` (cs:1047-1070) is the
whole six-arm predicate over the running template (`Routine._urgent_action`):
SurpriseNear always; SurpriseFar and Grab by their PostponeAlarm; the
interposed move by the target action's own bare PostponeAlarm; a use by
`PostponeAlarm || PostponeAlarmDuringUseOnly || Item.IsTricked()` — Level105's
four actions ship PostponeAlarmDuringUseOnly, and every tricked use postpones.
Two quirks kept as the code has them: `HearAlerter`'s tricked-item exception
(cs:272) dereferences the MoveAction's Item, which is never set
(ActionManager.cs:23), so a bark heard while *walking toward* a postponed
action throws out of `Alerter.CoRoutineRottweilerHearAlerter` and is lost;
and `!PortalMove` postpones a bark heard on the walk-up climb/descend, not
just the door pass. `MovingToAlarm` skips barks while running to an alerter.

Urgents nest as the original's `OriginalAction` chain (ActionManager.cs:
679-718): a run landing on a running one stashes it (`Routine._urgent_stack`)
and `StopUrgentAction`'s `StartAction(OriginalAction)` (cs:647) replays it —
a Grab replays its GrabSequence, a UseFixingItem its TryUseFixingItem, the
Return leg its ReturnSequence, an alerter run or toilet run its whole run;
the exceptions are the running SurpriseNear (cs:681-691), the chain
hand-overs (692-710), a ForceUseOriginalAction carrier (711-714 — L110's
UseFixingItemAction: the chain is abandoned with the tool in hand and the
next visit fixes with it, Item.cs:854-857), and the same template restarted
on itself (`action != ActiveAction`, cs:679). Before this the port collapsed
every nested urgent onto the routine action, and a bark during the L110
fetch left `_fix_tool` set for good. What the port still does not reproduce:
the original loses a parked alerter run when the resumed action needs no
walk (its MoveAction is stopped and the use started over it, ActionManager.
cs:161-170), and a bark parked during a tricked toilet-rush use fires
*before* the toilet run in the original (the use's OnActionStopped fires
inside `StartUrgentAction(Toilet)`, cs:157) but after it in the port; a
phone alarm during the WaitInFear interrupts it in the original (WaitInFear
is in no IsAlarmPostponed arm) and then replays the fear loop for good
(cs:715-718 + 647) — the port parks it and resumes the routine.

The urgent templates run or walk by their own `Urgent` flag
(RoutineActionMove.cs:68-75 → `MoveToGoalUrgent`, Pawn.cs:444-448):
SurpriseActionFar and ToiletAction run in every scene, the AlarmAction walks
(the CabinPhone hack sets its Urgent for good, cs:872-875), the fetch runs on
L110/L113 and walks on L111, the Return leg walks everywhere, Olga runs to
her hit and the Mother walks to hers except on Level210. Level102's
ToiletAction carries `ContinueToNextAfterFinished`: its end is a plain
advance (ActionManager.cs:530-538), not `StopUrgentAction`. A `Duration`
that runs out (L110's Beer, 1.0 s) is a bare `Finished` — OnActionStopped
alone at the next start, no `StopAction(bool)` body — but its `TakeGround`
drains in 4/7 s first, so the branch never fires in the shipped data.

**Under "Alerters and the alarm plumbing" (the Dog/Chili run):** the urgent
run to a Dog or Chili is watched by `RoutineActionMove.SameZone()` on every
`ActionManager.Update` (ActionManager.cs:442-448; RoutineActionMove.cs:105-
128): the first frame he stands in the pet's zone off a door latches
`RottPos` and `RottLastDoor` (Pawn.cs:1644-1647), and — every door of the
Dog/Chili levels serializing `RottweilerExitLocation` (0,0,0) — that same
frame switches the run: the surprise plays where he landed (a walk-up door
included, hanging on the landing until the walk), `Finished && SameZone`
walks him (the plain MoveToGoal) to the pet, and within 0.05 the "Angry"
yell of `SurpriseSequenceLeft` runs, whose end (Rottweiler.cs:485-510) sends
him to a raw-tricked DirtyCarpet in the zone — the fetch of the vacuum. A
neighbour who has never passed a door has no `RottLastDoor`: cs:121 throws
in Update each frame and the manager is dead — he walks to the pet and
stands — until the next StartUrgentAction retargets the MoveAction
(Level113's neighbour starts in the dog's zone; the port reproduces the
stall). `UpdateWalking` (Rottweiler.cs:833-849) runs on every walk, urgent
runs included: the toilet rush past a tricked NoticeWhenWalkNearby item
starts the near surprise, which chains the run as its OriginalAction and
resumes it (a run caught on its way keeps FeelSick); the ToiletAction /
AlarmAction stop angers at `GetTrickedItem` (RoutineActionUse.cs:548) —
Level102's loo visit pays the toilet on the way and the ToiletPaper on the
seat.

**Under "The neighbour's routine":** `AdvanceActionIndex` (ActionManager.cs:
566-584) wraps to the start index, else to `ActionSelectedIndex` only with
`LoopFromSelectedIndex`, else 0 — Level206's Mother (LoopFromSelectedIndex
false, ActionSelectedIndex 3) replays her whole lap; `StopOlgaInfiniteLoop`
clears the flag (Item.cs:2602). Both fields ship in the level JSON.

**Under "Season 2's anger ladder":** `Item.Fix` opens by clearing
`Rottweiler.TrickedAux` (Item.cs:2065), so a re-angry on a fully scored
linked pair (cs:650-652) only latches the meter until the next fixed trick;
`CanDecreaseAngryMeter=false` is Classic-only (cs:793-796, and
ActionManager.cs:588-591's release) — Season 2's meter keeps decaying
through the angry set; the compound statue/whistle of cs:702 is
`!NFH2Path`-gated — Season 2's statue rides the meter overflow alone.

**Under "The use side-effects" (replace the sentence "the L211 Olga
toilet-delay arm of the hit (`DelayToiletBehavior211`) rides the unported
Bouquet hack"):** the L211 `DelayToiletBehavior211` arm of the hit
(RoutineActionHitPawn.cs:23-27) is dead in the shipped build — it compares
`GameInfo.Instance.Olga` with the hit's `Target`, and the only callers of
`RunToHitPawn` (Rottweiler.cs:741, 752) pass the Rottweiler; the port keeps
the writer (`StopOlgaInfiniteLoop`, ported) and the live `else` arm. The
animated angry never rushes to the toilet: `OnAnimationSequenceEnded` runs
`FixTrickedItem` (cs:460, nulling `TrickedItem`) before `CheckRushToToilet`
(cs:478-484); only `AngryWithoutAnimations` items rush (cs:721) — every
`RushToToilet` carrier ships it. `RoutineActionUse.StopAction`'s angry gate
is `Item as TrickItem` (cs:419) — the Drawing (L107) and the Rake (L202) go
angry like any TrickItem.

**Under "The infinite-loop release and the mutex handshake" (replace the
AbortActiveMutex sentence and the Level205 paragraph):** `AbortActiveMutex`
(cs:127-134) marks the parked action Finished and calls
`AdvanceToNextAction`, whose `StartAction(next)` stops the still-Active
mutex action first (ActionManager.cs:157-160) — its `OnActionStopped` runs
after all: the ignore-loop resets (cs:326-341), not the non-mutex block
(cs:342: OnUseEnded, the abort branch, the alarm checks). Level205's mat
gets its InfiniteLoop back the moment the neighbour is sprung. A hidden
controller does not animate at all: `AnimationControllerBase.OnGUI` runs
`Refresh` only when `!Hidden` (cs:177) — a pawn behind a door pass, under
`HideOwnerDuringUse` / `PawnToHideDuringUse` or in the wardrobe, and a
hidden item, stand on their frame and resume when shown. That is what the
Level205 handshake is built on: Olga's mat use hides her, so her own
`HitPawn` never ends it; `TrickItem.PlayOlgaAnimation` plays the mat's
`UseNormalSequence` with `Olga.OnItemAnimationSequenceEnded` as the
sequence delegate (TrickItem.cs:964-975, 988; Olga.cs:154-158 —
`CurrentAction.StopAction(canPostponeStop: true)`), the neighbour's mat
mutex releases the mat's InfiniteLoop step on his arrival
(`ItemToStopInfiniteAnimation`) and re-arms it when he is sprung, so she
sunbathes until he comes to watch (her use spans his whole lap), the mat
drains 11.4 + 4.4 + 1 s after he parks, her stop springs him, and his
tennis stop springs her; both cycle for the level (400 s headless: 3 / 4
laps). Level210's mat is the second `PlayUseNormalSequence` carrier; the
two are the only non-mutex `HideOwnerDuringUse` actions in the data.

---

## Coordinator flags

1. **`_can_woody_use`, world.py:~5499** (item agent): `item.kind !=
   'TrickItem'` stands for the bool `Item.TrickedItem` (Item.cs:524; only
   ever set true for LionStatue, cs:1546; cleared cs:1593), not a type test.
   L209's Flowers GameObject has both a TrickItem and a SearchItem component
   — the exporter's kind pick decides which arm the port takes.
2. **`Pawn.tick` DOOR_CLIMB / DESCEND** (Pawn agent): the climb/descend
   velocity uses `door_force` regardless of `in_urgent`; the original picks
   `RunningDoorForceMagnitude` when InUrgentMove (Pawn.cs:1404-1411,
   1430-1436) — the toilet rush and the alerter run now set `in_urgent`
   correctly, so this is the remaining half of the run speed on walk-up
   doors.
3. **S2 Woody has no `Walk_*` animations** (74-anim controller, Run_* only):
   `Woody.UpdateWalkingAnimation` plays `Walk_*` when Sneaking (Woody.cs:
   886-937) → the port raises in `_walk_anim`/`play_looping` (the original
   throws too, AnimationControllerBase.cs:367, swallowed per Update). The
   monkey's Tab press crashes every S2 run (L201/202/205/206/211/213). Not
   mine (Woody movement).
4. **D13**: if the end-game agent adds a global `World.moving_to_hit_woody`
   (Rottweiler.HitWoody, cs:1092), `Routine.start_urgent` and
   `run_to_hit_pawn` should return on it (ActionManager.cs:657) — I did not
   wire a flag nobody sets. D14 (unfreeze on the alerter run) can only land
   after that, since `frozen` doubles as the catch gate today.
5. **D16 is now ported** (the item-sequence delegate + the OnGUI hidden
   gate + the abort's OnActionStopped); the README's Level205 paragraph and
   the "without OnActionStopped" sentence need the corrections in the README
   additions. The hidden gate is a global AnimPlayer semantic (every hidden
   pawn/item stops animating, as in the original) — the assets/anim agent
   should know.
6. Two other agents' checks fail under the exact hidden-controller gate
   (`AnimationControllerBase.cs:177`, part of the D16 port) and need their
   scenario adjusted, not the runtime: **`tests/checks/gameinfo_hud.py`
   "routine: Level205 cycles both routines (D8 guard)"** drives L205 for
   14 s and expects both routines past their first item — Olga's first mat
   use now legitimately lasts 2.33 → 20.1 s (Extra1 1 + UseNormal 11.4 +
   Extra3 4.4 + Extra2 1 s, the loop released by the parked neighbour), so
   the window must be ≥ 25 s (both reach TabbleTennis at ~20-22 s); and
   **`tests/checks/items.py` "items: empty search still runs UseItem"**
   plays Woody's search step at t=1.7 s, mid-entrance, while his controller
   is Hidden for the door pass (Pawn.cs:1617-1629, unhidden at 1638-1641) —
   frozen in the original too; start it after the entrance (t ≥ 3.5 s).
7. Latest moment-suite run: every `routine:` check ok (26 mine + the
   gameinfo agent's re-timed L205 guard), the items check passes again; the
   one failure, `pawn: S2 DoorBack has its pass sprite` (pawn_woody.py —
   the L213 DoorBack sprite's load-time hidden flag), is in the sprite/pawn
   agents' area (my edits set no sprite flag at load).
8. Earlier transient failures seen during my runs — `gameinfo: GameEnded
   only after the finish pose` and `sleep bar: the dog wakes early` (every
   animation briefly ran at half speed: BedSleep 0.52 → 1.0 s per element,
   Woody's Hello 0.42 → 0.82 s) — pass again in my last run; both were
   other agents' mid-edit states.
