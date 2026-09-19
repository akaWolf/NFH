# The neighbour's lap: PC original vs the mobile remake, all 28 episodes

> The lap ORDER of every Season 1 level is read from game.exe itself since
> 2026-09-16 (`tools/pcref/routine_order.py`, docs/PC_VERIFICATION.md "The
> routines and the scripts") and equals the mobile routine on all fourteen
> levels; this file remains the timing reference.

Measured 2026-09-06. PC side: Badinfos' 100 % runs (720p), the HUD's
neighbour-activity bubble sampled once a second and clustered
(`tools/pcref/bubble.py`), icons labelled by eye from the cluster sheets.
Mobile side: the port's recordings of the standard plans (the neighbour's
`using` item per frame) plus the `ActionManager` action lists in
`levels/*.json`. A "lap" is start-to-start of the routine's first activity;
PC laps after the first are often stretched by the run's tricks (angry
bursts, toilet rushes), so the CLEAN lap is the first undisturbed one.
Confidence: ±2 s on PC boundaries, ±1 s on mobile.

## Season 1

| ep | PC order (bubble) | PC lap | mobile order (ActionManager) | mobile lap | Δ |
|---|---|---|---|---|---|
| 101 The First Trick | Sofa/TV → Binoculars | 32 (then 59 with the tricks) | Sofa → Binoculars | 48-52 | mobile +50 % |
| 102 TV Time | Sofa → Beer (→ Toilet on the laxative) | 28-36 | Sofa → Beer | 38-43 | mobile +25 % |
| 103 Birthday Surprises | LetterBox → Cake+Candle | 32 | Candle → Cake → Cake → LetterBox | 33 | same |
| 104 The Apple Pie | Sink(shave) → Pie → Microwave → Deodorant | 62-80 | Pie → Microwave → Cream → Pie → Deodorant → AfterShave → Sink ×2 → AfterShave → Deodorant | 92 (27+65) | mobile +15-30 % |
| 105 The Old Spoilsport | Piano → Football → Plant (Phone, Toilet on tricks) | 40 | Piano → Football → Window → PlantStink | 50 | mobile +25 % |
| 106 Bath Time | Album → Candy → Pudding → BathTub (→ Towel) | 48-60 | Album → Candy → Pudding → BathTub ×2 (→ Towel) | 50-58 | same |
| 107 Art For Mum's Sake | Drawing → Camera → Pottery → MumStatue | 54-58 | Drawing → Camera → Magnesium → Camera → DieselChair → Generator → FootStool | 102 | mobile +80 % |
| 108 A Sunny Morning | ToothBrush ONCE (5-23 s) → Coffee → DeckChair → Can → Plant → Can → Coffee … | 95-97 | ToothBrush once (16 s) → Coffee → Shezlong → Can → Plant → Can | 95 | same |
| 109 One Little Piggy | Teeth → Bed → Alarm → Keys → Milk → Pig → Milk → Chips → Chili → Keys | 117 | Teeth → Bed → Alarm → Teeth → Keys → Milk → Pig → Milk → Chips → Chili → Keys | 113 | same |
| 110 Barbecue Time | Meat → Beer (BBQ) → Eat → Wine | 63-64 | Meat → Beer → BBQ → Spray → BBQ → Chair → Wine | 80 | mobile +25 % |
| 111 Laundry Day | Detergent → Washer → Drier → Iron → Airer → Fish → Airer → Iron | 122 | Detergent → Washer ×3 → Drier ×3 → Iron → Airer → Fish → Airer → Iron | 118 | same |
| 112 Fitness Frenzy | Book → Fish → Yoga → Book → Trampoline → Bike → Mixer → Expander → Weights → Rope | 135 | same ten, Mixer ×2 | 183 | mobile +35 % |
| 113 Do It Yourself | Chair → Grinder → Valve → Radiator → Sink → Valve → Fuse → Ladder → Fuse | 191 | Chair → Grinder → Valve → Radiator → Sink → Valve → Fuse → Ladder → Drill → Fuse | 204 | same (+7 %) |
| 114 Night of the Hunter | Polish → Cup → Polish → Pipe → Gram → CDs → Gram → Pipe → Gram → Shotgun → Hat → Horn | 168 | the same, MedalBox inside the Hat | 202 | mobile +20 % |

