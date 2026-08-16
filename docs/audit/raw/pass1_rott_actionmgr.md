# Flag-lifecycle audit — Rottweiler / Mother / Olga / Kid / ActionManager / RoutineAction*

Pass 1. Source of truth: `src/Assembly-CSharp/*.cs`; port: `runtime/world.py` (Routine ~1485,
World angry/urgent ~4000-5250), `runtime/scene.py` (spec export), `runtime/behaviors.py`.
Inventory: `flag_inventory.txt` sections Rottweiler(60) / Mother(7) / Olga(8) / Kid(11) /
ActionManager(41); RoutineAction* fields grepped by hand. Same-named-field pollution in the
inventory was resolved by reading code (e.g. `AnimationControllerBase.ShouldStopAction`,
`Woody.Frozen`, `CameraMover.Frozen`, `Item.TrickedItem`, `Olga.targetPawn` vs Pawn method
params, `RoutineActionUseFixingItem.TrickedItem` are all *different* fields).

**Counts**: 127 fields examined (60+7+8+11+41 inventory + ~25 RoutineAction* family).
Verdicts: OK 78 · DIVERGENCE 16 (2 high, 5 med, 9 low) · NOT-PORTED 2 (1 documented-stale,
1 documented-adjacent) · DEAD 12 · CONFIG 24 · OUT-OF-SCOPE 8 (tutorial/trick-camera paths).
Data facts used: `SurpriseActionFar.PostponeAlarm=False` in all 31 scenes;
`RushToToiletOnStart=False` everywhere; `ToiletAction.Urgent=True` everywhere;
`ToiletAction.PostponeAlarm=True` on L105/L211; Grab/UseFixingItem `PostponeAlarm=True` on
L110 only; `IgnoreNextActionAfterUrgentMove`/`frozenDuration` only Intro102;
routine `Duration>0` only L110 action 1; Urgent routine actions always pair with
`ContinueToNextAfterFinished=True` (L206/208/210); L206 Mother serializes
LoopFromStartIndex=False, LoopFromSelectedIndex=False, ActionSelectedIndex=3.

---

## DIVERGENCES

### D1 (HIGH) — `Rottweiler.TrickedAux` is never cleared: the NFH2 anger ladder freezes
- C# writes: `Rottweiler.cs:652` set (PlayAngryAnimation, NFH2 branch: both halves of a
  linked pair already tricked → `TrickedAux = true`); **`Item.cs:2065` clear — the first
  statement of `Item.Fix()` is `GameInfo.Instance.Rottweiler.TrickedAux = false;`** (runs on
  every successful fix, i.e. constantly).
