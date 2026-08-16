# Pass 1 — flag-lifecycle audit: GameInfo, HUD, animation model, bars, dexterity, cursor, inventory, music, zones, level

Scope: GameInfo.cs, HUD.cs, AnimationControllerBase.cs, AnimationInstance.cs, ItemAnimation{Controller,Instance,State}.cs,
PawnAnimation{Controller,Instance}.cs, ProgressBar.cs, HUDProgressBar.cs, DexterityComponent.cs, MouseCursor.cs,
Inventory.cs, InventoryManager.cs, MusicPlayer.cs, HUDAnimation.cs, Zone.cs, ZoneController.cs, Level.cs, Transition.cs
vs runtime/world.py (AnimPlayer, GameState, InventoryState, DexterityState, ProgressBarState, World), runtime/hud.py
(Hud, HudAnim), runtime/viewer.py, runtime/scene.py, runtime/record.py. Every C# line cited was read in source; every
port line verified. README-documented items (trick camera, ExitConfirmation, tutorials/intros, touch-only paths,
Modern mode, settings/menus, StatueAchieved-dead, dexterity FillSpeed-boost-dead, ProgressBar Start-order) are NOT
re-reported as findings.

Counts: **21 divergences** (2 high, 7 medium, 12 low) · 96 fields OK/matching · 41 DEAD · 19 CONFIG · 14 OUT-OF-SCOPE (documented).

---

## DIVERGENCES

### D1 (HIGH) — TimeUp forces a loss; the original preserves `Won`
- C#: `GameInfo.Update` (GameInfo.cs:241-249): `TimeUp = true; FinishGameOnHUDClick();` — **`Won` is not touched**.
  `FinishGameOnHUDClick` (cs:373-390) then branches `if (Won) PlaySuccess(Perfect) else PlayFailedMusic()`, and
  `CalculateRating` (cs:438-465) checks `Won` **before** `TimeUp`: a player who reached `WinningTricksCount`
  (Won=true via `TrickDone`, cs:477-481) and lets the clock run out gets the success jingle and an
  EXCELLENT/GOOD/PASSED band — the TIMEUP band exists only for `!Won`.
- Port: `World._time_up` (world.py:6297-6308) sets `self.game.won = False` unconditionally, then always plays the
  `failed` jingle; `GameState.calculate_score` then lands on 'TIME UP'.
- Failure scenario: L101 with `WinningTricksCount=3`, `TotalTricksCount=4`. Woody plays 3 tricks (Won=true, the
  complete-episode button lights) and idles until 00:00. Original: success music, "PASSED/GOOD" board, level counts
  as won. Port: failed music, "TIME UP" board, loss.

### D2 (HIGH) — the 2.5-s win wait is not guarded by GameEnding
- C#: `WinGameOnCompleteAllTricks` (GameInfo.cs:292-296) sets **`GameEnding = true` immediately** and only then
  waits 2.5 s (`WinGameAnimations` coroutine) before `PlayWinAnimations`. The whole Update block is gated
  `!GameEnded && !GameEnding` (cs:212), so during the wait: no catch can fire, the clock is frozen, HUD buttons and
  the world input are dead (`HUD.CheckClick` GameEnding branch cs:1286-1308, `MouseCursor.UpdateHover` cs:120-124,
  `DrawActionButton` cs:835).
- Port: `World.tick` (world.py:6531-6538) arms `win_timer = 2.5` with `game.ending` still False. For the whole wait:
  the clock keeps draining and runs first in the chain (6515-6521 — it can fire `_time_up` and `return`), the catch
  branches still run (6524-6530 sit *before* the `all_done` elif is even re-evaluated the next frame), and the HUD /
  clicks stay live (hud.py:1181 gates only on `g.ending`).
- Failure scenario: the last trick fires while the neighbour is mid-walk into Woody's zone. Original: the game locks
  the instant `CompletedTricksCount >= TotalTricksCount` is seen and always plays the win. Port: within the 2.5 s the
  neighbour's walk satisfies `can_rottweiler_see_woody` → `_catch` → beating + FAILED board. Same window: a timed
  level at 00:01 when the last trick lands → port plays TIME UP instead of the win.

### D3 (MED) — GameEnded set early on TimeUp / HUD finish: the score screen jumps the finish animation
- C#: `GameEnded` has exactly one write site — `FinishAnimationEnded` (GameInfo.cs:343-345) — reached when Woody's
  Win/Lose single ends (`IsPlayingFinish` → Woody.cs:1119, OnBlockingAnimationEnded → Woody.cs:325-327) or the touch
  skip. `HUD.DrawScore` gates on `GameEnded` (HUD.cs:731), so the board appears only after the finish animation.
- Port: `_time_up` (world.py:6303) and `finish_game_on_hud_click` (6318) set `g.ended = True` immediately, then play
  the finish animation whose `on_end=_finish_animation_ended` re-runs the ended/score/freeze block (double `_score`,
  harmless but confirms the early set is extra). `hud.draw` (hud.py:744) shows the board at once.
- Failure scenario: click complete-episode — original: Woody plays `WinAnimation` first, board after; port: board
  instantly over the still-dancing Woody. Same for TimeUp with `LoseAnimation`.

### D4 (MED) — `GameInfo.DisableProgressBar` event not ported: sleep bars survive the game end
- C#: `FinishAnimationEnded` → `DisableAllProgressBars` (GameInfo.cs:346, 535-541); every active `ProgressBar`
  subscribed in OnEnable (ProgressBar.cs:113) runs `DisableProgressBar` (cs:303-307): `SetSleeping(false)` (drops
  `Pawn.IsSleeping`, restores the HUD idle face and the think bubble) and disables itself.
- Port: `World._finish_animation_ended` (world.py:6284-6289) sets ended/score/freezes routines only. No port code
  references the event (grep `DisableProgressBar|disable_progress` → nothing); `ProgressBarState.tick` keeps running
  from `World.tick` (6473-6474) unconditionally.
- Failure scenario: TimeUp while the neighbour sleeps in the L109 bed — original: bar vanishes, face returns to
  idle under the board; port: the world bar keeps drawing and filling, `is_sleeping` stays true, the sleep face and
  the face-drain overlay persist over the score screen.

### D5 (MED) — the used inventory survives extra world clicks; C# clears it on every non-icon click
- C#: `HUD.CheckClick`'s promotion block (HUD.cs:1319-1322) runs on **every** click past the icons:
  `SetUsedInventory(CurrentInventory)` — `Woody.SetUsedInventory` (Woody.cs:1062-1064) assigns unconditionally, so
  with `CurrentInventory == null` the second and any later world click **resets `UsedInventory` to null** before the
  world processes that click. The used inventory lives for exactly one world click (the promoting one).
- Port: `Hud.check_click` (hud.py:1206-1207) promotes only when `inv.current is not None`; `InventoryState.promote`
  (world.py:1399-1404) leaves `used` alone otherwise. `used` is cleared only on a missed bare-zone click
  (world.py:5384-5388, the ShouldAbortMove arm) or on consumption.
- Failure scenario: select the egg, click the microwave (Woody walks, used=egg), then click the sofa mid-walk.
  Original: the sofa click's CheckClick nulls `UsedInventory`, Woody just examines the sofa. Port: `woody_use(sofa)`
  runs with used=egg → wrong-item refusal (`NoNo`) that the original never shows.

