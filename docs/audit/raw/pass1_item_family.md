# Pass 1 — Flag-lifecycle audit: Item family
Classes: Item, TrickItem, SearchItem, Door, HideItem, Alerter, Toilet, Television, Rake, Drawing, GroundItem, InspectItem
Sources read: src/Assembly-CSharp/{Item,TrickItem,SearchItem,Door,HideItem,Alerter,Toilet,Television,Rake,Drawing,GroundItem,InspectItem,RoutineActionUse,Rottweiler,ActionManager,Woody,Pawn,DexterityComponent,MouseCursor,RoutineActionUseFixingItem,IntroAnimation}.cs
Port read: runtime/world.py, runtime/scene.py, runtime/hud.py, runtime/viewer.py, runtime/behaviors.py. Data cross-checked against levels/s*/*.json.

**Counts: 9 divergences (2 high, 4 medium, 3 low) · 2 not-ported mechanisms (folded into D6, D7) · ~60 state fields verified OK · 14 DEAD-in-C# fields · localized-string families = CONFIG (one write at Start each).**
Documented items (trick camera, ExitConfirmation, tutorial/IntroAnimation layer, InventoryToAdd machinery, Toilet-subclass no-paper branch, audio-only arms, `PoorSequenceSkates`) are *not* reported as findings; they appear only as OUT-OF-SCOPE/DEAD rows.

---

## DIVERGENCES

### D1 — `Item.WasPriming` is never written in the port (stuck-false) — **HIGH**
C# lifecycle:
- `Item.cs:835` — `WasPriming = false` at the head of every `RottweilerUse`.
- `Item.cs:1330` — `RottweilerPrime` → `WasPriming = true`.
- `Item.cs:1361` — `RottweilerUnprime` → `WasPriming = true`.
C# reads:
- `TrickItem.cs:260` — `IsTricked()` ends in `&& !WasPriming && !FuckedUp`: a prime/unprime leg on a tricked item must **not** count as a tricked use.
- `RoutineActionUse.cs:458-480` — StopAction picks `RottweilerPrimeExitDelta` (priming) vs `RottweilerUseExitDelta` (use).
- `TrickItem.cs:691` — `OnUseEnded` skips `ReturnToIdleAnimation()` after a prime leg, so the primed pose played by `SetPrimed` persists.

Port: `scene.py:436` initializes `was_priming = False`; grep over runtime/ finds **no assignment of True anywhere** (only reads at `world.py:2651`, `world.py:2826`, `scene.py:906`). The routine prime/unprime legs (`world.py:1992-2044`) never touch it, and there is no `= False` at the use head either.

Consequences, each with a concrete carrier:
1. **Angry fires on the prime leg.** A `RottweilerUseTogglesPrime` item tricked while unprimed (L111 washing machines / dryer — `RequireUnprime`; L114 gramophone): the neighbour's next visit is the prime leg; its end runs `Routine._finish` → `it.is_tricked()` (scene.py:906) which is True because `was_priming` is False → the angry set + `TryFix` run **during the prime visit**. In the original (`RoutineActionUse.cs:546` reading `IsTricked()` with `WasPriming` true) the prime leg ends calmly and the discovery happens on the use leg.
2. **Wrong exit delta after a prime.** `world.py:2651` picks `rott_use_exit_delta` because `was_priming` is always False. Data: L205's BeerMat is the one toggles-prime item with a non-zero use exit delta (−3.0, 0). C# applies `RottweilerPrimeExitDelta` = (0,0) after the prime leg; the port teleports the neighbour −3 x after **every prime** of the mat.
3. **The primed pose is overwritten at the prime leg's end.** `world.py:2826` (`_action_stopped`) calls `_return_to_idle` because `not it.was_priming` is always True; C# `OnUseEnded` skips it. All toggles-prime items whose `PrimedNormal` pose exists but `ForcePrimedAnimationOnStart` is false lose the primed pose seconds after being primed: L103 cake (`CakeReady`), L106 bathtub (`BathTubNormal`), L109 teeth cup, L110 BBQ (`BBQSmoke`), L111 `AirerCloth`/`IronOn`, L112 `MixerOn`, L113 `Sink`, L114 `GramaphoneOpen` (data scan above). In the original the item visibly stays "primed" until the next use.

Fix shape: set `was_priming = False` at the head of the routine's Rottweiler use dispatch, True in both prime/unprime legs — exactly the three C# writes.

### D2 — GroundItem/InspectItem `CanWoodyUse` overrides are missing; every non-Search kind runs the TrickItem completion — **HIGH**
C#:
- `GroundItem.cs:3-8` — `CanWoodyUse`: `SwitchToStandAnimation()` + `ShowItemTooltip(DescriptionString)` + **return false**, always.
- `InspectItem.cs:5-22` — same, choosing `DescriptionString` / `DescriptionPrimedString` by `ItemThatChangesTooltip.GotTricked`.
- `Woody.cs:547-548` — `TryUseItem` sets `SearchingItem = target is SearchItem; TrickItem = target is TrickItem;` — `OnUseAnimationCompleted` (the trick tail: `Used=true`, `GetTricked`, UseCount--, TrickLaugh) is dispatched **only** for real TrickItems (`Woody.cs:412-437`).

Port: `world.py:_can_woody_use` (5385-5656) has no GroundItem/InspectItem branch, and `_woody_try_use`'s `anim_ended` (5822-5830) routes **every non-SearchItem kind** into `_woody_trick_done` (= TrickItem.OnUseAnimationCompleted, 5838-5935).

Failure scenario (verified against data): all 107 GroundItems ship `Animation=Walk_Down, CanUse=True, RequiredInventory=IT_NONE` on active GameObjects (e.g. L113's four `SlipperyGround` strips, colliders confirmed clickable in the port via `scene.Level('s1/Level113.json')`). Clicking one bare-handed:
- original: Woody walks over, stands, the description bubble shows (`GROUND_MARBLES_TRICKED_DESC` …).
- port: **no bubble** (`check_description_tooltip` requires `RequiredInventory`/`IgnoreRequiredInventoryForDescription`), Woody plays `Walk_Down` in place, the spot is marked `used=True` + `tricked=True` (`_get_tricked` at world.py:5869), and Woody plays `TrickLaugh`. Hover then resolves to the (empty) tricked name string.
Same for the single InspectItem (`CarnivorPlant`, L110, CanUse=True) — its click-time `GotTricked`-dependent tooltip never shows (only the hover variant in hud.py:610-616 exists) — and for L109's parrot (`Chili`, the only Alerter with `CanUse=True`): C# marks it Used and plays `Walk_Down`, nothing else; the port fake-tricks it and laughs.

Fix shape: kind checks at the top of `_can_woody_use` (stand + tooltip + False), and gate `_woody_trick_done` on `item.kind in TRICK_KINDS`.

### D3 — `Rottweiler.TrickedAux` is never cleared (C# clears it in `Item.Fix`) — **MED-HIGH**
C#: `Item.cs:2063-2065` — the very first statement of `Item.Fix()` is `GameInfo.Instance.Rottweiler.TrickedAux = false;`. Set: `Rottweiler.cs:652` (both halves of a linked pair already `AlreadyTricked`). Read: `Rottweiler.cs:655` — `!TrickedAux` gates the `AngryMeter += AngerAmount` accumulation of the NFH2 anger ladder. Since every angry run ends in `TryFix → Fix`, the flag is transient (one use) in the original.
Port: set at `world.py:4096`; `_fix` (4329-4430) never clears it; `world.py:300` even annotates it "`Rottweiler.TrickedAux (never reset)`" — contradicted by Item.cs:2065.
Failure scenario: any Season-2 level with a re-usable linked pair (LaunchPad+Harpoon L206, DogBasket pair L210, AztecThrones L212). After the pair has paid once and is tricked again, `tricked_aux` goes True and **stays** — from then on no item adds `AngerAmount` to the meter for the rest of the level: no level-2/3 angry sets, no freakout/statue/whistle, and the rating's angry-tick channel dies. In the original the very next Fix re-enables accumulation.

### D4 — the SearchItem take skips `UseItem`/`InternalUse` side effects — **MED**
C# flow: `SearchItem.OnFinishAnimationCompelted` (cs:114-119) → `Item.UseItem` (Item.cs:1879-1917: `Used = true` + the Dove/CowCrap/Rabbit name-hacks) → `SearchItem.InternalUse` (cs:156-212) which (a) runs the `KeepFull`/`TakeItemCount` head (cs:158-165), (b) calls `base.InternalUse()` (Item.cs:1919-1953: HideAfterUse / ShowAfterUse / HideDuringWoodyAnim / RubyThrone / BlockWhenItemPick unlock), (c) `DisableColliderAfterUse` (cs:180-182), (d) the IceBucket branch (cs:184-190), (e) `AcquiredInventoryCount = InventoryItems.Length` (cs:191), (f) the empty/ItemRemoved logic gated on **`!DontRemoveInventoryItem && !DexterityKeepItem`** (cs:192-206).
Port: `_woody_search_done` (world.py:5960-5982) covers only the hand-over, `keep_full`/`dont_remove_inventory`/`item_removed`, `TrickAfterWoodyUse` and the empty animation. Missing pieces, each with data-verified impact:
1. **`used = True` never set** → the `UseOnce && Used` gate (Item.cs:1654, port 5611) never fires for search items. Carriers: L105 `MOBILE`, L111 `FLAKES` (data scan). C#: second click refuses with NoNo + `WrongTrick`; port: replays the search animation and `WhatsUp`.
2. **`DisableColliderAfterUse` never applied on the search path** — ~40 Season-2 SearchItems (SAND, TOOLBELT, RICEBOWL, FLEA ×5, MOPED, SPADE, COW_CRAP, BRAILER, MUM_PICTURE, CROWBAR, BEEHIVE, CARPET, FISH …) keep taking clicks after the take; in C# they go permanently unclickable. (The port has the handler, but only on the TrickItem RottweilerUse arm — world.py:2166.)
3. **`base.InternalUse()` hide/show flags never run** — every S1 `TOILET_PAPER_HOLDER` / `RUBBISH_BIN` / `WORKBENCH` / `BALC_TABLE` / `CAR_PARTS` / `RAT_HOLE` (HideAfterUse=True) stays visible after being emptied; every `SOAP_DISH` / `KEYB` / L212 `SPIKES` (ShowAfterUse=True) never appears.
4. **The `KeepFull`/`TakeItemCount` head is missing** — `keep_full` is never cleared and `take_item_count` never decrements. L207 `PEDAL` (KeepFull, cnt 0, DontRemove=False): C# empties on the first take; port = infinite pedal source. L207 `CRAB` (KeepFull, cnt 2, DexterityKeepItem): C# allows exactly 3 takes then marks ItemRemoved; port = unlimited. (The other 12 KeepFull carriers ship `DontRemoveInventoryItem=True` + `TakeItemMultipleTimes`, where C# also ends up refilling — behaviour accidentally equal there.)
5. **`UseItem`'s SearchItem name-hacks sit in the wrong path and are dead**: `Rabbit` (L206, SearchItem — Item.cs:1911-1914 `SetActive(false)`), `CowCrap` (L209, SearchItem — Item.cs:1898-1910 cow idle + collider/controller off), `RubyThrone` (L212, SearchItem — Item.cs:1939-1942). The port implements all three inside `_woody_trick_done` (world.py:5888-5902), which SearchItems never reach — the rabbit/crap/throne stay active after the take. (`Dove` is a TrickItem — its hack at world.py:5880 is on the right path.)
6. **`AcquiredInventoryCount` not modelled** — `SetCloseTime` (SearchItem.cs:141-154) picks 1.0 s once `AcquiredInventoryCount > 0`; the port approximates with `item_removed` (world.py:4754), so ordinary emptied furniture re-closes after 1.5 s instead of 1.0 s. Also `SetCloseTime` is gated on `SearchingItem` in C#: the `SearchingItem=False` openers (PINS_BOARD ×4, some RUBBISH_BINs, MOBILE, SOIL_BAG, L201 SOAP) open **and never close** in the original (Update's tail returns for them, cs:252); the port closes them after 1.5 s (world.py:4744-4769). Low-visibility but real.

### D5 — `DoNothingWhileBeeingUsed` reads routine state instead of `Item.IsUsing` — **MED**
C#: `Item.cs:1429` — `if (DoNothingWhileBeeingUsed && IsUsing)` refuse (+ nail tooltip). `IsUsing` lifecycle: `Item.cs:1076` set at the start of the **use** leg of a `RequireUnprime` item, `Item.cs:1080` cleared only at the **unprime** leg, `TrickItem.cs:435` cleared by `FixAll`. So the original blocks Woody for the whole use→unprime span, including while the neighbour is away between visits.
Port: `is_using` is maintained faithfully (world.py:1996-2000, 4409) but the gate at world.py:5497-5500 tests `any(r.state == r.USING and r.item is item ...)` — only while the neighbour is physically mid-use.
Data: exactly one carrier — L114's gramophone (`PHO_LOCK`, RequireUnprime=True). Failure: between the neighbour's use visit and his unprime visit, the original refuses Woody's nail with the NotPrimedTooltip bubble; the port lets the trick through.

### D6 — `Pawn.ElephantAnimations` (zone-change) not ported: `Locked` write + `ElephantBehaviorAux` one-shot — **MED**
C#: `Pawn.cs:1536-1559` — on every `ChangeZone`, if `Woody.ItemBehavior` (serialized: L208 Woody → AngryElephant) is primed and Woody left its zone: play the elephant's `PrimedTricked/IdleTricked` (or `PrimedNormal/IdleNormal`) pair, set **`ObjectToPrimeWhenPrimed.Locked = true`** (Pawn.cs:1547, 1555 — the SafetyLine), latch `ElephantBehaviorAux = true`. The latch re-arms at `Item.cs:1581` (the Mouse+AngryElephant `DoublePrimingItem` branch).
Port: no equivalent — `ElephantAnimations`/`ItemBehavior`/`elephant_behavior_aux` appear nowhere in runtime/ (grep), and the port's DoublePrimingItem branch (world.py:5565-5580) lacks the aux clear. README's priming section documents only the `InventoryToAdd` rat grant as unported; this zone-change block is not mentioned → undocumented NOT-PORTED.
Failure: L208 — after Woody primes the elephant and walks out of its zone, the original locks the SafetyLine (it refuses with the locked bubble until unlocked) and the elephant visibly reacts; the port leaves the line unlocked and the elephant silent.

### D7 — `ActivateItemAfterUsingObject` (TrickItem.OnUseAnimationCompleted tail) not ported — **MED-LOW**
C#: `TrickItem.cs:333-351` — on Woody's completed trick, every routine action whose item is named "CaptainControls" is retargeted at `ActivateItemAfterUsingObject` with `HideObjectDuringUse = true`, and the target activates after `DelayActivateItemAfterUsingObject` (`DelayActivateItem`, cs:382-389, which also deactivates `LinkedItemTrick`).
Port: `activate_item_after_using` is loaded in scene.py:697-698 but never read in world.py (grep).
Data: one carrier — L214 `GROG` → CaptainWheel, delay 11.0 s. Failure: L214's grog trick never swaps the captain's routine to the wheel and never activates it. (Related `_captain_door_behavior` / CaptainDoor arm IS ported — world.py:4935 — so this is the one missing arm; adjacent Captain flows are partially covered by README's "one-off Season-2 scene hacks" caveat, but this specific field is not named there.)

### D8 — `_return_to_idle` / Fix tail: three pose arms differ — **LOW-MED**
1. **FuckedUp idle never plays.** C# `ReturnToIdleAnimation` (TrickItem.cs:698-701) plays `IdleFuckedUp` when `FuckedUp`; the port returns early (world.py:4568-4569) and `idle_fucked_up` is never played anywhere (only assigned at world.py:2178). After a failed fix (`fucked_up=True`, e.g. L102 TV — `CanFix=false`), `OnUseEnded`'s return-to-idle leaves the item on its last tricked-use frame instead of the broken-idle pose.
2. **Fix of a still-primed item.** `TrickItem.Fix` (cs:457-467) plays `PlayPrimedAnimation()` when `Primed` after the fix; the port's `_fix` ends in `_return_to_idle` (world.py:4430) which holds the primed pose only for `ForcePrimedAnimationOnStart` items — the re-primed WaterPuddle (L201, `Primed=true` written at Item.cs:2089-2092 / world.py:4427) gets its normal idle replayed where C# leaves the pose alone (`PrimedNormal=NONE`, `HideWhenNotAnimating=False` → C# no-op).
3. **The ElectricTrap arm** (cs:468-471: `AnimController.enabled = false` instead of an idle) is missing — L111's fixed trap keeps animating its idle in the port. (`ElectricTrap` ships `CanFix=True`, so the arm is reachable.)

### D9 — `ActivateItemTrick`'s ElephantBucket idle rewrite missing — **LOW**
C#: `TrickItem.cs:326-331` — arming `ActivateItemTrick` plays its tricked idle *and*, when the target is named "ElephantBucket", rewrites `IdleNormal = N2TrickItemIdleNormal`. Port: world.py:5870-5874 plays the tricked idle but skips the name-hack → after the bucket's later fix it returns to the wrong normal idle (L208).

---

## Per-field table

Legend: **OK** = matching write/read sites listed · **DIV#** = covered by divergence above · **CONFIG** = serialized/loaded once, no runtime lifecycle · **DEAD** = written or declared but never read (or unreachable) in C# — port omission correct · **OOS** = inside a documented unported subsystem.

### class Item (Item.cs)

| Field | C# writes | C# reads / gate | Port | Verdict |
|---|---|---|---|---|
| `Tricked` | TrickItem.OnUseAnimationCompleted 307/317 via GetTricked (1955-1962); Fix 2102; FixItemTrick(2103-2107)/Linked(2097-2101); ValveMain hack 1717/1722; SearchItem.InternalUse 205; RoutineActionUse 300 (`GameObjectToTrickAfterUse` toggle); ActionManager 755 (Plant); Rottweiler 717 (MumStatueFootStool); DexterityComponent 382 (`ActivateTrickItemIfSearchItem`); Woody 402 (`ActivateUseItemTrick`); behaviors | IsTricked 1043-1046 / TrickItem 260; the whole use dispatch (TrickItem 791-916); StopAction 398/415-427/489/521; angry ladder (Rottweiler 625-658); catch/notice flows; naming 2305+ | scene.py:488 load; world.py:5862-5878 (_woody_trick_done), 4380/4384/4378 (_fix), 5649-5654 (ValveMain), 5979 (search), 2545 (trick-after-use), 2578 (Plant), 4134 (MumStatue), dex at `_dex` flow; reads scene.py:896-906 + the dispatch/stop/angry sites listed in D-sections | **OK** (all flows matched; see D2 for the spurious set on non-trick kinds) |
| `GotTricked` | Item 838 (RottweilerUse head, raw-Tricked mark); 1718/1723 (ValveMain); GetTricked 1960 (`GetTrickedAtOnce`); TrickItem 418 (Rope fix clear), 879 (shade branch), 1132 (LetUntrick → true); Rottweiler 567 (DontGetAngry clear); Level206RoutineBehavior 27 | ActionManager 368/372 (Shower/Bouquet Olga-infinite), 614 (urgent-resume skip); AnimationControllerBase 264 (TowelSleep); InspectItem 13; MouseCursor 293; Item 1656 (`Tricked^GotTricked` spent-UseOnce arm); TrickItem 260/416/857 (IsTricked chain) | world.py:2089-2090 + 3131 (head mark), 5650-5653 (ValveMain), 5941 (_get_tricked), 4398-4399 (Rope), 2333 (shade), 4326 (LetUntrick), 4010 (DontGetAngry); behaviors.py:833-area (206); reads 3089 (resume), 1601-1606 (TowelSleep), hud.py:613 (InspectItem hover), 5612, scene.py:903 | **OK** |
| `Primed` | SetPrimed 1195 (+Start 697); WoodyPrime 1252; IceBucket 1276; Mouse hacks 1392-1404; ValveMain 1725; CowBehavior 1766; Fix 2091 (WaterPuddle); FixBull 2501; TrickItem.Fix 429 (PigKeys), 434 (FixAll), 449 (TakeOffIron); RoutineActionUse 266-296 (prime-after-use) | CanWoodyUse gates 1510-1671; Use toggle 1057-1093; SetPrimed visuals 1201-1242; naming/tooltips; SearchItem switcher 225-240; crab pass Pawn 1541-1586; TrickItem 459/476/705/837/920/999 | scene.py:360 load; world.py:5162-5203 (set_primed), 5205-5248 (woody_prime), 5236 (IceBucket), 5427-5432 (mouse), 5655 (ValveMain), 5446 (Cow), 4427 (WaterPuddle), 4446 (FixBull), 4405/4408/4420 (Fix arms), 2526-2541 (prime-after-use); reads across the same flows | **OK** (D1.3 affects only the *pose*, not the flag) |
| `Locked` | Door.Unlock 203; WoodyPrime chain 1271; FirstAid 1410; dexterity done 1465/1498; RoutineActionUse 396/402; Pawn 1547/1555 (elephant); SandCastleBehavior 73; LevelScript/Tutorial (OOS) | click contract (Pawn 628/639, MouseCursor 257/308); CanWoodyUse 1689; graph (ZoneController 21, Helpers 199/245); Door.CanWoodyUse 232 | scene.py:431 load; world.py:5230, 5471, 5702, 2623/2628, 4814 (unlock_door); behaviors.py:1375 (sand castle); reads 5637, 629, click branch 5349 | **OK** except Pawn.cs:1547/1555 → **DIV6** |
| `FuckedUp` (TrickItem) | TryFix 1127; Item 1279 (IceBucket chain target); RoutineActionUseFixingItem 57 (clear on tool arrival) | IsTricked 260; ReturnToIdle 699; SetPrimed override 1001; PlayAnimation 831/882; naming 1166/1187/1208 | world.py:4319/4321 (_try_fix), 5240 (IceBucket), 3194 (clear); reads scene.py:906, world.py:2292/2336, 5196, hud.py:437 | **OK** as a flag; the *pose* on ReturnToIdle → **DIV8.1** |
| `AlreadyTricked` / `SecondAlreadyTricked` | OnTrickDone 2127-2151; DoubleRequired swap 1748-1750; Hatch fix 2562 (clear) | OnTrickDone guard; anger ladder Rottweiler 642-655; StopAction 445 (not-tricked delta); MotherSleepBehaviour 44 | world.py:4277-4292; swap 5404-5405; 4500 (Hatch); reads 4091-4098, 2642 | **OK** |
| `WrongTrick` | clear WoodyUse 1857; set 1525 (unprimed toggles-prime + inventory), 1595 (wrong priming target, not-OnlyWhenTricked), 1667 (spent UseOnce, non-Iron), 1676 (wrong required inventory) | TrickItem.OnUseAnimationCompleted guard 270 | world.py:5775 (clear), 5534, 5584 (with the only-tricked exemption), 5621 (Iron exemption 5620), 5632; read 5840 | **OK** (near-dead defensively in both) |
| `IsUsing` | Use 1076 (use leg), 1080 (unprime); TrickItem.Fix 435 (FixAll) | Use 1074; CanWoodyUse 1429 (`DoNothingWhileBeeingUsed`) | scene.py:375; world.py:1996-2000, 4409; gate read replaced by routine-state test 5497 | **DIV5** |
| `WasPriming` | 835 clear; 1330/1361 set | TrickItem 260, 691; RoutineActionUse 458 | scene.py:436 init only — no writes | **DIV1** |
| `UseOnce` | serialized; DontGetAngry 1729; Fix 2095/2111; Iron/Rope 313 & TakeOffIron 419/454; ThroneBehavior 2454-2455 / FixThrone 2477-2478; Hatch 2565/2573; Rottweiler 566; TrickItem.Update sync 228-240; Woody 434 (UseItemMultipleTimes); FifiBehavior 47/55 | spent gate 1654 | scene.py:433; world.py:4009, 4388/4429, 5866-5867 + 4424, throne 4973-area, hatch 4503/4507, sync 6496-6501, 5934-5935; behaviors FifiBehavior ported; read 5611 | **OK** |
| `Used` | UseItem 1893; SetUnUsed 2635 (TurbanShop via Fix 2076; Level206RoutineBehavior 28) | spent gate 1654 | world.py:5842; 4360; behaviors.py:833; read 5611 | **OK** for trick path; **DIV4.1** for SearchItems (never set) |
| `UseCount` (Inventory, spent state) | TrickItem.OnUseAnimationCompleted 278 (`UseCount--`, remove at ≤0 unless KeepAfterUse 279-284) | same site | world.py:5843-5847 | **OK** |
| `ItemRemoved` | Use 1059/1063 (PigKeys toggle by Primed); SearchItem.InternalUse 200 | Use 1057/1061; CanWoodyUse 1515 (WhatsUp); (port also: close-time pick) | scene.py:426; world.py:1987-1990, 5977; reads 5456, 4754 | **OK** |
| `KeepFull` | SearchItem.InternalUse 158-165 (head clears it / decrements TakeItemCount) | InternalUse 158/192 | scene.py:418 load; head missing | **DIV4.4** |
| `MainValveOpen` | serialized TRUE (L113); RottweilerPrime 1354 (close); CanWoodyUse 1716/1724; TrickItem.RottweilerUse 572 (re-open) | 1335 (early-loop unprime swap, `ActionStartIndex<=3`), 1352, 1714/1720, naming 2299, TrickItem 570 | scene.py:413; world.py:2009-2015, 5647-5654, 2084-2085; hud.py:454-456 | **OK** |
| `DontUseOn` | none (serialized) | StopAction deltas 430/447/460-476; IsAtUseRange 2284 (walk-up y-skip); TrickItem 951 (UseTricked gate) | scene.py:608; world.py:2629-2655, 4619-4622; IsAtUseRange arm kept (documented) | **OK** |
| `GoNextAction` | serialized (L113 valves); ActionManager 622 clear | ActionManager 620 | scene.py:813; world.py:3095-3097 | **OK** |
| `SkipAction` | Drawing.Fix 35 | ActionManager 608 | world.py:4338; 3086 | **OK** |
| `NextActionAfterGramaphoneTricked` | TrickItem.Fix 436 (FixAll) | ActionManager 200-202 (StartNextAction skip) | world.py:4410; read: routine advance (ported per README's RequireUnprime trio verification) | **OK** |
| `MarblesNextAction` (ActionManager, item-set) | CanWoodyUse 1386 set; ActionManager 644 clear | ActionManager 614/620 | world.py:5451-5454, 3081; reads 3089-3095 | **OK** |
| `GameInfo.SnakeAux208` | CanWoodyUse 1556 | CanWoodyUse 1402 | world.py:5557, 5431 (init 3890) | **OK** |
| `IsRottweilerSleeping` (TrickItem) | RoutineActionUse 305 set (Bed, start), 515 clear (stop) | TrickItem.CanWoodyUse 537; CheckDescriptionTooltip 547 | scene.py:559; world.py:2546-2547, 2678-2679; reads 5513-5516, 5751-5753 | **OK** |
| `RottweilerUseItemExitDeltaAux` / `...NotTrickedExitDeltaAux` | StopAction 438/443, 451/456 (one-shot + else-clear) | 428, 445 | scene.py:612-613; world.py:2632-2648 (positive-component quirk kept, documented) | **OK** |
| `harpoonAux` | TrickItem 898 set; RoutineActionUse 543 clear | RoutineActionUse 541 | scene.py:630; world.py:2345, 2727; read 2725-2726 | **OK** |
| `PrimeItemAux` (DogFifi) | RottweilerPrime 1344 | 1342 | scene.py:428; world.py:2018-2020 | **OK** |
| `ElephantBehaviorAux` | Pawn 1543/1551 set; Item 1581 clear | Pawn 1539 | absent | **DIV6** |
| `ExecuteOnceAnimationMother206` | PlayMotherAnimation 1128 set / 1133 clear | 1121 | scene.py:817; world.py:2243, 2246; read 2239 | **OK** |
| `TrickedItem` (internal, LionStatue latch) | 1546 set, 1593 clear | 1548, CanWoodyUse 1421 | modeled as `blocked` local (world.py:5549) — same outcome | **OK** |
| `GetTrickedAtOnce` | serialized | GetTricked 1958 | scene.py:358; world.py:5940 | **OK** |
| `CanUse` | TrickItem 597 (DisableColliderAfterUse), 1159 (Football alert) | click contract | scene.py:522; world.py:2168, 4709; viewer.py:191 | **OK** |
| `CanFix` | serialized; RoutineActionUseFixingItem 55 (`CanFix=true` on tool arrival) | TryFix 1117; angry tail 767 | scene.py:351; world.py:3193; reads 4309, 4203 | **OK** |
| `CanUndoTrick` | serialized; Fix 2110 (BlockAfterFix) | OnUseAnimationCompleted 305 | scene.py:357, world.py:4387; read 5862 | **OK** |
| `BlockAfterFix`→(`CanUndoTrick`,`UseOnce`) | Fix 2108-2112 | — | world.py:4386-4388 | **OK** |
| `DontGetAngry` | serialized; TrickItem 516 clear (compound); CanWoodyUse 1727-1730 (`UseOnce=true`) | Rottweiler 564/655/785 | scene.py:352; compound arm at 5406-5418 region; world.py:4008-4010, 4097, 4165/4210 | **OK** |
| `Dexterity`/`DexterityDone`/`InDexterity`/`InvUsed` | CanWoodyUse 1438-1507; DexterityComponent 373-388 | same | world.py:5658-5709 (_dexterity_gate), dex_states; `_dex_inv_used` | **OK** (dexterity subsystem verified in README) |
| `TakeItemCount` | dexterity 1466/1499 read; SearchItem head 161 decrement | — | 5703; decrement missing → | **DIV4.4** |
| `AcquiredInventoryCount` (SearchItem) | InternalUse 191/210 | SetCloseTime 145 | approximated by `item_removed` (world.py:4754) | **DIV4.6** (low) |
| `CloseTime` (SearchItem) | PreUse→SetCloseTime 141-154; Update decrement 256 | Update 252-267 | scene.py:750; world.py:4744-4769 | **OK** mechanics; interval pick + SearchingItem gate → **DIV4.6** |
| `Aux1-4` (SearchItem) | StateSwitcher 214-220; Update 225-244 arms | Update | scene.py:506; world.py:4685-4700 (each combination re-arms the other three) | **OK** |
| `CauseAlarm`/`LastCauseAlarmTime`/`CauseAlarmInterval`/`WakeAlerter`/`AlarmItem`/`ActionDuration` | OnIconPressed 2176-2199; PhoneBehavior 2429-2448 | same | world.py:4857-4921 (icon_pressed, _raise_alarm, _phone_behavior); first-press semantics equal | **OK** |
| `Gg. localized strings` (NameString … SecondRequiredItemString, 27 fields) | one write each in LoadLocalizationData 731-756 (+ the swap hacks 1752-1756, 2115-2117 covered above) | naming/tooltips | scene.py:703-740; hud.py:446-491 | **CONFIG** |
| `MouseOverIcon`/`PrimedMouseOverIconName`/`ChangeMouseOverAfterTrick` | Start 704-715; SetPrimed 1215-1218; CanWoodyUse 1710-1713 | MouseCursor | scene.py:767-774; world.py:5179-5181; hud.py `_swap_cursor_icon` | **OK** |
| `TrickCamera` (internal) | RoutineActionUse 145 set / 388 clear | trick-camera subsystem | absent | **OOS** (documented: trick camera unimplemented) |
| `StartTrickCamera`/`DontShowTrickCamera` | Item 841 | camera | absent | **OOS** |
| `SignalScript`/`SignalOnLookAt`/`MouseOverSystemForTutorial`/`TutorialDrawers`/`NFH2Tutorial`/`BlockWhenUsingPickupItem`-InputLock arm | tutorial layer | LevelScript | absent (TutorialDrawers stand-variant has no data — noted in port comment 5638) | **OOS** |
| `AlreadyTrickedOnce` | none | none | absent | **DEAD** |
| `SnakePrimed` (private) | none | none | absent | **DEAD** |
| `PrimedItem` (WoodyPrime local latch 1290-1294) | set/consumed same call | — | folded into woody_prime's head ChangeType | **OK** (equivalent) |
| `Sweets211Aux` (TrickItem) | none | none | absent | **DEAD** |
| `IdleAnimationInProcess` | TrickItem 731 set | **no reader** | absent | **DEAD** (set-never-read in C#) |
| `NextAction…`, `ChangeIronRoutine`/`LastPath` | TrickItem.Fix 450-451 | ActionManager iron jumps | scene.py:424-425; world.py:4421-4422; jumps ported (README Iron/Rope) | **OK** |
| `GoldCup/Turban/Kart/Throne/Bull/Boat/Hatch/Bouquet/Captain/Rabbit206/Cow/Crap` name-hack state | Fix/Use bodies 2063-2776 | — | world.py:4344-4536, 4928-5010, 5880-5902 | **OK** except the three SearchItem-path hacks (**DIV4.5**) and ElephantBucket (**DIV9**) |

### class TrickItem (TrickItem.cs)

| Field | C# writes | C# reads | Port | Verdict |
|---|---|---|---|---|
| `Compound` | serialized | CanWoodyUse 509; GetTrickScore 393; PlayAnimation 824; Rottweiler 702 | scene.py:437; world.py:5406, 2288, 4130 | **OK** |
| `CompoundTricked` | CanWoodyUse 513 set; Item.FixPlantCarnivore 2511 clear | score 393; angry 620/630/702; Rake 5; naming 1170+ | scene.py:439 (serialized init honoured); world.py:5411, 4482; reads 2288, 4070/4079, 2121, hud.py:439 | **OK** |
| `AtHome` | Start 197 (true); RottweilerUse 603 toggle | CanWoodyUse 533; Fix 438; RottweilerUse 604-605 | scene.py:606; world.py:2171-2173, 4412; CanWoodyUse arm covered by `clickable=at_home` (2173) — refusal equal | **OK** (by collider equivalence) |
| `SunShade`/`Shezlong` (private, resolved by Find) | PlayAnimation 801-802 | 869-881 | world.py:2313-2317 (name lookup) | **OK** |
| `OnlyOnceWaterPuddle` | WaterPuddleBehavior 1245 (one-shot) | 1242 | absent — the Valve hover arm rides the unported hover machinery (documented in world.py:4547-4551 comment) | **OOS** (annotated) |
| `WrongZoneItem` (internal) | none | none | absent | **DEAD** |
| `IsBed` | serialized | 537/547; RoutineActionUse 303/513 | scene.py:558; world.py:2546, 2678, 5513, 5751 | **OK** |
| `NoticeWhenEnterZone`/`NoticeWhenWalkNearby` registrations | Start 198-204; CheckDestroyWhenTricked 656-681 removals | zone notice runs | world.py:3880-3888; 4628-4643 | **OK** |
| `UseAtOtherPlace`/`ShouldReturn` | RottweilerUse 599-607 | IsTricked 260; Fix 438; CanWoodyUse 533 | scene.py:485/605; world.py:2169-2173, 4412; scene.py:899 | **OK** |
| `DependsOn`/`UseDependsOnWhenTricked`/`FixDependsOn`/`Dependant`/`AnimateDependant` | Start 218-220 back-link | IsTricked; PlayAnimation 857-881; TryFix 1136-1143; PlayItemAnimation echo 1046 | scene.py:484, world.py:2318-2335, 4294-4300, 4665-4669 | **OK** |
| `Neutral` | serialized | IsTricked; fixing dispatch 843/979 | scene.py:486; world.py:3125, scene.py:899 | **OK** |
| `Animating`/`Looping`/`HideWhenNotAnimating`/`UseAnimationType` | serialized | PlayItemAnimation 1018-1050 | scene.py:503-505 + `animating`; world.py:4644-4669 | **OK** |
| `IdleNormal`/`IdleTricked`/`SecondIdleTricked` swaps | DoubleRequired 1745-1747; ForceFuckedUp 616; Beer 478; hacks (Hatch/Bull/Throne) | ReturnToIdle etc. | world.py:5399-5403, 2177-2180, 4542, 4493-4508, 4444-4445 | **OK** |
| `FuckedUp`-pose fields (`IdleFuckedUp`,`UseFuckedUp`,`PrimedFuckedUp`) | ForceFuckedUp swap 614-618 | ReturnToIdle 701; PlayAnimation 834/885; SetPrimed 1003 | swap 2177-2180; plays 2294/2338, 5197 | **OK** except ReturnToIdle arm → **DIV8.1** |
| `TakeOffIronPrimed` | serialized | Fix 447-456 | scene.py:415; world.py:4419-4424 | **OK** |
| `DependsPigKeys`/`PigKeys`/`PigMilk` | Fix 426-430 (clear keys) | PlayAnimation 837-842 | scene.py:420-422; world.py:4401-4405, 2295-2301 | **OK** |
| `BlockValveAfterFix` | Fix 421-425 | — | world.py:4393-4395 | **OK** |
| `FixAll` | Fix 431-437 | — | world.py:4406-4410 | **OK** |
| `UseMultipleTimes` sync | Update 226-241 | — | world.py:6493-6501 | **OK** |
| `DexterityAlert`/`RottInAnimation` watch | Update 243-249 (+SearchItem 245-251) | — | world.py:6477-6490 | **OK** |
| `IsRottweilerSleeping` | see Item table | — | — | **OK** |
| `LetUntrickTrickedItem`/`SetTrickedOnItem` | OnUseAnimationCompleted 352-355; TryFix 1129-1133 | — | world.py:5875-5878, 4322-4326 | **OK** |
| `ActivateItemAfterUsingObject`/`DelayActivateItemAfterUsingObject` | OnUseAnimationCompleted 333-351; DelayActivateItem 382-389 | — | loaded, never read | **DIV7** |
| `TrickedObject`/`IsGroundTrick` overlays | SetTrickedObjectHidden 400-410; OnUseAnimationCompleted 295-299; Fix 442; SetActiveObjectHidden 495-505 | — | world.py:5853-5855, 4414, 4781-4806 | **OK** (documented overlay pass) |
| `KidActions` (SandSculpture/SandCastle) | RottweilerUse 569→632-653 | — | world.py:2086-2088 (_trick_kid_actions) | **OK** |
| `ChangeActionsWhenTricked208` | MotherUse 1253-1262 | — | world.py:2068-2074 | **OK** |
| `EnableColliderWhenAlerted`/`AlertAnimation`/`AlarmAnimation` | PlayAlertAnimation 1150-1162; PlayAlarmAnimation 1012 | — | world.py:4702-4709, 4901 | **OK** |
| `HoverAnim`/`Ready`/`EnterZone`/`LeaveZone`/`BeforeAngry` | OnMouseHover 557-564; PlayReady 1081; zone 1095-1113; PlayBeforeAngry 1145 | OnItemAnimationCompleted 1059-1079 | world.py:3936-area, zone_reaction 5139, 4129; _item_anim_completed 4547 | **OK** (`PlayReady` callers are behaviors, ported) |
| `TrickProgressBar` | — | ProgressBarTrick | absent | **OOS** (documented: ProgressBarTrick overlay unported, state kept) |
| `DependsOnNFH2` | — | PlayAnimation 931-945 | world.py:2282/2308/2348 (_depends_nfh2) | **OK** |
| `CaptainDoor214`/`SecondCaptainDoor214`/`ExtraItem` | — | CaptainDoorBehavior 2606-2623 | world.py:4935-4952 | **OK** |
| `DogBasketBehavior210` + `ChangeAnimation210` | 918-929 | 920; anger 635 | world.py:2384-2394 area (_change_animation_210), 4082-4088 | **OK** |

### class SearchItem (SearchItem.cs)

| Field | C# | Port | Verdict |
|---|---|---|---|
| `InventoryItems` (hand-over, emptying, `inventory.Item = this` source stamp) | InternalUse 167-207 | world.py:5964-5977 (source stamp via `item=item.pid`) | **OK** |
| `AcquiredInventoryCount` | 145/191/210 | approximated | **DIV4.6** |
| `KeepFull`/`TakeItemCount` head | 158-165 | missing | **DIV4.4** |
| `DontRemoveInventoryItem`→`ItemRemoved` | 192-206 | 5973-5977 (`DexterityKeepItem` term missing — masked by DIV4.4 on the only carrier) | **OK*** |
| `TrickAfterWoodyUse` | 203-205 | 5978-5979 | **OK** |
| `DisableColliderAfterUse` | 180-182 | missing on search path | **DIV4.2** |
| `OpenObject`/`OpenRenderObject`/`CloseTime`/`LeaveToolBoxOpen` | PreUse 125-152, Update 250-268 | world.py:4744-4769 | **OK** / interval+gate → **DIV4.6** |
| `Aux1-4` state switcher | 214-244 | world.py:4685-4700 | **OK** |
| `FullAnimation`/`EmptyAnimation`/`PrimedAnimation`/`TrickedAnimation` | Start 106; OnFinish 118; switcher | scene fields; 5980-5982, switcher | **OK** |
| IceBucket arm (PrimedAnimation=NONE + WoodyPrimeAnimation swap) | 184-190 | missing (the Item.cs:1273 chain IS ported at world.py:5231-5243) | **DIV4** (low, folded) |
| `EnterZone`/`LeaveZone` inverted crab plays | 275-293 | world.py:5110-5137 | **OK** (documented inverted semantics kept) |
| `Looping`/`HideWhenNotAnimating` | PlayItemAnimation 68-89 | world.py:4671-4683 | **OK** |
| `UseItem`-head name-hacks on SearchItems (Rabbit/CowCrap/RubyThrone) | Item.cs:1898-1942 | present but on the trick path only | **DIV4.5** |
| `Used=true` on take | UseItem 1893 | missing | **DIV4.1** |

### class Door (Door.cs)

| Field | C# | Port | Verdict |
|---|---|---|---|
| `PassingPawn` | set PlayAnimation 143; cleared OnAnimationEnded 194 (after enter/leave callbacks); read IsOtherPawnPassing 227, GetPassingPawn 244-248 | set world.py:883 (both sides); cleared 893/915/942/951 at each side's animation end; read 854-855 (both sides, matching `MoveToDoor`'s twin check) | **OK** |
| `PassingPawnTransitionNFH2` | Pawn.cs:300/304, 1007-1018, 1240-1266 claim/release both sides | world.py:1017-1087 (claim pair, release on arrival/zone change; Olga's missing `AdjacentZonesEnabled` kept as shipped — documented) | **OK** |
| `Locked` | Unlock 203; tutorial writes (OOS) | scene.py:926 load; world.py:4808-4814; reads: graph 629, click 5310/5319/5349 | **OK** |
| `UseAlternateIdleAnimation` | Unlock 204 set; ReturnToIdle 214/218 | scene.py:950; set 4814; read 928 | **OK** |
| `OnPawnLeft` | SetOnPawnLeftDelegate has **no caller** | absent | **DEAD** |
| `TemporalLock` | no writes; read ZoneController 21 (graph keeps locked-but-temporal links) | absent; carriers are the three Intro cutscenes only (no playable Woody) | **DEAD**-in-playable-data (annotate) |
| `DisableOnStart` | Start 64-67 | scene `disabled`; L214 pair verified (README) | **OK** |
| `IgnoreIdleAnimation` | 211 (+ enable/disable controller 75-83) | world.py:901/909/925-926 (sprite hidden between passes) | **OK** |
| `ExitDoor`/`ExitAnimation`/`DeltaExitLocation`/`DeltaMotherExitLocation`/`RottweilerExitLocation` | pass/finish contract | ported (README audit items) | **OK** |
| `Unlock`→`SetMouseOverNotLocked` | 202 | cursor swap covered by hover icon fields | **OK** |
| enter/leave anim fields | play sites 85-153 | `_door_anims`/transit | **OK** |
| `CanWoodyUse` locked refusal (Stand_Down + description + ClearTooltip) | 230-240 | world.py:5349-5360 | **OK** |

### class HideItem (HideItem.cs)

| Field | C# | Port | Verdict |
|---|---|---|---|
| `WoodyLeaving` | set Leave 80, cleared OnUseAnimationCompleted 54-57 | absent | **DEAD**-in-practice: `OnUseAnimationCompleted` is dispatched only for `target is TrickItem` (Woody.cs:548) — never for a HideItem; and `UseAfterAnimation` (the flag that would make the guard matter) is False on all 33 HideItems (data scan) |
| `UseAfterAnimation` | ShouldUseAfterAnimationFinishes 48 | no carrier | **DEAD**-in-data |
| `HideWoody` | InternalUse 36-39; Leave 71-74 | world.py:550-551, 560; all 32 ship False — the real hide is `HideOnAnimationEnd` (documented) | **OK** |
| `IdleAnim`/`HideAnim`/`LeaveAnimation` | Start 26-29; InternalUse 40-43; Leave 75-80 | world.py:545-570 | **OK** |
| immediate `InternalUse` + `Woody.Hide` | 32-44 | world.py:5802-5808 | **OK** (`used=True` not set — no HideItem carries UseOnce, data scan) |

### class Alerter (Alerter.cs)

| Field | C# | Port | Verdict |
|---|---|---|---|
| `Alert` | set WakeUp 105; cleared OnRottweilerLeave 133, OnAnimationSequenceCompleted 147/156 | world.py:1327; 1341, 1353, 1360 | **OK** |
| `Awake` | Start 47 false; WakeUp 104; OnRottweilerEnter 124; sleep drop 155 | 1241; 1326; 1335; 1359 | **OK** |
| `TriggeredByWoody` | Update 57/63/68/75 | 1293/1299/1302/1306; consumed at coroutine fire 1318 (same read-at-fire semantics as CoRoutineRottweilerHearAlerter 119) | **OK** |
| `CanStart` | IntroAnimation.cs:293 (post-intro) | hard-coded True at 1245 | **CONFIG** (intro layer documented as not modelled; port = post-intro state) |
| `AlertOnStartTimer` | Update 70-78 countdown, one-shot notice with TriggeredByWoody=false | world.py:1303-1307 | **OK** |
| `CanSleepNow` | set WakeAnimation 201 / cleared 162 — `WakeAnimation` has **no caller** in the build | absent | **DEAD** (PoorSequenceSkates documented dead) |
| `AnimationType` | 56/62 | 1292/1298; sequence pick 1328-1331 (start+dir+dir vs dir+dir) | **OK** |
| `CanSeeWoody` gates (zone, passing, hiding, sneak-or-still ∥ awake) | 81-84 | 1271-1278 | **OK** |
| the two Update notice arms + begging/wake/sleep chain (incl. "neighbour out of zone" sleep guard) | 51-166 | 1287-1361; enter/leave wired at world.py:3436, 5069 | **OK** |
| `AlerterDelay` write from DexterityComponent.cs:80 | dexterity alert plumbing | dex_states (documented) | **OK** |

### Toilet / Television / Rake / Drawing / GroundItem / InspectItem

| Class / field | C# | Port | Verdict |
|---|---|---|---|
| `Toilet` (no-paper branch, `ToiletPaper.InventoryItems` read) | Toilet.cs:7-21 | not modelled | **DEAD**-in-data (0 instances in any scene — census; also documented in README) |
| `Television` (TVOn/TVBad swaps, Start loop) | Television.cs:9-29 | not modelled | **DEAD**-in-data (0 instances — the L102 TV is a plain TrickItem) |
| `Rake` (`Tricked && CompoundTricked` gate, else StopCurrentAction(postpone)) | Rake.cs:3-11 | world.py:2120-2128 | **OK** |
| `Drawing.CurrentDrawingAnimation` | Start 21 reset; RottweilerUse 57 increment/reset 60; Fix 33 | scene.py:834; world.py:2140-2143, 4336 | **OK** |
| `Drawing.DoneCleaning` | RottweilerUse 49-51/64; Fix 36 | world.py:2133-2147, 4339 | **OK** |
| `Drawing.AlwaysSmeared` | declared, never used | absent | **DEAD** |
| `Drawing` hidden-start + hidden-click/tooltip overrides | Start 20; CanWoodyUse 81-88; CheckDescriptionTooltip 90-100 | world.py:3924-3926, 5508-5510, 5755-5757 | **OK** |
| `Drawing.SkipAction` | Fix 35 | 4338 | **OK** |
| `GroundItem.CanWoodyUse` override | GroundItem.cs:3-8 | missing | **DIV2** |
| `InspectItem.CanWoodyUse` override (+`ItemThatChangesTooltip.GotTricked` click tooltip) | InspectItem.cs:5-22 | hover half only (hud.py:610-616) | **DIV2** |

---

## DEAD-in-C# fields confirmed this pass (port omission correct)
`Item.AlreadyTrickedOnce`, `Item.SnakePrimed`, `TrickItem.Sweets211Aux`, `TrickItem.IdleAnimationInProcess` (set at TrickItem.cs:731, zero readers), `TrickItem.WrongZoneItem`, `Drawing.AlwaysSmeared`, `Door.OnPawnLeft` (no SetOnPawnLeftDelegate caller), `Door.TemporalLock` (carriers only in the three Intro cutscenes), `Alerter.CanSleepNow` + `WakeAnimation` + `PoorSequenceSkates` (no caller), `HideItem.WoodyLeaving` + `HideItem.UseAfterAnimation` (dispatcher never reaches HideItems; no data carrier), `Toilet` (0 instances), `Television` (0 instances), `Item.AnimationAngryCollapse` / `FixAnimationExtra` (already in README's dead list).

## Notes (no action)
- `Item.IsAtUseRange`'s walk-up `DontUseOn` skip: kept as shipped (documented).
- `Alerter.CanStart`=True at construction equals the post-IntroAnimation state; consistent with the documented "title cards not modelled".
- The `Item.UsedInventory` capture point differs (port captures after the gates, C# before) — no observable difference: all consuming gate branches return refusal.
- `WoodyPrime`'s triple `ChangeType` (head / PrimedItem arm / ReturnWoodyToStand) collapses to the single head conversion in the port — idempotent on the same held entry.
- `viewer._hit_at` honours `clickable`+`can_use`, which is what keeps the eight `CanUse=False` Alerters and fetched-away tools unclickable — the C# collider/CanUse contract.