## Season 2 / On Vacation

| ep | PC order (bubble) | PC lap | mobile order | mobile lap | Δ |
|---|---|---|---|---|---|
| 201 All Aboard | Hat → Buffet → Rail/Puddle (tutorial) | 40-75 | Hat → Buffet → Puddle → Rail → Puddle | 55-175 | tutorial, n/a |
| 202 Covert Advance | Mat → Rake → Swim → BridgeRail | 70 | Mat ×2 → Rake → Swim → Rail | 69-80 | same |
| 203 The Cabin Is Occupied | Microphone → Toilet → Melons → Bicycle | 84 | Microphone → Paper → Flush → Melon → Bicycle | 91 | same (+8 %) |
| 204 From Whom The Gong Sounds | Kart → Karate → Gong → HotDog → Necklace | 81 | the same five | 76 | same |
| 205 Ping-Pong Fucius | Tennis → Skis → Chef → Rockets → Sculpture | 102 | Mat → Tennis → Skis ×2 → Chef → Rockets → Sculpture | 113 | same (+10 %) |
| 206 Every Shot A Hit | Mum/Chair → Pillows (once) → Dog → Pad → Harpoon → Pad → Weights → Pad → Dynamite → Pad → Harpoon → Dog | ~173 | Dog → Chair → Pillows → Chair → Dog → Pad → Harpoon → Pad → Harpoon → Pad → Weights → Dog → Dynamite | ~185 | same |
| 207 Mummy's Darling | Board → Bar → Elephant → Shell → Castle → Towel | 107 | the same six | 102 | same |
| 208 Above The Clouds | Platform → ShoeMachine → Elephant → Bowl (Mother/Fifi episode) | 71-75 | Platform → ShoeMachine → Elephant → Bowl | 76-98 | same |
| 209 Burning With Ambition | Fakir → Taj → Shoes → Coal → IceCream → Cow | 97 | Fakir → Shoe → Taj → Shoe → Coal → IceCream → Cow | 96-97 | same |
| 210 The Enlightenment | DeckChair (15 s) → Mother → Basket → Turban → Elephant → Basket | 102-120 | DeckChair (55 s sleep) → Mother → Basket → Turban → Elephant → BasketPut | 165 | mobile +38 % (the sleep) |
| 211 Neighbour Over Board | Sweets → Rod → LifeBoat → Jacket → DivingGear | 68 (117 with the walks) | the same five | 82-89 | mobile +20 % |
| 212 Action! | Throne → Whip → Cigars → (Bench) → Bull → Parrot | 113 | Throne ×2 → Whip → Cigars → Bench → Bull → Parrot ×2 | 133 | mobile +18 % |
| 213 Eat And Be Eaten | Bull → Plant → Tortilla → Boat → Pinata → MechBull → Cement | 136 | the same seven | 112-125 | mobile −12 % |
| 214 Don't Panic | Shower → Bouquet → Wheel → Pistol → Hatch | 91-102 | Shower → Bouquet → CaptainDoor → Pistol → Hatch | 95-106 | same |

## What it says

- **The order is the PC's in every episode.** Nordi re-authored the
  routines as ActionManager lists, but the sequence of activities matches
  the PC bubble sequence one for one, including the doubled steps (109's
  Teeth before and after the bed, 111's three washer visits, 114's Polish
  twice) — where the mobile list has an extra item it is a sub-step the PC
  bubble does not split (Drill inside Ladder, MedalBox inside Hat,
  CaptainDoor for the Wheel).
- **108 is faithful.** The PC neighbour brushes his teeth ONCE, at the
  start (5-23 s in Badinfos' run), and never again in the routine; the
  toothbrush icon returns only after the soil coffee (TheMusician05's run,
  342 s) — the rinse rush. The mobile's `RemoveFromRoutineAfterFirstUse` on
  the ToothBrush and the CoffeeMaker's RushToToilet reproduce exactly that.
  `docs/PC_FIDELITY.md` §2.2 and the earlier "brushes every lap" reading
  were wrong and are corrected.
- **Periods:** the table above compares the PC run with the port's PLAN
  runs, and both carry the tricks' reactions — its "mobile slower by
  20-80 %" on nine levels is that contamination (a 41 s Shotgun in 114 is
  ElectricShock + AngryHard + FixMid, the aim itself 3 s). The natural
  laps, measured on idle runs, are below: within ±15 % on 21 of 26
  comparable levels; the exceptions are scenes, not speeds.
