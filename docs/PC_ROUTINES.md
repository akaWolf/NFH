# The PC neighbour's routines, read from game.exe

Each Season 1 level is a compiled class in the PC game's `game.exe`; its `run` method is a
linear script of engine calls — the bubble icon (`Icon`), the walk (`GoTo object`), the
action (`Action object.action`), a branch on the object's tricked variant (`If variant`), and
the object swap after a trick (`Switch a -> b`) — with a wait after each. The lists below are
those calls in code order, read with radare2 (`tools/pcref/exe/`): the object names are the
level's objects.xml names, the actions its <action> names. Register tracking loses an
argument now and then (an `Action` without its object, a `GoTo` without a name): the
preceding line names the object. Extracted 2026-09-15 with tools/pcref/exe_scripts.py.

Mind the layout: the compiler puts the tricked-variant branches out of line, so the code order
is not always the lap order (the fitness level's expander, home trainer, mixer, rope, barbell,
trampoline appear in that order in code where the lap goes trampoline, bike, mixer, expander,
weights, rope) — docs/PC_LAPS.md's orders, read off the video, stay the reference for the lap;
this file gives the actions, their repeats and the branches: the laundry's washer runs two
wash cycles (give, wash, get_clothes twice) and the drier two dry cycles where the mobile lists
three of each; the bath's shower sequence (take_towel, dry) and the pudding's foam branch; the
piano's kick of the football and the bowling ball's throw through the window.

Where the rest lives: game.exe holds the level classes, the level state and the scoring;
Loader.dll parses the XML (`%s\level.xml`); GFXEngine.dll is the engine with the HUD
(`rageometer`, `bonuscount`, `trickcount`, `head_01`-`head_04` are its `ingame` dialog's
elements). The engine's messages (game.exe): CreateRoomMsg, AddObjectMsg, AddActionMsg,
AddHotSpotMsg, AddContentMsg, AddNoiseTriggerMsg, AddObjectTriggerMsg, CreateCombinationMsg,
AddIngredientMsg, SetStdActionMsg, GoToPosMsg, UseObjectMsg, LookAtObjectMsg, SetAnimMsg,
SetSpeedMsg, PauseActorMsg, StopJobMsg, GameOverAnimMsg, StartLevelMsg.

**The anger and the bonus, read from the code (2026-09-16).** The trick parser (0x444390)
reads `name`, `quota1`-`quota4` and `angrytime` (a missing quota is 0, a missing angrytime
-1) and AddTrick (0x444220) builds the 0x24-byte record: +4 the name, +8/+0xc/+0x10/+0x14
quota1-4, +0x18 the index of the quota that pays next, +0x1c angrytime, +0x20 0. The level
parser (0x44f1d0, the attribute at 0x44f29a) puts the level's `angrytime` at +0xc of a
0x14-byte level record. The level state object (its constructor fcn.0043b9b0) carries: +0x54
the tick count, +0x58 the elapsed time and +0x5c the limit, +0x60 the score, +0x64 the bonus
count, +0x6c the face-icon timer, +0x70 the rage current, +0x74 the rage maximum, +0x78 the
hold, +0x7c the bonus flag, +0x84 the level's angrytime (120 from the constructor, overwritten
from the level record's +0xc at 0x440a13), +0x88 running.

The game tick fcn.0043ab40 calls fcn.00438a80 once per tick while the level runs (0x43b2fc):
the icon timer counts down and resets the face (SetIcon fcn.00437f70, 0) when it reaches 0;
then `if (current || hold) { if (hold) hold--; else { current--; if (current == 0) flag = 0; }
send the rage event }`; then the clock: elapsed++ (clamped to the limit), a time event every
12 ticks. The rage event (a 0x14-byte object, vtable 0x4e0a04, built by fcn.004381c0: +4
maximum, +8 current, +0xc `hold > 0`, +0xd the flag) is dispatched through the 111-slot
listener table of GFXEngine.dll (0x100a3740, default 0x1000ec10 = not handled): slot 46
(0xb8, game.exe 0x435e90 → GFXEngine 0x10011460) draws it — the mercury is `current × 100 /
maximum` clipped at 100 (fcn.1000ffc0 → fcn.10014a80 looks up `rageometer`, fcn.1000bd70 sets
it), the face (fcn.1000ffb0 → `head_0N`) is 0 idle, 1 while current > 0, 2 during the hold,
3 during the hold of a bonus trick. The `gui::InGameGUI` object itself is 0x6c bytes with the
vtable 0x100a3908 (+0x28 the engine, +0x34 the dialog, +0x44 the dialog the elements are
looked up in); its listener sub-object is what game.exe holds.

