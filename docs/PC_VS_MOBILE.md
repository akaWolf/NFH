# PC (2003/2004) vs the mobile remakes (Nordi Games, 2017)

What the two share, where the mobile data diverges, and what that does to the
100 % rating. The mobile side is the decompiled truth of this repo
(`levels/*.json`, `src/Assembly-CSharp`); the PC side is not available as
data — it is read from the PC 100 % walkthroughs, so a PC trick list here is
"what the guide does", not a data dump.

Sources:

- PC Season 1: [Neighbours From Hell 100% Viewers' Rating Guide](https://steamcommunity.com/sharedfiles/filedetails/?id=2584421942)
  (Steam, 2021; every episode, with videos).
- PC "On Vacation": [Neighbors From Hell 2 100% Completion Guide](https://steamcommunity.com/sharedfiles/filedetails/?id=2586279724)
  (Steam, 2021; every episode).
- PC 100 % videos: Badinfos' "ALL Seasons [100% walkthrough]" and "NFH 2 — ALL
  Episodes [100%]"; TheMusician05's "Season 1/2 all levels 100%" (2026 — the
  PC game despite the title, see the storyboard check below).
- Mobile: this repo's data, `tests/plans/*`, the bench replays
  (`tools/livediff/README.md`, "The rating"), the App Store / 4PDA threads.

## The games are the same fourteen episodes, twice

| mobile | PC episode (S1 game) | mobile | PC episode (NFH2: On Vacation) |
|---|---|---|---|
| 101 | The First Trick | 201 | All Aboard |
| 102 | TV Afternoon | 202 | Covert Advance |
| 103 | Birthday Surprises | 203 | The Cabin Is Occupied |
| 104 | The Apple Pie | 204 | From Whom The Gong Sound |
| 105 | The Old Spoilsport | 205 | Ping-Pong Fucius |
| 106 | Bath Time | 206 | Every Shot A Hit |
| 107 | Art For Mum's Sake | 207 | Mummy's Darling |
| 108 | A Sunny Morning | 208 | Above The Clouds |
| 109 | One Little Piggy | 209 | Burning With Ambition |
| 110 | Barbecue Time | 210 | The Enlightenment |
| 111 | Laundry Day | 211 | Neighbour Over Board |
| 112 | Fitness Frenzy | 212 | Action! |
| 113 | Do It Yourself | 213 | Eat And Be Eaten |
| 114 | Night Of The Hunter | 214 | Don't Panic |

The PC game groups 1-14 as "Season 1/2/3" (6+4+4); the mobile store split is
"Season 1" = 101-114 and "Season 2" = 201-214. A YouTube "Season 2 all levels
100%" is therefore ambiguous: TheMusician05's is the PC game's episodes 7-10
(the PC episode-selection book and HUD are visible in its storyboard frames).

The trick SETS match episode for episode — every PC walkthrough step has its
mobile item (the shoe brush, the gong drumstick, the double pool-board spring,
the fishing net + tongs + valve of 210, the bent nail on the child's rod of
211). What differs is the machinery around them.

## The rating rules

| | PC | mobile |
|---|---|---|
| Season 1 100 % | "pull off every trick; some scenes require chaining tricks in succession" (guide) | `GameInfo.CalculateScore` (cs:392-405): FinalTrickScore + CompletedTricksCount × min(CompoundTrickScore, AngryCountTicks), capped 100; a tick is an angry landing while the meter is still above zero (Rottweiler.cs:598-611; 4.23/s decay, 23.6 s window) |
| Season 2 100 % | "completely fill up the gauge on the left" + every trick (guide) | int(completed × 90 / total) + 10 iff AngryCountTicks == 1 (cs:413-416): the meter must overflow EXACTLY once; 0.37/s decay, no pause (Rottweiler.cs:793-796) |
| Lives | 3 attempts (PC NFH2) | 1 (both mobile games; 4PDA thread, 2017) |

The Season 1 rule is the same idea on both sides. The Season 2 rule is not: on
PC the gauge only has to fill; on mobile a second overflow (AngryCountTicks 2)
loses the +10 — Level206's DeckChair (45) and LaunchPad triple (30+20+15) are
each big enough that any lap paying both overflows twice.

## Mechanics the mobile added or changed

- **RemoveFromRoutineAfterFirstUse** (RoutineActionUse.cs:424-427): Level108's
  ToothBrush is used once and dropped from the routine. On PC the neighbour
  brushes again every lap — the guide puts the shoe brush in "after he has
  gone to the balcony". On mobile the same trick pays through the coffee's
  RushToToilet: his ToiletAction's item is the ToothBrush, so the soil coffee
  sends him back to the sink (Level108 both plans, 100 / 94).
- **Alerters instead of the dog whistle.** PC Night of the Hunter: "wait for
  the neighbour to get vinyl, use dog whistle, use rusty nail with record
  player, use gunpowder with tobacco tin" — the whistle is an inventory item
  used from the kitchen and pulls him out of the living room. Mobile
  Level114 has no whistle: the Dog is an `Alerter` in Zone06 that only fires
  with Woody in its zone (Alerter.cs:81-84), Zone06's other exits are dead
  ends (Zone07, Zone08), and the Gramaphone/Pipe accept Woody only while
  primed (Item.cs:1520-1535) — i.e. only during his Zone02 stretch, where
  there is no hiding place. 7 of 9 on mobile; PC 9 of 9.
- **Colliders.** Level211's FishingRod sits inside the door's collider
  (x −5.27..−4.42 within −5.86..−4.06); the tap opens the door instead. The
  PC guide tricks the rod ("use bent nail with child's fishing rod"). The
  App Store review of the mobile Season 2 ("a bug prevents you from getting
  maximum score in the final mission", 2021) is the same class of defect on
  the final level's wheel ("only works if you touch its top").
- **Dexterity mini-games** (`DexterityUnlocker`, `unlock` legs) gate several
  Season 2 sources (the duck cage, the crayfish nest, the ToolBelt); PC has
  none.
- **Two extra catchers**: Olga (a bystander on PC) and the Mother are real
  catchers on several mobile levels (GameInfo.Update checks
  CanRottweilerSeeWoody / CanMotherSeeWoody); the mobile Mother's sleep
  windows drive the Level206/207/210 plans.
- **Linked and extra coins**: LinkedItemTrick pairs (JadeNecklace+Vase,
  PoolBoard+PoolAwning, SandCastle+BeachTowel, IndianPlatform+SeeSaw,
  DogBasket+DivingBoard), ExtraCoinLinkedTrick, ExtraCoin206/210,
  CompoundExtraCoin — all mobile-side data that decides WHEN anger lands,
  and therefore whether the one overflow happens.
- **Toilet rushes** (RushToToilet + the pawn's ToiletAction) exist on both,
  but on mobile they are the substitute for repeated routine uses (108).

## Level by level

Trick counts: PC = steps in the guide that pay (the guide text is known to
skip a step here and there — its own comments say so — so treat a
count as approximate); mobile = `TotalTricksCount` and the scoring items in
the data. "Same set" means every PC step has a mobile item and vice versa.

### Season 1

| lvl | PC steps that pay | mobile total / scoring items | note |
|---|---|---|---|
| 101 | glue→telescope, egg→microwave, TV antenna, balloon→sofa | 4: Binoculars 30, Sofa 25, TV 20, Microwave 16 | same set |
| 102 | tissue→loo, egg, laxative→drinks, antenna, hacksaw→sofa | 6: Sofa 25, Beer 18, TV 15, Microwave 10, Toilet 10 | same set |
| 103 | loo, soap→floor, dynamite→candle box, egg, marker→portrait, mousetrap→letter box | 6: Cake 25, Candle 25, LetterBox 20, Portrait 10, Toilet 10, Ground 10, Microwave 10 | mobile adds the magnesium cake |
| 104 | marker, glue→aftershave, hair restorer→deodorant, cream swap, soap, loo, egg | 7: SinkAftershave 20, AfterShave 20, Deodrant 15, SinkDeodrant 15, WhippedCream 15, Toilet/Microwave/Ground/Portrait 8 | same set |
| 105 | bowling ball swap, piano sheet, egg, soap, prank call, portrait, cheese→plant | 8: Football 15, PlantStink 13, Piano 13, Phone 10, Toilet/Ground/Portrait/Microwave 7 | same set |
| 106 | egg, milk↔bath water, portrait, soap, shoe polish→towel, hair restorer→tub, glue→album, bath pearls→sweets, loo | 9: Towel 12, BathTub 12, Pudding/Candy/PhotoAlbum 8, Ground/Toilet/Portrait/Microwave 7 | same set |
| 107 | pigeon leash, stain remover→painting, magnesium→camera, footstool, banana, pins→stool, wrench→generator | 7: FootStool 15, Generator 15, Camera 12, DieselChair 10, Dove 10, Ground 8 | same set |
| 108 | shoe brush (after his balcony visit), pins→chair, umbrella, honey→lotion, weedkiller→can, soil→coffee, banana | 6: SunLotion 20, Plant 20, ToothBrush 15, Coffee 15, Shezlong 10, Ground 8 | **routine differs**: PC brushes every lap; mobile once + the coffee rush |
| 109 | cactus→alarm clock, hot sauce→dentures, corn chips, nitro→milk, key→cage, pins→bed, banana | 7: PigMilk 20, Pig 20, Chili 15, Teeth 15, AlarmClock 13, Bed 8, Ground 7 | same set |
| 110 | extinguisher, growth liquid→spray, alcohol→beer, vinegar→wine, pins→chair, banana | 6: BBQ 20, Beer 20, Spray 15, Extinguisher 15, Wine 15, Chair 10, Ground 10 | same set |
| 111 | knife→vacuum, shovel→plant, wine→washer, cable→socket, pliers→drier, soil→carpet, marbles, soap flakes→fish food, iron, bird food→airer | 8: Carpet 15, Vacuum 15, Airer 13, ElectricTrap 11, Drier/FishTank/Washer/Iron 10, Marbles 7 | same set |
| 112 | spring→trampoline, knots book→yoga book, steroids→fish food, tongs→bike, skate, marbles, rope→expander, cable, saw→barbell, skipping rope | 10: Skates 14, Weights/FishTank/Trampoline/Bicycle/Expander 8, Yoga/Rope/Marbles/ElectricTrap/YogaBook 7 | same set |
| 113 | main valve, tongs→ladder, book swap, cable, valves, fuse, marbles, grinder | 8: ValveHot/Radiator/Ladder 15, Sink/ValveMain 12, Drill/Chair/Book/Fuse/Grinder 10, ElectricTrap 8, Marbles 7 | same set |
| 114 | polish, cartridges+cork→gun, cable, **whistle**, nail→record player, gunpowder→tobacco, marbles, balloon→horn, glue→hat, rat→medal box | 9: Gramaphone/Pipe/Shotgun 10, MedalBox/Polish/Hat/GoldCup/Horn 8, Marbles/ElectricTrap 7 | **no whistle on mobile** → Gramaphone and Pipe unreachable |

### Season 2

| lvl | PC steps that pay | mobile total / anger amounts | note |
|---|---|---|---|
| 201 | the tutorial's tricks + spaghetti→hat | 4: DeckRail 50, CaptainHat 50, Buffet 40, WaterPuddle 40 | same set |
| 202 | crab→cool box (mat), rake+seaweed, eel→pond, fin→submarine, sawfish→rail | 5: Submarine 50, Pond 30, BeerMat 30, Swimming 20, BridgeRail 20 | same set; mobile mat is toggles-prime (two visits) |
| 203 | tights→generator, oil→lever, chili→toilet paper, cannon ball→melons, spanner→bike | 5: Watermelon/Rocket/Generator/Toilet/Microphone/Bicycle 30 | same set |
| 204 | bear→kid, brick, grease→rickshaw, stand→drumstick, popper→hotdog, scissors→necklace, grease→vase | 6: Drumstick 30, Vase 25, Kart 25, Karate/Necklace/HotDog 20 | same set; mobile 100 needs the kart armed last |
| 205 | egg→table, bangers+glasses→statue→sculpture, tube→eels, nails→skis, rope→rockets | 5: Chef 40, Rockets/Skis 30, Tennis 25, Sculpture 20 | same set; mobile: the sculpture's window precedes its arming chain |
| 206 | blanket↔towel, rabbit→pad, band→harpoon, denture→dynamite bag (+ the tutorial's weights) | 6: DeckChair 45, Weights/LaunchPad 30, Harpoon/Dynamite 20 (+15 extra) | same set; mobile: two big coins → two overflows, +10 lost |
| 207 | spring→board (twice), whisky→barman, bucket→tap→elephant, crab→conch, crab→castle, urchin→towel, pedal→awning | 7: SandCastle 40, Awning 30, Board/Towel/Shell/Elephant 20 (+10 extra) | same set incl. the double spring; mobile 100 with the second spring last |
| 208 | balloon→charmer, spade→seesaw, mouse→stones, unleash dog, board→shoe machine, mouse→elephant, sponge→line, snake→bowl, cable→safeguard | 7: SeeSaw 30, Elephant 30, Snake 27, ArmsBowl/SafetyLine/Magician/Platform/Rake 20, ShoeMachine/ElectricTap 15 | same set |
| 209 | penknife→flowers, matches→drain, bellows→coals, fuel→trough, nappies→coals, coal→shoes, dung→ice cream, penknife→cow, fuel→channel | 7: all 20 | same set |
| 210 | net→tool belt, tongs→valve, urchin→stall, bat→elephant, bra→melons→pylon, urchin→deck chair, octopus→stall, suntan→board, bone→dog | 8: Shop 37, Elephant 30, Board/Basket/Valve/... 20, Pylon/DeckChair 10 | same set (the pool coins were missing from our plan until now) |
| 211 | rasp→lifeboat, cylinder→jacket, extinguisher→diving gear, tablets→sweets, cylinder↔toy, rasp→toilet sign, coin→phone, **nail→fishing rod** | 8: OlgaChild 25, DivingGear/ToiletSign/Jacket/Rod/Phone/Boat 20, Sweets 15 | **rod under the door collider on mobile** |
| 212 | crowbar→plate, crowbar→mine, explosive→cigars, paint→bench, resin→bull, corn→parrot, coin→slot, rubies→throne, dagger→disc, dagger→whip | 9: Bull 30, Throne hands/Cigars/Whip/Bench/... 20 | same set |
| 213 | jar→termites, tequila+chili→nachos, chicken+teeth→plant, cement→bath salts, flower→trough, termites→basket, hand→lever, wasps→pinata | 9: all 20, controls 15 | same set |
| 214 | carpet→hatch, glass→strap, fish→flowers, ammo→flare gun, fish→bucket, cloth→pane, key, pill→toddy, code→wheel | 6: Wheel 80, Door/Bucket/Glass/Shower/Bird/Pistol/Bouquet/Hatch 40 | same set; mobile wheel collider is touchy (review) |

## What this means for "100 % on every level"

- On PC every episode is documented at 100 % (both guides, both video series).
- On mobile the trick sets are the same, but three levels lose a trick to the
  remake's own machinery — 114 (no whistle), 211 (the rod's collider) — or
  to its rating rule — 206 (two overflows). 108 looked like a fourth and was
  not: the coffee rush is the mobile's replacement for the repeated brushing.
- The Season 2 "+10 for exactly one overflow" turns arming ORDER into the
  whole game: the meter must climb on one of his laps, so the trick he
  visits earliest is armed last (204, 207, 209, 212-214 at 100). Where his
  visits are spread or an item needs two of his visits (202's toggles-prime
  mat, 205's sculpture chain, 208's early platform pair, 210's eight coins
  over four laps) the runner reaches 90.
- Nothing on the web shows the mobile games at 100 % across the board: the
  "all levels 100%" videos are the PC game, the mobile walkthrough sites and
  videos cover the free chapters, and the only mobile-specific report is the
  App Store review that the final Season 2 level cannot be maxed.

The full per-plan table and the bench evidence live in
`tools/livediff/README.md`, "The rating: what EXCELLENT takes, level by level".
