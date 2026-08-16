# Pass 3 — the trick matrix, group s1b: Level107 … Level110

Plans: `tests/plans/s1/Level107.txt` … `Level110.txt`. Driver:
`tests/run_tricks.py` (`SDL_VIDEODRIVER=offscreen python3 tests/run_tricks.py
tests/plans/s1/Level1XX.txt --out=/tmp/nfh-tricks-s1b`). Traces of the last
run of each plan: `/tmp/nfh-tricks-s1b/s1_Level1XX/{results.json,state.jsonl}`
(copies with the driver's stdout: `/tmp/nfh-tricks-s1b/final/L1XX_results.json`,
`L1XX.log`). Final tally: **L107 22 legs / 0 failed, L108 21 / 0 (+1 manual),
L109 21 / 0, L110 18 / 0 — 0 restarts everywhere; 25 of the 26 scoring
tricks the data can express are PAID at the C# score.**

Season-1 particulars that shape all four plans (each read from the source and
the data):

- The `Ground` twins (2 in L107, 6 in L108, 3 in L109, 4 in L110) share ONE
  banana: `RubbishBinBanana(2)` hands `IT_Banana` x0 once — `Woody.AddInventory`
  then `InventoryItems = null` (SearchItem.cs:154-201) and `UseCount 0` is
  spent by the first use (TrickItem.cs:277-282). `TotalTricksCount` counts one
  Ground per level (7/6/7/6 = the other scoring items + 1). Each plan pays the
  Zone03 Ground (on his walk from the Zone02 door to the kitchen item).
- Zone02 holds the Chili dog (`Alerter`, L107-L110): a moving Woody wakes it
  unless sneaking while it sleeps (Alerter.cs:73-76). The driver sneaks
  through it (below).