A trick fires in fcn.0047bd00: return if the trick already fired (+0x1c of the trick); look
the record up by name (fcn.00443920); points = the record's quota at its index, and
fcn.004439d0 advances the index; no points, no scoring. Otherwise, in this order: bonus =
(rage current > 0) (fcn.004357e0 returns +0x70 — the manual's "before the anger indicator is
back to zero" is exactly that); fcn.00438070: score += points + (bonus ? 3 : 0), clamped to
0..100, the bonus count += 1 on a bonus, a score event for the HUD; fcn.00438b90(amount,
bonus) with amount = the record's angrytime, or the level's (+0x84) when it is -1: maximum
= the level's angrytime, current = max(current, amount), hold = 60, flag = bonus; the face
icon (fcn.00438550): 4 for a bonus, else 3 for more than 10 points, else 2; the jingle
(`music/jingle_joke.mp3`); then the trick's animation. So after a trick the anger indicator
stays above zero for 60 + amount ticks, the mercury sits at full for 60 + (amount − level
angrytime) of them and drains over the level's angrytime ticks; the next trick's bonus is
decided by that indicator alone — the scores and the neighbour's whereabouts play no part.

The tick is 12 Hz — not the 20 an earlier reading of the mercury suggested. Three things
say so. leveldata.xml gives the bath `time="4320"` and its HUD clock starts at 6:00 (Badinfos'
video), so a time unit is 1/12 s; the GUI's clock handler (GFXEngine 0x10011310 → fcn.10014ba0)
shows `(limit − elapsed) × 10 / 12` tenths of a second, and the clock keeps real time through a
level's every tantrum (E06 6:00 → 1:02 over 297 s, E14 10:00 → 2:51 over 427 s) — that
counter is the same `elapsed++` of fcn.00438a80 that decrements the rage. And the mercury
itself, read as the first non-blue row of the tube (tools/pcref/thermo_rows.py; the old
red-only reader missed the column's white-hot top and so held its "full" while the true fill
fell to ~83 %): after a trick with no own value the column stays at the rim 5.4-5.8 s — the
60-tick hold, 5.0 s, plus the top 3 % — and then falls at 0.7 × angrytime ticks per visible
tube (E03 180: 10.6 s, E04 204: 11.7 s), the tube showing the top ~70 % of the bar, the rest
sitting in the bulb. The engine's own frame pacing was not found in game.exe (the
GetTickCount-driven scheduler at 0x423b60 is the AVI recorder's, `CAVIFile::addFrame`); the
scripts pump frames from inside their waits (fcn.0044b540 → fcn.0044ade0 → fcn.00449f80 →
fcn.0043ab40), one level tick per pump. The data, then (`tools/pcref/canon.py` reads the
UTF-16 XML — grep does not), in 1/12 s ticks: peep 280, sofa 240, mail 180, pie 204
(mum_smeared 264, toiletstuffed 228), piano 204 (groundsoap 276, phone 276, bowlingball 288),
bath 156 (foambottle 240, dirtytowel 216), art 180 (potterswheel_fast 204, picture_smeared
204), suntan 180 (the six banana skins 300), pig 192 (the four banana skins 252,
babybottle_nitro 240), barbecue 180 (the four banana skins 252), laundry 240 (marbles 300,
vacuum_hole 300, tumbledrier_smashed 270), fitness 240 (electrotrap 264, marbles 288,
hometrainer_tonged 288, barbell_sawed 264, skate 300), DIY 228 (marbles 264), hunter 240
(electrotrap 272, marbles 360). The indicator's window after one trick is therefore 5 s plus
the amount over 12: 18 s (bath, no own value) to 35 s (the hunter's marbles) — 20 s on the
180 levels, 25 s on the 240 ones, against the mobile's 23.6 s for every trick. The profile
carries this rule since 2026-09-16 (pcprofile.s1_rage_fire / s1_rage_tick / s1_rage_percent,
run by Pawn.tick and World.play_angry; the values as PCAngryTime in ticks in levels/pc).

Season 2 (GameLogic.dll, base 0x10000000) has the same constant pattern (`tools/pcref/exe/
nfh2_gamelogic_globals.json`, 4373 names) but its scripts call a different engine: the
cabin-boat level (cn_b1, Level202) at 0x100216xx reads `SetIcon(actor, icon)` = fcn.100422a5
(`bridge`, `neighbor`), `DoAction(actor, anim)` = fcn.10002cd5 followed by the wait
fcn.1000ae19 (`lookaround`, `crash`, `electrify`, `leave`), a variant test on a pair of
objects = fcn.1000fb6e (`pond_bridge_damaged`, `pond_bridge`), a tricked test on one =
fcn.1000ec67 (`pond_pond_eel`); the walks pass the object in a register the listing does not
show. The ship1 code at 0x100269xx is the tutorial (`wait1`, `hurry`, `combo2`/`combo4`,
room moves of `woody` and `neighbor` = fcn.1000fc33). Its trick parser (fcn.10052a89)
reads `name`, `coins` and `rage` into a 0x1c-byte record (+8 coins, +0xc rage, +0x10 a
flag), and the trick accounting in fcn.1000140b works on a copy of the level state: coins +=
the record's coins, rage += the record's rage, and a byte of the copy is set when the rage
total reaches 100000 (0x10001500) — the gauge's length: the HUD's `rageometer` progressbar
(nfh2 dialogs/*/menuleft_bar.xml) runs 0..100000. The copy — eleven dwords: coins, the total,
mincoins, the lives at +0x14, the rage at +0x1c — is written back and broadcast by fcn.10042358
(the level state's status struct at +0x80, then a status event, vtable 0x100b1038, whose slot
7 dispatches to the GUI listener's slot 50 = GUIEngine 0x100046ef → fcn.1000292c: the coins
text, the `needmorecoins` mark when coins ≥ mincoins, the `rageometer` set to the raw rage,
the `heart` and `rage` animations on the event's flag byte); the other three writers of that
struct are the caught handler (fcn.10042471: lives − 1, then game over or a `woody` respawn)
and the level start/end (fcn.10044234). None of them subtracts from the rage, so the 0.37 %/s
decay the bar shows on the video (docs/PC_FIDELITY.md §7) lives outside those writers — not
located. The Season 2 game.exe (`tools/pcref/exe`'s dumps cover it now) is an application
shell whose string table holds `rage`/`quota` once each. Naming the walk and finishing the
Season 2 scripts are the remaining steps of this reading; the `time` attribute of
objects.xml's actions is not a clock unit (the laundry's wash 59 with a 5-frame `wait` loop
lasts ~24 s on the video, its iron 71 with an 18-frame loop ~14 s; the doors' 9-25 about a
second) and is not needed by the port, which runs the mobile routines.

## level_peep (Level101)

- `0x4708da` Icon sofa
- `0x470962` If lir/sofa_fartbag of lir/sofa
- `0x470a06` Action lir/sofa_fartbag.surprise
- `0x470abc` Switch lir/sofa <- lir/sofa_fartbag
- `0x470bed` Icon binoculars
- `0x470c0a` OBJ3 kit/binoculars
- `0x470c32` OBJ3 kit/binoculars_glue
- `0x470d2b` OBJ3 kit/binoculars_glue
- `0x470dcf` Action kit/binoculars_glue.peep_glue
- `0x470e15` OBJ2 kit/binoculars_glue
- `0x470e4c` OBJ1 kit/binoculars_glue
- `0x470ef3` OBJ3 kit/binoculars
- `0x470f8f` Icon sofa
- `0x47102b` If lir/twistedantenna of lir/tv
- `0x471098` Icon shout
- `0x4714fe` Action ?.start

## level_sofa (Level102)

- `0x46f6d8` Icon beer
- `0x46f709` GoTo kit/beer
- `0x46f7de` Action ?.take
- `0x46f873` Icon sofa
- `0x46f90d` If lir/twistedantenna of lir/tv
- `0x46f96a` Icon sofa
- `0x46f9d6` If lir/sofa_broken of lir/sofa
- `0x46fc7b` Action ?.?
- `0x46fd48` Action neighbor.spit
- `0x46fe2a` Icon shout
- `0x470025` Icon toilet
- `0x47016b` Action ?.?
- `0x4701fa` Action ?.?
- `0x470309` Action ?.?
- `0x4704e7` If toi/toiletstuffed of toi/toilet

## level_mail (Level103)

- `0x45e80e` GoTo kit/candlebox
- `0x45e8e0` Action ?.take
- `0x45e937` Switch kit/candlebox <- kit/candlebox_boom
- `0x45ea12` Icon cake
- `0x45ea43` GoTo kit/cake
- `0x45eabe` Action kit/cake.put_candle_dead
- `0x45eb1b` Action kit/cake.light_candle_dead
- `0x45eb74` Action kit/cake.celebrate
- `0x45ebcd` Action kit/cake.take_candle_dead
- `0x45ec66` Action kit/cake.put_tnt
- `0x45ecbf` Action kit/cake.light_tnt
- `0x45ed18` Action kit/cake.celebrate_boom
- `0x45ed63` OBJ2 kit/candlebox_boom
- `0x45edc9` Action kit/cake.put_candle
- `0x45ee26` Action kit/cake.light_candle
- `0x45ee82` Action kit/cake.celebrate
- `0x45eed8` Action kit/cake.take_candle
- `0x45ef6a` Icon mail
- `0x45ef9b` GoTo anc/mailbox
- `0x45f011` If anc/mailbox_trap of anc/mailbox
- `0x45f0d9` Action anc/mailbox_trap.search_mailbox
- `0x45f17f` Switch anc/mailbox <- anc/mailbox_trap
- `0x45f2a0` Action anc/mailbox.search_mailbox
- `0x45f2fe` Action anc/mailbox.read_mail
- `0x45f359` Action anc/mailbox.return_mail
- `0x45f3d8` Icon first_aid
- `0x45f410` GoTo toi/firstaid
- `0x45f487` Action toi/firstaid.take3
- `0x45f4e9` Action toi/firstaid.put_plaster

## level_pie (Level104)

- `0x4619de` GoTo kit/applepie
- `0x461a5c` Action kit/applepie.take
- `0x461ade` Icon microwave
- `0x461bc5` If kit/microwavedirty of kit/microwave
- `0x461c2f` OBJ2 kit/microwavedirty
- `0x461d4d` Action kit/microwave.put_apple_pie
- `0x461da8` Action kit/microwave.cook
- `0x461e03` Action kit/microwave.take_apple_pie
- `0x461e79` Icon whippedcream
- `0x461f97` Action ?.put_cream
- `0x462062` Action neighbor.eat_foam
- `0x4620af` OBJ2 kit/foamcream
- `0x4620f2` Switch kit/whippedcream <- kit/foamcream
- `0x462180` Action neighbor.eat
- `0x462213` Icon basin
- `0x462244` GoTo toi/aftershave
- `0x4622f9` OBJ1 toi/aftershave_glue
- `0x46244a` OBJ1 toi/grease_exchanged
- `0x462569` Icon basin
- `0x46259a` GoTo toi/basin
- `0x462649` Action toi/basin.shave_glue
- `0x462691` OBJ2 toi/aftershave_glue
- `0x4626ed` Action toi/basin.shave
- `0x462790` Action toi/basin.grow_hair
- `0x4627db` OBJ2 toi/grease_exchanged
- `0x46283d` Action toi/basin.grease_hair
- `0x4628bc` Icon basin
- `0x4628ed` GoTo toi/aftershave
- `0x46295b` Action toi/aftershave.give
- `0x462a3f` Action toi/grease.give

## level_piano (Level105)

- `0x46d723` Icon piano
- `0x46d7aa` If lir/scoresmeared of lir/score
- `0x46d85d` Action lir/scoresmeared.play_piano_offkey
- `0x46d94d` OBJ2 lir/scoresmeared
- `0x46db12` Action lir/score.play_piano_noangry
- `0x46dc22` Action lir/score.play_piano_normally
- `0x46dd4d` Action kit/football.inv
- `0x46ddab` Action kit/football.fly_into_kitchen
- `0x46df77` Action lir/score.look_angry
- `0x46dfdb` Icon football
- `0x46e046` GoTo 
- `0x46e0a0` If kit/bowlingball of kit/football
- `0x46e156` Action kit/bowlingball.kick
- `0x46e1a5` OBJ2 kit/bowlingball
- `0x46e270` Action kit/football.kick
- `0x46e2b1` OBJ1 kit/football
- `0x46e36f` Icon football
- `0x46e3a0` GoTo kit/bowlingball
- `0x46e417` Action neighbor.take_low
- `0x46e458` OBJ1 kit/bowlingball
- `0x46e620` Action kit/window.throw_bowling
- `0x46e6a5` Icon football
- `0x46e6d6` GoTo kit/window
- `0x46e763` Icon flower
- `0x46e7ce` GoTo 
- `0x46e825` If anc/stinkflower of anc/flower
- `0x46e8d5` Action anc/stinkflower.sniff
- `0x46e923` OBJ2 anc/stinkflower
- `0x46e968` Switch anc/flower <- anc/stinkflower
- `0x46ea7b` Icon toilet
- `0x46eaaf` GoTo toi/toilet
- `0x46eb37` Action neighbor.puke
- `0x46ec14` If toi/toiletstuffed of toi/toilet
- `0x46ecc9` Icon phone
- `0x46ed0b` GoTo fast, anc/phoneringing
- `0x46edfc` Action anc/phoneringing.phone
- `0x46ee41` Switch anc/phone <- anc/phoneringing
- `0x46eecf` OBJ2 anc/phone

## level_bath (Level106)

- `0x46bb1f` Action lir/stickybook.read_stickybook
- `0x46bb65` OBJ2 lir/stickybook
- `0x46bc1f` Action lir/book.read_book
- `0x46bdee` If lir/bathcandy of lir/candy
- `0x46be5e` Action lir/bathcandy.eat_bathcandy
- `0x46bea4` OBJ2 lir/bathcandy
- `0x46bf37` Switch lir/candy <- lir/bathcandy
- `0x46c01f` Action lir/candy.eat_candy
- `0x46c133` If kit/foambottle of kit/milkbottle
- `0x46c1a1` Action kit/foambottle.make_foampudding
- `0x46c260` OBJ2 kit/foambottle
- `0x46c2b6` Action kit/foampudding.repair
- `0x46c2ee` OBJ1 kit/foampudding
- `0x46c372` Switch kit/milkbottle <- kit/foambottle
- `0x46c405` Action kit/milkbottle.make_pudding
- `0x46c5b3` Icon photo_album
- `0x46c5e4` GoTo lir/book
- `0x46c63f` Icon candy
- `0x46c670` GoTo lir/candy
- `0x46c6d9` Icon milk_bottle
- `0x46c70a` GoTo kit/milkbottle
- `0x46c766` Icon bath
- `0x46c7de` GoTo toi/tub_empty
- `0x46c846` Action toi/tub_empty.give
- `0x46c88f` Switch toi/tub <- toi/tub_empty
- `0x46c997` If toi/tub_hair of toi/tub
- `0x46ca91` Icon towel
- `0x46caee` If toi/dirtytowel of toi/towel
- `0x46cb6a` Action toi/shower.take_towel
- `0x46cc3d` Action toi/shower.dry
- `0x46cd01` Action toi/shower.take_towel
- `0x46cd40` Switch toi/towel <- toi/dirtytowel
- `0x46cdd0` Action toi/shower.take_towel
- `0x46cea4` Action toi/shower.dry
- `0x46cefc` Action toi/shower.take_towel
- `0x46cfeb` Switch toi/tub
- `0x46d0e6` Icon toilet
- `0x46d11a` GoTo toi/toilet
- `0x46d193` Action neighbor.puke
- `0x46d264` If toi/toiletstuffed of toi/toilet
- `0x47d49c` OBJ3 toi/groundsoap
- `0x47d4e4` OBJ3 stuffed_toilet, toi/toiletstuffed
- `0x47d659` Action neighbor.doubletake1
- `0x47d6c8` OBJ2 anc/mum_smeared
- `0x47d8b9` Action neighbor.doubletake1
- `0x47d928` OBJ2 kit/microwavedirty
- `0x47db4e` Action neighbor.doubletake1
- `0x47dbbd` OBJ2 toi/toiletstuffed
- `0x47dcf7` OBJ2 lir/twistedantenna
- `0x47e259` OBJ3 toi/toiletstuffed
- `0x47e2a8` OBJ3 toi/groundsoap
- `0x47e3e7` OBJ3 toi/groundsoap
- `0x47e436` OBJ3 toi/toiletstuffed

## level_art (Level107)

- `0x45771d` Icon camera
- `0x45774e` GoTo bed/posingspot
- `0x4577c4` If bed/camera_flashy of bed/camera
- `0x457843` Action bed/camera_flashy.flash
- `0x457888` Switch bed/camera <- bed/camera_flashy
- `0x45798e` OBJ2 bed/camera_flashy
- `0x4579df` Action bed/camera.flash
- `0x457a70` Icon magnesium
- `0x457aa1` GoTo bed/magnesiumbottle
- `0x457b1e` Icon camera
- `0x457b4f` GoTo bed/camera
- `0x457bce` Icon potterswheel
- `0x457bff` GoTo kit/stool
- `0x457cb0` If kit/stool_pins of kit/stool
- `0x457d7c` Action ?.cry
- `0x457e25` OBJ2 kit/stool_pins
- `0x457f9a` If kit/potterswheel_fast of kit/potterswheel
- `0x45801d` Action kit/potterswheel_fast.potter_fast
- `0x458100` OBJ2 kit/potterswheel_fast
- `0x4581f1` Action kit/potterswheel.potter
- `0x45826f` Icon statue
- `0x4582a0` GoTo lir/statue
- `0x4582e0` If lir/statue_broken of lir/statue
- `0x45835f` Icon statue
- `0x458390` GoTo lir/footstool
- `0x458406` If lir/footstool_unlocked of lir/footstool
- `0x458482` Action lir/footstool_unlocked.sculpt
- `0x4584c1` Switch lir/statue_broken <- lir/statue
- `0x458543` OBJ2 lir/footstool_unlocked
- `0x458591` Action lir/footstool.sculpt
- `0x45860d` Icon painting
- `0x45878f` OBJ2 bal/dove_free
- `0x45880d` Icon painting
- `0x45883e` GoTo bal/picture_empty
- `0x45889f` OBJ3 bal/picture_smeared
- `0x458931` OBJ2 bal/picture_smeared
- `0x45898f` Action bal/picture_smeared.clean
- `0x4589d4` Switch bal/picture_empty <- bal/picture_smeared
- `0x458ac4` OBJ2 bal/picture_smeared
- `0x458b22` Action bal/picture_smeared.paint_nonsense
- `0x458b6e` OBJ3 bal/picture_smeared
- `0x458bbe` OBJ3 bal/picture
- `0x458bf9` Action bal/picture.clean
- `0x458c3e` OBJ3 bal/picture_empty
- `0x458c5f` Switch bal/picture <- bal/picture_empty
- `0x458d0d` Action bal/picture.?
- `0x458db2` Action ?.?
- `0x458e41` Icon noise

## level_suntan (Level108)

- `0x45c68b` OBJ3 bal/ewer
- `0x45c6af` OBJ3 bal/ewer_poisoned
- `0x45c9e7` Action neighbor.take_low
- `0x45cb5d` Icon toothbrush
- `0x45cbc8` GoTo 
- `0x45cc60` If toi/shoebrushset of toi/toothbrushset
- `0x45ccdf` Action neighbor.take3
- `0x45cdb8` Action neighbor.brush_black_teeth
- `0x45ce7b` Action neighbor.brush_teeth
- `0x45ced6` Action neighbor.take3
- `0x45cf18` Switch toi/toothbrushset <- toi/shoebrushset
- `0x45d026` Action neighbor.take3
- `0x45d103` Action neighbor.brush_teeth
- `0x45d15e` Action neighbor.take3
- `0x45d26b` Icon coffee
- `0x45d2d6` GoTo 
- `0x45d358` If kit/coffeebox_soil of kit/coffeebox
- `0x45d38e` Action kit/coffeebox_soil.make_coffee
- `0x45d3cc` Action kit/coffeebox.?
- `0x45d494` If kit/coffeebox_soil of kit/coffeebox
- `0x45d513` Action neighbor.drink_soil_coffee
- `0x45d5bd` Switch kit/coffeebox <- kit/coffeebox_soil
- `0x45d683` Action neighbor.drink_coffee
- `0x45d71d` Icon toothbrush
- `0x45d78f` GoTo 
- `0x45d7cb` Icon foldingchair
- `0x45d7fc` GoTo bal/ewer
- `0x45d85c` Icon foldingchair
- `0x45d88d` GoTo bal/foldingchair
- `0x45d8cd` If bal/foldingchair_pins of bal/foldingchair
- `0x45d974` Action bal/foldingchair_pins.sunbath
- `0x45da15` OBJ2 bal/foldingchair_pins
- `0x45db21` If bal/sunshade_closed of bal/sunshade
- `0x45db58` If bal/suncream_sweet of bal/suncream
- `0x45dbce` Action bal/foldingchair.sunbath_cream_sweet
- `0x45dc29` Action bal/foldingchair.beeattack
- `0x45dcd0` OBJ2 bal/suncream_sweet
- `0x45dd15` Switch bal/suncream <- bal/suncream_sweet
- `0x45ddab` Action bal/foldingchair.sunbath_cream
- `0x45de03` Action bal/foldingchair.sunbath
- `0x45de93` Icon ewer
- `0x45dec4` GoTo bal/ewer
- `0x45def0` Icon ewer
- `0x45dfb6` Action neighbor.take_low
- `0x45e0ce` Icon flower
- `0x45e0ff` GoTo anc/flower
- `0x45e1bf` Action neighbor.water_to_death
- `0x45e204` Switch anc/deadflower <- anc/flower
- `0x45e290` OBJ2 anc/deadflower
- `0x45e2f9` Action neighbor.water
- `0x45e385` Icon ewer
- `0x45e3b6` GoTo bal/ewer
- `0x45e415` Icon noise
- `0x45e7dd` Icon candle

## level_pig (Level109)

- `0x468cce` Icon pigkey, pig_key
- `0x468cff` GoTo bed/keyboard
- `0x468da0` Action bed/keyboard.give
- `0x468f3b` Icon teeth
- `0x468f73` GoTo bed/teeth_empty
- `0x468fde` Action bed/teeth_empty.give
- `0x469024` Switch bed/teeth <- bed/teeth_empty
- `0x4690e1` Icon bed
- `0x469112` GoTo bed/bed
- `0x469152` If bed/bed_pins of bed/bed
- `0x4691ff` Action bed/bed_pins.sleep
- `0x46924b` OBJ2 bed/bed_pins
- `0x469356` Icon sleep
- `0x46949d` Action bed/bed_sleep.sleep
- `0x469527` Icon alarm_clock
- `0x46958a` If bed/cactusclock of bed/alarmclock
- `0x469603` Action bed/cactusclock.ring
- `0x469661` Action bed/bed_sleep.hit_cactus
- `0x46980c` Switch bed/alarmclock <- bed/cactusclock
- `0x4698a2` Action bed/alarmclock.ring
- `0x469904` Action bed/bed_sleep.hit_alarm
- `0x469a60` Icon teeth
- `0x469ad9` GoTo 
- `0x469c12` Action ?.take
- `0x469c58` Switch bed/teeth_empty
- `0x469d8f` Action ?.take
- `0x469dd9` Switch bed/teeth_empty
- `0x469eb3` Icon pig_key
- `0x469ee4` GoTo bed/keyboard
- `0x469fc5` Action bed/keyboard.take
- `0x46a109` Action neighbor.surprise
- `0x46a1a2` Icon milk_bottle
- `0x46a218` GoTo 
- `0x46a2f7` Action ?.take
- `0x46a405` Icon pig
- `0x46a498` Icon pig
- `0x46a4c4` If anc/pigout of anc/pig
- `0x46a4fc` GoTo anc/pigout
- `0x46a52a` GoTo anc/pig
- `0x46a5cc` OBJ2 anc/pigout
- `0x46a62a` Action anc/pigout.catch_pig
- `0x46a66f` Switch anc/pig <- anc/pigout
- `0x46a85a` Action neighbor.shake_bottle
- `0x46a8b8` Action neighbor.bottle_explode
- `0x46a907` OBJ2 kit/babybottle_nitro
- `0x46a96e` Action neighbor.shake_bottle
- `0x46a9d0` Action anc/pig.feed
- `0x46aa52` Icon milk_bottle
- `0x46aa83` GoTo kit/babybottle
- `0x46aaf5` Action kit/babybottle.give
- `0x46ac0a` Icon cookies
- `0x46ac83` GoTo 
- `0x46ad6e` Action ?.open
- `0x46ae7d` Switch kit/cookiebox <- kit/cookiebox_hot
- `0x46af55` Icon parrot
- `0x46afe9` Icon parrot
- `0x46b218` Action ?.eat
- `0x46b276` Action ?.get_hot
- `0x46b37f` Action ?.give
- `0x46b3e1` Action ?.eat
- `0x46b4d9` Icon noise
- `0x46bab1` If lir/stickybook of lir/book

## level_barbecue (Level110)

- `0x45fa43` Icon meatbowl
- `0x45fa74` GoTo kit/meatbowl
- `0x45fb32` Icon bbq
- `0x45fb63` GoTo bal/barbecue
- `0x45fbe0` Icon beer
- `0x45fc11` GoTo bal/beer
- `0x45fc87` If bal/fuelbeer of bal/beer
- `0x45fcc5` Action bal/fuelbeer.take
- `0x45fd0e` Switch bal/beer <- bal/fuelbeer
- `0x45fd90` Action bal/beer.take
- `0x45fe0f` Icon bbq
- `0x45fe40` GoTo bal/barbecue
- `0x45fef7` Action bal/barbecue.pour_fuel
- `0x45ff39` Switch bal/barbecue_burn <- bal/barbecue
- `0x460113` Action bal/barbecue.pour_beer
- `0x46022c` Action ?.take
- `0x46043d` Action bal/barbecue_burn.extinguish_explo
- `0x46049c` Action bal/barbecue_burn.repair_extinguisher
- `0x4604fb` Action bal/barbecue_burn.extinguish
- `0x4605d1` OBJ2 bed/extinguisher_knotted
- `0x460628` Action bal/barbecue_burn.extinguish
- `0x46071f` Action neighbor.?
- `0x4607cb` Action bal/barbecue_burn.repair
- `0x46080b` Switch bal/barbecue <- bal/barbecue_burn
- `0x4609b1` Icon plant
- `0x4609e2` GoTo bal/plant
- `0x460a52` If bal/growspray of bal/spray
- `0x460ac8` Action bal/growspray.growspray
- `0x460b23` Action bal/plant.grow
- `0x460bcf` Switch bal/plant_dead <- bal/plant
- `0x460c72` Action bal/spray.spray
- `0x460cf1` Icon bbq
- `0x460d22` GoTo bal/barbecue
- `0x460dd2` Action bal/barbecue.take
- `0x460e30` Action bal/barbecue.give
- `0x460eab` Icon table
- `0x460edc` GoTo lir/table
- `0x460fa5` If lir/chair_pins of lir/chair
- `0x46107c` Action lir/table.cry
- `0x4610cb` OBJ2 lir/chair_pins
- `0x461129` Action lir/table.repair
- `0x46116e` Switch lir/chair <- lir/chair_pins
- `0x461263` Action lir/table.eat
- `0x4612de` Icon wine
- `0x46130f` GoTo lir/wine
- `0x461385` If lir/vinegar of lir/wine
- `0x461404` Action lir/vinegar.drink
- `0x461453` OBJ2 lir/vinegar
- `0x4614fd` Action lir/wine.drink
- `0x46157c` Icon noise
- `0x4619ad` Icon applepie

## level_laundry (Level111)

- `0x45489d` Action neighbor.doubletake1
- `0x454ed3` Icon detergent
- `0x454f04` GoTo kit/detergent
- `0x454f82` Icon washing_machine
- `0x454fb3` GoTo bas/washingmachine
- `0x4550d6` Action ?.give
- `0x455130` Action ?.wash
- `0x45518a` Action ?.get_clothes
- `0x4551d7` OBJ2 bas/washingmachine_wine
- `0x455280` Action ?.give
- `0x4552de` Action ?.wash
- `0x455338` Action ?.get_clothes
- `0x4553ca` Icon tumble_drier
- `0x4553fb` GoTo bas/tumbledrier
- `0x455516` Action ?.give
- `0x455570` Action ?.dry
- `0x4555bd` OBJ2 bas/tumbledrier_smashed
- `0x455666` Action ?.give
- `0x4556c4` Action ?.dry
- `0x455720` Action bas/tumbledrier.take
- `0x4557b3` Icon ironing
- `0x4557e4` GoTo bed/ironingboard
- `0x45584e` Action bed/ironingboard.give
- `0x455894` Switch bed/ironingboard_clothes <- bed/ironingboard
- `0x455951` Icon laundry_rack
- `0x455982` GoTo bal/noclothes
- `0x4559ec` Action bal/noclothes.putclothes
- `0x455a35` Switch bal/clothes <- bal/noclothes
- `0x455af2` Icon aquarium
- `0x455b23` GoTo wor/aquarium
- `0x455b99` If wor/fishfood_soap of wor/fishfood
- `0x455bfa` OBJ1 wor/fishfood_soap
- `0x455c97` Action wor/aquarium.feedsoap
- `0x455ce6` OBJ2 wor/fishfood_soap
- `0x455d44` Action wor/aquarium.repair
- `0x455d7d` OBJ1 wor/fishfood
- `0x455e1e` Action wor/aquarium.feed
- `0x455f17` Icon laundry_rack
- `0x455f48` GoTo bal/clothes
- `0x455fbe` If bal/clothes_food of bal/clothes
- `0x45602b` OBJ2 bal/clothes_food
- `0x4560cd` Action bal/clothes.take
- `0x45610c` Switch bal/noclothes <- bal/clothes
- `0x4561ae` OBJ3 bed/ironingboard
- `0x4561ee` Icon ironing
- `0x45621f` GoTo bed/ironingboard
- `0x456280` OBJ3 bed/ironingboard_clothes
- `0x4562bb` Action bed/ironingboard_clothes.iron
- `0x4562fa` Switch bed/ironingboard <- bed/ironingboard_clothes
- `0x4563ab` Icon noise
- `0x4564b2` If lir/dirtycarpet of lir/carpet
- `0x45651c` Icon vacuum
- `0x45654d` GoTo lir/vacuum
- `0x4565bf` If lir/vacuum_hole of lir/vacuum
- `0x456638` Action lir/vacuum_hole.take
- `0x456678` OBJ1 lir/vacuum_hole
- `0x456762` Action lir/dirtycarpet.vacuum_hole
- `0x45682d` Action lir/dirtycarpet.repair
- `0x45688b` Action lir/dirtycarpet.vacuum2
- `0x4568d0` Switch lir/carpet <- lir/dirtycarpet
- `0x4569ba` Action lir/vacuum.give
- `0x456a95` Action lir/vacuum.take
- `0x456ad9` OBJ1 lir/vacuum
- `0x456bc3` Action lir/dirtycarpet.vacuum
- `0x456c08` Switch lir/carpet <- lir/dirtycarpet
- `0x456cf2` Action lir/vacuum.give

## level_fitness (Level112)

- `0x4630b2` OBJ1 kit/skate
- `0x463207` Action kit/window.fallout
- `0x4632f5` OBJ2 kit/skate
- `0x46349f` Action neighbor.wheeze
- `0x4636f3` Icon book
- `0x463724` GoTo wor/book
- `0x4637fc` Action ?.take
- `0x46390d` Icon aquarium
- `0x46393e` GoTo wor/aquarium
- `0x4639b3` If wor/fishfood_steroid of wor/fishfood
- `0x463a0e` OBJ1 wor/fishfood_steroid
- `0x463aa5` Action wor/aquarium.feed_steroid
- `0x463af1` OBJ2 wor/fishfood_steroid
- `0x463b27` OBJ1 wor/fishfood
- `0x463bc2` Action wor/aquarium.feed
- `0x463cba` Icon yoga_mat
- `0x463ceb` GoTo lir/mat
- `0x463da2` Action lir/mat.knot_yoga
- `0x463dec` OBJ2 wor/book_replaced
- `0x463e3b` Action lir/mat.make_yoga
- `0x463ebd` Icon book
- `0x463eee` GoTo wor/book
- `0x463f5e` Action wor/book.take
- `0x464061` Icon expander
- `0x464092` GoTo bas/expander
- `0x464108` If bas/expander_elastic of bas/expander
- `0x464187` Action bas/expander_elastic.train
- `0x4641d6` OBJ2 bas/expander_elastic
- `0x46427d` Action bas/expander.train
- `0x4642f9` Icon home_trainer
- `0x46432a` GoTo lir/hometrainer
- `0x4643a0` If lir/hometrainer_tonged of lir/hometrainer
- `0x46441c` Action lir/hometrainer_tonged.train
- `0x464465` OBJ2 lir/hometrainer_tonged
- `0x464509` Action lir/hometrainer.train
- `0x464585` Icon mixer
- `0x4645b6` GoTo kit/mixer
- `0x46461d` Action kit/mixer.mix
- `0x464677` Action neighbor.drink
- `0x4646f5` Icon skipping_rope
- `0x464726` GoTo anc/skippingrope
- `0x4647cf` Action ?.take
- `0x46490c` Action neighbor.skip_knotted_rope
- `0x46495c` OBJ2 anc/skippingrope_knotted
- `0x4649b0` Action neighbor.skip_rope
- `0x464a0f` Action anc/skippingrope.take
- `0x464b28` Icon barbell
- `0x464b59` GoTo bas/barbell
- `0x464bcf` If bas/barbell_sawed of bas/barbell
- `0x464c4e` Action bas/barbell_sawed.use_sawed_barbell
- `0x464c9d` OBJ2 bas/barbell_sawed
- `0x464d47` Action bas/barbell.use_barbell
- `0x464dc6` Icon trampoline
- `0x464df7` GoTo bed/trampoline
- `0x464e6d` If bed/trampoline_elastic of bed/trampoline
- `0x464eec` Action bed/trampoline_elastic.jump
- `0x464f3b` OBJ2 bed/trampoline_elastic
- `0x464fe5` Action bed/trampoline.jump
- `0x465064` Icon noise
- `0x465323` OBJ3 bas/gun

## level_DIY (Level113)

- `0x452031` Icon valve
- `0x452062` GoTo bas/valve_on
- `0x4520c9` OBJ3 bas/valve_on
- `0x452103` Action bas/valve_on.switch_off
- `0x45214c` Switch bas/valve_off <- bas/valve_on
- `0x45224d` Icon heater
- `0x45227e` GoTo kit/heater
- `0x4522ee` If kit/heater_hot of kit/heater
- `0x45236a` Action kit/heater_hot.vent
- `0x4523b6` OBJ2 kit/heater_hot
- `0x452488` Icon heat_valve
- `0x4524c0` GoTo bas/heatvalve_off
- `0x452530` OBJ3 bas/heatvalve_on
- `0x45256a` Action bas/heatvalve_on.switch_off
- `0x4525b0` Switch bas/heatvalve_fixed <- bas/heatvalve_on
- `0x452694` Action bas/heatvalve_off.switch_off
- `0x4526d6` Switch bas/heatvalve_fixed <- bas/heatvalve_off
- `0x45278e` Icon basin
- `0x4527bf` GoTo toi/basin_flooded
- `0x45282e` If toi/basin_flooded of toi/basin
- `0x4528ad` Action toi/basin_flooded.repair
- `0x4528f9` OBJ2 toi/basin_flooded
- `0x45295d` Action toi/basin.repair
- `0x4529ca` OBJ3 bas/valve_fixed
- `0x452a09` Icon valve
- `0x452a48` GoTo bas/valve_off
- `0x452ac4` OBJ3 bas/valve_on
- `0x452afe` Action bas/valve_on.switch_off
- `0x452b47` Switch bas/valve_fixed <- bas/valve_on
- `0x452c34` Action bas/valve_off.switch_off
- `0x452c79` Switch bas/valve_fixed <- bas/valve_off
- `0x452cf6` OBJ3 bas/valve_off
- `0x452d30` Action bas/valve_off.switch_on
- `0x452d79` Switch bas/valve_on <- bas/valve_off
- `0x452e80` Icon fuse
- `0x452eb1` GoTo anc/fuse
- `0x452f18` OBJ3 anc/fuse
- `0x452f52` Action anc/fuse.get_fuse
- `0x452f9b` Switch anc/no_fuse <- anc/fuse
- `0x4530a2` Icon ladder
- `0x453122` If wor/ladder_cut of wor/ladder
- `0x45325d` OBJ2 wor/ladder_cut
- `0x4533a7` OBJ3 anc/fuse
- `0x45341d` Action wor/ladder.drill
- `0x453475` Action wor/ladder.touch_electricity
- `0x4534cd` Action wor/ladder.climb_down
- `0x453525` Action neighbor.wheeze
- `0x453571` OBJ2 anc/fuse
- `0x4535c5` Action wor/ladder.drill
- `0x453624` Action wor/ladder.touch
- `0x453682` Action wor/ladder.climb_down
- `0x4536fd` Icon fuse
- `0x45372e` GoTo anc/fuse
- `0x453795` OBJ3 anc/fuse
- `0x45381b` Action anc/no_fuse.put_fuse
- `0x453864` Switch anc/fuse <- anc/no_fuse
- `0x45391e` Icon chairkit
- `0x45394f` GoTo lir/stoolkit
- `0x4539c5` If lir/stoolkit_pain of lir/stoolkit
- `0x453a44` Action lir/pieces.assemble_electrochair
- `0x453a93` OBJ2 lir/stoolkit_pain
- `0x453af1` Action lir/pieces.disassemble
- `0x453b9e` Action lir/pieces.assemble
- `0x453c7b` Icon powertool
- `0x453cac` GoTo bal/anglegrinder
- `0x453d5f` Action ?.take
- `0x453eb1` Action bal/anglegrinder_manipulated.grind
- `0x453f01` OBJ2 bal/anglegrinder_manipulated
- `0x453f60` Action bal/anglegrinder_manipulated.give
- `0x454094` Action bal/anglegrinder.grind
- `0x4540f3` Action bal/anglegrinder.give
- `0x4541e6` OBJ3 bas/valve_fixed
- `0x454238` Icon noise

## level_hunter (Level114)

- `0x46535e` OBJ3 bas/gun, bas/gun, bas/gun_loaded
- `0x465396` OBJ3 bas/gun_loaded, bas/gun_loaded, bas/gun_plugged
- `0x4653d3` OBJ3 bas/gun_plugged, bas/gun_plugged, bas/gun_loaded_plugged
- `0x465764` Action neighbor.riphat
- `0x4657aa` OBJ2 bed/stickyhat
- `0x465802` Action neighbor.putbackhat
- `0x465858` Action bed/hat.give
- `0x465a23` Icon polish
- `0x465a54` GoTo kit/polish
- `0x465b2c` Action ?.take
- `0x465c31` Icon cups
- `0x465c69` GoTo wor/cups
- `0x465d21` Action wor/cups.blackpolish
- `0x465d63` Switch wor/cups_black <- wor/cups
- `0x465deb` OBJ2 kit/blackpolish
- `0x465e9d` Action wor/cups.polish
- `0x465f1f` Icon polish
- `0x465f50` GoTo kit/polish
- `0x465fbf` Action kit/polish.give
- `0x4660be` Icon smoke
- `0x4661bc` Action neighbor.give
- `0x4662c0` Icon phonograph
- `0x4662f1` GoTo lir/lockedphono
- `0x46635d` Action lir/lockedphono.open
- `0x4663a6` Switch lir/phono_open <- lir/lockedphono
- `0x466464` Icon records
- `0x466495` GoTo lir/records
- `0x466514` Icon phonograph
- `0x466545` GoTo lir/phono_open
- `0x466669` Action ?.put_record
- `0x4666c8` Action lir/phono_nail.play
- `0x466718` OBJ2 lir/phono_nail
- `0x4667c1` Action lir/phono_open.close
- `0x466807` Switch lir/lockedphono <- lir/phono_open
- `0x46689c` Action ?.put_record
- `0x4668e6` Switch lir/phono_play <- lir/phono_open
- `0x4669a9` Icon smoke
- `0x4669da` GoTo lir/tabacbox
- `0x466afe` Action ?.take
- `0x466bde` Action neighbor.smokepipe_explosive
- `0x466c2e` OBJ2 lir/tabacbox_explosive
- `0x466d67` Action neighbor.smokepipe
- `0x466de2` OBJ3 lir/phono_play
- `0x466e22` Icon phonograph
- `0x466e53` GoTo lir/phono_play
- `0x466ec5` Action lir/phono_play.close
- `0x466f0e` Switch lir/lockedphono <- lir/phono_play
- `0x466fc9` Icon gun
- `0x466ffa` GoTo bas/gun
- `0x467113` Action ?.take
- `0x4671e1` Action neighbor.shoot_loaded
- `0x46722b` OBJ2 bas/gun_loaded
- `0x467301` Action ?.take
- `0x4673d2` Action neighbor.shoot_loaded_plugged
- `0x46741f` OBJ2 bas/gun_loaded_plugged
- `0x4674d3` Action ?.take
- `0x4675b7` Action neighbor.shoot_klick
- `0x467747` Icon hat
- `0x467778` GoTo bed/hat
- `0x467855` Action ?.take
- `0x467939` Action neighbor.takehat
- `0x467a1d` If bed/medalbox_rat of bed/medalbox
- `0x467a7e` OBJ1 bed/medalbox_rat
- `0x467be4` OBJ1 bed/medalbox
- `0x467c85` Action neighbor.wearmedals
- `0x467dbf` Icon horn
- `0x467df0` GoTo bal/woodhorn
- `0x467f14` Action ?.take
- `0x467ff4` Action neighbor.blowballoon
- `0x468044` OBJ2 bal/balloonhorn
- `0x4680b4` Action bal/woodhorn.take
- `0x468198` Action neighbor.blowhorn
- `0x468315` Icon noise

## tutorial_2

- `0x459b84` Icon neighbor, noise
- `0x459c86` Icon sign1
- `0x459cb3` GoTo lir/sign1
- `0x459d40` Icon sign2
- `0x459d6d` GoTo kit/sign2
- `0x45a0d4` Action neighbor.slip1
- `0x45ab0e` OBJ3 lir/mum
- `0x45ad21` Icon sign1
- `0x45ad4f` GoTo lir/sign1
- `0x45ad8e` Icon sign2
- `0x45adbc` GoTo kit/sign2
- `0x45afa4` Action neighbor.doubletake1
- `0x45b0b3` OBJ2 lir/mum_smeared
- `0x45b21e` Action neighbor.slip1
