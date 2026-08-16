# Verified: items (Item family flags, Woody's use side)

Area: `runtime/scene.py` class Item (spec loading, kind, flags),
`runtime/world.py` `_can_woody_use` / `_dexterity_gate` / `_woody_try_use` /
`_woody_trick_done` / `_woody_search_step` / `_woody_search_done` /
`woody_use` / `woody_prime` / `set_primed` / `_return_to_idle` /
`_item_anim_completed` / `play_item_anim` / `search_play` / `_search_switch` /
`zone_reaction` / `crab_animations` / `Routine._trick_kid_actions`, plus the
score lines of `_on_trick_done`.

Sources: `docs/audit/raw/pass1_item_family.md` (D1-D9),
`docs/audit/raw/pass4_twins.md` (F1-F5, F8, F13). Regression module:
`tests/checks/items.py` (33 checks, ~6 s; every check was reasoned to fail
on the pre-fix code — most call the fixed function directly and assert the
C# outcome; the D6/D7 ones call new methods that did not exist).

**Counts: 16 claims received (D1-D9, F1-F5, F8, F13; F2 = D2) ·
15 CONFIRMED-FIXED (D1, D2/F2, D4 all six sub-claims, D5, D6, D7, D8 all
three arms, D9, F1, F3, F4, F5, F8, F13 — its third item, a docstring
outside the area, CONFIRMED-DOCUMENTED instead) · 0 REFUTED ·
0 already-documented · 1 OUT-OF-SCOPE (D3, the routine agent's) · plus 15
same-class findings fixed while sweeping (E1-E15 below) and 10 coordinator
flags.**

Every fix in `runtime/world.py` / `runtime/scene.py` carries its C# lines in
a comment. Line numbers below are the working tree at the time of writing
(other agents edit the same files; use the function names).

---

## A. pass1_item_family

### D1 — `Item.WasPriming` never written — CONFIRMED, FIXED
- C#: `Item.cs:835` clears at the head of every `RottweilerUse`; `Item.cs:1330`
  (`RottweilerPrime`) and `1361` (`RottweilerUnprime`) set it. Readers:
  `TrickItem.cs:260` (`IsTricked` ends in `&& !WasPriming`), `691`
  (`OnUseEnded` skips `ReturnToIdleAnimation` after a prime leg),
  `RoutineActionUse.cs:458-480` (prime vs use exit delta).
- Port before: `was_priming` initialised only (scene.py), read at
  `world.py` `_stop_side_effects` / `_action_stopped` / `Item.is_tricked`,
  never assigned.
- Fix (`Routine._use`, world.py:2266-2337, the one method outside my list the
  finding required — three small hunks): `it.was_priming = True` when a
  prime/unprime leg is chosen (before `_after_use_side_effects`, since
  `Item.Use` runs before the cs:209 `IsTricked()` read), `it.was_priming =
  False` at the RottweilerUse head (the plain use and the RequireUnprime use
  leg both pass it), and `tool.was_priming = False` for the fixing tool's own
  RottweilerUse (`Item.cs:857`). `TrickItem.RottweilerUnprime`'s
  `ReturnToIdleAnimation()` at the leg's start (`TrickItem.cs:1052-1057`) is
  ported with it (`unprime` flag) — the old code got the same end pose from
  the now-skipped `_action_stopped` return-to-idle.
- Effect verified on L111 (WashingMachine tricked): prime leg 21.4-22.2 s with
  `was_priming` True and no angry, the use leg (IsUsing) angry at 26.8 s and
  the fix, unprime leg with the flag again — the C# three-phase order.
- Checks: `items: prime leg raises WasPriming`, `no angry on the prime leg`,
  `the use leg still pays angry` (L111 WashingMachine armed, routine jumped
  to its prime action), `primed pose survives the prime visit` (L111 Airer:
  primed at action 8, FishTank at 9 — `AirerCloth` must hold while he is
  away; the old return-to-idle replayed `AirerNoCloth`).
- Same-class sweep: the other `Item.Use` entry points of the port
  (`_urgent_arrived`'s alarm use and the Neutral-TrickItem urgent use — the
  routine agent's) never run the toggles-prime dispatch; the data has no
  toggles-prime item reachable by them (14 Neutral toggles-prime items exist —
  L104 Deodrant/AfterShave, L113 FuseBox/ValveMain, the S2 DeckChair family —
  none carries NoticeWhenEnterZone/NoticeWhenWalkNearby/AlarmItem), so no
  carrier; noted for the routine agent.

### D2 / F2 — GroundItem / InspectItem `CanWoodyUse` overrides — CONFIRMED, FIXED (+ the collider finding)
- C#: `GroundItem.cs:3-8` and `InspectItem.cs:5-22` replace the whole gate:
  `SwitchToStandAnimation` + `ShowItemTooltip(DescriptionString)` (InspectItem:
  `DescriptionPrimedString` once `ItemThatChangesTooltip.GotTricked`) + return
  false — no `CheckDescriptionTooltip`, no use, no trick. `Woody.cs:547-548`
  dispatches `OnUseAnimationCompleted` only for `target is TrickItem`; every
  other kind (the L109 parrot is the one clickable Alerter) runs `UseItem`
  at once (`Item.cs:1865-1871`) and its animation ends into nothing
  (`Woody.cs:412-444`).
- Port before: no kind branch — a click ran the base gates, then
  `_woody_trick_done` (Used, GetTricked, TrickLaugh) for every non-Search kind.
- Fix: `_can_woody_use` (world.py:6155-6210) opens with the Drawing-hidden
  refusal (Drawing.cs:81-88, the outermost override), then the
  GroundItem/InspectItem stand + bubble + False, then TrickItem.CanWoodyUse's
  compound / away / bed arms (TrickItem.cs:507-543) — the compound branch now
  also drops `DontGetAngry` and sets `UseOnce` (cs:514-518, the L202 Rake
  carries it), plays the item pose through `PlayItemAnimation`, and the
  untricked Rake shows `HideString` (cs:531, F13) — and only then the base
  gate's `CheckDescriptionTooltip`. `_woody_try_use` (world.py:6656-6676)
  defers `UseItem` to the animation's end for TrickItem/SearchItem only and
  runs `_use_item` immediately for the rest.
- **The premise of the claim's failure scenario was itself a port bug**: all
  107 SlipperyGround strips (and 114 more items — L104's ApplePie until its
  round trip, L105's Football until alerted, L114's Pipe until primed, the
  L107/L109 Chili, L105 Phone, L110 SteakTable, L111 Dove, L112 Mixer, the S2
  fences, thrones, GongMan...) ship their `BoxCollider.enabled = false`, and
  `Physics.Raycast` never hits a disabled collider. The port initialised
  `Item.clickable = True` for everything. Fixed in `Level._link_item_sprites`
  (scene.py:1528): `clickable` reads the collider's `enabled`. Every C# site
  that enables a collider is already ported (`Item.cs:1326-1333`,
  `TrickItem.cs:599-606, 1154-1157`, `Item.cs:2455-2476`, the behaviors'
  collider toggles, `ActionManager.cs:411`, and `TrickItem.cs:1247` — see
  E10). The existing trick plans agree (`tests/plans/s2/Level204.txt` already
  calls GongMan "collider off"; every planned target has an enabled collider).
- Checks: `items: disabled colliders are unclickable`, `GroundItem click
  refuses with its description`, `InspectItem click refuses, primed text once
  tricked`, `Rake compound bubble, then DontGetAngry drops`.
- Not scriptable: the Alerter path (L109 Chili — its collider is disabled, so
  it is not a click target in the original either).

### D3 — `Rottweiler.TrickedAux` — OUT-OF-SCOPE
The routine agent's (`_fix` / `play_angry`); its module already carries
`routine: TrickedAux cleared by Item.Fix`.

### D4 — the SearchItem take skips `UseItem` / `InternalUse` — CONFIRMED (all six), FIXED
- C#: `SearchItem.OnFinishAnimationCompelted` (SearchItem.cs:114-119) →
  `Item.UseItem` (Item.cs:1879-1917) → `SearchItem.InternalUse`
  (SearchItem.cs:156-212) → `PlayItemAnimation(EmptyAnimation)`.
- Fix: three helpers (world.py:6678-6787) — `_use_item` (Item.UseItem: the
  Dove hack, `Used`, the CowCrap and Rabbit hacks, the InternalUse dispatch,
  `Woody.ClearTooltip`), `_item_internal_use` (Item.InternalUse:
  HideAfterUse/ShowAfterUse, HideDuringWoodyAnim + layer + show-after-single,
  RubyThrone, the BlockWhenItemPick unlock with `ClearStoreBlockedInput`, the
  MouseClickAfterDexterity unlock — the last two were unported), and
  `_search_internal_use` (SearchItem.InternalUse: the KeepFull/TakeItemCount
  head, base InternalUse, the source stamps with `AssignFirstInventoryOnly`,
  `Woody.OnSearchItemUsed`, the hand-over, `DisableColliderAfterUse`, the
  IceBucket re-arm, `AcquiredInventoryCount`, the emptying with the missing
  `!DexterityKeepItem` term, `TrickAfterWoodyUse`). `_woody_trick_done` and
  `_woody_search_done` both go through `_use_item`; the duplicated hack block
  on the trick tail is gone.
  1. `Used` — set on every take (L105 Mobile, L111 Detergent now spend).
  2. `DisableColliderAfterUse` — 41 S2 SearchItems (Sandbucket, ToolPelt,
     RiceBowl, the Fifi weights, Moped, Spade, CowCrap, Crowbar, Carpet...).
  3. hide/show flags — 22 HideAfterUse (the toilet-paper holders, bins,
     drawers, MouseHole), 6 ShowAfterUse (SoapDish x4, PigKeys, WhipStonePlate).
  4. KeepFull head — L207 Moped2 (count 0) empties on the first take, L207
     CrayFish (count 2, DexterityKeepItem) decrements and keeps its stock; the
     12 DontRemove carriers behave as before.
  5. Rabbit / CowCrap / RubyThrone — now on the shared UseItem/InternalUse
     path (SearchItems all three).
  6. `AcquiredInventoryCount` + the `SearchingItem` gate on `SetCloseTime`
     (`open_search_furniture`, world.py:5429): the 19 `SearchingItem=False`
     openers (PinsBoard x4, ToiletPaper x5, RubbishBin* x7, Mobile, SoilBag,
     SoapChest) open and never close (SearchItem.cs:143, 252); a searching
     drawer re-closes after 1.0 s once a take landed, else 1.5 s.
  Also: the empty re-click runs `OnFinishAnimationCompelted` too
  (`Woody.cs:409` raises SearchAnimation on the WhatsUp arm), so `Used` and
  `AcquiredInventoryCount = 0` land there as well; the empty pose plays through
  `SearchItem.PlayItemAnimation` (`search_play`), not a bare PlaySingle.
- Checks: `items: search take sets Used (UseOnce gate)`, `HideAfterUse on the
  take`, `DisableColliderAfterUse on the take`, `KeepFull head — count 0
  empties, count 2 decrements`, `Rabbit take deactivates it`,
  `SearchingItem=False opener stays open`, `drawer closes, 1 s once taken`,
  `empty search still runs UseItem`.

### D5 — `DoNothingWhileBeeingUsed` read routine state — CONFIRMED, FIXED
- C#: `Item.cs:1429` reads `IsUsing` (set at the RequireUnprime use leg
  `1076`, cleared at the unprime leg `1080` and by FixAll `TrickItem.cs:435`).
- Port before: `any(r.state == USING and r.item is item)`. Fix:
  `_can_woody_use` reads `item.is_using` (world.py:6312). One carrier — L114's
  gramophone — refuses Woody for the whole use→unprime stretch, neighbour
  present or not.
- Check: `items: IsUsing refuses the nail-less click with NoNo`.

### D6 — `Pawn.ElephantAnimations` not ported — CONFIRMED, PORTED (small and clear)
- C#: `Pawn.cs:1536-1558`, run from `ChangeZone` after `CrabAnimations`
  (`Pawn.cs:1528-1529`): while `Woody.ItemBehavior` (L208's AngryElephant,
  `Woody.cs:158`) is primed and Woody changes to a zone that is not the
  elephant's, and the `ElephantBehaviorAux` latch is clear: the elephant plays
  `[N2TrickItemPrimedTricked, N2TrickItemIdleTricked]` (tricked) or the Normal
  pair, its `ObjectToPrimeWhenPrimed` — the SafetyLine (pid 242, serialized
  Locked, unlocked by the prime chain's UnlockObjectToPrime) — locks again,
  the latch sets. `Item.cs:1581` (the Mouse+AngryElephant DoublePrimingItem
  arm) re-arms the latch.
- Fix: `World.elephant_animations` (world.py:5869-5897), one call in
  `on_pawn_zone_changed` (5779), the pawn spec's `item_behavior`
  (scene.py:2167), the Item slot `elephant_behavior_aux` (scene.py:330, 466),
  the latch clear in the DoublePriming arm (world.py:6376).
- Checks: `items: elephant zone watch locks the line once`, `elephant zone
  watch is one-shot`.

### D7 — `ActivateItemAfterUsingObject` unread — CONFIRMED, FIXED
- C#: `TrickItem.cs:333-351` (+ `DelayActivateItem` 382-389). One carrier:
  L214 CaptainMug → CaptainWheel, 11.0 s, LinkedItemTrick Captain.
- Fix: `_woody_trick_done` (world.py:6831-6857): every Rottweiler action on
  "CaptainControls" is retargeted to the wheel with `hide_object`
  (HideObjectDuringUse); the wheel activates after the delay via
  `call_later`, dropping the Captain (`set_active`), or at once. Note the
  L214 routine holds no CaptainControls action at load (the retarget loop
  matches the C# `Actions` array at trick time).
- Check: `items: grog activates the wheel after 11 s`.

### D8 — `_return_to_idle` / Fix tail arms — CONFIRMED (three), FIXED
1. `IdleFuckedUp` (`TrickItem.cs:699-702`): `_return_to_idle` plays it (five
   carriers: L103 CakeDead, L107 MumStatueBroken x2, L110 CarnivorPlantDead /
   BBQDirty). Check: `items: ReturnToIdle plays IdleFuckedUp`.
2. Fix of a still-primed item (`TrickItem.cs:457-467`): new `_fix_idle_tail`
   (world.py:5261) — `PlayPrimedAnimation` when Primed, else
   `ReturnToIdleAnimation` — replaces the unconditional `_return_to_idle` as
   the last line of `_fix` (world.py:5061; the one line of `_fix` I touched,
   as the finding required). The re-primed WaterPuddle keeps its pose
   (PrimedNormal NONE, HWNA false → PlayItemAnimation no-op).
3. The ElectricTrap arm (`cs:468-471`): the controller is disabled for good —
   ported as `sprite.hidden = True`; exact for the shipped data (all four
   traps ship `UseOnce=True`, so no re-trick can ever play on them again),
   and a no-op today: the trap has no sprite in the port (see flag 2).
   Not scriptable until the sprite model changes.

### D9 — ElephantBucket `IdleNormal` rewrite — CONFIRMED, FIXED
`TrickItem.cs:326-331`: the ActivateItemTrick target now plays
`PlayIdleTrickedAnim` outright (not `ReturnToIdleAnimation`) and the
ElephantBucket rewrites `IdleNormal = N2TrickItemIdleNormal` (world.py:6823).
Check: `items: ElephantBucket IdleNormal rewrite`.

## B. pass4_twins

### F1 — `TrickItem.KidActions` bound to the Kid pawn — CONFIRMED, FIXED
`Item.Kid` is a TrickItem (`Item.cs:522`; L205 OlgaKid pid 285) with the
item-side `UseNormalSequence` / `UseTrickedSequence` (`TrickItem.cs:634-641`);
only the SandCastle arm animates the Kid pawn (`Rottweiler.kid`, cs:642-653).
`Routine._trick_kid_actions` (world.py:1908) now plays the OlgaKid item's
sequences on its own player. Check: `items: SandSculpture animates the OlgaKid
item`.

### F3 — crab strips through the TrickItem twin — CONFIRMED, FIXED (routing)
`crab_animations` (world.py:5825) calls `search_play` for the SearchItem
lists (`SearchItem.cs:275-293` → `SearchItem.PlayItemAnimation` cs:68-89: no
Animating gate, unconditional unhide, the Looping flag). Both L202/L207
CrayFish have no sprite in the port (flag 2), so the routing is right and the
strips will play once sprites exist. The NFH2 TrickItem pass now goes through
`_play_zone_leave` (raw Tricked, unhide) / `_play_zone_enter` (IsTricked).
Check: `items: crab zone strip rides search_play` (spy on `search_play`).

### F4 — `TrickItem.GetTrickScore` override dropped — CONFIRMED, FIXED
`World.trick_score(item)` (world.py:4882): `Compound && CompoundTricked →
CompoundTrickScore` (`TrickItem.cs:391-398`); `_on_trick_done` pays through
it (L114 Shotgun: 13 over 10). The routine agent's `_extra_coin_*` /
`_toilet_211` still pass `it.trick_score` — the C# calls `GetTrickScore()`
there too (Item.cs:2383-2425); no numeric effect (Tortilla, PlantCarnivore:
0/0), noted for the routine agent. Check: `items: compound trick pays
CompoundTrickScore`.

### F5 — second `TrickDone` for `ExtraCoinLinkedTrick` — CONFIRMED, FIXED
`Item.cs:2143-2146` in `_on_trick_done` (my edit stays on the score /
second-TrickDone lines; the flow is the routine agent's). L207 SandCastle pair
counts three. Check: `items: ExtraCoinLinkedTrick counts three`.

### F8 — `zone_reaction` inline play — CONFIRMED, FIXED
`_play_zone_enter` / `_play_zone_leave` (world.py:5854-5867) =
`TrickItem.PlayZoneEnter/Leave` (cs:1095-1113) through `play_item_anim`
(UseAnimationType keeps the strip's Looping type — L110's BBQFullSmoke loops;
the leave gate is the raw Tricked flag and unhides first). Check: `items:
BBQFullSmoke loops on zone enter`.

### F13 — the small twins
- Rake `HideString` bubble (`TrickItem.cs:531`) — FIXED (see D2/F2).
- WaterPuddle `FinalDeltaLocationNormal` mirror (`Item.cs:1196-1200`) — FIXED
  in `set_primed` (world.py:5922+), docstring corrected. And the load-time
  half: `Item.Start → SetPrimed(Primed)` runs the name-hack once at load, so
  L201's serialized `DeltaLocation.x = +0.6` is `-0.6` from the first frame
  (`Level._build`, scene.py:1406) — the neighbour's stand x on every puddle
  visit was mirrored by 1.2 before. Check: `items: WaterPuddle DeltaLocation
  flipped at load`.
- `_move_to_empty_space` docstring — CONFIRMED-DOCUMENTED, not mine (the
  catch flow); left for its owner: `Mother.MoveToEmptySpace` (Mother.cs:142)
  has no final MinDistanceToNearestDoor shift, no behavior effect.

## E. Same-class findings fixed while sweeping (each with its C# lines)

- E1 `_woody_trick_done`'s idle tail was `ReturnToIdleAnimation`; the C#
  (`TrickItem.cs:357-379`) is: Compound && !CompoundTricked →
  PlayIdleTrickedAnim; CompoundTricked → CompoundDoubleTrickedAnim; else raw
  `Tricked` → PlayIdleTrickedAnim; else the normal idle/sequence. Effects:
  a tricked Neutral item now shows its tricked idle (L104 Deodrant
  `DeodrantHair`, AfterShave `AftershaveGlue`, L113 FuseBox `FusePlaced`,
  L206 Harpoon — `IsTricked()` is false for Neutral, so the port replayed the
  normal idle), and the compound Shotgun/Tortilla/PlantCarnivore show
  `CompoundDoubleTrickedAnim` (`ShotgunShellsAndCork` over `ShotgunShells`).
  Checks: `items: a tricked Neutral item shows its tricked idle`, `compound
  trick tail plays the double anim`.
- E2 `_return_to_idle` and `set_primed` played idles with a bare
  `play_single`; the C# goes through `PlayItemAnimation` (UseAnimationType →
  PlayAnimationDirectly keeps the strip's Looping type; the Looping flag →
  PlayLoopingAnimation; NONE hides a HideWhenNotAnimating item; the
  AnimateDependant echo). 210 items carry UseAnimationType; 75 idles are
  multi-frame Looping strips (L209 FireFakir 127 frames, L207 Bartender 171,
  L211 OlgaChild 73...) that froze on their last frame after every use. L113
  FuseBox (HWNA, PrimedNormal NONE) hides its FusePlaced strip while primed,
  as the original. New helpers `_play_idle_tricked_anim`,
  `_play_primed_animation`. Checks: `items: ReturnToIdle keeps a
  UseAnimationType idle looping`, `primed FuseBox hides its strip`.
- E3 the compound branch's `DontGetAngry` drop (`TrickItem.cs:514-518`, L202
  Rake) — see D2.
- E4 `Collider.enabled` at load — see D2 (221 items).
- E5 HideItem: `Used`, and the base `InternalUse` (HideItem.cs:34 →
  Item.cs:1919-1953) — 18 HideItems carry `HideDuringWoodyAnim`: the bed /
  basket / lorry hides for the span of Woody's Hide_In and re-shows at its
  end (verified on L107: hidden during `BedIn`, back at `Stand_Down`).
  `HideItem.Leave`'s twin arm lives in `Pawn.unhide` (not mine) — flag 8.
- E6 the empty re-click runs `OnFinishAnimationCompelted` (`Woody.cs:409`).
- E7 `AssignFirstInventoryOnly` (`SearchItem.cs:37, 173-176`): L112
  SportsBag's rubber rope and L114 DeskDrawer's gunpowder carry no source
  stamp — the door click (`Pawn.cs:633`) lets them through. New Item slot.
- E8 `BlockWhenItemPick` unlocks in InternalUse — after the take for search
  items, with `ClearStoreBlockedInput` (nothing buffered during a pick
  replays), and the `MouseClickAfterDexterity` unlock (`Item.cs:1948-1952`,
  the flag was set by the dexterity win and never read).
- E9 the IceBucket take arm (`SearchItem.cs:184-190`): PrimedAnimation NONE,
  WoodyPrimeAnimation = [ItemFoundUp, TakeLow].
- E10 `TrickItem.WaterPuddleBehavior` (`TrickItem.cs:1240-1251`) in
  `_item_anim_completed`: L210's Valve — primed through the Pool's
  ObjectToPrimeWhenPrimed chain — plays `N2TrickItemExtra1` and at its end
  hands the click to its ValveWaterPuddle once (valve collider off, puddle on,
  PrimedAnimation = N2TrickItemIdleNormal, played). The puddle's collider
  ships disabled, so with E4 this arm is what makes the L210 octopus take
  possible; the old docstring called it "the unported hover machinery". New
  slot `only_once_water_puddle`. Check: `items: Valve Extra1 end hands the
  click to the puddle`.
- E11 the `HoverAnim` return-to-idle arm (`TrickItem.cs:1070-1073`).
- E12 `_can_woody_use`'s bed refusal and the hidden Drawing sit before the
  base gate in the C#, so `CheckDescriptionTooltip`'s two override arms
  (ItemInUseString, EmptyDrawingString) are unreachable from a click
  (TrickItem.cs:537-542, Drawing.cs:81-88; nothing else calls it) — the port
  showed both bubbles. `check_description_tooltip` keeps the arms (they
  mirror the C# override bodies) with a docstring saying so. README's
  "the occupied bed, the empty wall" bubbles claim is contradicted by the
  call order — see README additions.
- E13 `Woody.ClearTooltip` moves to `Item.UseItem`'s tail (cs:1916): after the
  take for search items, at OnUseAnimationCompleted for tricks, at once for
  the rest — instead of the end of Woody's first animation.
- E14 CowCrap's UseItem hack disables its own controller (cs:1909) — ported as
  the sprite hide (no sprite in the port today, flag 2).
- E15 `crab_animations`' NFH2 TrickItem pass used `IsTricked()` for the leave
  gate; the C# `PlayZoneLeave` reads the raw `Tricked` (cs:1105).

## Validation
`python3 -c "import ast..."` over runtime/*.py: parses. `tests/run_moments.py`:
all my checks pass (33/33); the suite shows one failing check that is not
mine — `sleep bar: the dog wakes early (<80%)` (see flag 4; earlier in the
session `gameinfo: GameEnded only after the finish pose` failed once, another
agent's, and passed on the rerun). Single-level monkeys L104/L110/L111/L113
(seed 1, 60 s): no crashes; each reports the pre-existing
`stuck-colored-tooltip` invariant (the HUD latch, flag 9). L207's monkey dies
on the harness's sneak toggle in an S2 level (flag 3).

## README additions (ready to paste)

**Into "The trick loop" (Woody's side):** Two kinds of use. Only a TrickItem
or SearchItem defers `UseItem` to the end of Woody's animation
(`ShouldUseAfterAnimationFinishes`, TrickItem.cs:263-266, SearchItem.cs:
121-124); every other kind runs it at once (Item.cs:1865-1871) and the
animation ends into nothing (Woody.cs:412-444) — GroundItem and InspectItem
never get that far: their `CanWoodyUse` overrides stand, show the description
(InspectItem's primed variant once `ItemThatChangesTooltip.GotTricked`) and
refuse (GroundItem.cs:3-8, InspectItem.cs:5-22). `Item.UseItem`
(Item.cs:1879-1917) is one shared body — the Dove/CowCrap/Rabbit hacks,
`Used`, `InternalUse` (HideAfterUse/ShowAfterUse, HideDuringWoodyAnim, the
RubyThrone drop, the BlockWhenItemPick unlock with its buffer clear, the
post-dexterity unlock), `ClearTooltip` — and the SearchItem take runs it too
(SearchItem.OnFinishAnimationCompelted, cs:114-119), through
`SearchItem.InternalUse` (cs:156-212): the KeepFull/TakeItemCount head, the
source stamps (`AssignFirstInventoryOnly` stamps the first entry alone —
L112's SportsBag, L114's DeskDrawer), the hand-over, `DisableColliderAfterUse`
(41 S2 items), the IceBucket re-arm, `AcquiredInventoryCount`, the emptying
(`!DontRemoveInventoryItem && !DexterityKeepItem`, else `ItemRemoved`),
`TrickAfterWoodyUse`, then the empty pose through SearchItem's own
`PlayItemAnimation`. The empty re-click runs the same tail after WhatsUp
(Woody.cs:409). `SetCloseTime` runs only on a `SearchingItem`
(SearchItem.cs:143): the 19 `SearchingItem=False` openers — the pin boards,
the toilet-paper holders, the bins, the mobile, the soil bag, L201's soap
chest — open and never close; a searching drawer re-closes after 1.5 s, or
1.0 s once a take has landed. The trick tail's idle switch is
TrickItem.cs:357-379, not `ReturnToIdleAnimation`: a compound item plays its
tricked idle until CompoundTricked, then `CompoundDoubleTrickedAnim`; else the
raw `Tricked` flag picks the tricked idle — a Neutral item too (L104's
deodorant shows its hair). `OnTrickDone` pays through the virtual
`GetTrickScore` (a compound-tricked compound item pays `CompoundTrickScore`,
L114's Shotgun 13 over 10) and a fresh linked pair with `ExtraCoinLinkedTrick`
pays a second time (Item.cs:2143-2146; L207's SandCastle counts three).
`ActivateItemTrick`'s target plays `PlayIdleTrickedAnim` outright and the
ElephantBucket rewrites its normal idle (TrickItem.cs:326-331);
`ActivateItemAfterUsingObject` retargets every routine action on
"CaptainControls" and activates after `DelayActivateItemAfterUsingObject`,
dropping the LinkedItemTrick (cs:333-351, 382-389 — L214's grog: the
CaptainWheel 11 s later).

**Into "Priming":** `WasPriming` (Item.cs:398) is the flag that keeps a
prime/unprime visit from counting as a tricked use: `RottweilerPrime` /
`RottweilerUnprime` raise it (Item.cs:1330, 1361), every `RottweilerUse` head
clears it (cs:835), `IsTricked()` ends in `&& !WasPriming` (TrickItem.cs:260),
`OnUseEnded` keeps the primed pose after a prime leg (cs:691) and StopAction
picks `RottweilerPrimeExitDelta` over the use delta (RoutineActionUse.cs:
458-480). L111's washing machine tricked while unprimed: the prime visit ends
calmly, the use visit (`IsUsing`) pays the angry, the unprime visit resets the
idle at its start (TrickItem.cs:1052-1057). `DoNothingWhileBeeingUsed` reads
`IsUsing` itself (Item.cs:1429) — L114's gramophone refuses Woody for the whole
use→unprime stretch. `TrickItem.SetPrimed` and `ReturnToIdleAnimation` play
through `PlayItemAnimation` (UseAnimationType → PlayAnimationDirectly, so a
Looping strip loops; NONE hides a HideWhenNotAnimating item — L113's FuseBox
drops its FusePlaced strip while primed). `TrickItem.Fix`'s pose tail
(cs:457-471) replays the primed pose of a still-primed item and disables the
ElectricTrap's controller for good. `Pawn.ElephantAnimations` (Pawn.cs:
1536-1558) is ported: with L208's primed AngryElephant (`Woody.ItemBehavior`),
Woody's first zone change to another zone plays the elephant's primed-then-idle
pair and locks the SafetyLine again, once, until the Mouse arm re-arms it
(Item.cs:1581). The L210 Valve's `N2TrickItemExtra1` (its primed pose, reached
through the Pool's prime chain) ends into `WaterPuddleBehavior`
(TrickItem.cs:1240-1251): the puddle's collider comes on and it shows
`N2TrickItemIdleNormal`. The WaterPuddle name-hack negates `DeltaLocation`
and `FinalDeltaLocationNormal` at every SetPrimed — including `Item.Start`'s,
so L201's serialized +0.6 is -0.6 from the first frame.

**Into "Things that bite" / the click contract:** `BoxCollider.enabled`
ships off on 221 items (every SlipperyGround strip, L104's ApplePie until its
round trip, L105's Football until alerted, L114's Pipe until primed, the S2
fences and props) and `Physics.Raycast` never hits them; `Item.clickable`
now starts from that byte, and the C# enable sites are the ported ones.

**Correction to "The description bubble" (Fixed in the audit list):** the
occupied-bed and empty-wall bubbles cannot show in the original —
`TrickItem.CanWoodyUse` refuses the slept-in bed and `Drawing.CanWoodyUse` the
hidden drawing before `base.CanWoodyUse` reaches `CheckDescriptionTooltip`
(TrickItem.cs:537-542, Drawing.cs:81-88), and nothing else calls it; the port
now refuses silently there too (`ItemInUseString` / `EmptyDrawingString` are
dead strings).

**Into "Zones" / crabs:** `SearchItem.PlayItemAnimation` (SearchItem.cs:68-89)
is the crabs' own twin — no Animating gate (that field is TrickItem-only),
an unconditional unhide, the Looping flag — and `Pawn.CrabAnimations` uses
it; the TrickItem lists ride `PlayZoneEnter` (IsTricked gate) /
`PlayZoneLeave` (raw Tricked, unhide first), both through
`TrickItem.PlayItemAnimation` so L110's BBQFullSmoke keeps its Looping type.
`TrickItem.KidActions`' SandSculpture arm animates `Item.Kid` — the L205
OlgaKid TrickItem with its item-side sequences — while the SandCastle arm
animates the Kid pawn.

## Coordinator flags

1. **HIGH, animation core (not my area, one line):** `AnimPlayer._advance`
   (world.py, `self.sprite.cur_frame = min(self.frame, a.end)`) clamps
   pattern animations to `EndFrame` too; the C# `UpdateCurrentFrame`
   (AnimationInstance.cs:228-234) sets `CurrentFrame = Pattern[idx]` with no
   clamp. 6260 pattern animations, 4557 with `EndFrame < max(Pattern)`
   (4393 on pawns) render frame 0 / EndFrame forever — verified live: L209's
   FireFakir idle (127-entry pattern, EndFrame 0) draws sheet frame 0 while
   `frame` cycles 0..5; L101's neighbour `ShitNormal` (pattern 4..10,
   EndFrame 0) draws frame 0 on the toilet, `SlipLeft` (pattern 8..12,
   EndFrame 7) draws frame 7 for its second half. Fix:
   `self.sprite.cur_frame = self.frame if a.pattern else min(self.frame, a.end)`.
   The anim draft called this line "OK".
2. **HIGH, sprite model (README's "IdleNormal == NONE means not a sprite"):**
   121 item controllers with sheets and playable strips get no sprite in the
   port — every S2 SearchItem (their FullAnimation/EmptyAnimation are the
   full/empty looks: L202 RubbishBin `Rubbish_Full`/`Rubbish_Empty`, the
   CrayFish `B_hide`/`B_unhide`, Sandbucket, SawFish...), the L111/112/113/114
   ElectricTrap (its `ElectricTrap` spark loop is the tricked idle), L111
   WashingMachine (`WasherLoop`/`WasherRed`)/Drier, L114 Gramaphone
   (`GramaphonePlay`/`GramaphoneNail`)/GoldCup/MouseHole, L105 Football/Phone,
   L106 BathTub, L107 Drawing (its hidden/shown state — Drawing.cs:20, 45 —
   is unmodelled, so Woody can trick the wall before the neighbour draws),
   L207 ElephantBucket, L209 CowCrap/FireChannel... The C# controller draws
   nothing until its first play (`CurrentAnimation == null`, the port already
   has `AnimPlayer.reveal_on_play` for that) — the right model is a sprite
   with no current animation, not "no sprite". This blocks the visible half
   of D8.3, F3, D4's empty poses and E14. Needs the render/anim owner.
3. Harness: `tests/monkey.py:471-472` and `runtime/record.py:100-103` set
   `woody.sneaking = sneak_toggle` directly, bypassing `Woody.toggle_sneak`'s
   NFH2 guard (S2 Woody has no `Walk_*` strips) — the L207 monkey dies with
   `No animation found !!! State: Walk_Up`. Use `woody.toggle_sneak()`.
4. `sleep bar: the dog wakes early (<80%)` now fails: L109's Bed sequence is
   `BedIn + 30 x BedSleep` (2 frames at 2 fps = 1.0 s each ≈ Duration 29.3),
   so the bar completes; the committed HEAD ran each BedSleep in 0.5 s
   (woke at 15.25 s, ~52 %). Another agent's animation-timing fix moved it;
   the moment's expectation looks like it was written against the old timing
   — please re-verify against AnimationInstance and re-aim the check.
5. Routine agent: `_urgent_arrived`'s Neutral-TrickItem full use and the
   alarm use skip `Item.Use`'s toggles-prime dispatch (no data carrier
   today); `_extra_coin_*` / `_toilet_211` should pay `w.trick_score(it)`
   (no numeric change in data); `RoutineActionUse.OnActionStarted` calls
   `Item.Use` before the cs:209 `IsTricked()` read — the port's prime-leg
   order now matches that (was_priming set before `_after_use_side_effects`).
6. `Pawn.unhide` lacks `HideItem.Leave`'s HideDuringWoodyAnim arm
   (HideItem.cs:64-68: hide the bed for the span of LeaveAnimation, show at
   its end) — the entry half is now ported in `_woody_try_use`.
7. `set_tricked_object_hidden`'s docstring says the IsGroundTrick collider
   arm (TrickItem.cs:405-408) is "approximated by the item's own
   clickability" but the code toggles nothing — with E4 the ground strips
   are unclickable anyway; the overlay's own collider (a click surface with
   no Item behind it) is not modelled.
8. `_bbq_dirty` plays `BBQDirty` with `play_single`; the C# is
   `PlayItemAnimation(IdleNormal)` (TrickItem.cs:479) — no carrier with a
   sprite today (L110 Beer has none).
9. `stuck-colored-tooltip` monkey findings on L104/L110/L111/L113 (the HUD's
   `MakePermanentTooltip` latch at an inventory click with nothing held,
   hud.py:1315-1327) — the HUD/click-contract owner; not changed by this pass
   (`Woody.ClearTooltip` moved to `Item.UseItem`'s tail, same flows).
10. `_move_to_empty_space` docstring (F13.3) — the catch flow's owner.