- Zone07 (the balcony) is a dead end behind Zone06 (the Bed hides Woody in
  L107/108/110; L109's Zone07 is never visited by the routine).
- The level ends when `CompletedTricksCount >= TotalTricksCount`
  (GameInfo.cs:226-231) — L107, L109 and L110 win at their last trick.

## Status per level

Status legend: PAID n (the leg `await <Item> n` passed: `Item.OnTrickDone`
paid n into `GameInfo.TrickDone`, attributed per item by the driver), MANUAL
(a step the data/timing cannot script — a finding), KNOWN (open-bugs list),
PORT (a finding), DEAD (unreachable by the data, listed once per level).

### Level107 (TotalTricksCount 7, winning 5) — 7/7 paid, 82 points, 22 legs / 0 failed

| trick | status | leg |
| --- | --- | --- |
| DieselChair (IT_Pins, UseOnce) | PAID 10 | `take PinsBoard IT_Pins`, `usewith DieselChair IT_Pins`, `reclick DieselChair` (UseOnce+Used → CantUse/WrongTrick, no change, Item.cs:1654-1668) → `await DieselChair 10` (t=49) |
| DieselGenerator (IT_Wrench) | PAID 15 | `take Drawer IT_Wrench`, `usewith DieselGenerator IT_Wrench` → `await DieselGenerator 15` (t=75) |
| Ground@Zone03 (IT_Banana, NoticeWhenWalkNearby) | PAID 8 | `take RubbishBinBanana IT_Banana`, `usewith Ground@Zone03 IT_Banana` → `await Ground@Zone03 8` (SlipRight, t=43) |
| Ground@Zone02 | DEAD | the second banana does not exist (one Ground counted, above) |
| MumStatueFootStool (bare hand, UseOnce; PlayAngryAnimation's name-hack un-tricks it, Rottweiler.cs:715-718; RottweilerUseFuckedUp `Cry` on later visits) | PAID 15 | `use MumStatueFootStool` → `await MumStatueFootStool 15` (t=87) |
| Camera (IT_Magnesium; RottweilerUseTogglesPrime, ships Primed, DeltaPrimedLocation 1.3) | PAID 12 | `take MagnesiumBottle IT_Magnesium`, `usewith Camera IT_Magnesium` → `await Camera 12` (TakePhotoTricked on his primed visit, t=127) |
| Dove (IT_Scissors, NoticeWhenEnterZone, DestroyAfterUseTricked, no CanFix) | PAID 10 | `take FirstAid IT_Scissors` (the kit hands scissors + antispot), `usewith Dove IT_Scissors` → `await Dove 10` (FindLeftFar on entering the balcony, t=172) |
| Drawing (`Drawing` subclass, IT_Antispot, NoticeWhenWalkNearby; the wall is Hidden until his first drawing, Drawing.cs:17-22/81-88) | PAID 12 | `usewith Drawing IT_Antispot` (after his first `BalconyDrawing`) → `await Drawing 12` (FindRight surprise → angry, t=177) — the KNOWN "Drawing tricks never go angry" did not show here: the walk-nearby surprise paid it |
| MumStatueDummy (IT_Detergent) | DEAD | no detergent in the level (score 0 anyway) |

Notes. The camera starts Primed and his [1] use unprimes it, [2] takes the
magnesium, [3] primes again (Item.cs:1064-1078); Woody's magnesium lands
whenever (no RequirePriming on the Camera → the 1520 gate does not apply)
and pays at the next primed visit. The balcony raids: Woody hides in the
Zone06 Bed while he passes to and from the balcony (`hide Bed`), the two
`await`s after `hide` keep him hidden (a hidden Woody is not parked out).

### Level108 (TotalTricksCount 6, winning 4) — 5/6 paid, 73 points, 21 legs / 0 failed, 1 manual

| trick | status | leg |
| --- | --- | --- |
| ToothBrush (IT_Brush; RemoveFromRoutineAfterFirstUse, ReuseAfterFix; his action [0]) | MANUAL — see finding 1 | `manual ToothBrush 15: …` |
| Shezlong (IT_Pins; DependsOn SunLotion, FixDependsOn, ReuseAfterFix) | PAID 10 | `take PinsBoard IT_Pins`, `usewith Shezlong IT_Pins` → `await Shezlong 10` (SunBath, PinsJump → angry → fix → RestartCurrentAction, t=64) |
| SunLotion (IT_Honey; not in the routine — fires at his Shezlong use through the DependsOnWhenShadeTricked branch, TrickItem.cs:869-881, only while SunShade.Tricked; paid through GetTrickedItem → DependsOn, RoutineActionUse.cs:556-568) | PAID 20 | `use SunShade` (bare hand, Neutral), `take Fridge IT_Honey`, `usewith SunLotion IT_Honey +10` → `await SunLotion 20` (SunBath, SunBathLotion, SunBathBees, the RottweilerExtraAngryAnimation PinsJump, t=236) |
| CoffeeMaker (IT_Soil_only; AngryWithoutAnimations) | PAID 15 | `take SoilBag IT_Soil_only`, `usewith CoffeeMaker IT_Soil_only`, `reclick CoffeeMaker` → `await CoffeeMaker 15` (SpitLeft, then the toilet rush RunWC*, t=149) |
| Plant (IT_Balloon — no source; DependsOn WateringCan, DestroyAfterUseTricked; StopAction's `RemoveActionByItem(Plant)` name-hack sets Plant.Tricked, ActionManager.cs:748-753, so GetTrickedItem returns the Plant) | PAID 20 | `take BedDrawer IT_Key`, `prime FirstAid IT_Key` (the FirstAid+key hack: Locked=false, WoodyPrime, the key becomes IT_Poison — Item.cs:1407-1411, 1246-1250), `usewith WateringCan IT_Poison` → `await Plant 20` (WaterPlantTricked → angry at the removed action, t=205) |
| Ground@Zone03 (IT_Banana) | PAID 8 | `take RubbishBinBanana2 IT_Banana`, `usewith Ground@Zone03 IT_Banana` → `await Ground@Zone03 8` (SlipRight on his coffee walk, t=135) |
| BeeHive (IT_Balloon), WateringCan (score 0, UseAtOtherPlace), SunShade (Neutral) | DEAD / not scoring | no balloon source; the can and the shade are fuses of the Plant / SunLotion |

Notes. The SunShade must be "tricked" (folded) or the Shezlong use never
reaches the lotion (`SunShade.Tricked && …` in both shade branches). The
locked kit contains nothing; the poison exists only through
`PrimedInventoryType` (Item.cs:1246-1250). The watering-can dance after
the Plant (RemoveWateringCan / RemoveNow, ActionManager.cs:748-790) ran:
the routine dropped the Plant and re-parked the can.

### Level109 (TotalTricksCount 7, winning 5) — 7/7 paid, 83 points, 21 legs / 0 failed

| trick | status | leg |
| --- | --- | --- |
| AlarmClock (IT_Cactus, AngryWithoutAnimations) | PAID 13 | `take Cactus IT_Cactus` (Zone07), `usewith AlarmClock IT_Cactus` (the click aimed past the Bed's covering box) → `await AlarmClock 13` (BedAlarmCactus, BedOut, t=153) |
| Pig (IT_Pigkey; DependsOn PigMilk, DependsPigKeys, NoticeWhenWalkNearby, IgnoreDependsOnWhenFixed) | PAID 20 | `take PigKeys IT_Pigkey` (during his sleep — the hook holds them only while Primed, Item.cs:1057-1063/1515; TrickAfterWoodyUse arms them, DontPrimeWhileTricked keeps them Primed through his [4] visit → SurpriseNotFound), `usewith Pig IT_Pigkey` → `await Pig 20` (t=188) |
| PigMilk (IT_Nitro; UseAtOtherPlace+ShouldReturn; pays at the Pig through GetTrickedItem → DependsOn) | PAID 20 | `take ChemicalSet IT_Nitro`, `usewith PigMilk IT_Nitro` → `await PigMilk 20` (ShakePigMilk ×3, ShakePigMilkExplode at the pig, t=329) |
| Bed (IT_Pins; IsBed, the sleep bar; ReuseAfterFix; IsRottweilerSleeping refuses Woody, TrickItem.cs:537-541) | PAID 8 | `usewith Bed IT_Pins` (with the bed empty, t=298) → `await Bed 8` (BedIn, BedPinsJump, t=389, the level wins) |
| Chili (score 15; DependsOn CornChips) | PAID 0 as CornChips — see finding 2 | `take SpicyChips IT_Chips`, `usewith CornChips IT_Chips` → `await CornChips 0` (t=365; `completed` +1) |
| Teeth (IT_Tabasco; RequirePriming + RottweilerUseTogglesPrime — Woody only while Primed, Item.cs:1520) | PAID 15 | `take Fridge IT_Tabasco`, `usewith Teeth IT_Tabasco` (during his sleep, primed by his [0]) → `await Teeth 15` (TakeInventory, SpitFire at [3], t=279) |
| Ground@Zone03 (IT_Banana) | PAID 7 | `take RubbishBinBanana2 IT_Banana`, `usewith Ground@Zone03 IT_Banana` → `await Ground@Zone03 7` (t=305) |
| Ground@Zone01, Ground@Zone06 | DEAD | one banana |

Notes. The bedroom is worked while he sleeps (~30 s per lap: BedSleep is
the sleep bar's window, `IsSleeping` gates the catch — but the Bed branch of
`CanRottweilerSeeWoody` swaps the sleep term for `Woody.Velocity > 0`
(GameInfo.cs:183-185): a running Woody in the room is caught, a sneaking one
is not, because the sleeper's BedSleep is a blocking animation and the
common chain carries `!IsPlayingBlockingAnimation() || !Sneaking`). The
driver tiptoes whenever a catcher shares the room; the L109 raids ran clean.
The AlarmClock's collider centre sits inside the Bed's box (the raycast's
nearer face wins, Viewer._hit_at); the driver aims at the sliver of the
clock the bed leaves free (`_click_point_of`).

### Level110 (TotalTricksCount 6, winning 5) — 6/6 paid, 85 points, 18 legs / 0 failed

| trick | status | leg |
| --- | --- | --- |
| SteakChair (IT_Pins, ReuseAfterFix) | PAID 10 | `take PinsBoard IT_Pins`, `usewith SteakChair IT_Pins` → `await SteakChair 10` (SitSteakStart → angry, t=63) |
| SteakWine (IT_Vinegar) | PAID 15 | `take Fridge IT_Vinegar`, `usewith SteakWine IT_Vinegar` → `await SteakWine 15` (DrinkWine → angry, t=77) |
| Ground@Zone03 (IT_Banana) | PAID 10 | `take RubbishBinBanana2 IT_Banana`, `usewith Ground@Zone03 IT_Banana` → `await Ground@Zone03 10` (SlipRight on his steak walk, t=94) |
| BBQ (IT_Cork — no source; RequirePriming + RottweilerUseTogglesPrime, ships Primed; DependsOn Beer, FixingItem FireExtinguisher, FixDependsOn, no CanFix) — tricked by the Beer's fuel via `SetTrickedOnItem` (TrickItem.cs:352-355) | PAID 20 | `take FirstAid IT_Fuel` (fuel + growth liquid), `usewith Beer IT_Fuel +8` → `await BBQ 20` (TakeGround at the beer, BarbecueBeer, BarbecueBurn → angry, t=179) |
| FireExtinguisher (bare hand; the BBQ's FixingItem — pays only as the fetched tricked tool: RoutineActionUseFixingItem's own-trick + RedoAction, README "The fixing-tool run") | PAID 15 | `use FireExtinguisher` → `await FireExtinguisher 15` (Run to Zone06, TakeInventory grab, back, FireExtinguisherStart, FireExtinguisherTricked → angry, t=193; then FireExtinguisherRepair, Start, Loop = the redo and the fix of the Beer, LetUntrickTrickedItem un-tricks the BBQ) |
| CarnivorPlantSpray (IT_Growthliquid, RemoveFromRoutineAfterUseTricked) | PAID 15 | `usewith CarnivorPlantSpray IT_Growthliquid` → `await CarnivorPlantSpray 15` (CarnivorPlantSprayTricked, CarnivorPlantFight → angry, t=214, the level wins) |
| Beer (score 20) | DEAD as a payer — see finding 3 | its `usewith` is the BBQ's arm |
| Ground@Zone02/06/07 | DEAD | one banana |
| SteakMeat / PigPen (IT_Handy, Neutral), SteakTable (Neutral), SteakWineGlass (score 0), CarnivorPlant (InspectItem) | not scoring | IT_Handy has no source; the InspectItem was never clicked (KNOWN "InspectItem clicks trick it" not exercised) |

Notes. No dexterity gate exists in Season 1: `Dexterity`/`DexterityTrickItem`
are set only on S2 items (L201-213); the `DexterityUnlocker IT_Antispot` on
every S1 item is the serialized default. The `unlock` leg was not needed.

## Findings

### 1. L108 ToothBrush (15) — unreachable in the port by ~0.1 s under perfect input (open, needs the original's timing)

The C#: the toothbrush is his action [0] and `RemoveFromRoutineAfterFirstUse`
drops the action in `StopAction` after that first use (RoutineActionUse.cs:
424-427 → `ActionManager.RemoveActionByItem`, cs:748-774); Woody must arm it
before he brushes. The port's numbers (`state.jsonl`, and a perfect-input
script clicking the Drawer the frame the entrance Hello ends): Woody in
Zone01 at t=3.05, brush taken 5.5, bathroom door 8.7, in Zone04 10.8,
tricked 11.97 (MakeTrick), back at the door 12.6 — the neighbour (DelayStart
1.5, walk 0.875 u/s, the Zone06→Zone02 and Zone02→Zone01 walk-up passes
~3 s each) claims the Zone01→Zone04 door pair at 12.55 (`IsOtherPawnPassing`
parks the other pawn standing, Pawn.cs:1359-1364; the port's
`_wait_for_passing`) and lands in Zone04 at 14.47 → Woody standing at the
door is caught. Every alternative fails by the same rules: crossing him in
the door is impossible (the pair is held), Zone04 has no HideItem, and once he
is in the room only a blocking animation or a sneak past a *blocking*
neighbour hides Woody (GameInfo.cs:189) — his walk to the sink is not
blocking. The plan carries it as `manual`. Whether the original's frame
timing (a variable `Time.deltaTime` against the port's fixed 60 Hz, the same
door and animation data) leaves the extra ~0.1-0.6 s cannot be decided from
the port; the intent of the data (TotalTricksCount 6 counts it) says the race
should be winnable. Classified MANUAL/PORT-suspect, not fixed.

### 2. L109 Chili (TrickScore 15) pays 0 — a C# fact, the port matches

The Chili's use with the tricked CornChips plays `DependsOn.GetUseTricked
Animation` (TrickItem.cs:857-862); `StopAction` then calls
`PlayAngryAnimation(GetTrickedItem(Chili))` and `GetTrickedItem` returns the
DependsOn when the item itself is not `Tricked` and `ForceFixOriginal` is off
(RoutineActionUse.cs:556-568) — so `CornChips.OnTrickDone` fires with its
`TrickScore 0` and `CompletedTricksCount++`. The Chili's own 15 is dead data
in this build; the plan asserts `await CornChips 0` and it passed. Not a port
divergence — recorded so nobody "fixes" the port to pay 15.

### 3. L110 Beer (TrickScore 20) never pays; the BBQ (20) does — a C# fact

The Beer is `UseAtOtherPlace`: `TrickItem.IsTricked` reads `Tricked &&
!UseAtOtherPlace && !Neutral` (cs:260), so his Beer action never goes angry;
the fuel's `SetTrickedOnItem` sets `BBQ.Tricked` (cs:341-343) and the BBQ's
own use pays the BBQ. Together with the impossible `IT_Cork` on the BBQ this
is why TotalTricksCount is 6 for 7 scoring items. The port matches
(`await BBQ 20`, `await FireExtinguisher 15` passed in that order).

### 4. Data facts worth keeping (no divergence)

- One banana per level (above): the Ground twins are alternatives, not
  separate tricks; the plans pay one and list the rest DEAD.
- L108's kit is empty (`InventoryItems=[]`, `Locked`, `RequirePriming`); the
  key→poison conversion is the only poison source, and `RemoveActionByItem`'s
  Plant name-hack is what makes the Plant pay its own 20 rather than the
  can's 0.
- No dexterity gates in Season 1 (the note handed to this group about L110's
  gates was wrong; verified over all 28 level files).

## Driver changes made in this group (all in tests/run_tricks.py)

- Per-item pay attribution (`Driver.paid`, filled in `step_world` from the
  `AlreadyTricked` flip against the new `GameInfo.log` entries) and an
  order-independent `leg_await`: a trick that paid earlier passes at once,
  the score is checked against the paid table; a hidden Woody stays hidden
  during an await instead of walking out; the parking walk is gated like a
  leg (`gate_open` on the safe zone, re-fired every 4 s).
- `gate_open`: the route is read whole — the catchers' ETA to every zone
  Woody crosses against his real arrival/departure there (`arrive[]`, sneak
  pace in Alerter rooms, per-door pass times); a dead-end target with no
  HideItem also needs the exit (walk to its only door + the pass) before the
  catcher's ETA (the door pair is held while he passes).
- Plan modifiers: `op!` (rush — no gate wait, no dodging for that leg; the
  human's judgement call) and a trailing `+N` (the gate holds N more seconds:
  a raid into a dead end sized as a whole).
- New leg `hide <HideItem>` (climb into the bed/wardrobe and stay; the next
  leg's click brings Woody out).
- Auto-sneak (`_auto_sneak_tick`, default; `sneak on|off|auto` in a plan
  overrides): tiptoe in and into Alerter rooms, tiptoe whenever a catcher
  shares the room Woody is in or is warping into (the blocking-animation
  escape of GameInfo.cs:189, the Bed branch's Velocity term), run when a
  catcher is due in a pet room sooner than the tiptoe to the flee door;
  `woody_speed` reads the shared-room tiptoe too so the flee math matches.
- Dodge: the "route ahead" check ignores a catcher standing in the next zone
  but leaving it before Woody's door (and stops Woody only when he is not
  about to be walked into here); `_occupied` counts a warping catcher in the
  room he warps INTO, not the one he leaves; the "sealing" flee applies only
  from a one-door room and only with >1.5 s of slack; a withheld poke is
  retried within a second (the clear windows of a tight routine are shorter
  than the 8 s cadence).
- `TRICKS_DEBUG=1` prints each click's target/result and a 0.5 s pawn trace.

Other agents' concurrent additions this group leaned on: `use_len`
(sequence-length ETAs), `wait_gate` + `_stage_toward`, `_escape_slack`,
`_click_point_of` (the raycast-aware click point), `woody_door_time`,
`use_time`.