- **114 on PC:** the Zone02 stretch (Pipe → Gram → CDs → Gram → Pipe →
  Gram) is 46 s (54-100 s of the lap); the mobile's is 37 s (63-100). The
  whistle window sits inside it on PC.
- The per-activity durations for every episode are in
  `docs/PC_LAPS_DETAIL.md`.

## Natural laps (idle runs, 2026-09-06)

`tools/pcref/laps_natural.py`: the port driven by a wait-only plan (Woody
dodging, nothing armed — no angry sequence stretches an action), one lap =
the mobile routine list once, each action paired by name with the PC bubble
span of the first PC lap (a mobile sub-step the bubble does not split is
folded into its neighbour). PC / mobile seconds; the actions off by 5 s or
more.

| level | PC | mobile | Δ | where |
|---|---|---|---|---|
| 101 | 32 | 40 | +25 % | Sofa 15/21 |
| 102 | 28 | 31 | +10 % | |
| 103 | 42 | 39 | −8 % | Candle+Cake 10/17, LetterBox 23/14 |
| 104 | 36-80 | 64 | ≈ | the PC's first lap is cut by the intro (Sink 2 s), its second carries tricks; the shaving chain 17/34 |
| 105 | 40 | 39 | −2 % | |
| 106 | 108 | 88 | −19 % | PhotoAlbum 19/12 |
| 107 | 54 | 60 | +11 % | |
| 108 | 94 | 104 | +11 % | Coffee+DeckChair 30/45 — the walks, the sunbath itself is 3 s |
| 109 | 113 | 112 | 0 % | Bed 27/32 |
| 110 | 59 | 59 | +1 % | |
| 111 | 122 | 118 | −3 % | the first lap (PC_LAPS_DETAIL: Detergent 5 to 127); the pairing had summed the second, tricked lap's washer 47 and drier 26 into a 219 |
| 112 | 155 | 159 | +2 % | Mixer 14/20, Weights 14/20 |
| 113 | 191 | 168 | −12 % | Ladder+Drill 47/26 |
| 114 | 168 | 165 | −2 % | |
| 201 | n/a | n/a | | the tutorial drives him |
| 202 | 94 | 87 | −8 % | BridgeRail 27/21 |
| 203 | 84 | 80 | −5 % | Microphone 18/24, Watermelon 22/14 |
| 204 | 81 | 71 | −13 % | Gong 23/15, Necklace 24/16 |
| 205 | 102 | 127 | +24 % | the Olga-mat scene (20 + 12 s, no PC counterpart); without it 88, −14 % |
| 206 | n/a | n/a | | he waits for the Mother (WaitWatch) — event-driven on both |
| 207 | 107 | 103 | −4 % | |
| 208 | 71 | 65 | −8 % | IndianPlatform 9/18, ShoeMachine 35/28 |
| 209 | 97 | 96 | −1 % | the order differs (PC Taj → Shoe, mobile Shoe → Taj → Shoe), the sum matches |
| 210 | 102 | 118 | +16 % | DeckChair 25/54 — he sits until the Mother's call |
| 211 | 68 | 72 | +6 % | |
| 212 | 113 | 122 | +8 % | |
| 213 | 136 | 114 | −17 % | CementBath 36/18 |
| 214 | 91 | 81 | −11 % | the PC's CaptainWheel bubble is the door (16 s; unpaired before 2026-09-23, the PC lap read 75); Hatch 34/19 |

Slower on mobile: 101 (+25 %, the sofa), 210 (+16 %, the chair), 108 (+11 %,
the walks); faster: 106, 113, 213, 214 (−11..−19 %); the rest within ±10 %.