- C# reads: `Rottweiler.cs:655-658` — `if (... && !TrickedAux && !Item.AlreadyTricked)
  AngryMeter += Item.AngerAmount;` — the *only* meter-accumulation arm for plain tricks.
- Port: set `world.py:4096`; read `world.py:4097`; **no clear anywhere** — `world.py:300`
  even annotates it "`Rottweiler.TrickedAux (never reset)`", which is wrong about the
  original: `Item.Fix` resets it.
- Scenario (S2 only — the write sits in the `NFH2Path` branch): L206, LaunchPad+Harpoon both
  tricked and scored (`AlreadyTricked` both); a re-angry on the still-tricked pair sets
  `tricked_aux`. Original: the very next `Fix()` (any fixed trick) clears it and the meter
  resumes accumulating. Port: the flag sticks for the rest of the level → every subsequent
  trick adds 0 to `angry_meter` → the anger stays at whatever level it had; no Level2/3
  escalation, no freakout/statue/whistle for the remainder of the level.

### D2 (HIGH) — tricked `Drawing`/`Rake` never go angry: `kind == 'TrickItem'` misses subclasses
- C#: `RoutineActionUse.StopAction` — `TrickItem trickItem = Item as TrickItem;`
  (`RoutineActionUse.cs:419`) and the angry gate `trickItem != null && trickItem.IsTricked()`
  (`cs:546-549`). `Rake : TrickItem` (Rake.cs:1) and `Drawing : TrickItem` (Drawing.cs:3)
  pass the cast — a tricked Drawing/Rake use ends in `PlayAngryAnimation` (score via
  `Item.OnTrickDone`, fix via `FixTrickedItem`→`TryFix`, `Drawing.Fix` sets `SkipAction`).
- Port: `world.py:2731` — `if it.kind == 'TrickItem' and it.is_tricked(...)` — the exact
  string excludes the exported concrete kinds `Drawing`, `Rake`, `Toilet`, `Television`
  (the port's own `TRICK_KINDS` tuple at `world.py:9` exists because kinds are concrete).
  The Rake early path (`world.py:2120-2129`) also funnels into the same `_finish`.
- Live data: Drawing is L107 routine action 0; Rake is L202 routine action 2 (only
  routine-used subclasses; L102's Television rides the notice/urgent path, which has no
  kind gate — `world.py:2954` — and stays correct).
- Scenario: L107 — Woody tricks the Drawing; the neighbour's next drawing use ends silently,
  the routine advances: no angry animation, no trick score, no fix/`skip_action` — the
  drawing trick can never be completed. Same for L202's Rake (both the tricked-non-compound
  case, where C#'s `Rake.PlayAnimation` stops straight into the angry, and the
  compound-tricked case).

### D3 (MED) — parked alarms are not released when the postponing action stops
- C#: `RoutineActionUse.OnActionStopped` (`RoutineActionUse.cs:358-362`) calls
  `CheckSurpriseActionFar(NextAction)` + `CheckPendingAlarm(NextAction)` on **every**
  non-mutex Rottweiler use stop; `RoutineActionSurpriseFar.OnActionStopped`
  (`RoutineActionSurpriseFar.cs:70`) calls `CheckPendingAlarm()`. These consume
  `ShouldStartSurpriseActionFar` (`Rottweiler.cs:1141-1148`) and
  `PendingAlarm/PendingAlarmItem` (`cs:231-240`) the moment the postponing action ends.
- Port: both flags are merged into `Routine.pending_alarm` (`world.py:1510`), released only
  at `continue_alarm` (`world.py:3395` — reached from WaitInFear/SurpriseNear stops), zone
  change (`world.py:3428`) and the `AlarmNextAction` tick gate (`world.py:3478-3483`).
  `_action_stopped` (`world.py:2795-2834`) and `_urgent_finished` (`world.py:3045`) never
  look at `pending_alarm`.
- Scenario: L114 — the pet barks while the neighbour is mid-use of action 0
  (Polish, `PostponeAlarm=True`): original parks the alarm and starts the run to the pet the
  instant the polish use stops; the port keeps the alarm parked until the neighbour happens
  to cross a zone — he can play several more routine actions deaf to the pet.

### D4 (MED) — `is_alarm_postponed` covers one of six C# arms; L110 fetch chain can be clobbered for good
- C# `Rottweiler.IsAlarmPostponed` (`Rottweiler.cs:1047-1070`) is true for: current
  `RoutineActionSurpriseNear`; `RoutineActionSurpriseFar {PostponeAlarm}` (data: always
  false — inert); a `RoutineActionMove` whose `NextAction.IsAlarmPostponed()` (the *walk
  toward* a postponed action); `RoutineActionGrab {PostponeAlarm}`; and for a
  `RoutineActionUse`: `PostponeAlarm || PostponeAlarmDuringUseOnly || Item.IsTricked()`.
  Gates: `HearAlerter` (`cs:272`), `OnAlarmRaised` (`cs:1038`), `CheckPendingAlarm` (`cs:233`).
- Port: `world.py:2857-2860` — only `action['postpone_alarm'] and state == USING`.
  `PostponeAlarmDuringUseOnly` is not even exported (`scene.py:_find_routines` parses only
  `PostponeAlarm`); the Move-wrapping, Grab and `Item.IsTricked()` arms are absent
  (`_can_check_surprise_far`, `world.py:3439-3449`, covers the Grab arm only for the
  zone-change gate, not for `hear_alerter`/`_raise_alarm`).
- Scenarios:
  (a) L105 (all 4 actions ship `PostponeAlarmDuringUseOnly=True`): Woody triggers the phone
  alarm while the neighbour is mid-use → original parks it (released at the use stop);
  port interrupts the use at once.
  (b) L113: alerter fires during the sink use (`IsTricked()` via the valve `DependsOn`,
  raw `Tricked` false → C# postpones, the exception `Item.Tricked` does not apply) →
  port interrupts.
  (c) **Stuck-flag chain, L110** (`GrabFixingItemAction.PostponeAlarm=True` there): the pet
  barks during the vacuum fetch → C# `PostponeAlerterAction` parks it; the port's
  `hear_alerter` sees `is_alarm_postponed()==False`, `state==MOVING` → `start_urgent(pet)`
  overwrites `_urgent_handler` (`world.py:2888`), dropping `_grab_arrived`; `_fix_tool`
  stays set forever (only `_fixing_done`/`_return_arrived` clear it) →
  `_can_check_surprise_far()` returns False forever → every later zone-change alarm release
  is dead and the carpet is never fixed. (C# recovers: the interrupted Grab is re-entered
  via `OriginalAction`, `ActionManager.cs:692-706`.)

### D5 (MED) — L206 Mother wraps to action 3 instead of 0 (`LoopFromSelectedIndex` conflated)
- C# `AdvanceActionIndex` (`ActionManager.cs:566-584`): on wrap — `LoopFromStartIndex` →
  start; else `LoopFromSelectedIndex` → `ActionSelectedIndex`; **else → 0**.
- Port `_advance` (`world.py:1641-1649`): `loop_from_start` → start; `elif
  self.selected_index:` → selected; else 0 — i.e. the *truthiness of the index* stands in
  for the missing `LoopFromSelectedIndex` export (`scene.py` does not read it).
- Data: the only live mismatch is **L206 Mother** — `LoopFromStartIndex=False,
  LoopFromSelectedIndex=False, ActionSelectedIndex=3`, actions
  `[DeckChairThrow, DeckChairCall, DeckChairOrder, DeckChair]`. Original wraps to 0 and
  replays the whole lap; the port wraps to 3 — from the second lap on the Mother repeats
  only `DeckChair`. (L206 Rottweiler Sel=4/LoopSel=True, L214 Olga Sel=1/LoopSel=True,
  L210 Olga Sel=0 all coincide under the truthiness trick; `Item.cs:2601-2602`'s
  `LoopFromSelectedIndex=false` write is emulated equivalently by
  `_stop_olga_infinite_loop`'s `ort.selected_index = 0`, `world.py:4533`.)

### D6 (MED) — the toilet rush walks instead of running
- C#: `MoveToToilet` → `StartToiletAction` → `StartUrgentAction(ToiletAction)`;
  `ToiletAction.Urgent` is serialized **True in all 31 scenes** → the interposed move is
  `MoveToGoalUrgent` (`RoutineActionMove.cs:68-70`) → `InUrgentMove` → run force.
- Port: `move_to_toilet` (`world.py:3371-3384`) → `start_urgent(it, alarm_use=True)`, and
  `start_urgent` sets `pawn.in_urgent = (not alarm_use) or item.name == 'CabinPhone'`
  (`world.py:2894`) → **False** for the toilet → walking force (`world.py:1194`).
  (For actual alarms this is right — `AlarmAction.Urgent` is false except the CabinPhone
  hack, `Rottweiler.cs:869-877`.) The `RunWC*` frames still play (FeelSick arm), so the
  neighbour visibly "runs" at walk speed.
- Scenario: L103 tricked sweets → the WC dash crosses the level at 0.8 u/s instead of the
  running magnitude — several seconds slower, detection windows shift accordingly.

### D7 (LOW-MED) — a parked phone alarm loses its answer-use on release
- C#: `CheckPendingAlarm` → `MoveToAlarm(PendingAlarmItem)` (`Rottweiler.cs:236,869-877`)
  → `AlarmAction` is a `RoutineActionUse` → arrival runs a full `Item.Use` (the answering
  sequence at the phone).
- Port: every release of the merged `pending_alarm` (`world.py:3395-3397, 3428-3431,
  3480-3482`) calls plain `start_urgent(it)` without `alarm_use=True` — the arrival takes
  the SurpriseFar path (`world.py:2950-2980`: angry / neutral-use / surprise animation)
  instead of the full use. Only the direct, un-parked path (`_raise_alarm`,
  `world.py:4897`) passes `alarm_use=True`.
- Scenario: L105 — Woody rings while the neighbour passes a door → `OnAlarmRaised` parks;
  on release the original answers the phone (`RottweilerUse` sequence); the port plays the
  item's surprise (or nothing) and resumes.

### D8 (LOW) — `CanDecreaseAngryMeter=false` written unconditionally; C# gates on `!NFH2Path`
- C#: `Rottweiler.cs:793-796` — `if (Woody != null && !Woody.NFH2Path)
  CanDecreaseAngryMeter = false;` (and the matching true-write in `StopUrgentAction`,
  `ActionManager.cs:588-591`, is `!NFH2Path`-gated too). In Season 2 the meter *keeps
  decaying during the angry animation*.
- Port: `world.py:4158, 4194, 4212` set `pawn.can_decrease_angry = False` with no NFH2
  gate (re-set True at `world.py:4141, 2832, 3053`).
- Effect (S2 only): the port's meter is up to `AngryMeterDecay * angry-duration`
  (≈ 6/s × 3-5 s = 18-30 points) higher at the next trick's threshold comparison
  (`num <= 1 / <= 2`, `Rottweiler.cs:669-683`) — the anger face/sequence can read one level
  higher than the original's.

### D9 (LOW) — S2 compound tricks blow the statue whistle
- C#: `Rottweiler.cs:700-706` — `if (TrickedItem.Compound && TrickedItem.CompoundTricked
  && !GameInfo.Instance.Woody.NFH2Path) Item.OnCompoundTrickDone();`
  (`Item.OnCompoundTrickDone`, `Item.cs:2161-2169`: compound count + `PlayStatueAchieved`
  + `PlayWhistle`).
- Port: `world.py:4128-4131` — same call **without the `not nfh2` gate**.
- Scenario: S2 compound (Tortilla / PlantCarnivore `CompoundTricked`) → the port restarts
  the statue strip, plays the whistle and bumps `game.compound_tricks`; the original does
  none of that in Season 2 (its S2 statue rides only the meter-overflow arm,
  `Rottweiler.cs:684-692`).

### D10 (LOW) — L110's `Duration=1.0` action runs the wrong stop flow on timeout
- C#: a `Duration>0` action whose time expires is simply `Finished`
  (`RoutineAction.cs:91-105`) → `AdvanceToNextAction` — **no `StopAction(bool)` run** (no
  exit deltas, no unlocks, no angry postpone); only `OnActionStopped` fires when the next
  action starts (`ActionManager.cs:157-159`).
- Port: the timer branch (`world.py:3509-3512`) calls `_finish()` — the full
  `StopAction(canPostponeStop: true)` body including `_stop_side_effects` and the tricked
  angry hand-off.
- Live data: exactly one such action — L110 Rottweiler action 1. If its sequence outlasts
  1.0 s and the item is tricked at that moment, the port plays an angry the original skips.

### D11 (LOW) — the port can rush to the toilet from animated angry paths the original cannot
- C#: `OnAnimationSequenceEnded` runs `FixTrickedItem()` at `Rottweiler.cs:460` — which
  nulls `TrickedItem` — *before* the `IsPlayingAngryAnimation` branch calls
  `CheckRushToToilet()` at `cs:478-484` → on the animated angry path the rush is dead code;
  the live rush is only the `AngryWithoutAnimations` branch (`cs:719-724`, `TrickedItem`
  freshly set at `cs:698`).
- Port: `after_run` (`world.py:4143-4149`) rushes whenever `item.cause_rush_to_toilet()` —
  reachable on animated paths too.
- Data: every direct `RushToToilet` carrier ships `AngryWithoutAnimations=True`
  (Intro102, L102, L103, L105, L106, L108, L211) — so the difference is latent; it becomes
  live only through `CauseRushToToilet`'s `DependsOn.RushToToilet` arm
  (`TrickItem.cs:683-686`) on an item without `AngryWithoutAnimations`.

### D12 (LOW) — `Olga.DelayToiletBehavior211` writer ported, consumer missing (stale doc)
- C#: write `Item.cs:2600` (`StopOlgaInfiniteLoop`, the tricked Bouquet — **ported**,
  `world.py:4526`); reads `RoutineActionHitPawn.cs:23-27` — `DelayToiletBehavior211 > 0` →
  `InvokeWCBehavior211(Target)` (hide the target Rottweiler after 4.8 s via
  `Olga.targetPawn`/`WCBehavior211`, `Olga.cs:160-169`) **and**
  `Olga.ActionManager.Actions[0].Item.SetObjectHidden(false)` (reveal the shower).
- Port: `_hit_pawn_arrived` (`world.py:3338-3358`) hides the target immediately and never
  reveals Olga's action-0 item; `pawn.delay_toilet_211` (`world.py:342`) is written and
  never read. `Olga.targetPawn`: NOT-PORTED with it.
- README (~line 880) documents this as riding "the unported Bouquet hack" — stale: the
  Bouquet hack (`StopOlgaInfiniteLoop`) *is* ported now. L211 visible: the neighbour
  disappears instantly instead of 4.8 s into Olga's shower rage, and the shower item stays
  hidden.

### D13 (LOW, note) — `MovingToHitWoody`'s global gate approximated per-routine
- C#: `ActionManager.StartUrgentAction` (`ActionManager.cs:657`) checks
  `GameInfo.Instance.Rottweiler.MovingToHitWoody` in **every** manager — during the catch
  walk no pawn can start an urgent action. (`Mother.MovingToHitWoody`, `Mother.cs:12,133`,
  is write-only — dead; and neither flag is ever cleared, by design: the game is ending.)
- Port: `_catch` freezes only the catcher's routine (`world.py:6226`); other routines could
  still start urgents during the catch walk (post-`game.ending` the detection stops but
  routines/alerters still tick, `world.py:6467, 6506, 6511`). Practical exposure is
  minimal (input locked ⇒ no new alerts/tricks), hence note-level.

### D14 (LOW, note) — `StartSurpriseActionFar` unfreezes in C#; the port's `start_urgent` returns when frozen
- C#: `Rottweiler.cs:1150-1154` — `ActionManager.Unfreeze(!triggeredByWoody);
  StartUrgentAction(...)` — a frozen manager still takes the alerter run.
- Port: `start_urgent` (`world.py:2877-2878`) — `if self.frozen: return`.
- Both live freeze sources outside end-of-game (`FreezeAfterCompletion` data uses,
  Intro103's tutorial neighbour) sit behind unported tutorial flows (README-documented);
  the `animal_tutorial` arm unfreezes explicitly (`world.py:3252-3257`).

### D15 (LOW, note) — `hear_alerter` misses the `PortalMove` gate
- C#: `Rottweiler.cs:272` — `!IsPassingDoor() && !PortalMove && ...` — an alarm heard
  mid-portal-climb is postponed (`PostponeAlerterAction`).
- Port: `world.py:3241` gates only on `pawn.is_warping` (door transit) — a climbing
  neighbour (`DOOR_CLIMB`/`DESCEND`) is redirected mid-ladder instead.

### D16 (LOW-MED, S2, documented-adjacent) — `Olga.OnItemAnimationSequenceEnded` not ported
- C#: `TrickItem.cs:972` — Olga's non-tricked use passes
  `olga.OnItemAnimationSequenceEnded` into `PlayUseAnimation`; when the **item's** use
  sequence drains it stops Olga's current action
  (`ActionManager.CurrentAction.StopAction(canPostponeStop: true)`, `Olga.cs:154-158`) —
  one of the releases that lets her out of long/looping poses.
- Port: `play_use_item_anim` (`world.py:4598-4610`) takes no callback; Olga's action ends
  only when her own pawn sequence drains. Falls under README's "Season 2 is not finished —
  the release machinery" cluster (README ~211-218), but this specific hook is not in its
  list, so recorded here.

---

## Per-field tables

Verdict legend: OK (port sites listed) · DIV-n (see divergence n) · NP (not ported) ·
OOS (out of scope: tutorials/menus/trick camera/touch) · CFG (serialized-only) · DEAD
(no live runtime caller in this build).

### Rottweiler (Rottweiler.cs, declaration order)

| Field (decl) | C# writes | C# reads / gate | Port | Verdict |
|---|---|---|---|---|
| ActionManager (22) | wiring (Pawn.cs:229, RoutineAction.cs:112) | everywhere | `Routine` bound per pawn (world.py:6054-6061) | CFG |
| DelayStart (24) | Start=1.5 (153); Update decrement (920) | 916, 921 — gates StartFirstAction | `Routine.delay_start` (1504; tick 3457-3460); CanStart≡immediate (intro unported, documented) | OK |
| SurpriseActionFar (26) | Item field: 271 (HearAlerter), 331 (RunToTricked), 503 (carpet) | urgent template everywhere | `urgent_item` (2887) | OK |
| SurpriseActionNear (28) | Item: 853 | OnSurpriseNear | `_on_surprise_near` (3276) | OK |
| FallAction (30) | Item: 859 | OnFall (CauseSlip) | same `_on_surprise_near` path (3269-3273) — templates are identical class | OK |
| ToiletAction (32) | Urgent=true: 874(CabinPhone-n/a), 888(dead) | StartToiletAction 866; AM.cs:723-725 | `toilet_action` spec (scene.py:1981) + `move_to_toilet` (3371) | **DIV-6** (walks) |
| GrabFixingItemAction (34) | Item/UseFixingItemAction: 1080-1081 | RunToFixingItem | `grab_action` + `_fix_tool` (3135-3143) | OK |
| UseFixingItemAction (36) | Item: 1079 | chain | `use_fixing_action` + `_fix_target`; tool's stop side-effects (UFIA.StopAction sets Item=tool) not run — low note | OK |
| NoticeWhenNearTrickedDistance (38) | — | 837 | `notice_near_distance` (349, 3272) | CFG |
| Woody (40) | wiring | everywhere | `world.woody` | CFG |
| PortalRunDown/Up (42/44) | — | 423/406 | `portal_run_up/down` (455-479) | CFG |
| ShouldStartUrgentAction (46) | 332 set, 348 clear | 346 — OnSingleAnimationEnded consumes → StartUrgentAction | startle single's `on_end=start_urgent` (3417-3426) | OK |
| TrickedItem (48) | 698 set (PlayAngry), 389 clear (FixTrickedItem). (Item.cs:1546/1593 & UFIA.cs:43 are other fields) | 544 CheckRushToToilet; 386-390; 699-706; 722-724 | closure `item` in play_angry/after_run (4140-4149); order fix-then-second-stop kept | OK (+DIV-11 note) |
| AngryMeter (50) | 611/618/623/628/633/638/644/647/657/661 (PlayAngry), 910/913 (decay) | 597/659/664/679 (ladder), 908/911 (decay), HUD.cs:327,1240-1245 | 4047-4104; decay 1121-1122; hud.py:868 | OK |
| CanDecreaseAngryMeter (52) | Start 157 (NFH2 true); AM.cs:590 true (!NFH2); 795 false (!NFH2); 891 true (OnUseEnded) | 908 decay gate | init True (298); True 2832/3053/4141; False 4158/4194/4212 **ungated** | **DIV-8** |
| AngryMeterDecay (54) / Maximum (56) | — | decay/ladder | `angry_decay/angry_max` (296-297) | CFG |
| IsTestingAnimation (58) / TestSequence (60) | — | 377/455/925/457/935 | absent; serialized false | CFG/DEAD |
| AlarmAction (62) | Urgent=true 874 (CabinPhone) | MoveToAlarm 871-876 | `alarm_use=True` + CabinPhone hack (2894, 4897) | OK direct / **DIV-7** parked |
| RushToToiletOnStart (64) | — | 886-889, 928-931 | absent — serialized False in all 31 scenes | CFG/DEAD |
| IgnoreWoody (66) | Item.cs:827-829 set (RottweilerUse head); AM.cs:228-231 clear (next start) | GameInfo.cs:185/189/198; Pawn.cs:368/382 (door-exit catch) | set 2080-2081; clear 1875-1877; reads 6148, 5089/5100 | OK |
| MediumLaughs/BigLaughs/LaughVolume (68-72) | — | 805-818 | `_audience_laugh` (3988-3994), Random 0..2 | CFG/OK |
| MinDistanceToNearestDoor (74) | — | 1197-1200 | `min_door_distance` (6280-6282) | CFG |
| IgnoreStartedByWoody (76) | — | decl only | absent | DEAD |
| ShouldStopAction (78) | 709 set (!ReuseAfterFix), 468/728 clear+consume. (ACB.cs:242/292 = controller's own field) | 466/726 → StopCurrentAction(false) | `_angry_done` → `_pending='advance'` (2750-2754); AngryWithoutAnimations sync path 4153-4169 | OK |
| ShouldRestartAction (80) | 713 set (ReuseAfterFix), 474/733 clear | 472/731 → RestartCurrentAction | `_angry_done` → `_pending='start'` on `reuse_after_fix` (2751-2752) | OK |
| FixingItem (82) | Grab.cs:21 set; Return.cs:17 null; UFIA.cs:84 null | Item.cs:847-857 dispatch; UFIA.cs:49-52,77-79; TrickItem.cs:443, 1121-1123 | `pawn.fixing_item` set 3156, cleared 3208/—; reads 2054, 3123, 4311-4312, 4416 | OK |
| IsUsingToilet (84) | RoutineActionUse.cs:203 set / 356 clear | none (decl only) — **write-only in C#** | mirrored write-only (2478, 2830, 3059, 3382) | DEAD (parity kept) |
| IsPlayingAngryAnimation (86) | 778 set, 480 clear | 478 → CheckRushToToilet tail | angry sequence's `on_end=after_run` (4215) | OK |
| ShouldStartSurpriseActionFar (88) | 305 set (PostponeAlerterAction), 1143 clear | 1141 CheckSurpriseActionFar | merged into `pending_alarm` (1510, 3259) | **DIV-3/4** |
| HitWoodyAction (90) | Target/Urgent: 1089-1090 | HitWoody | `hit_action` spec + `_catch` (6195-6258) | OK |
| IsPlayingWoodyHit (92) | RoutineActionHitWoody.cs:30 set | 449 → FinishAnimationEnded; never cleared (game over) | `on_end=_finish_animation_ended` (6252) | OK |
| MovingToHitWoody (94) | 1092 set; never cleared | AM.cs:657 — global StartUrgentAction gate | catcher `frozen=True` (6226) only | **DIV-13** note |
| PendingAlarmItem (96) / PendingAlarm (98) | 1043-1044 set (OnAlarmRaised), 235 clear | 233/236 CheckPendingAlarm | merged `pending_alarm` (4899) | **DIV-3/7** |
| HoldingCake (100) | 1118 (toggle via CakeAction) | 1028 walk pick, 1113 | 1959-1960; 440-442 | OK |
| HasFifi (102) | 1108 | 408/425 portals, 1028 | 1961-1966; 462-471 | OK |
| HasBowlingBall (104) | 1123 (+TrickItem.cs:620-628 give/remove) | 1028 | 2181-2184; 442-443 | OK |
| HasSkates (106) | 1103 | 429 portal, 1028 | 1963-1968; 446-447, 474-476 | OK |
| AlarmPostponed (108) | 1129 set (PostponeAlarm), 1135 clear (ContinueAlarm) | 274 HearAlerter | `alarm_postponed` 3388/3394; read 3242 | OK |
| ItemToIgnoreNextTime (110) | 739/750 set, 824 null | 737/748 affect gates, 823 ContinueAngry arg | 4179/4253/4266-4268 | OK |
| ShouldContinueMovement (112) | only 356 (the clear) — never set | 354 | absent | DEAD |
| WasAlerted (114) | 287 set, 906 clear | 902 (Update, IsMoving) | `was_alerted` 3251/3472-3474 | OK |
| RottAlerter (116) | 288 | 905 (as `triggeredByWoody`) | merged into `was_alerted` (the item) | OK (DIV-14 nuance) |
| CheckAlarmNextAction (118) | — | decl only | absent | DEAD |
| AnimalTutorial (120) | — (serialized) | 290 | `animal_tutorial` 386, 3252-3257 | CFG/OK |
| kid (122) | — | KidActions etc. | `pawns['Kid']` | CFG |
| NFH2TutorialAux (124) | 442 set | decl only | absent (NFH2Tutorial teleport is tutorial layer) | DEAD/OOS |
| TrickedAux (126) | 652 set; **Item.cs:2065 clear (`Fix()`)** | 655 meter gate | set 4096, read 4097, **never cleared** (300 comment wrong) | **DIV-1** |
| AngryCountTicks (128) | 605 (Classic hard), 686 (NFH2 overflow) | GameInfo.cs:396/398/416 score; HUD.cs:669 | 4053/4117; hud.py:1136; 6293 | OK |
| DoneYelling (130) | 493/500/508 | 494/498 — carpet urgent after the Dog/Chili Angry yell | `_yell_done` (3025-3043), first-carpet-only kept | OK |
| ShowCoins (132) | Item.cs:2666 set (ShowObjects) | Item.cs:2664 gate | `_show_objects` 4226-4227 | OK |
| DeckChairAux (134) | TutorialScriptCameraNFH2206 only | decl | absent | OOS |
| NormalPosAux (136) | 1271/1282 set (CheckFinalPosition), AM.cs:190 clear | AM.cs:180/188 gates, 1259 | 4840/4850 set; 1838-1839 clear; 1834 gate. Wrap nuance: port `(index-1)%len` vs C#'s unwrapped `index-1>=0` in AM.cs:180-212 — inert for shipped data (WaterPuddle not last, UFB items not last, gram not at len-2) | OK (low note) |
| ItemAngryAux (138) | 562 | 620/630/635 (CompoundTricked/DogBasket gates) | local `aux` = current item (4066) — persistence across calls immaterial: the gating flags exist only on TrickItems | OK |
| randomNumber (140) | — | decl | absent | DEAD |

### Mother (Mother.cs)

| Field | Lifecycle | Port | Verdict |
|---|---|---|---|
| ActionManager (6) | wiring | Routine role=Mother | CFG |
| HitWoodyAction (8) | Target/Urgent 130-131 | `hit_action`; `_catch` — no MoveToEmptySpace for the Mother (RoutineActionMotherHitWoody.cs:24-32; README-documented), port 6242 gates on role | OK |
| IsPlayingWoodyHit (10) | RAMotherHitWoody.cs:29 set; read 90 → FinishAnimationEnded; never cleared | `on_end=_finish_animation_ended` | OK |
| MovingToHitWoody (12) | 133 set; **no reader reads the Mother's** (AM.cs:657 reads the Rottweiler's) | absent | DEAD |
| Woody (14) | Start 23 | — | CFG |
| IgnoreWoody (16) | serialized only (runtime writes target Rottweiler's) | read `_detect_common` 6148, 5100 | CFG/OK |
| DelayStart (18) | 78-84 | `delay_start` 1504 | OK |

### Olga (Olga.cs)

| Field | Lifecycle | Port | Verdict |
|---|---|---|---|
| ActionManager (6) | wiring | Routine role=Olga | CFG |
| DelayStart (8) | 31-37 | 1504 | OK |
| DelayToiletBehavior211 (10) | write Item.cs:2600 (ported 4526); reads Olga.cs:163 + RoutineActionHitPawn.cs:23-27 | written, **never read** | **DIV-12** (NP consumer, stale doc) |
| animationAuxOlga (12) | AM.cs:335/376 | AM.cs:378-380 (Glass), Item.cs:2524-2525 (FixBoat) | `olga_aux_anim` 1781/1811/1813; 4458-4460 | OK |
| animationWorkoutOlga (14) | Item.cs:2525 (FixBoat) | Item.cs:2537 (FixMechanicalBull → InfiniteLoop=true) | `olga_workout_anim` 4460; the FixMechanicalBull release rides the ported kart/bull behavior chain | OK |
| animationWaitPicnicOlga (16) | AM.cs:340 | AM.cs:353-355 | 1792, 1800-1802 | OK |
| animationWorkoutOlga2 (18) | AM.cs:349 | AM.cs:361-363 | 1797, 1803-1804 | OK |
| targetPawn (20) | Olga.cs:162 (InvokeWCBehavior211) | Olga.cs:168 (WCBehavior211). (Pawn.cs:450/457 = method params, pollution) | absent — consumer of the missing D12 branch | NP (with DIV-12) |
| OnItemAnimationSequenceEnded (154) | — method state; wired TrickItem.cs:972 | stops her action at the *item* sequence end | `play_use_item_anim` takes no callback (4598) | **DIV-16** |

### Kid (Kid.cs)

| Field | Lifecycle | Port | Verdict |
|---|---|---|---|
| Crying (3) / UseCryingSequence (5) / CryingSequence (7) / RemoteSequence (9) | config; Update 32-44, StartCrying 53-59 | spec `kid_crying*`, `kid_remote_sequence` (scene.py:1972-1975); `_kid_update` 5984-6009; `kid_start_crying()` 6011 | CFG/OK |
| UseNormalSequence (11) / UseTrickedSequence (13) / UseLinkedTrickSequence (15) | config; TrickItem.KidActions cs:632-653 | spec `kid_use_*_seq`; `_trick_kid_actions` 1651-1670 | CFG/OK |
| olga (17) | config; Update 31 (break her loop) | 5991-5993 | CFG/OK |
| KidStartCrying (19) | AM.cs:398 set (Rake, Rottweiler owner); Kid.cs:30 clear | Kid.cs:28 | set 1680-1682; consume 5989-5990 | OK |
| UsingRemote (21) | AM.cs:403 set (OlgaMat, ContAux>0); Kid.cs:43 clear | Kid.cs:41 (`else if` chain kept) | set 1684-1686; consume 6001-6005 | OK |
| KidRemote (23) | AM.cs:413 set (BridgeRail); Kid.cs:48 clear | Kid.cs:46 | set 1707; consume 6006-6009 | OK |

### ActionManager (ActionManager.cs)

| Field | Lifecycle | Port | Verdict |
|---|---|---|---|
| ActiveAction (9) | 169 set (StartAction), 665 (unwrap Move) | the whole Update machine | `Routine.state/index/urgent_item` | OK |
| ActiveActionIndex (11) | 105/203/216/226/624/632/636/771/777/802 + Item.cs hacks 2084/2369/2394/2527/2529/2576/2593/2601 + SandCastleBehavior.cs:77 | loop machine | `index`; hacks: 4363-4367 (BullControls +2), 4345-4349 (StarActionAgain −1), 2434-2445 (FishPlant), 4461-4468 (FixBoat), 4509-4511 (Hatch), 4532-4536 (StopOlgaInfinite), behaviors.py (SandCastle) | OK |
| OriginalAction (13) | 672-717 (StartUrgentAction wiring incl. ForceUseOriginalAction chains) | StopUrgentAction resume 597-647 | implicit: urgent never moves `index`, resume = indexed action; nested urgents collapse to the routine action by construction (ForceUseOriginalAction data on L107/L110 honored implicitly) | OK |
| UrgentAction (15) | 537/610/616/623/629/646/661 | 530, 642, 720 | `urgent_item` (2887, 3051) | OK |
| Owner (17) | wiring + UFIA temp swap (RoutineActionUse.cs:346-349) | everywhere | `pawn`; swap ≡ `_abort_parked_mutex` set_hidden(False) (2847-2853) | CFG/OK |
| RenderGizmos (19) | — | editor gizmos | absent | DEAD |
| Actions (21) | 774/787/841/849 (Remove/Add) | loop | `actions` list; `remove_actions_by_item` 2570-2605, `add_in_game_actions` 2561-2568 | OK |
| MoveAction (23) | — | interposed move | `MOVING` state | OK |
| ActionStartIndex (25) | — | 105, 216, 573; Item.cs:1335 (ValveMain ≤3, ported 2009-2011) | `start_index` | CFG |
| LoopFromStartIndex (27) | — | 571 | `loop_from_start` | CFG |
| ActionSelectedIndex (29) | — | 577 | `selected_index` | CFG |
| LoopFromSelectedIndex (31) | Item.cs:2602 (Bouquet, ported as `selected_index=0` — equivalent); tutorial write OOS | 575 | **not exported; truthiness conflation** | **DIV-5** |
| Frozen (33) | 794 Freeze / 799 Unfreeze / Level204OlgaBehavior.cs:34,42. (Woody.cs:995/1001, CameraMover.cs:527/532 = other classes' own `Frozen`) | 106/148/232/432/522/604/657 | `frozen` 1501; tick gate 3452; start 1558; start_urgent 2877; _urgent_finished 3075; behaviors.py 546/584/714/724 | OK |
| Walk (35) | 521/548/562 | 550/558 — only with `frozenDuration>0` (data: Intro102 only) | absent | OOS/DEAD |
| ActionChanged (37) | 234 set (StartNextAction) | Rottweiler.cs:897-899 (with AlarmNextAction) | 1878 set; 3478-3479 consume (clear only when gate true — matches) | OK |
| AlarmNextAction (39) | Level105RoutineBehavior.cs:14/23 | Rottweiler.cs:897 | behaviors.py:252/258; `alarm_next_action` 1518 | OK |
| StopDogAction (41) | 596 set (StopUrgentAction, always) | TutorialScriptCameraIntro3 only | absent | OOS |
| FreezeNeighbour (43) | 541 set | tutorial reads only; the paired `Freeze()` is the live half | `freeze_after_completion` → frozen (3497-3501) | OOS flag / OK mechanism |
| RemoveWateringCan (45) | 788 set | 195, 757, 781 | `remove_watering_can` 1881-1884, 2580, 2599-2605 | OK |
| RemoveNow (47) | 197 set, 778 clear | 757, 775 | `remove_now` 1883, 2596-2598 | OK |
| MarblesNextAction (49) | Item.cs:1384-1387 set (CanWoodyUse GroundMarbles); 644 clear | 614/620 skip suppressors | set 5451-5455; clear 3080-3081; gates 3089/3094 (the missing `IgnoreNextActionAfterUrgentMove` term is Intro102-only data) | OK |
| SameZone (51) | 446 set / 455 clear / Rottweiler.cs:492 clear | 152, 444, 461 | `_same_zone` 2904, 3031, 3069; positional latch (Move.SameZone's RottPos/RottweilerExitLocation arithmetic) approximated by immediate same-zone start — outcome preserved (walk → 0.05 yell) | OK (low note) |
| MovementToGoalDone (53) | 468 set / Rottweiler.cs:491 clear | 463 | one-shot via `goto_item(on_arrive=_same_zone_yell)` (3005) | OK |
| AngryAnimationStarted (55) | 479 set / Rottweiler.cs:490 clear | 475, Rottweiler.cs:485 | `_same_zone_yelled` 2905/3013/3032 | OK |
| RottweilerPositionToDog (57) | 470/473 | 471/475 (<0.05) | inline `abs(x - move_x) < 0.05` (3489-3490) | OK |
| ContAux (59) | 400 (++ in KidActions) | 401 (OlgaMat gate >0) | `cont_aux` 1520, 1683-1685 | OK |
| ActionsToAddInGame (61) | — | 816-826 | `actions_to_add`, 2561-2568; Mother 208 injection 2070-2074 | CFG/OK |
| animationAux (63) | 390 (OlgaInfiniteBehavior), 507 (OlgaActions) | 335/376 (assign to Olga), 386-388 | `anim_aux` 1719-1724, 3470 | OK |
| animationWC (65) | 320 | 293-295/310-312/322 | `anim_wc` 1770-1778 | OK |
| animationStandingLeft (67) | 278 | 280-283/306-308/323-325 | 1749-1760 | OK |
| animationStandingUP (69) | 303 | 289-291/305/327-329 | 1761-1769 | OK |
| animationWCFlag (71) | 319 | 317 | `anim_wc_flag` 1771-1772 | OK |
| animationStandingLeftFlag (73) | 282/287 | 276 | 1750-1756 | OK |
| animationStandingUPFlag (75) | 302 | 300 | 1762-1763 | OK |
| OlgaLaugh211 (77) | — | decl | absent | DEAD |
| OneTime (79) | 348 set (Olga at BoatPicnic/BullWait); never cleared. (Other writes = other classes' `OneTime`) | 346 | `one_time_olga` 1793-1796 | OK |
| SecondOneTime (81) | 343 (dead arm: `Owner is Olga` inside a Rottweiler-gated block), 358 clear | 337 | `second_one_time_olga` 1790, 1802 — same dead-set shape kept | OK |
| getActiveIndex (83) | property (Rottweiler.cs:742 = local var, pollution) | Iron hack 461; RoutineActionHitPawn.cs:32 | Iron 1890-1901; `_hit_pawn_arrived` uses own routine's item (3349-3351) | OK |
| CurrentAction (85) | property | HUD bubble, hacks | routine state | OK |
| IsMotherUrgentAction (99) / StopMotherUrgentAction (101) | subscribed by ProgressBar.cs:111-119, MotherWakeSleepBehavior.cs:19/24 | fired 592-594, 653-655 | events `mother_urgent`/`mother_urgent_stop` 2876/3074; subscribers 3746-3747, behaviors.py:2086 | OK |

### RoutineAction* family

| Field | Lifecycle | Port | Verdict |
|---|---|---|---|
| RoutineAction.Active / TimeLeft / ForceFinished | StartAction/StopAction/Update (cs:107-137) | `state`/`timer`/`_pending` | OK |
| RoutineAction.Duration | Finished getter (cs:91-105): expiry → bare advance, **no StopAction(bool)** | timer → `_finish` (3509-3512) runs the full stop | **DIV-10** (L110 only) |
| RoutineAction.FreezeAfterCompletion | AdvanceToNextAction 539-543 | 3497-3501 | OK |
| RoutineAction.frozenDuration + AM.Walk | 544-564 | absent — data Intro102 only | OOS |
| RoutineAction.ForceUseOriginalAction | StartUrgentAction chains 683-713 | implicit (index-based resume) | OK |
| RoutineAction.Urgent | IsUrgent; MoveToGoalUrgent 68-75 | `a['urgent']` → `in_urgent` 1928 | OK |
| RoutineAction.ContinueToNextAfterFinished | AdvanceToNextAction 530-538 | implicit normal advance; data always pairs with Urgent (L206/208/210) | OK |
| RoutineAction.KeepAnimationsInMemory | texture memory (526-528) | not modelled (README-documented) | OOS |
| RoutineAction.MoveOnly/MoveLocation/MoveZone/MoveThreshold | move-only actions | 1903-1914 | CFG/OK |
| RoutineAction.OriginalAction / Target / Item / MaximumPawnDistanceToAction | wiring | specs | CFG |
| RoutineActionMove.NextAction | MoveToAction 125 | `MOVING` + `on_arrive` | OK |
| RoutineActionMove.Flag / RottPos / RottweilerLastDoor | SameZone latch 105-128 | approximated (see SameZone above) | OK (note) |
| RoutineActionUse.* config (Hide*/Doors/Items/Prime/Trick/Cake/Fifi/Skates/Mutex/AlertNext/Ignore-loop refs/ChangeLayer) | OnActionStarted 136-307 / StopAction 366-554 | exported (scene.py:1591-1663); `_use`/`_after_use_side_effects`/`_stop_side_effects`/`_infinite_flags_on_start`/`_action_stopped` | OK |
| RoutineActionUse.PostponeAlarm | IsAlarmPostponed 573-576 | `postpone_alarm` — but see gate | **DIV-4** |
| RoutineActionUse.PostponeAlarmDuringUseOnly | Rottweiler.cs:1067 | **not exported** (L105 data) | **DIV-4** |
| RoutineActionUse.IgnoreNextActionAfterUrgentMove | StopUrgentAction 614 | not exported — Intro102-only data | CFG/OOS |
| RoutineActionUse.TrickItem + TrickCamera | 142-146, 386-389 | trick camera unimplemented (README-documented) | OOS |
| RoutineActionUse.LayerToChangeAux | 253-259 / 521-530 | `a['_layer_aux']` 2519-2525, 2688-2696 | OK |
| RoutineActionGrab.GrabSequence / UseFixingItemAction | 12-24 | `grab_action` spec; `_grab_arrived` 3145-3162 | OK |
| RoutineActionGrab.PostponeAlarm | IsAlarmPostponed 26-29 (L110 data) | only in `_can_check_surprise_far` (3443-3446), missing from hear/raise gates | **DIV-4c** |
| RoutineActionUseFixingItem.TrickedItem / RedoAction / SecondTime | Finished-setter redo loop 19-45; StopAction Item=tool 75-86 | redo via `angry → on_done=_use_fixing_arrived` (3175-3192); `SecondTime` transient shape preserved; tool's stop side-effects skipped (low note) | OK |
| RoutineActionUseFixingItem.ShouldReturnFixingItem / ReturnFixingItemAction / UseFixingItemSequence | 63-73 | `use_fixing_action` spec; `_fixing_done` 3204-3214 | CFG/OK |
| RoutineActionReturn.ReturnSequence | 8-20 (show tool, FixingItem=null) | `_return_arrived` 3216-3232 | OK |
| RoutineActionHitWoody.Sequence1-4 | GetRandomSequence 26/25/25/24 | `hit_action['sequences']` (scene.py:1952-1962); pick 6248-6251 | OK |
| RoutineActionMotherHitWoody.Sequence1-4 | same; no MoveToEmptySpace | same table; `_catch` role gate 6242 (README-documented) | OK |
| RoutineActionHitPawn.HitPawnSequence / ItemIndex | 20-45 | `hit_pawn_action` spec; `_hit_pawn_arrived/_hit_pawn_done` 3338-3369 | OK |
| RoutineActionHitPawn — DelayToiletBehavior211 branch (23-27) | delayed hide + reveal Olga's action-0 item | missing | **DIV-12** |
| RoutineActionHitPawn.RottItemIndex | decl only | absent | DEAD |
| RoutineActionWaitInFear.FearAnimation | 13-27 + ChangeHitPawnAnimation207 rewrites | `wait_in_fear_anim` (scene.py:1987) + `_change_hit_pawn_animation_207` 2447-2466; `_start_wait_in_fear` 4235-4247 / `continue_angry_animation` 4249-4268 | OK |
| RoutineActionSurpriseFar.PostponeAlarm | 7; IsAlarmPostponed arm | serialized False in all 31 scenes — arm inert | CFG/DEAD |
| RoutineActionSurpriseFar OnActionStarted/Stopped/StopAction | 41-87 | `_urgent_arrived` 2918-2980, `_urgent_finished` (CheckPendingAlarm at stop missing → DIV-3) | OK core / DIV-3 |
| RoutineActionSurpriseNear (whole) | 12-57: pause, PostponeAlarm, facing-matched sequence (Right→Right — not inverted), SurpriseDeltaLocation; stop: ContinueMovement/Alarm/CheckPendingAlarm | `_on_surprise_near` 3276-3312 (facing kept; continue_alarm covers the merged pending release) | OK |

Additional cross-checks done and clean: `RandomFreakOut` Range(0,1)≡0 (port constant,
4118-4120); Classic vs NFH2 branch selection (GameMode Classic everywhere — documented);
the NFH2 extra-coin ladder arms 615-658 line-for-line (4067-4099); `_finish`'s
fix-then-second-stop ordering ≡ Rottweiler.cs:460→469; `StopUrgentAction` branch order
(after-toilet angry before the Frozen gate) ≡ world.py:3054-3079; watering-can dance
(195-199, 748-790) ≡ 1881-1886/2570-2605; `AdvanceToUrgentMove`/`RunToTrickedItem`
startle inversion (moving Right → SurpriseFarLeft) kept at 3417-3418;
`GetLastActiveIndex` wrap arms (RemoveActionAfterUse, IgnoreWoodyWhenUse) wrap in both;
`Mother/Olga.Start` `IsSleeping=false` overrides inert (no level serializes true);
`_detect_common` carries IgnoreWoody/IsSleeping/blocking terms per GameInfo.cs:185-199.