### D6 (MED) — pressed-inventory draw clobbers the tooltip, ignores the hover target, and shows `used` as pressed
- C#: `DrawInventory` (HUD.cs:942-955): only `CurrentInventory` draws the pressed icon, and its per-frame tooltip is
  `SetTooltip(UseWith, name, HoverItem == null ? EmptyUseString : HoverItem.GetNameString())` — hover-aware, and
  routed through `SetTooltip`, which the `ColoredTooltip` latch blocks (cs:1024-1027). `UsedInventory` has no draw
  state at all.
- Port: `_draw_inventory` (hud.py:785-791): `if inv.current is entry or inv.used is entry:` draws pressed **and
  assigns `self.tooltip` directly** to `use + name + with + empty_use` — every frame, bypassing both the hover
  target and the colored latch, and also while merely `used`.
- Failure scenario: select the egg and hover the microwave — original bar: "Use egg with microwave"; port: "Use egg
  with nothing" (the update_hover line from viewer.py:350 is overwritten during draw). After promoting, the latched
  yellow "Use egg with <target>" is likewise overwritten with "…with nothing" each frame.

### D7 (MED) — every world tap latches the colored tooltip in C#; the port latches only after promotion
- C#: the same CheckClick block calls `UpdateTooltip()` (HUD.cs:1321, 1062-1067) = clear latch → `UpdateHover
  (tooltipOnly)` → `MakePermanentTooltip` — which latches whenever `CurrentTooltipState != GoTo` (cs:1069-1075),
  i.e. for **any** tap while hovering an item (Use/LookAt/Examine/Hide/End/UseWith), inventory held or not; the
  follow-up `if (HoverItem == null) ClearPermanentTooltip()` (cs:1324-1327) undoes it only for empty-space taps.
- Port: `check_click` latches only inside `if promoted:` (hud.py:1208-1214), i.e. only when an inventory selection
  was just promoted.
- Failure scenario: click the TV bare-handed — original: "Use TV" flips to the yellow `ColoredTooltipStyle` and
  stays while Woody walks over even as the cursor moves away; port: the line stays white and keeps following the
  hover.

### D8 (MED) — `AnimationControllerBase.Hidden` freezes Refresh in C#; the port only hides the sprite
- C#: `OnGUI` (AnimationControllerBase.cs:172-189) gates `Refresh()` on `!Hidden` — a hidden controller neither
  draws **nor advances**: no frame stepping, no `PlaySound`, no sequence progress, no end delegates. Writers:
  `HideOwnerOnAnimationEnd` (cs:226-229), `Pawn.SetHidden` (Pawn.cs:1464-1467), the transit hides
  (Pawn.cs:1615-1635, 1661), `RoutineActionUse` mutex/span-of-use hides (RoutineActionUse.cs:174-177, 213-216).
- Port: `render.draw_sprite` skips hidden sprites (render.py:106) but `World.tick` ticks **every** AnimPlayer
  (world.py:6462-6463); `AnimPlayer` has no hidden gate.
- Failure scenario: a `HideOwnerDuringUse` span-of-use action (RoutineActionUse.cs:213-216): in C# the hidden user's
  use sequence is frozen at its first element and the action ends on its serialized Duration; in the port the
  sequence advances invisibly and ends the action at its drain — different action timing wherever
  Duration ≠ sequence length, and frame-keyed sounds of hidden animations still play in the port (silent in C#).
  (The mutex parks are unaffected — looping either way.)

### D9 (MED) — `PrevAnimState` is never written in C#: bare singles always stand facing DOWN; the port stands by facing
- C#: the only write is PawnAnimationController.cs:165-172 — `if (CurrentAnimation.Type == Looping)` **after**
  `base.PlaySingleAnimation`, but `SetAnimation(state, Single)` → `GetAnimation` (cs:137-151) only ever returns an
  instance with `Type == Single` (the type filter is strict; `IgnoreAnimationType` is set only by the dev-only
  `PlayTestSequence`). The guard is therefore never true and `PrevAnimState` stays `default(AnimationState)` =
  `Walk_Down` for the life of the controller. `SwitchToStandAnimation` (cs:84-135) uses `PrevAnimState` whenever a
  Single is current (`IsPlayingSingleAnimation`), so **every bare single that falls through to the stand switch
  plays `StandDownAnimation`** — the facing-matched switch arms are reachable only through the direct
  `SwitchToStandAnimation` calls made while a looping walk is current (Pawn.cs:1025, 1070, …).
- Port: `Pawn._stand_name` (world.py:410-417) always resolves the last movement facing through the `Stand*` map.
- Failure scenario: Woody runs left, plays the `NoNo` refusal (a bare single, no callback): original snaps to the
  front-facing stand; port stands facing left. Cosmetic but systematic on every bare single (NoNo, WhatsUp, idles).

### D10 (LOW) — `HUD.OnInventoryAdded`'s auto-scroll to the newest item dropped
- C#: `OnInventoryAdded` (HUD.cs:898-905): when `Count > InventoryRects.Length`, `DisplayedItemsBegin = Count −
  Rects.Length` — the page jumps so the just-picked item is visible; `OnInventoryRemoved` (cs:907-914) down-clamps.
- Port: `InventoryState.add` (world.py:1374-1376) doesn't touch paging; `_draw_inventory` only down-clamps
  (hud.py:770-771 — the removal half).
- Failure scenario: holding 5+ items (searchable S2 levels), a new pickup lands on page 2 with no visible change;
  the original scrolls to it.

### D11 (LOW) — FinishGame cleanup partial: description bubble and the cake prop
- C#: `FinishGame` (GameInfo.cs:358-371) always runs `Rottweiler.SetHoldCake(false)` (cs:362) and
  `HUD.ShowDescription = false` (cs:366) on every ending path.
- Port: `show_description = False` only in `_catch` (world.py:6205); `_time_up`, `_win`,
  `finish_game_on_hud_click` leave it; `holding_cake` (world.py:327, 440) is never cleared at game end (no port
  counterpart of cs:362).
- Failure scenario: a refusal bubble on screen when the clock expires stays drawn under/over the ending; a
  pie-carrying neighbour keeps the `WalkPie_*` set during the catch walk-over (original switches to plain walk).

### D12 (LOW) — `Woody.PlayFinishAnimation`'s deferral latch (`ShouldPlayFinish`) unported
- C#: Woody.cs:1104-1118 — mid-door-pass or hiding, the finish is deferred (`ShouldPlayFinish=true`, replayed at
  Woody.cs:331/490); `IsPlayingFinish` marks the playing single for `FinishAnimationEnded` (cs:325-327).
- Port: `_play_finish_animation` (world.py:6332-6346) plays immediately regardless of transit/hiding state.
- Failure scenario: the clock hits zero during Woody's door pass — original waits for the arrival, then plays the
  lose pose; port plays it mid-warp (sprite hidden/off-door), then `_finish_animation_ended` fires as usual.

### D13 (LOW) — zone graph rebuilt on unlock; C# adjacency is frozen at Start
- C#: `ZoneController.Start` (ZoneController.cs:8-28) builds `Zone.Neighbors` once from `(!Locked || TemporalLock)`
  doors; `Door.Unlock` (Door.cs:198-207) never adds an edge. TemporalLock ships only in the three Intro scenes; the
  28 playable levels' runtime-unlocked doors (L201 ships 3 `DoorsToUnlock` uses, RoutineActionUse.cs:392) never
  become path edges — only direct own-zone door clicks cross them.
- Port: `unlock_door` calls `level._build_graph()` (world.py:4808-4819), so `find_path` gains the link.
- Failure scenario: L201 after the unlock — clicking a target two zones away through the unlocked door: original
  finds no path (click swallowed / other route); port routes through the door in one click.

### D14 (LOW) — detection predicates lack the `CurrentAction != null` gate
- C#: both `CanRottweilerSeeWoody` branches and `CanMotherSeeWoody` require
  `ActionManager.CurrentAction != null` (GameInfo.cs:183, 187, 196) — no detection while no action is current
  (the initial 1.5-s DelayStart, single-frame gaps between actions).
- Port: `can_rottweiler_see_woody` / `can_mother_see_woody` (world.py:6163-6166, 6187-6189) only require the
  routine object to exist.
- Failure scenario: marginal — a Woody standing in the neighbour's start zone could be caught during the first
  1.5 s in the port; no shipped level spawns them together, so impact is theoretical.

### D15 (LOW) — angry-meter 0.1-s repaint throttle dropped
- C#: `DrawAngryMeter` recomputes `AngryMeterFullRect`/`AngryMeterFullUVRect` only when
  `Time.time − LastUpdateAngryMeterTime > 0.1` (HUD.cs:1242-1247) — the fill moves in 10-Hz steps.
- Port: `_draw_angry_meter` (hud.py:868-877) recomputes every frame; `LastUpdateAngryMeterTime` has no equivalent.
  Purely visual smoothness difference.

### D16 (LOW) — the tooltip is never cleared per frame: stale line over the ending
- C#: `DrawHUD` clears `Tooltip = string.Empty` after drawing unless latched (HUD.cs:646-649); with `GameEnding` the
  hover stops writing and the (unlatched) line disappears next frame.
- Port: no per-frame clear; during play `update_hover` overwrites each frame, but once `game.ending` is set the
  viewer skips `update_hover` (viewer.py:345) and `hud.tooltip` freezes at its last value, drawn over the ending
  and the score screen. (A *latched* line persists in C# too — only the unlatched case diverges.)

### D17 (LOW) — cursor and hover read `used` where C# reads `CurrentInventory` only
- C#: `UpdateMouseOver` (MouseCursor.cs:189-198) and `UpdateCursor` (cs:362-373) branch on `CurrentInventory`; after
  promotion (Current=null, Used armed for its one click) the cursor reverts to the item icon and the tooltip to the
  plain arms — the yellow latch carries the "Use X with Y" message.
- Port: `update_hover` uses `held = current or used` (hud.py:540) and `update_cursor` `current or used`
  (hud.py:644) — the use-inventory cursor and the UseWith line persist while `used` is armed (which, per D5, is
  longer than in C#). The port comment on hud.py:643 ("reads CurrentInventory") contradicts its own code.

### D18 (LOW) — inventory hover-bubble details
- C#: the 1-s hover bubble draws only when `DescriptionString` is non-empty (HUD.cs:991); hovering a non-selected
  icon with nothing held also writes the "Use X with nothing" tooltip line (cs:962-967).
- Port: `_draw_inventory` draws the bubble after 1 s with `desc or name` fallback (hud.py:818-819 — bubble with the
  item's *name* where C# shows none), and the icon-hover branch sets no tooltip (hud.py:792-793).

### D19 (LOW) — `Invoke` slot vs per-timer closures (latent)
- C#: `InvokeMethodForSetPrime` / `InvokeHideObjectDuringUseTricked` (GameInfo.cs:513-533) store the target in the
  single `ObjectToPrime`/`ObjectToHide` field — two overlapping invokes both act on the **last** stored item.
- Port: `call_later` closures capture their own item (world.py:2490, 2533, 2541, 5158-5160). The zero-delay
  immediate branch matches C# exactly (RoutineActionUse.cs:262-297). Divergent only if two delayed
  primes/hides ever overlap — none observed in the data; latent.

### D20 (LOW) — `forcewin` differs from `ForceWinGame`
- C#: `ForceWinGame` (GameInfo.cs:315-321): `CompletedTricksCount = Total; FinalTrickScore = 100; Won = true;
  WinImmediate = true` — rating 100 and `PlayWinAnimations` fires without the 2.5-s wait (Update cs:228-235).
  Only caller is the tutorial `LevelScript` (LevelScript.cs:191).
- Port: record.py:145-149 sets `completed = total; won = True` only — the score is computed from the real trick log
  and the 2.5-s wait still runs. Debug-surface only; noted for completeness since the port names it after the
  original method.

### D21 (LOW) — `ShouldStopAction` stale-latch quirk dropped
- C#: `PlayLoopingAnimation` (AnimationControllerBase.cs:344-348) nulls the sequence but leaves a pending
  `ShouldStopAction=true` latched; the next bare single's end then fires a stale `ActionManager.StopCurrentAction`
  (cs:234-247).
- Port: `play_looping` clears `on_end` (world.py:117-119), so the stale stop can never fire. The port is "saner",
  but it is a semantic difference from the source-of-truth in the interrupt-during-last-element window.

---

## Per-field tables

Verdicts: **OK** (write/read sites match), **DIV#** (see numbered divergence), **DEAD** (no reader/writer in the
shipped code — set-and-never-read or never-set; safe on both sides), **CONFIG** (serialized constant, consumed from
data), **OOS** (out of scope: documented unported subsystem — menus, tutorials/intros, trick camera, touch-only,
Modern mode, persistence).

### GameInfo (GameInfo.cs)

| Field | C# writes | C# reads | Port | Verdict |
|---|---|---|---|---|
| TotalTricksCount | config | Update:226, InitializeTricks, CalculateScore | GameState.total; hud._tricks | CONFIG/OK |
| WinningTricksCount | config | TrickDone:477, HUD:787,1355 | GameState.winning; hud.py:843,1237 | CONFIG/OK |
| CompletedTricksCount | Awake:152=0, ForceWinGame:317, TrickDone:473,475 | Update:226, CalculateScore:400-426, SaveScore, HUD DrawButtons:787, DrawTricks:1202-1218, CheckClick:1355 | GameState.completed (trick_done world.py:1468-1478; linked pair via _on_trick_done 4270-4292 matches Item.cs:2121-2153) | OK |
| TimeMinutes | config | InitializeTime:173 | game_info.time_minutes | CONFIG/OK |
| TimeSeconds | InitializeTime:173/177, Update:243(−dt),253(+dt) | Update:241,244 `(int)<=0`, HUD DrawTime:1124 | GameState.time_seconds; tick 6515-6523 (same `int()<=0` cast, same `>0` gate); hud._draw_time 926 | OK (but the count-down runs during the win wait — D2; the `IntroAnimation.Finished` clock gate cs:237 belongs to the unported title cards — OOS) |
| GameEnding | WinGameOnCompleteAllTricks:294, FinishGame:367 | Update:212 gate; HUD:835,944,962,982,1286,1337; MouseCursor:78,120; Woody:321; TutorialScript* | game.ending — written in _catch/_time_up/_win/finish_game_on_hud_click; read tick:6511, hud.py:639,792,839,857,1181, viewer:238,345 | **DIV2** (not set at win-wait start) |
| GameEnded | FinishAnimationEnded:345 | Update:212, HUD DrawScore:731, CheckClick:1288, Woody:321, TutorialScript* | game.ended — _finish_animation_ended:6286 **and** early in _time_up:6303 / finish_game_on_hud_click:6318 | **DIV3** |
| Won | ForceWinGame:319, OnNeighborCaughtWoody:325=F, OnMotherCaughtWoody:335=F, TrickDone:479=T | FinishGameOnHUDClick:382, CalculateRating:441, SaveScore:435, Woody.PlayFinishAnimation:1120 | game.won — _catch:6202=F, trick_done:1478=T, hud check_click:1239=T, **_time_up:6301=F (extra write)** | **DIV1** |
| TimeUp | Awake:153=F, Update:246=T | CalculateRating:443 | game.time_up (tick:6519; calculate_score:1460) | OK |
| Rottweiler/Woody/Olga/Mother/Instance/GameCamera/LevelScript | wiring refs | everywhere | world.pawns / world.woody / snap_camera | OK (wiring) |
| EntryLevel/FinalCutScene | config | CheckClick:1298 / menu flow | — | OOS (menus) |
| GameMode | config (Classic in all 31 scenes) | Update:212, HUD:733,770,1288 | port is Classic-only | CONFIG (documented) |
| CompoundTrickScore | config=4; **CalculateScore:398 overwrites** (`= AngryCountTicks` when smaller, non-tutorial) | CalculateScore:396-400 | calculate_score:1447-1451 uses a local `compound` — non-destructive; called once per game in both | OK (write-site differs, observable state identical — CalculateScore runs once per ending) |
| CoinScore/LifeScore/StatueScore/TimeScore/StartTimeScore/MaximumRating | config | Final* family never computed (Modern leftovers); MaximumRating read :402,422 | min(final,100) ported (1456) | CONFIG (Modern parts DEAD) |
| Alerter | Alerter.Start:46 (last pet wins) | Item.OnIconPressed:2194, Item:2446, LevelScript:179 | port wakes **all** FSMs (world.py:4882-4883, 4917-4919) | OK-minor (single-pet levels; noted under D-none) |
| StatueAchieved | OnStatueAchieved:486 ← Rottweiler.cs:691 | none | not modeled | DEAD (documented) |
| CompoundTricks | OnCompoundTrickDone:491 ← Item.cs:2165 | none | game.compound_tricks (world.py:3983) | DEAD-write parity (both count, neither reads) |
| FinalTrickScore | ForceWinGame:318=100, TrickDone:476 += | CalculateScore:401 | GameState.log/sum (1476, 1451) | OK (forcewin=100 not ported — D20) |
| FinalCompoundTrickScore | CalculateScore:400 | :401 | local in calculate_score | OK |
| FinalViewerRating | CalculateScore:401-424 | :402-427, SaveScore, (HUD shows ViewerRating string) | game.final_viewer_rating:1456; jingle pick 6326-6328 mirrors PlaySuccess(Perfect) | OK |
| FinalTimeScore/FinalCoinScore/FinalLifeScore/FinalStatueScore/FinalTotalScore | never written | never read | — | DEAD (Modern) |
| TrickRatio/ViewerRating/Rating | CalculateScore:406-427, CalculateRating:445-463 | HUD DrawScore:736-738 | game.trick_ratio/viewer_rating/rating (1457-1466); hud._draw_score 1146-1160 re-attaches the GO_TRICKS/GO_VIEWER_RATING label halves and localizes the rating keys | OK |
| Perfect | CalculateRating:440=F,455=T | FinishGameOnHUDClick:384, SaveScore:435 | no field; `final_viewer_rating >= 100` at the jingle (6327) — same value CalculateRating derives it from | OK (note: C# PlayWinAnimations hard-codes `PlaySuccess(perfect:true)` cs:312 — port _win plays 'success_perfect' 6360, matching) |
| WinImmediate | ForceWinGame:320 | Update:228 | not ported (record forcewin waits 2.5 s) | OOS/D20 (tutorial-only caller) |
| EXCELLENTMSG…GO_VIEWER_RATING | LoadLocalizationData:160-166 | CalculateScore/Rating | RATING_KEYS + loc() in hud.py:30-32,1146 | OK |
| LinkedTrick | Item.cs:2128,2134,2141 | TrickDone:470-474 | game.linked_trick (1472-1474; writes 4279,4283,4288) | OK |
| DontShowAngryCount | config | HUD DrawAngryCount:667 | game.dont_show_angry_count; hud.py:1131 | CONFIG/OK |
| TextureAux | never | never | — | DEAD |
| TotalTricksDoneSoFar | never | never | — | DEAD |
| SnakeAux208 | Item.cs:1556=T | Item.cs:1402 | world.snake_aux_208 (3890; used in the L208 chain) | OK |
| IgnoreScore | config (false in all levels) | CalculateScore:414 | not modeled (data shows no `true`) | CONFIG/DEAD |
| IsTutorial | config | CalculateScore:396, HUD via Level.IsTutorial | game.is_tutorial (1430; calculate_score:1449) | CONFIG/OK |
| ShowTutorialTextAfterIntro, IsTutorialEnabled | tutorial layer | tutorial layer | — | OOS |
| flagAux | ActionManager.cs:505=T (one-shot) | ActionManager.cs:503 gate | world.flag_aux (3896); Routine.tick 3461-3470 incl. the `InfiniteLoop=false` mutation and `anim_aux` | OK |
| IsTrickCameraOn / StartTrickCamera | Level.Update:367/371; Item RottweilerUse:839 | many (all trick-camera) | — | OOS (documented) |
| IsDexterityOn | DexterityComponent:144=T, 392=F | ControlWindow, Pawn:351, Woody:256, CameraMover | world.is_dexterity_on (3905; DexterityState.start 3555 / cleanup 3697); viewer:223 click mute, hud draw_cursor:671 | OK |
| canSkip / TimeSinceLastTap / TapOnce | OnNeighborCaught:330, Update:257-289 | Update | — | OOS (touch-only skip, documented cs:257-289) |
| gotCaught | Update:218=T | Update:216 | game.got_caught (_catch:6201; gates 6525,6529 — port also latches the Mother catch, superset but unobservable behind GameEnding) | OK |
| ShowInteractionIcon | HUD DrawActionButton:862=T, 893=F | Item.OnGUI:2749 | game.show_interaction_icon (hud.py:858 mouse-hold adaptation; viewer.py:307 draw gate) | OK (documented adaptation) |
| ObjectToPrime / ObjectToHide + Invoke queue | InvokeMethodForSetPrime:521 / InvokeHideObjectDuringUseTricked:515; consumed :525-533 | the Invoke callbacks | call_later closures (world.py:5158-5160, 2490, 2533, 2541); zero-delay branch matches cs:262-297 | OK / **DIV19** (slot overwrite latent) |
| DisableProgressBar (static event) | subscribed ProgressBar.cs:113/120 | fired FinishAnimationEnded:346→537-540 | **no port counterpart** | **DIV4** |

### HUD (HUD.cs) — runtime state

| Field | C# writes | C# reads | Port | Verdict |
|---|---|---|---|---|
| Tooltip | SetTooltip:1029-1055 (gated `!ColoredTooltip`), DrawHUD:648 per-frame clear | DrawHUD:642, DrawTooltip:1088-1092, SetTooltip:1057 | hud.tooltip — written by update_hover (526-618) + _draw_inventory:788 | **DIV6, DIV16** (direct write bypasses the gate; no per-frame clear) |
| ColoredTooltip | MakePermanentTooltip:1073=T, ClearPermanentTooltip:1079=F (← Woody.ClearTooltip 1130-1132, CheckClick:1326, UpdateTooltip:1064) | SetTooltip:1026 gate, DrawHUD:646, DrawTooltip:1086 | hud.colored_tooltip (update_hover gate 536; check_click 1209-1214; world clears 5378, 5826, 5291, 5371) | **DIV7** (latch only on promotion) |
| CurrentTooltipState | SetTooltip:1028 | MakePermanentTooltip:1071 | implicit (`if self.tooltip` at latch time) | OK-equiv |
| InventoryHoverStart / HoverInventory | DrawInventory:1014-1015 set; :1020 reset IT_NONE | :989-991 (1-s gate) | hover_index / hover_started (hud.py:796-825; reset 823-825) | OK (keyed by index vs type — equivalent) |
| InventoryHoverStartDelta | never | never | — | DEAD |
| DisplayedItemsBegin | OnInventoryAdded:902, OnInventoryRemoved:911, CheckDisplayedItemsBegin:920, CheckClick:1330/1347 | DrawNavigationArrows:808-809, DrawInventory:940+, CheckClick:1309-1345 | displayed_begin (hud.py:162; paging 1215-1222; draw-clamp 770-771) | **DIV10** (add-scroll missing) |
| ShowDescription | ShowItemTooltip:706=T; GameInfo.FinishGame:366=F; Woody.MoveToGoal:773=F | DrawHUD:636 | show_description (hud.py:170, 501; world 648 MoveToGoal, 6205 catch) | **DIV11** (other endings don't clear) |
| DescriptionString/DescriptionPosition/UseLongDescriptionBubble | ShowItemTooltip:707-709 | DrawDescription:684-699 | desc_string/desc_pos/desc_long (496-524; big-bubble pick per LongDescription = HUD.cs:687-696) | OK |
| MousePosition / MouseDelta | DrawHUD:635 (=Input.mousePosition+MouseDelta); MouseDelta never written | all PointInRect tests | hud.mouse (draw arg); MouseDelta dropped | OK / MouseDelta DEAD |
| LastClickCheckTime | CheckClick:1313,1319 | never (CheckClickDelta const unused) | not ported | DEAD |
| IsButtonDownMouseLeftPressed | Update:388-392 | never | not ported | DEAD |
| OnlyOnce (+InvManager.FirstInventoryItem) | DrawInventory:972-974 | :972 | not needed (icons/strings resolved at load) | OK-equiv |
| EndGame / SneakPressed / TricksDone / TricksRequired / TricksTotal / StatueIndex | Start:370 (SneakPressed) or never | never | — | DEAD |
| AngryMeterFullRect/UVRect, AngryMeterOriginalHeight/Top, LastUpdateAngryMeterTime | AdjustRectangles:570-571; DrawAngryMeter:1244-1246 (0.1-s throttle) | DrawAngryMeter:1248 | _draw_angry_meter (hud.py:868-877) per-frame | **DIV15** |
| WhistleAnim / WhistleRects | InitializeHUDAnims:417 (paused frame 0), PlayWhistle:1480 ← Item.cs:2167, Rottweiler.cs:690; per-frame rect averaging Start:353-357 | DrawAngryMeter:1250-1251 | whistle_anim (hud.py:139, play_whistle 694-701 incl. sound; callers world.py:3986, 4124; breathing rect 884-889) | OK |
| TrickAnim | PlayTrickDone:1389 ← Woody.cs:1147 ← GameInfo.TrickDone:469 | DrawTricks:1204,1214-1219 | trick_anim (play_trick_done 680-684, wired via game.on_trick_done; draw 896-912 incl. the hide-last-coin rule) | OK |
| StatueAnim | InitializeHUDAnims:419 (frame 0 grey), PlayStatueAchieved:1394 ← Item.cs:2166, Rottweiler.cs:689 | DrawTricks:1221-1222 | statue_anim (139; restarts world.py:3985, 4123; draw 913-917) | OK (resting grey documented) |
| Woody/Rottweiler/MotherActiveAnim + the strips | InitializeHUDAnims:415-435 (only 3 idles started), Play*():1397-1466 with Restart(→idle) | DrawCharacters:1151-1191 | woody_active/rott_active/mother_active state machine (hud.py:157-161, 937-1009); sleep/blind picked by pawn.is_sleeping/hud_blind from ProgressBar.SetSleeping; angry via play_rottweiler_angry; return-to-idle on `finished` | OK (all sleep/blind strips ship `Looping=true`, so C#'s Restart(→idle) callback and the port's park behave identically; angry/laugh strips non-looping → both return to idle) |
| CompleteEpisodeAnim | PlayCompleteEpisodeEnabled:1470 ← GameInfo.TrickDone:480 | never drawn (not in InitializeHUDAnims; no Frame read) | not modeled; button enabled by `completed >= winning` (hud.py:843) = C# DrawButtons:787 | DEAD (anim), OK (button) |
| MotherAngryAnim / PlayMotherAngry | never called | — | not modeled | DEAD |
| DisableRottweilerThinkBubble / DisableMotherThinkBubble | Start:333-334=F; ProgressBar.cs:193/198/217/222 | DrawCharacters:1155,1176 | pawn.hud_disable_think (ProgressBarState.set_sleeping 3801; hud.py:979,1004) | OK |
| TooltipRect←TooltipMotherRect | InitializeCharacters:613 | DrawTooltip | hud.py:731-732 | OK |
| HasFingerPressed / TimeSinceLastFingerPressed / CanClickMobile / touch | Update:411-412, CheckClick:1375-1383 | CheckClick tail | port models the short-tap arm (`return False`, hud.py:1252) | OOS (documented touch path) |
| CheckClick flow | :1282-1385 | — | check_click (hud.py:1174-1252): score branch, icon select (OnIconPressed moved from the per-frame DrawInventory poll at cs:944 to click time — same outcome), promote, prev/info/sneak/next/power/complete/faces | OK except **DIV5** (unconditional `SetUsedInventory(Current)` dropped) |
| Buttons draw | DrawActionButton:812-896 (hover art touch-only; sneak pressed = MbSneakToggle:879) | — | hud.py:833-859 (mouse hover shows textures[0] — desktop adaptation; sneak pressed = sneak_toggle; info hold = mouse-down) | OK (documented desktop adaptation) |
| DrawScore | :712-765 (GameEnded gate, hover style swap) | — | _draw_score (1139-1171) + check_click restart/ok (OK button = level-select, unported) | OK/OOS (menus) |
| DrawTime/DrawTricks tutorial gate | :652-656 | — | hud.py:740-742 | OK |
| DrawLives / NewScoreboard / WoodyLives | Modern only | — | — | DEAD (Classic everywhere) |
| TrickCameraHUD / TrickCameraBackground | :1483-1490 | — | — | OOS |

### AnimationControllerBase (AnimationControllerBase.cs) → AnimPlayer (world.py:12-263)

| Field | C# lifecycle | Port | Verdict |
|---|---|---|---|
| AnimationSequence / SequenceIndex | PlayAnimationSequence:318-324 (reset, Alternate=null), PlayNextSequenceAnimation:254-299 (index++, null past end), PlayLoopingAnimation:346 (null) | seq/seq_index (play_sequence 122-137, _next_seq_anim 139-155, play_looping 117) | OK |
| SequenceOverride | SetSequenceOverride:251; consumed :256-260 | seq_override (157-160, 144-146; port clamps, C# would throw OOB — unused with bad values) | OK |
| CurrentAnimation | SetAnimation:350-371 (throws on miss; strict name+type match) | sprite.current via _set (82-96; throws on missing **name**; `mode` forced per call instead of the type-filtered lookup) | OK-equiv (0 duplicate names per sprite in data; port permissive where C# would throw on a name-with-wrong-type — no data hits) |
| PrevAnimState | only write PawnAnimationController.cs:170 — dead (see D9); read SwitchToStandAnimation:99 | facing-based _stand_name | **DIV9** |
| animationTime | Refresh:105-106, ResetAnimationTime:144-151 (+1/FrameRate, ×SlowAnimationsFactor) | acc (tick 228-263, slow_factor) | OK (verbatim; sound-before-advance order matches :110-111) |
| OnAnimationEnded / OnBlockingAnimationEnded | SetSingle/BlockingAnimationEndedDelegate; fired StopSingleAnimation:236 (skipped when ShouldStopAction) | single_end_hook (persistent: items 3933, Woody 6044) + per-call `on_end` wrappers (`as_sequence=False`) | OK (port fires single_end_hook at sequence ends too where C# skips — hooks are name-guarded (world.py:4552-4558, 5721-5731), no observable effect found) |
| OnAnimationSequenceEnded | Set…:92-95; fired :243 (Rottweiler's includes IsPlayingWoodyHit→FinishAnimationEnded, Rottweiler.cs:448-455) | seq_end_hook (212-216, Rottweiler only, README-documented); the hit sequence's `on_end=_finish_animation_ended` (6251-6252) | OK |
| OnLastSequenceElementPlaying | :97-100; fired :293-296 when the last element starts | last_element_hook (153-154) | OK |
| AlternateOnSequenceEnded | PlayAnimationSequence(seq,alt):312-316; nulled :320; fired :243 first | modeled by `on_end` callback | OK (port fires seq_end_hook before cb even when C#'s Alternate would return true and skip OnAnimationSequenceEnded — Rottweiler-only hook, no wired conflict found) |
| ShouldStopAction | PlayNextSequenceAnimation:292=T (last element), StopSingleAnimation:242=F | consumed as `on_end` firing at drain | OK / **DIV21** (stale latch across PlayLoopingAnimation dropped) |
| IgnoreAnimationType | PlayTestSequence:308 only | not ported | DEAD (dev) |
| IgnoreInfiniteLoop / IgnoreInfiniteLoopOnce | SetIgnoreInfiniteLoop:208-211, SetIgnoreInfiniteLoopOnce:213-217; auto-clear Refresh:124-127 | ignore_infinite / ignore_infinite_once (43-44, 246-252 — same clear point, before hold/stop) | OK |
| Hidden | StopSingleAnimation:226-229 (HideOwnerOnAnimationEnd), Pawn.SetHidden:1464-1467, transit Pawn.cs:1615-1661, RoutineActionUse:174-177/213-216/481-484; **read OnGUI:177 — gates draw AND Refresh** | sprite.hidden (render skip only, render.py:106; AnimPlayer always ticks, world.py:6462) | **DIV8** |
| OnSequenceIndexChange (static event) | fired :285-288 after index++/stamps; subscriber Item.cs:2681 (EnableAnimationIndexControl) | seq_step_hook → Routine._seq_step_hack (1587-1606: post-increment stamp `idx+1`, _anim_index_control) | OK |
| ChairAssembly / TowelSleep name-hacks | :261-275 (pre-increment SequenceIndex==1; TowelSleep InfiniteLoop=true) | _seq_step_hack 1598-1606 | OK |
| Item.CurrentSequenceIndex stamp | :277-284 (Rottweiler/Mother owner → post-increment) | 1594-1595 | OK |
| ActionManager / Owner / spriteSheet* / UseNFH2Sounds / AnimationMaterial / BaseAnimationPath / DeltaLocation / AnimationGUIDepth | wiring/config (AnimationGUIDepth is runtime-reassigned by behaviors — README-documented, re-sorted per frame) | sprite.depth | CONFIG/OK |

### AnimationInstance (AnimationInstance.cs) + Item/PawnAnimationInstance

| Field | C# lifecycle | Port | Verdict |
|---|---|---|---|
| CurrentFrame / CurrentFrameIndex | SetStartFrame:217-226, AdvanceFrame:206-215, LoopToStartFrame:186-195, hold snap Refresh:132; CurrentIndex:66-76 | frame/pat_idx (68-79, 178-193); `cur_frame` clamped to `end` for draw (186) — C# can draw overrun frames in the delegate-handled-no-switch corner; pathological in both | OK |
| InfiniteLoop | config; **mutated** ACB:274 (TowelSleep→true), ActionManager:507 (OlgaWCUse→false) | anim.infinite; both mutations ported (1606, 3469) | OK |
| Type | config; never mutated; consumed via the strict GetAnimation type filter | `mode` per play call | OK-equiv (see ACB.CurrentAnimation note) |
| FrameRate = -1 | ResetAnimationTime:146 → negative accumulator → one frame per Refresh | `fps or 10.0` keeps −1 → same negative-acc advance; **but all 12374 shipped animations have FrameRate > 0** | CONFIG/DEAD |
| HoldOnLastFrame | Refresh:128-134 (parks; never advances a sequence; non-pattern snaps to EndFrame) | 253-257 | OK |
| Blocking / HideOwnerOnAnimationEnd / ShowChildRenderersOnEnd | read IsPlayingBlockingAnimation:398-401, StopSingleAnimation:226-233 | blocking:162-165, hide_owner_on_end/show_child hook 206-209 | OK |
| StartFrame/EndFrame/Sheet*/Pattern/PatternFile/Sounds/DeltaLocation/Original* | config (PatternFile resolved by the exporter — documented) | scene.py anims | CONFIG |
| AlternateStartFrame / OverridesTransformation | data, no reader | — | DEAD (documented) |
| ItemAnimationState | pure enum | strings | CONFIG |
| ItemAnimationController.LoadTexturesAsynchronously / PawnAnimationController Search*/Log* | loading/debug | — | DEAD/CONFIG |
| PawnAnimationController Stand*/WaitWatch/WaitInFear | config, SwitchToStandAnimation:100-134 | spec['stand'] map (scene.py:1865, world.py:391,410-417) | OK (facing source differs — D9) |

### ProgressBar (ProgressBar.cs) → ProgressBarState (world.py:3721-3831) / HUDProgressBar

| Field | C# lifecycle | Port | Verdict |
|---|---|---|---|
| Visible | Start:77=F, SetSleeping:179, RestoreVariables:293 | OnGUI:258, HUDProgressBar:14 | visible (3734, 3797, 3816); draw hud.py:1063-1091, 1018-1033 | OK |
| Progress | Start:78=0, Update:157/161, Restore:294 | OnGUI:260-269, GetProgress | progress (3735, 3783-3786, 3817) | OK |
| ExecutedOnce | =T decl/Restore:295; SetSleeping:177=F | Update:151 (first-entry SetSleeping(true)) | executed_once (3736, 3781-3782, 3796, 3818) | OK |
| ExecuteOnce2/3/4 | Restore:296-298=T; Update:127/136/166=F | Update:125/134/164 (CanSee/urgency and out-of-window kills; non-Mother210 → SetActive(false)) | execute_once_2/3/4 (3762-3791) — same order: kill checks first, then the window | OK |
| SecondsCount | Update:150 +=dt; Restore:299 | Update:155-157 | seconds (3780, 3822) | OK |
| StopProgressBar | StopForUrgency:236=T; Restore:300=F | Update:125,134 | stop_progress (3806, 3823) | OK |
| enabled/SetActive latch | Item.Use SetActive(true) → OnEnable → RestoreVariables + resubscribe (cs:108-114; activation sites Item.cs:831-834, 861-864, 1110-1113, 1322-1325); kill = SetActive(false) until the next use re-arms | active (3732); World.activate_progress_bar (3966-3976) restores only when inactive — same as OnEnable running only on the inactive→active edge | OK (the README's "kills … for the level" overstates both sides equally — the next use re-arms in C# and in the port) |
| event subscriptions | OnEnable/OnDisable pair (IsMotherUrgentAction/Stop) | subscribed once in __init__ (3746-3747), never unsubscribed — an inactive bar can still receive stop/resume, but restore() + the active gate make it a no-op | OK-equiv |
| DisableProgressBar handler | GameInfo event → SetSleeping(false)+disable (cs:303-307) | **missing** | **DIV4** |
| SetSleeping side-effects | HUDProgress.enabled, Pawn.IsSleeping, HUD Play*Sleep/Blind/Idle + think-bubble flags (cs:175-225) | set_sleeping (3793-3801): visible, pawn.is_sleeping, hud_blind, hud_disable_think; face swap in hud.py:944-963, 985-996; fill overlay _face_fill (1011-1033) with the menu hide (world.menu_open = InGameMenu events) | OK |
| PawnHUDRect / SelectedHUDTexture / IsPawnHUDAnimation | Start:82-105 (RottweilerFaceRect copy — Start-order documented) | spec + hud rect at draw | OK (documented) |
| IndexOfSequenceAnimation / SelectedPawn / Mother210 / rects / DataStyle | Update:143; Start; config | _check_state (3825-3830), pawn property, mother_210 | OK/CONFIG |
| HUDProgressBar.Visible | menu Hide/Show (cs:23-43) | _face_fill's `world.menu_open` gate (hud.py:1016) | OK |

### DexterityComponent (DexterityComponent.cs) → DexterityState (world.py:3526-3718)

| Field | C# lifecycle | Port | Verdict |
|---|---|---|---|
| enabled | armed by Item.CanWoodyUse's dexterity gate; CleanUp:393=F | enabled (3535, 3554, 3698; gate world.py:5658+) | OK |
| PercentageDone | StartDexterity:147=20; FixedUpdate:254 += sway; floor 267=12 | percent (3556, 3616-3621) | OK |
| FillSpeed | CheckMargins=1.2 (dead — FixedUpdate:243 resets to 1 before the drain) | fill_speed always reset (3605) | OK (documented dead boost) |
| FirstTimeOnly | Start:148=F; FixedUpdate:233-236 | first_time (3537, 3600-3601) | OK |
| RottInAnimation | DexterityAlert:424=T | SearchItem.cs:245-251 / TrickItem.cs:243-249 watchers | rott_in_animation (3539, 3718; consumed world.py:6479-6490) | OK |
| StartDexterityAgain | LoseDexterity:365, WinDexterity:386, FixedUpdate:205-208 (runs only while enabled — the re-click re-arms) | start_again (3540, 3588-3590, 3683, 3691) | OK |
| UpdateAux | one-shot cancel on CanSee (FixedUpdate:210-215); never reset | update_aux (3541, 3591-3596) | OK |
| Margin fields / rand vector / rects | CheckMargins:273-339, UpdateRandomMovement:341-359, StartDexterity rect math (int division) | _check_margins (3638-3663), _random_move (3625-3636), start (3562-3576) | OK |
| wrong (BackgroundTexture swap) | CheckMargins/Restore | wrong (3542, 3646-3658, 3699) | OK |
| initialized/timer | one skipped FixedUpdate at start | not modeled (one 1/60-s tick) | OK-negligible |
| Camera freeze / cursor lock | StartDexterity:170-171, CleanUp:400-401 | viewer freezes camera & mutes clicks on is_dexterity_on (documented) | OK |
| Win/Lose side-effects | WinDexterity:369-388, LoseDexterity:361-367, CleanUp:390-406 | _win/_lose/cleanup (3665-3705) incl. DexterityCannotLose floor, N2TrickItemUseNormal literal (documented), tricked/again flags | OK |

### MouseCursor (MouseCursor.cs) → hud.update_cursor/draw_cursor + viewer hover

| Field | C# lifecycle | Port | Verdict |
|---|---|---|---|
| CurrentTexture | UpdateHover:122 (ending/menu → DefaultHUD), UpdateCursor:350-403, OnGUI draw | cursor_tex (hud.py:626-665; draw_cursor 667-678) | OK except **DIV17** (`used` in the held branch) |
| IgnoreRender | Start:46=T forever — the mobile build never draws the cursor | port draws (desktop reference) | OK (adaptation; mobile path dead) |
| Woody.MouseOverHUD | UpdateHover:119 (`mousePosition.y < MinMouseY` raw px) | over_hud scaled by H/600 (hud.py:636); viewer HUD-strip swallow (viewer.py:236) | OK (scaling adaptation; equal at 600-height reference) |
| Woody.HoverItem | UpdateHover:150,165 | hud._hover_item (535); world hover pose via on_mouse_hover | OK |
| UpdateMouseOver tooltip arms | :189-347 (incl. MouseOverIcon reloads) | update_hover (526-618) + _swap_cursor_icon (620-624) | OK (README-verified arms) / **DIV17** |
| UpdateCursor arms | :350-403 (held → Use/Cancel icons; item MouseOverIcon w/ CanUse + same-zone-door; far-door walking/locked; zone floor band −0.6..0.16) | update_cursor (642-665) | OK / **DIV17** |
| TextureDeltaLoc / MinMouseY / cursorSize / ShowWindowsCursor | ctor/config | mc spec | CONFIG |

### Inventory / InventoryManager → InventoryState

| Field | C# lifecycle | Port | Verdict |
|---|---|---|---|
| InventoryItems | AddInventory:15-23 (+HUD.OnInventoryAdded per item), RemoveInventory:47-58 (first match, +OnInventoryRemoved) | items (add 1374-1376, remove 1386-1397) | OK / **DIV10** (paging hook) |
| _CurrentInventory | SetCurrentInventory:25-28 (HUD select 1314, promote-null 1322, DrawInventory:958 auto-deselect) | current (check_click 1200, promote 1404) | OK (auto-deselect folded into click-time icon_pressed — same outcome) |
| UsedInventory | Woody.SetUsedInventory (unconditional; CheckClick:1320 every world click; ShouldAbortMove Woody.cs:790; consumed TrickItem.cs:278-283) | used (promote 1403; miss-click clear world.py:5384-5388; consumption 5843-5847) | **DIV5** |
| UseCount | config; TrickItem.cs:278 `--`, removal when `<=0 && !KeepAfterUse && Required != NONE` | use_count (5844-5847) | OK |
| Type / ChangeType / Initialize(reload) | prime conversions (Inventory.cs:138-142) | port converts entries (knife/flowers path documented) | OK |
| Name/Description/WrongZone strings, icons | Initialize:87-136 | _icon_names (703-710), loc() | OK |
| FirstInventoryItem / OneTime | DrawInventory one-shot init | not needed | OK-equiv |

### MusicPlayer (MusicPlayer.cs)

| Field | C# lifecycle | Port | Verdict |
|---|---|---|---|
| OneTime | Start:51 (=T when audio off), PlayLevelMusic:73-76 (first-run 15-s Invoke) | exporter → `delay` 0/15 (scene.py:1286); World._music_timer (3851-3856, 6380-6386) | OK |
| IsEntry | config | entry scenes are menu scenes (not run) | CONFIG |
| PlayCaught/Failed/Success(perfect) | :143-166 (each stops the level track) | _play_jingle (6364-6374) + call sites 6209, 6308, 6326-6330, 6360 | OK (D1 changes *which* jingle on TimeUp-with-Won) |
| PlayEntranceMusic/StopEntranceMusic | IntroAnimation only | — | OOS (title cards) |
| PlayJokeMusic / HoverSound / ClickSound / ChangeVolume | no callers / menu widgets | — | DEAD/OOS |
| EntranceClap | Start:47 | World.__init__ 3852-3854 | OK |
| volume/settings (MusicLevel×AudioLevel) | Level settings | not modeled (settings menu OOS) | OOS |

### HUDAnimation (HUDAnimation.cs) → HudAnim (hud.py:74-119)

| Field | C# lifecycle | Port | Verdict |
|---|---|---|---|
| CurrentFrameIndex/CurrentFrameTime | Initialize:44-45, Update:81-103 (frame times count down; finish backs the index up) | idx/t (87-119) | OK |
| Finished/Paused/Running | Initialize:46-48 (paused), Restart:59-63, Pause/Unpause | finished/paused/running (82-97; initial finished=True vs C# false+paused — Running false either way, Frame 0 either way) | OK |
| OnAnimationFinished | Restart(cb):53-57; fired :93-96 (→ Play*Idle) | modeled by the `finished` checks in _draw_characters (955-966, 988-996) | OK |
| Looping | config; Update:98-101 | 113-118 | OK |

### Zone / ZoneController / Level / Transition

| Field | C# lifecycle | Port | Verdict |
|---|---|---|---|
| Zone.PlayLeft/PlayRight | SetPlayLeft/Right:135-147 ← **Level.Awake's rebuild** (Level.cs:183-209, around the repositioned x) | scene.py:_apply_zone_bounds (1469-1520) incl. the ZoneController offset; consumed as zone.left/right (route clamp world.py:679-681 = Helpers.AdjustEndMoveInZoneArea) | OK (README-documented rebuild; note: it is Level.**Awake**, README says Start — same effect) |
| Zone.HeightDelta / collider size / NameString | Level.Awake:186-198 | 1505-1516 | OK |
| Zone.NoticeOnEnterItems | Add TrickItem.Start:200; Remove TrickItem.cs:679 (CheckDestroyWhenTricked:656-665) | notice_items (3880-3883; removal 4634-4638) | OK |
| Zone.NoticeWhenNearItems | Add :204; Remove :671 | near_items (3885-3888; removal 4639-4642) | OK |
| Zone.Neighbors | ZoneController.Start:8-28 once, `(!Locked || TemporalLock)`; never updated | level.graph (_build_graph 1679-1691) — **rebuilt by unlock_door** | **DIV13** |
| Zone.Cost/Previous | Helpers path-search scratch (Helpers.cs:164-217) | find_path BFS (uniform cost 1 = GetShortestPath) | OK |
| Zone.ZoneEnter/Leave (+Search) | Add* from item Starts; fired Pawn.cs:1617/1630 | _zone_items + zone_reaction (3866-3871, 5139) | OK |
| Zone.Alerter | Alerter.Start:45; read Rottweiler.cs:173,202-204,249-251 | alerters dict keyed by item, zone-matched in the FSM enter/leave hooks | OK |
| Zone.NotifyOnPawnEnter / Children / Actors | never populated / bookkeeping without reads | — | DEAD |
| Zone.ExitZone/EndString/BubbleIcon | config | zone.exit/end_string; MoveOnly bubble icons | CONFIG/OK |
| ZoneController.Zones (static) | Start:10-15 | level.zones | OK |
| Level.Zones*/Start-Entrance offsets | Awake rebuild | scene.py | OK |
| Level.TimedGame/MusicEnabled/AudioEnabled/Music-AudioLevel/TrickCamera/GameLanguage/Sensibility | LoadSettings PlayerPrefs (defaults: timed on, trick camera off) | timed=True hardcoded (world.py:1427); audio always on; camera per README | CONFIG/OOS (settings menu documented) |
| Level.IntroAnimation.Finished | IntroAnimation.cs:82,101,280; gates the clock (GameInfo.cs:237) and FindInput (Pawn.cs:343-355) | no title cards → clock runs from load | OOS (documented Not-implemented; the clock starts a few seconds earlier than the original's card-gated start) |
| Level.CurrentLevel/MusicPlayer/LevelLoader/ExitMessage/MenuLoader/OpenLevelSelection/EscapeAux/IntroAnim | wiring/menus | — | OOS |
| Level.SaveScore / Set* / PlayerPrefs family | CalculateScore→SaveScore:433-436, InitializeLevelsData | no persistence | OOS (menus/save; no reader in the port) |
| Level.OnGUI fences / LoadFenceSize / DisableFences | :244-252, 322-341 | viewer fence pass (documented) | OK |
| Level.IsTrickCameraEnabled / ForceTrickCamera / TrickCameraOnMove | trick camera | — | OOS |
| Level.LevelBehaviors | empty in every scene | — | DEAD (documented) |
| Transition.TransitionDownwards/Upwards | read Pawn.cs:1286-1291 — **only for non-ComplexMove transitions; all 116 shipped transitions are ComplexMove** | not needed (walk-through stairs path) | DEAD (data) |

---

## Additional matching-site notes (no action)

- `GameInfo.Update` order: C# catch→win→clock vs port clock→catch→win — unobservable outside D1/D2's windows
  (C# freezes everything via GameEnding on the same frame either branch fires).
- The Bed-branch of `CanRottweilerSeeWoody` (GameInfo.cs:185) omits the `PassingComplexMove` terms; the port's
  shared `_detect_common` adds them — ComplexMove is Season-2-only and the Bed case is Season 1, so no effect.
- `Item.OnIconPressed`'s gate is `!IsPassingDoor() && !DonePassingToOtherZone` (Item.cs:2177); the port checks only
  `is_warping` (world.py:4867) — the missing NFH2 term is a same-frame corner of the stairs pass.
- `GameInfo.Alerter` is a single slot (last pet's Start wins); the port wakes every FSM — all WakeAlerter levels
  ship one pet.
- `hud.check_click`'s complete-episode arm sets `won=True` explicitly before `finish_game_on_hud_click` — C#'s Won
  is already true whenever the button is active (TrickDone:477-481); redundant, not divergent.
- `_catch` computes the score at `_finish_animation_ended` instead of C#'s FinishGame-time CalculateScore — inputs
  (AngryCountTicks, counts) cannot change during the hit sequence; identical output.