The Season 2 laps under the profile (2026-09-23: the walk, the stays, the
routes and the catch by GameLogic.dll; idle runs, the lap period on the
neighbour's first station, ~/nfh-bench/runs/idle2s2): against the code's lap
model (tools/pcref/lap_model_s2.py) 203 99.5 s / 105, 208 82.5 / 85.5, 209
102.7 / 104, 211 80.8 / 85, 212 125.2 / 124, 213 125.3 / 123, 214 85.3 /
90.3 (its Mother's script and the pistol's poll carried the same night) and
202 81.7 / 80.7 plus his wait at the shore for Olga's sub (its mat and swim
carried the same night: docs/PC_FIDELITY.md "202's mat and swim"; the
video's 70 and 90-94; 60.2 before, on the video's stays) — within 6 %;
against the video on the levels the code does not close 204 79.2 / 81, 205
89.3 / 102, 207 109.3 / 107, 210 86.8 / 102 (120.7 before the path finder's
routes: the walks around the pool ring). 201 (the tutorial) and 206 (his
waits on the Mother) have no free lap.

The same Season 1 laps from the code and the data (`tools/pcref/lap_model.py`,
2026-09-17): the level class's lap as the walker reads it out of game.exe,
walked at the neighbour's speed records (8 px a tick along the floor, 3 up
and down, 12 a second) between the objects' hotspots through the doors
(their standing points and `enter`/`leave` ticks), the actions at their
`time` or animation frames — 101 34 s (video 32), 102 29 (28), 105 44 (40),
108 90 (94), 109 104 (113), 110 60 (59), 112 143 (155), 113 172 (191),
114 147 (168): nine within ±12 %. 103 (28/42), 106 (60/108) and 107
(37/54) come out short: the bath is not in the tokens, and the video's lap
may carry a trick. 111 is 114 s against its first lap's 122 (2026-09-23:
the 219 was a pairing of the second, tricked lap; the walker reads the
board's clothes and irons them, below), 113 167 and 114 153 since the
walker follows the objects' presence (tools/pcref/routine_order.py:
isObjectPresent over level.xml and the switches — 113's valve switched off
and on at 0.33 s where the false branch had two 2-s surprises, 114's third
phonograph visit). The model is the check of the walking rule read from the binary
(docs/PC_VERIFICATION.md, "the walking speed" and "the lap's timing").

The port's own idle laps under the profile's four rules read from the
binary and the data — the walking speeds, the door pass (both clips in
turn at their ticks), the catch on sight and the stations' durations
(2026-09-17, `~/nfh-bench/runs/idlepc4`, the neighbour alone on every
level): 101 34 s (model 34, video 32), 102 27 (29, 28), 103 25 (28), 104
70 (70), 105 43 (44, 40), 106 120 (video 108), 107 62 (video 54), 109 108
(104, 113), 110 55 (60, 59), 111 120 (108), 112 141 (143, 155), 113 180
(172, 191), 114 168 (147, 168). Every level with a complete model is
within 10 % of it, the rest within 15 % of the video; what 110 still lacks
against the model is the PC's vertical legs to the hotspots (the meat bowl
30 px above the floor line, the back doors' 50 — 3 px a tick each), which
the mobile's item positions do not have.
Under the PC profile (2026-09-09) the sofa and album overlays
(levels/pc/Level101, Level106: RottweilerUseAnimation lists sized to the PC
spells) bring 101 to +11 % and 106 to −6 %; 111, 213 and 210 are
structural (docs/PC_FIDELITY.md §7). 111's washer and drier are one
station each in game.exe (give, wash, get_clothes; give, dry, take — the
2026-09-16 reading of two cycles was the case's two branches, the tricked
and the normal one), the mobile's three-phase machine kept whole under the
profile since 2026-09-23 (the tricked use ends the station) and its three
legs at the case's three DoActions (the washer's give 0.33 s, wash 4.92 —
objects.xml `time="59"`, the neighbour's `wait` clip over the machine's
loop — and get_clothes 2.0; the drier's give 0.33, dry 2.42 and take 0.33);
there is no wait step beside them (the `wait` helper fcn.0047c640 of the
switch steps runs a held object's method and completes at once), and the
first lap's bubble — the washer 24 s, the drier 6 — is the walk to each
and those actions (the model's 18.8 and 4.1 s); the 47 and 26 s were the
second lap's, the wine and the tongs tricked.
The PC's own numbers are from one run's first lap (±2 s per activity).
