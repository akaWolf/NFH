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

**The fire's tail and the trick steps, read from the code (2026-09-22).** fcn.0047bd00 is slot 2
of the vtable 0x4e5944 — the trick STEP the level scripts and the walk-trigger handlers push
through the script fiber (fcn.004766e0 runs one step and waits for it): `OBJ2 <object>` in
tools/pcref/exe_scripts.py's listings is fcn.0047c290(object, index, flags) (the constructor
fcn.0047ba80: +0xc the name, +0x10 = index ≠ 0, +0x14 the flags), and the five-argument
fcn.0047c320(object, animation, actor, index, flags) (fcn.0047bca0 / fcn.0047baf0) is the same
step carrying a DoAction of that animation at +0x18. When the step runs: the record lookup; no
points → nothing but the fired flag; else the bonus test, the score, the rage (fcn.00438b90),
the face, the jingle (music/jingle_joke.mp3), THEN the +0x18 animation if any (waited on), THEN
the shout as a DoAction on `neighbor` — `shout2_extra` (92 frames, 7.67 s) when the trick was
a bonus, else by the points: ≤ 5 shout0_light (25 frames, 2.08 s) or shout2 (26, 2.17 s),
≤ 10 shout0_medium (45, 3.75 s) or shout2, > 10 shout0 (26, 2.17 s) or shout2 — the second
of each pair at index 1 (the tables 0x51b584, 0x51b590, 0x51b598, 0x51b5a0) — unless flag 2
is set; then a sync step (fcn.0047bc90 sets +0x8a) unless flag 1, fcn.00444d30 on the object,
the fired flag +0x1c. The script functions only queue: fcn.004766e0 appends a step to the
level's list (the sequence at the level state's +0x14, fcn.0041ae40) and `push N; jmp` yields
to the next case of the class's `run`; the tick's runner fcn.00444db0 runs the head step every
tick until it reports done, pops it and goes on within the tick (nothing runs while the busy
byte +0x78 is set); a sub-sequence (fcn.00476770, vtable 0x4e5430) posts its steps one at a
time behind itself (fcn.00444d30 with the run-now flag clear, fcn.00478f90's append); a step's
run(a1, a2) gets the level state (the fire reads its angrytime at +0x84 and asks it for the
rage through fcn.004357e0) and the list owner. A DoAction (fcn.00477f60) is an action object
(vtable 0x4e546c) whose run starts its animation when its step comes up and reports done when
the engine ends it; an object never appended never plays. The fire appends its own steps — the
+0x18 animation, the shout, the sync — to the tail of that list, behind whatever the script
queued in the same case: the foam pudding's `repair`, OBJ1 and Switch come before its shout
(the same sum either way). The
bonus flag is `bl = (fcn.004357e0(level) != 0)`, the rage current above zero, and it also
picks the face (4) and the +3. The repair is not in the step: the walk-trigger handlers call
fcn.0047ae70(normal, tricked, …, 1) after it, which plays the tricked object's `repair`
action if it has one, else its `clean`, else nothing (fcn.00445d30 asks the object; objects.xml: anc/mum_smeared clean 24 frames = 2.0 s, kit/microwavedirty and
toi/groundsoap clean 23 ticks = 1.9 s, toi/toiletstuffed clean 47 = 3.9 s) and switches the
objects, and the station branches play theirs themselves (kit/foambottle: `make_foampudding`
38 frames = 3.17 s, the OBJ2 step, then `repair` 23 ticks). So the order per trick kind: a
station — the tricked object's own action, the fire, the shout, the repair; a doubletake
(mum_smeared, microwavedirty, toiletstuffed, twistedantenna: fcn.0047d9e0 and its siblings) —
doubletake1 and doubletake3 (15 frames each) as two DoActions of which only the second is
appended to the step list (fcn.004766e0) — a DoAction builds an action object with its own node
list (fcn.00477ed0, fcn.00477d50, fcn.00477e00) that runs only when its step comes up, and the
first object is released unrun — so doubletake3 alone plays, 1.25 s, then the fire, the shout,
the repair; a slip (toi/groundsoap: fcn.0047ddc0, reached through fcn.0047e000) — a
sub-sequence of the stop message (fcn.0047b350, engine listener slot 26), the fire with the
fall inside it — slip1 or slip3 (31 frames, 2.58 s each) by the neighbour's facing,
fcn.0047c7f0 reading the direction digit of his walk animation (mg0/mg1/…), one of the two,
not both — and a follow-up step (vtable 0x4e1bdc → fcn.00438c80: an engine event, listener
slot 65, on the soap; no clean animation): the score first, then the fall, then the shout; and
the other five-argument sites pay before their own clip too: the tub's hair
(`show_hair` on toi/shower after the 2.83 s `shower` clip), the dirty towel (`show_black`),
the electrotrap, the mailbox trap, the vacuum, the sofa, the tabasco teeth, the coffee soil,
the shoebrush, the ironing board, the plant fight, the rat. The sites' index and flags (tools/pcref/fire_sites.py: the
pushes and slot stores before each call through a stack emulation; a register-valued int
through radare2's analysis of the level fiber — the level classes' `run` is a switch on the
resume index, and every such site sits in a case that never reloads the register, so the
prologue's `mov ebx, 3` / `xor ebp, ebp` / `xor edi, edi` stands): index 1 (shout2 when cold)
at kit/foambottle, lir/stickybook, kit/foamcream, kit/bowlingball, toi/aftershave_glue,
toi/grease_exchanged, kit/candlebox_boom, bal/suncream_sweet, bed/bed_pins, bed/stickyhat,
kit/babybottle_nitro, kit/stool_pins, kit/potterswheel_fast, bed/camera_flashy,
kit/heater_hot, toi/basin_flooded, anc/fuse, bas/expander_elastic, anc/skippingrope_knotted,
kit/binoculars_glue and at the five-argument lir/vacuum_hole, toi/shoebrushset,
anc/mailbox_trap, bal/growspray, bed/teeth_tabasco, bas/electrotrap, toiletpaper and every
soap and marbles slip; flags 3 (no shout, no sync) at toi/tub_hair, toi/dirtytowel,
lir/bathcandy, anc/stinkflower, bed/medalbox_rat, bal/fuelbeer, kit/laxativebeer and
kit/skate; flags 2 (no shout) at kit/coffeebox_soil, lir/sofa_broken, toiletpaper and
bed/cactusclock; the rest flags 0. The four-argument step fcn.0047c3b0 (fcn.0047bc00: name,
index, flags and a ready step at +0x18 the fire waits on before the shout) serves the marbles
(0x45b2aa queues slip1 then slip3 as two DoActions — the second alone plays — and fires after
it; 0x45a1cf fires after a level event step), kit/laxativebeer (the fire after the queued
`spit`), bal/fuelbeer (the fire after `pour_fuel` on the barbecue, 29 frames = 2.42 s, with the
Switch to bal/barbecue_burn inside it and flags 3: no shout, no sync), bed/cactusclock (flags
2, a bed/bed_sleep event step inside) and lir/sofa_fartbag (the index from a level helper):
at these the pay follows the clip, unlike the soap slip. The three engine-side steps of
these sequences are read through GFXEngine.dll (its text listing
~/nfh-bench/pcref/r2/nfh1_gfxengine_text.txt, made like the game.exe one; the events are
0xc-byte objects whose slot 2 calls one slot of every registered listener's 111-slot table,
default 0x1000ec10 = not handled; game.exe's own level listener, tables 0x4e07b8 / 0x4e1638,
handles neither): the stop message fcn.0047b350 (vtable 0x4e5798, listener slot 26, payload
0) reaches the GUI table 0x100a3740 as fcn.10011a10 → fcn.1000ffd0 → fcn.10014770 — the
in-game GUI's byte +0x30 set, GetTickCount stored at +0x2c and the four face elements
head_01..head_04 (globals 0x100cd704..0x100cd710) set to state 1 through fcn.100091f0 — while
the scene and actor tables' slot-26 handlers (0x10022f90, 0x10005240, 0x10022370, 0x1001a0b0,
0x10020470) act only on a payload of 1 with a subfield 0x1b and ignore this one; the soap
slip's follow-up (vtable 0x4e1bdc → fcn.00438c80: the object looked up by name, its flag
word +0x14 given bit 0x20 through fcn.0043c280, the 0xc-byte event 0x4e095c dispatched, and
the object deleted when its bit 1 is set) reaches listener slot 65: table 0x100a2b90's
fcn.1001bc00 → fcn.100207b0 plays sfx_na_slip_up1.wav, table 0x100a2b48's fcn.100054d0 only
fills the event's out-slot with two fields; and the cactus clock's ready step (fcn.00468700,
vtable 0x4e1bd0, run fcn.004792c0 — the string "SwitchObjectsJobCallback::Do: Old object not
in world") is a SwitchObjects job on bed/bed_sleep. None of the three plays an animation on
the neighbour or takes time: the face icons, a sound, an object swap. Badinfos' E06 agrees to the second: the tub's hair fires 7.0 s before the towel
and the towel 18.0 s before the album (no shout at either), the cold microwave (7 points:
shout0_medium 3.75 + clean 1.9 + the walk + make_foampudding 3.17) 15.0 s before the pudding,
and every bonus trick is followed by the 7.67 s shout2_extra.

Two more facts of the same state: no Season 1 trick carries a `quota2`-`quota4` in
tricks.xml (every trick pays once, as the mobile's OnTrickDone does), and the level's end is
the state machine of fcn.00436bb0 (docs/PC_VERIFICATION.md, "The level's end"): 5 = success
once the score reaches 100 or every reachable trick has fired, 4 = time's up below minquota
(5 at or above it), 2 = caught after the beating unless the quota is already reached — then
a 5 as well; the jingle table at 0x440f2f (0 and 2 `jingle_failed`, 1 `jingle_caught`,
3 `jingle_success_normal`) is indexed by the dialog's outcome, and `jingle_success_perfect`
is never played by the code. Season 1 has no lives, a catch ends the level, where Season 2
starts every level with three (GameLogic.dll fcn.10044234, the status copy's +0x14 = 3) and
takes one per catch (fcn.10042471).

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
and the level's tick (fcn.10044234, second half, 0x10044712): it copies the status, counts a
respawn timer down (+0x18), subtracts the level record's +0x28 from the rage (+0x1c, not below
zero), counts the time (+0x24) up by one and calls fcn.10042358 — so the HUD gets the status
every tick. The record is the leveldata.xml entry found by the level's name (the app's parser
at game.exe 0x40d0c0 stores `reachable` at +0x1c, `mincoins` at +0x20, `coins` at +0x24,
`time` at +0x28, `score` at +0x2c), and `time` is 30 on all fourteen levels: the gauge falls
30 per tick. The tick is the same 12 Hz as Season 1's — the HUD clock (GUIEngine fcn.10007334)
divides the count by 12 before its minutes and seconds — so the decay is 360 a second, 0.36 %
of the gauge (the mobile's AngryMeterDecay 0.37 is that, rounded; the video's 0.40-0.43 read
carries the reader's scale). The profile carries it as PCRageDecay 30 on the Season 2
neighbour (pcprofile.s2_rage_tick, 12 ticks a second). The COLLAPSE! board is fcn.10040226:
`(coins + lives) × 1000 + (collapsed ? 5000 : 0) + fcn.10040205`, where fcn.10040205 is
6 000 000 / the status's tick count (+0x24) — 500 000 over the seconds — and the collapse byte
(+0x28) is the accounting's flag at 100 000 rage; the level end (fcn.10042471, second half)
compares that sum with the leveldata record's `score` (+0x2c) and keeps the better. The Season 2 game.exe (`tools/pcref/exe`'s dumps cover it now) is an application
shell whose string table holds `rage`/`quota` once each. The walk is fcn.1000e3e0(level, actor, object), a bool that is false when the walk was
interrupted, followed by the wait fcn.1000aeb8; fcn.1000f977(actor, n) is a shout — a random
`shout<n>_*` / `freakout` animation — not a walk. The Season 2 scripts are extracted below
(2026-09-16). The `time` attribute of objects.xml's actions is a tick count of the 12 Hz level tick: the
fiber that runs a timed action counts `[obj+0x28]` down once a tick (fcn.00474a20,
fcn.00475850, fcn.00478120), so a door's 9–25 is 0.75–2 s and the laundry's wash 59 is 4.9 s
a visit (the video's ~24 s at the washer are its three visits, its iron 71 the two of 5.9 s);
`time="auto"` runs the animation to its end at one frame a tick, and GFXEngine keeps no
sprite timer of its own (its only 83 ms constant is a button's auto-repeat). The earlier
"not a clock unit" here came from the 20 fps misreading of the tick; corrected 2026-09-16.
The port runs the mobile routines.

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

# Season 2 (GameLogic.dll)

The same reading for GameLogic.dll (`tools/pcref/exe_scripts.py --gl`, the globals from
`tools/pcref/exe/nfh2_gamelogic_globals.json`, the calls in `tools/pcref/exe/nfh2_gamelogic_scripts.json`):
`Icon` = SetIcon(actor, icon) fcn.100422a5, `GoTo` = fcn.1000e3e0(level, actor, object) — the walk,
false when interrupted, its object often held in a local the listing does not name — `Action` =
DoAction(actor, anim) fcn.10002cd5 with the wait fcn.1000ae19, `Shout n` = fcn.1000f977(actor, n), a
random shout<n>/freakout animation, `If variant a of b` = fcn.1000fb6e, `If tricked` = fcn.1000ec67,
`Room` = fcn.1000fc33, `Set n` = fcn.1000f5c9. The level of a block is the objects.xml whose
room/object names it shares (cn_c1, Level204, matched none and its calls sit under its
neighbours or none). Code order, as for Season 1.

## ship1 (Level201)

- `0x10026990` Room auweia auweia topleft woody
- `0x10026a1a` Room wait1 wait1 bottomleft neighbor
- `0x10026b8e` Room wait1 wait1 bottomleft neighbor
- `0x10026c7e` Room hurry hurry bottomleft woody
- `0x10026cae` Room bottomleft neighbor
- `0x10026ce5` Room topleft woody
- `0x10026f63` If tricked topright_reling_open
- `0x10026ffc` If tricked topright_soappuddle
- `0x10027151` If tricked topright_soappuddle
- `0x100271b5` If tricked topright_reling_open
- `0x100273c7` If tricked topleft_buffet_damaged
- `0x10027a66` If tricked topright_waterpuddle
- `0x10028371` Icon 32 neighbor
- `0x100283a7` GoTo entry
- `0x100283db` Shout 0
- `0x100284ba` Icon 0 reling neighbor
- `0x100284fd` If variant topright_soappuddle of topright_waterpuddle
- `0x10028531` GoTo ?
- `0x10028592` Action topright_waterpuddle.slip.1.topright_waterpuddle
- `0x100285ff` Action topright_soappuddle.crash_short
- `0x10028699` Shout 2
- `0x100286de` Set 
- `0x10028a9f` Icon olga_fight neighbor
- `0x10028bdb` Icon neighbor_entry olga neighbor
- `0x10028c0f` GoTo topleft_buffet
- `0x10028c3c` Action topleft_buffet.flirt.0.0
- `0x10028cba` Icon captncap neighbor
- `0x10028cfd` If variant topleft_captncap_manip of topleft_captncap
- `0x10028d31` GoTo ?
- `0x10028edf` Icon topleft_captncap_manip 1 captncap neighbor
- `0x10028f15` GoTo topright_waterpuddle
- `0x10028f42` Action topright_waterpuddle.slipleft.0.0
- `0x10028fbf` Icon reling neighbor
- `0x10028ff3` GoTo topright_reling
- `0x10029020` Action topright_reling.look.0.0
- `0x1002909d` Icon reling neighbor
- `0x100290d2` GoTo topright_reling_open
- `0x10029111` Action topright_reling_open.repair
- `0x10029209` Icon topright_reling topright_reling_open reling neighbor
- `0x1002924c` If variant topright_soappuddle of topright_waterpuddle
- `0x1002927f` GoTo ?
- `0x100292e0` Action topright_waterpuddle.slip.1.topright_waterpuddle
- `0x100293a2` Action topright_soappuddle.crash_long
- `0x10029533` Icon neighbor tutorial neighbor
- `0x1002956a` GoTo entry
- `0x100295a9` Action neighbor.wheeze
- `0x100295ec` Shout 2
- `0x100296c2` Icon 1 neighbor
- `0x100297ff` Icon neighbor_entry reling neighbor
- `0x10029831` GoTo topright_soappuddle
- `0x10029870` Action topright_soappuddle.crash_long
- `0x10029969` Icon topright_waterpuddle topright_soappuddle 1 neighbor
- `0x10029ab5` Icon wait neighbor o_hurt_n neighbor
- `0x10029b02` Shout 0
- `0x10029b84` Action topleft_buffet_damaged.repair
- `0x10029c84` Icon topleft_buffet topleft_buffet_damaged olga neighbor
- `0x10029cb6` GoTo topleft_buffet_damaged
- `0x10029cf5` Action topleft_buffet_damaged.flirt
- `0x10029d44` Action topleft_buffet_damaged.crash
- `0x10029de6` Icon captncap neighbor
- `0x10029e17` GoTo topleft_captncap
- `0x10029edd` Icon topleft_captncap captncap neighbor
- `0x10029f13` GoTo topright_waterpuddle
- `0x10029f40` Action topright_waterpuddle.slipleft.0.0
- `0x1002a011` GoTo topright_reling
- `0x1002a033` Icon neighbor
- `0x1002a0a6` Icon wait neighbor reling neighbor
- `0x1002a0da` GoTo topright_reling
- `0x1002a107` Action topright_reling.look.0.0
- `0x1002a206` Icon tutorial reling neighbor
- `0x1002a239` GoTo topright_soappuddle
- `0x1002a278` Action topright_soappuddle.crash_short
- `0x1002a312` Shout 2
- `0x1002a406` Icon 0 wait neighbor neighbor
- `0x1002a499` Icon 1 0 captncap neighbor
- `0x1002a4ca` GoTo topleft_captncap
- `0x1002a523` Icon captncap neighbor
- `0x1002a55a` GoTo topright_waterpuddle_closed
- `0x1002a5ee` Action topright_waterpuddle.slipleft.0.0
- `0x1002a6c5` Icon 1 0 reling neighbor
- `0x1002a6f9` GoTo topright_reling
- `0x1002a726` Action topright_reling.look.0.0
- `0x1002a7a3` Icon reling neighbor
- `0x1002a7d5` GoTo topright_waterpuddle_closed
- `0x1002a810` Action topright_waterpuddle_closed.slip.0.0
- `0x1002a88f` Icon olga neighbor
- `0x1002a8c3` GoTo topleft_buffet
- `0x1002a8f0` Action topleft_buffet.flirt.0.0
- `0x1002a96d` Icon captncap neighbor
- `0x1002a99e` GoTo topleft_captncap
- `0x1002ac57` If variant 36 of topleft_buffet_damaged
- `0x1002ac88` GoTo ?
- `0x1002acc6` Action 1
- `0x1002aeb5` Action topleft_buffet_damaged.crash.0.0

## cn_b1 (Level202)

- `0x100216c8` Icon 16 bridge neighbor
- `0x1002170b` If variant pond_bridge_damaged of pond_bridge
- `0x1002173f` GoTo ?
- `0x1002177e` Action neighbor.lookaround
- `0x100217e9` If tricked pond_pond_eel
- `0x10021817` Action crash
- `0x10021863` Action electrify
- `0x100218af` Action leave
- `0x100218f5` Shout 2
- `0x10021903` Action ?
- `0x1002194f` Action leave
- `0x10021995` Shout 1
- `0x100219db` Set 6
- `0x10021a1f` Action repair
- `0x10021a9d` Action look.pond_bridge.2
- `0x10021d9f` Icon 2 goswim neighbor
- `0x10021e2e` Icon 97 beachright_theocean goswim neighbor
- `0x10021ead` Shout 0
- `0x10021ff0` Icon beachright_theocean beachright_theocean_shark goswim neighbor
- `0x10022078` If tricked beachright_theocean_shark
- `0x100220fc` Action dive
- `0x100221a8` Action beachleft_sub.run_ashore.beachleft_sub
- `0x1002221d` If tricked shark
- `0x100222e7` Action shark.dive.beachright_theocean_shark
- `0x10022393` Action beachleft_sub.run_ashore.shark.beachleft_sub
- `0x10022449` Icon goswim neighbor
- `0x1002247a` GoTo beachright_theocean
- `0x100224a8` If tricked 4
- `0x100224c9` If tricked shark
- `0x100225c3` Icon 0 waitsea goswim neighbor
- `0x100225de` If tricked pond_rake_ground_weed
- `0x1002261a` GoTo pond_rake_ground_weed
- `0x10022659` Action pond_rake_ground_weed.crash
- `0x1002269e` Shout ?
- `0x100226e4` Set 6
- `0x1002272b` Action pond_rake_ground_weed.repair
- `0x100227ed` If tricked pond_rake_ground
- `0x10022827` GoTo pond_rake_ground
- `0x10022866` Action pond_rake_ground
- `0x100228b5` Action pond_rake_ground.repair
- `0x10022952` Set 1 pond_rake pond_rake_ground 6
- `0x100229da` Icon beer neighbor
- `0x10022a1d` If variant beachright_mat_hn_guarded_manip of beachright_mat_hn_guarded
- `0x10022a8f` Action 4
- `0x10022b35` Shout beachright_mat_hn_guarded_manip
- `0x10022b7b` Set 6
- `0x10022bbf` Action repair
- `0x10022cc7` Icon 2 beachright_mat_hn neighbor
- `0x10022d10` If variant beachright_mat_hn_guarded_manip of beachright_mat_hn_manip
- `0x10022d45` GoTo ?
- `0x10022f93` If variant 20 of beachleft_mat_olga_guarded
- `0x10022fc8` GoTo ?
- `0x100230de` If variant beachleft_mat_olga_guarded of beachleft_mat_olga_guarded
- `0x10023112` GoTo ?
- `0x100231e7` Action take.beachleft.4
- `0x10023460` Action beachleft_mat_olga_guarded.wakeup.2
- `0x1002359a` Action beachleft_mat_olga_guarded

## cn_c2 (Level203)

- `0x10033754` If variant groundleft_bike_manip of groundleft_bike
- `0x10033788` GoTo ?
- `0x100337c4` Action ?
- `0x1003382e` Shout groundleft_bike_manip
- `0x10033874` Set 6
- `0x100338b8` Action repair
- `0x10033bf6` Icon 2 melons neighbor
- `0x10033c39` If variant wallleft_melons_manip of wallleft_melons
- `0x10033c6d` GoTo ?
- `0x10033ca9` Action ?
- `0x10033d14` Shout wallleft_melons_manip
- `0x10033d5a` Set 6
- `0x10033e5b` Icon 1 wallleft_melons ricetoilet neighbor
- `0x10033e8e` GoTo groundleft_toilet
- `0x10033ed7` If variant groundleft_chilipaper of groundleft_toiletpaper
- `0x10033f1a` If variant groundleft_ricechute_manip of groundleft_ricechute
- `0x10033fea` Action groundleft_toilet.shit.groundleft_ricechute_manip.groundleft_chilipaper
- `0x1003400f` Action groundleft_toilet.shit_chili
- `0x100340fb` Action groundleft_toilet.flush_rice.flush
- `0x10034175` Action groundleft_toilet.flush.manip
- `0x100341d6` Shout 2
- `0x1003421c` Set 6
- `0x10034263` Action groundleft_toilet.repair
- `0x100343db` Icon 2 groundleft_ricechute neighbor
- `0x1003440e` GoTo wallright_generator_manip
- `0x1003444d` Action wallright_generator_manip.repair
- `0x10034545` Icon wallright_generator wallright_generator_manip speech neighbor
- `0x10034588` If variant wallright_stage_broken of wallright_stage
- `0x100345bc` GoTo ?
- `0x10034633` If tricked wallright_generator_manip
- `0x100346d6` Action crash.wallright_image.crash.wallright_stage
- `0x10034758` Shout 1
- `0x1003479e` Set 6
- `0x10034830` Action wallright_image
- `0x10034b05` Action shout.0.0.2

## cn_b2 (Level205)

- `0x10023840` Action shop_glasses_guarded.0.0
- `0x10023934` If tricked shop_glasses
- `0x10023a13` Action shop_glasses_guarded.take.shop_glasses_guarded.shop
- `0x10023b60` Action shop_chef_blind.search.shop_chef_blind.shop_chef_blind
- `0x10023ddb` Icon 24 o_hurt_n neighbor
- `0x10023e69` Action beachleft_sandlion.build.0.0
- `0x10024141` Icon 2 sandlion
- `0x10024192` If variant beachleft_sandlion_iron of beachleft_sandlion
- `0x100241c3` GoTo ?
- `0x10024202` Action neighbor.lookaround
- `0x1002424e` Action kick
- `0x100242f9` Shout beachleft_sandlion_iron
- `0x1002433f` Set 6
- `0x10024383` Action repair
- `0x10024426` Action laugh.beachleft_sandlion.1
- `0x1002448a` Action dirt
- `0x10024558` Icon rockets
- `0x100245a9` If variant beachleft_firework_rope of beachleft_firework
- `0x100245da` GoTo ?
- `0x10024674` Action beachleft_rocket.ignite.beachleft_rocket.beachleft
- `0x10024775` Action beachleft_rocket_rope.ignite.neighbor
- `0x10024812` Action crash.beachleft_rocket_rope
- `0x10024868` Shout 1
- `0x100248ad` Set 
- `0x10024974` Icon 1
- `0x100249c5` If variant shop_chef_blind of shop_chef
- `0x100249f6` GoTo ?
- `0x10024a3c` If tricked shop_tube
- `0x10024aaa` Action cut_tyre.shop_tube.disappear
- `0x10024b35` Action eat_tyre.shop_tube
- `0x10024b78` Shout 2
- `0x10024bbe` Set 6
- `0x10024c1b` Action take_tyre.shop_tube.disappear
- `0x10024ca6` Action cut_eel.shop_tube
- `0x10024cf2` Action eat_eel
- `0x10024d38` Set 6
- `0x10024d71` Action cut_eel
- `0x10024dbd` Action eat_eel
- `0x10024e86` GoTo beachleft_waterski_guarded
- `0x10024f01` Action beachleft_waterski_guarded.putski.neighbor.idle
- `0x10025011` GoTo beachleft_waterski_nailed_guarded
- `0x10025060` Action neighbor.pant.262144
- `0x100250a3` Shout 1
- `0x1002512d` Action beachleft_waterski_nailed_guarded.repair
- `0x10025233` Icon 5 beachleft_waterski beachleft_waterski_nailed_guarded waterski
- `0x10025284` If variant beachleft_waterski_nailed of beachleft_waterski
- `0x100252b7` GoTo ?
- `0x100253f6` Action beachleft_waterski_nailed_guarded.skiing.beachleft_waterski_nailed_guarded.beachleft
- `0x1002545d` Action beachleft_waterski_guarded.skiing.beachleft_waterski_guarded
- `0x1002551d` Icon pingpong
- `0x10025576` If variant beachright_pingpong_egg of beachright_pingpong
- `0x100255b3` GoTo ?
- `0x1002561e` Action play.beachright_pingpong_guarded
- `0x100256f3` Action play.6.beachright_pingpong_egg_guarded
- `0x100257cd` Shout 0
- `0x10025945` Icon olga_fight pingpong
- `0x10025996` If variant beachright_mat_guarded of beachright_mat
- `0x100259c9` GoTo ?
- `0x10025a00` Action neighbor.talk
- `0x10025bb1` Action beachright_mat_guarded.wakeup.beachright_mat_guarded.20
- `0x10025cd1` If variant beachright_pingpong_egg_guarded of beachright_pingpong_guarded
- `0x10025d02` GoTo ?
- `0x10025f08` If variant beachright_pingpong_guarded of beachright_pingpong_egg_guarded
- `0x10025f39` GoTo ?

## ship2 (Level206)

- `0x1002b4b0` If tricked topright_pillows_manip
- `0x1002ba35` Icon topleft_deckchair 0 4 mother
- `0x1002ba65` GoTo topleft_deckchair
- `0x1002baf7` Icon 720 topleft_deckchair m_hurt_n mother
- `0x1002bbfc` Icon tutorial m_hurt_n mother
- `0x1002bc2a` GoTo bottomleft_ramp
- `0x1002bd3b` Icon fifi_crash m_hurt_n mother
- `0x1002bdad` Icon 268614457 neighbor mother
- `0x1002bde2` Action topleft_deckchair.fart.0.0
- `0x1002be5d` Icon neighbor mother
- `0x1002beb8` Icon topleft_deckchair neighbor bring_pillow mother
- `0x1002bee1` Action mother.order.0.0
- `0x1002bfe5` Action topleft_deckchair.pillow_slip.topleft_deckchair.topleft_deckchair
- `0x1002c034` Action mother.callneighbor
- `0x1002c0e3` GoTo topleft_deckchair
- `0x1002c1b2` Icon tutorial topleft_deckchair mother
- `0x1002c211` Icon neighbor mother
- `0x1002c26c` Icon topleft_deckchair neighbor bring_pillow mother
- `0x1002c295` Action mother.order.0.0
- `0x1002c30f` Icon neighbor mother
- `0x1002c3f3` GoTo topleft_deckchair
- `0x1002c58a` Icon 36 dynamitefish neighbor
- `0x1002c5bf` GoTo topright_reling
- `0x1002c6ae` Icon 1 2 dynamitefish neighbor
- `0x1002c6e3` GoTo topright_reling
- `0x1002cadc` Icon dynamitefish neighbor
- `0x1002cb25` If variant topright_dynamitebag_manip of topright_dynamitebag
- `0x1002cb58` GoTo ?
- `0x1002cb94` Action take
- `0x1002ccc9` Icon topright_dynamitebag topright_dynamitebag_manip fifi neighbor
- `0x1002ccfc` GoTo topleft_fifi
- `0x1002cd2f` If tricked topleft_fleablanket
- `0x1002ce14` Action topleft_fifi.topleft_fifi.topleft
- `0x1002ce63` Action topleft_usedblanket
- `0x1002cee4` Action topleft_fifialone.topleft_fifialone.topleft
- `0x1002cf89` Icon workout neighbor
- `0x1002cfcc` If variant bottomright_dumbbell_manip of bottomright_dumbbell
- `0x1002d007` GoTo ?
- `0x1002d046` Action bottomright_fifi
- `0x1002d095` Action olga.marvel
- `0x1002d10c` Action bottomright_dumbbell.bottomright_dumbbell
- `0x1002d15b` Action olga
- `0x1002d1ae` Action bottomright_dumbbell_manip
- `0x1002d1fd` Action olga.laugh
- `0x1002d297` Shout 4
- `0x1002d2dd` Set 2
- `0x1002d33c` Action bottomright_fifi.take
- `0x1002d3ef` Icon fifi neighbor
- `0x1002d427` GoTo bottomleft_fifi
- `0x1002d454` Action bottomleft_fifi.take.0.0
- `0x1002d4d0` Icon fifi neighbor
- `0x1002d508` GoTo bottomleft_fifi2
- `0x1002d535` Action bottomleft_fifi2.take.0.0
- `0x1002d5af` Icon neighbor
- `0x1002d5f6` If variant bottomleft_harpoon_manip of bottomleft_harpoon
- `0x1002d629` GoTo ?
- `0x1002d6e9` Action bottomleft_harpoon.bottomleft_harpoon_manip.bottomleft_harpoon
- `0x1002d797` Icon neighbor
- `0x1002d7de` If variant bottomleft_harpoon_manip of bottomleft_harpoon
- `0x1002d811` GoTo ?
- `0x1002d8d1` Action bottomleft_harpoon.bottomleft_harpoon_manip.bottomleft_harpoon
- `0x1002d981` Icon shoot_teddy neighbor
- `0x1002d9b9` GoTo bottomleft_ramp
- `0x1002d9e6` Action bottomleft_ramp.shootbear.0.0
- `0x1002da64` Icon shoot_teddy neighbor
- `0x1002da9a` GoTo bottomleft_ramp
- `0x1002dad9` Action bottomleft_ramp.rubberbear
- `0x1002db1c` Shout 1
- `0x1002db62` Set 6
- `0x1002dc0d` GoTo bottomleft_ramp
- `0x1002dc4c` Action bottomleft_ramp.repair
- `0x1002dd45` Icon bottomleft bottomleft_rabbit shoot_teddy neighbor
- `0x1002dd8e` If variant bottomleft_harpoon_manip of bottomleft_harpoon
- `0x1002ddc1` GoTo ?
- `0x1002dde9` Action take
- `0x1002deb2` Icon bottomleft_harpoon being_hit neighbor
- `0x1002defb` Shout 0
- `0x1002dfd3` Icon 0 shoot_teddy neighbor
- `0x1002e00b` GoTo bottomleft_ramp_manip
- `0x1002e135` Icon bottomleft_ramp bottomleft_ramp_manip shoot_teddy neighbor
- `0x1002e16d` GoTo bottomleft_ramp_manip
- `0x1002e2ba` Icon bottomleft_ramp bottomleft_ramp_manip shoot_teddy neighbor
- `0x1002e303` If variant bottomleft_harpoon_manip of bottomleft_harpoon
- `0x1002e336` GoTo ?
- `0x1002e35e` Action take
- `0x1002e41a` Icon bottomleft_harpoon shoot_teddy neighbor
- `0x1002e467` If variant bottomleft_ramp_manip of bottomleft_ramp
- `0x1002e49a` GoTo ?
- `0x1002e4d9` Action bottomleft_fifi
- `0x1002e525` Action load
- `0x1002e598` Action bottomleft_fifi.bottomleft_ramp_manip
- `0x1002e677` Icon bottomleft_ramp fifi neighbor
- `0x1002e6c0` If variant topleft_fifialone of topleft_fifi
- `0x1002e6f3` GoTo ?
- `0x1002e75a` Action topleft_usedblanket.empty.topleft_fifi
- `0x1002e7a9` Action topleft_fifi.take
- `0x1002e870` Action topleft_fifialone.take.topleft_usedblanket.topleft_fleablanket
- `0x1002e96f` Icon topleft_fifialone m_hurt_n neighbor
- `0x1002e9ba` Shout 0
- `0x1002ea90` Icon 0 bring_pillow neighbor
- `0x1002eacb` GoTo topleft_deckchair
- `0x1002eaf8` Action topleft_deckchair.give.0.0
- `0x1002eb75` Icon get_pillow neighbor
- `0x1002ebae` GoTo topright_pillows_manip
- `0x1002ebef` Action topright_pillows_manip.take
- `0x1002ecec` Icon topright_pillows topright_pillows_manip mother neighbor
- `0x1002ed24` GoTo topleft_deckchair
- `0x1002ed86` Icon neighbor
- `0x1002edba` GoTo topleft_fifi
- `0x1002ee88` Icon neighbor 1 bring_pillow neighbor
- `0x1002eec4` GoTo topleft_deckchair
- `0x1002ef03` Action topleft_deckchair.give
- `0x1002efd7` Icon 1 get_pillow neighbor
- `0x1002f012` GoTo topright_pillows
- `0x1002f03f` Action topright_pillows.take.0.0
- `0x1002f0b9` Icon mother neighbor
- `0x1002f0f1` GoTo topleft_deckchair
- `0x1002f359` If tricked fifi_manip

## in_b1 (Level207)

- `0x10013d8c` If tricked bar_bar_whiskey
- `0x10013e07` Action bar_keeper.drink.0.0
- `0x10013fe0` Action tongue.0.1.tongue
- `0x100140f7` Icon 16 pool
- `0x1001422e` Icon deckchair
- `0x10014328` GoTo pool_deckchair
- `0x100144c5` Icon awake pool_deckchair deckchair
- `0x10014574` Icon 268517856 240 pool_deckchair m_hurt_n
- `0x10014914` Icon 1 beachleft_mat beachleft_mat_guarded m_hurt_n
- `0x10014968` Icon o_hurt_n neighbor
- `0x10014d91` Icon 24 24
- `0x10014de2` If variant beachleft_mat_hedgehog of beachleft_mat
- `0x10014e13` GoTo ?
- `0x10014e7a` Action beachleft_mat_hedgehog.laydown.beachleft_mat_hedgehog
- `0x10014ec9` Action hurt_low
- `0x10014f0c` Shout ?
- `0x10014f43` Set 6
- `0x10014f8a` Action beachleft_mat_hedgehog.repair
- `0x1001518a` Icon 268519356 120 beachleft_mat_guarded o_hurt_n
- `0x100152db` Shout n_lift
- `0x1001542f` If variant 6 of beachleft_sandcastle_destroyed
- `0x10015498` Icon beachleft_sandcastle_destroyed sandcastle
- `0x100154d8` GoTo ?
- `0x10015517` Action neighbor.lookaround
- `0x1001558a` Action splash.beachleft_sandcastle
- `0x10015601` If tricked beachleft_mat_hedgehog
- `0x100156ba` Action splash_crayfish_hedgehog.6.262144
- `0x100157b4` Action beachleft_sandcastle_destroyed.fall.beachleft_mat_hedgehog.beachleft_mat
- `0x10015817` Action splash_crayfish
- `0x100158a4` Shout 2
- `0x100158ea` Set 6
- `0x100159bd` Shout 0
- `0x10015b01` Icon 20 shell
- `0x10015b52` If variant beachright_mat_guarded of beachright_mat
- `0x10015b85` GoTo ?
- `0x10015bce` If variant beachright_shell_crayfish of beachright_shell
- `0x10015ca8` Action shell.shell.beachright_shell
- `0x10015d64` Action shell_crayfish.6.shell_crayfish.262144
- `0x10016040` Icon elephant
- `0x10016080` GoTo bar_elefant
- `0x10016107` Action neighbor.lookaround.bar_elefant
- `0x1001614a` If tricked bar_bucket_water
- `0x1001617b` Action bar_elefant.spit_at_neighbor_1
- `0x10016208` Action bar_elefant.spit_at_neighbor_2.bar_bucket_water.hide
- `0x1001638a` Shout 269350356
- `0x100163d0` Set 6
- `0x10016479` Action bar_elefant.spit_at_elefant
- `0x10016539` Icon ?
- `0x10016577` GoTo bar_keeper
- `0x100165a1` If tricked bar_bar_whiskey
- `0x100165ce` Action bar_keeper.order_drink_drunken
- `0x100165f9` Action bar_keeper.order_drink
- `0x100166a2` Icon divingboard
- `0x100166e2` GoTo pool_divingboard_spring
- `0x10016728` Action pool_divingboard_spring.repair
- `0x10016883` Icon 2 pool pool_spring divingboard
- `0x100168c3` GoTo pool_divingboard_spring
- `0x10016909` Action pool_divingboard_spring.repair
- `0x10016a10` Icon 2 pool_divingboard pool_divingboard_spring divingboard
- `0x10016a6c` If variant pool_divingboard_spring of pool_divingboard
- `0x10016a9d` GoTo ?
- `0x10016b8a` Action dive.pool_deckchair.mother
- `0x10016bfb` If variant pool_divingboard_spring of pool_awning_pole
- `0x10016e66` Action crash.nohandle.pool_awning_handle.fall
- `0x10016fea` Shout 269350348
- `0x10017030` Set 6
- `0x10017237` Icon wait m_hurt_n
- `0x10017281` Shout 0
- `0x100174fc` If variant 20 of beachright_mat_guarded
- `0x10017531` GoTo ?
- `0x1001763d` GoTo beachleft_sandcastle_destroyed
- `0x1001766e` Action beachleft_sandcastle_destroyed.n_lift.0.0
- `0x10017a20` Action beachright_mat_guarded.wakeup.beachright_mat_guarded
- `0x10017cb1` If tricked beachleft_poolvalve_help

## in_c1 (Level208)

- `0x1001c10b` If tricked elephant_elephant_gone
- `0x1001c12c` If tricked elephant_line
- `0x1001c162` If tricked elephant_elephant
- `0x1001c183` If tricked elephant_line
- `0x1001c23b` If variant elephant_line of elephant_elephant_gone
- `0x1001c3d1` Action elephant_elephant.return.elephant_elephant.elephant
- `0x1001c48d` Action elephant_elephant_line.return.elephant_elephant_line
- `0x1001c567` If tricked bazar_rake_ground
- `0x1001c588` If tricked bazar_fifi_primary
- `0x1001c5f1` If tricked bazar_fifi_gone
- `0x1001c612` If tricked bazar_rake_primary
- `0x1001c798` If tricked bazar_fifi_gone
- `0x1001c949` GoTo bazar_hideout
- `0x1001cb12` GoTo bazar_shop
- `0x1001ccc1` Icon 16 neighbor
- `0x1001cd15` If variant bazar_fifi_gone of bazar_fifi_secondary
- `0x1001cd47` GoTo ?
- `0x1001cf0f` Icon neighbor
- `0x1001cf4f` GoTo bazar_fifi_gone
- `0x1001cfb5` Action mother.order_left.neighbor.bazar_blades
- `0x1001d07b` Icon wait fifi
- `0x1001d0ce` If variant bazar_fifi_gone of bazar_fifi_secondary
- `0x1001d101` GoTo ?
- `0x1001d154` Action mother.callneighbor.bazar_fifi_gone
- `0x1001d1fa` Icon dressingroom
- `0x1001d238` GoTo bazar_dressing_room
- `0x1001d37f` Icon 16 stealmoney
- `0x1001d3d0` If variant altar_statue_snake of altar_statue
- `0x1001d403` GoTo ?
- `0x1001d449` Action neighbor.lookaround
- `0x1001d495` Action take
- `0x1001d559` Shout altar_statue_snake
- `0x1001d59f` Set 6
- `0x1001d655` Action elephant_tap_electricity.electrify
- `0x1001d69d` Shout ?
- `0x1001d6e3` Set 6
- `0x1001d76a` Action elephant_tap_electricity.repair.elephant_tap
- `0x1001d873` Icon 1 elephant_tap elephant_tap_electricity mother
- `0x1001d8a5` If tricked bazar_rake_ground
- `0x1001d8dd` GoTo bazar_rake_ground
- `0x1001d91c` Action bazar_rake_ground.crash
- `0x1001d95e` Shout ?
- `0x1001d9a4` Set 6
- `0x1001d9eb` Action bazar_rake_ground.repair
- `0x1001dab8` GoTo bazar_blades
- `0x1001db19` Icon fifi
- `0x1001db5e` GoTo bazar_fifi_gone
- `0x1001dbf7` Action bazar_fifi_secondary.bazar_fifi_secondary
- `0x1001dc85` Action bazar_fifi_secondary.repair.bazar_fifi_gone
- `0x1001e048` Icon 2 elephant
- `0x1001e09b` If variant elephant_elephant_line of elephant_elephant_gone
- `0x1001e0ce` GoTo ?
- `0x1001e13c` Action neighbor.lookaround.elephant_elephant_gone
- `0x1001e188` Action fool
- `0x1001e1f6` Shout elephant_elephant_line
- `0x1001e23c` Set 6
- `0x1001e280` Action repair
- `0x1001e3e7` Icon 1 elephant elephant_line fifi
- `0x1001e42a` GoTo bazar_hideout
- `0x1001e469` Action fifi.take3
- `0x1001e64f` Icon electrify call order shoecleaner
- `0x1001e6a0` If variant tadj_mahal_shoe_cleaner_blades of tadj_mahal_shoe_cleaner
- `0x1001e6d1` GoTo ?
- `0x1001e70d` Action ?
- `0x1001e777` Shout tadj_mahal_shoe_cleaner_blades
- `0x1001e7bd` Set 6
- `0x1001e804` Action tadj_mahal_shoe_cleaner_blades.repair
- `0x1001e91d` Icon 1 tadj_mahal_shoe_cleaner tadj_mahal_shoe_cleaner_blades platform
- `0x1001e94f` If tricked amusement_fakir_balloon
- `0x1001ea07` Action amusement_fakir.stop.amusement_fakir.amusement_fakir
- `0x1001eaa4` Icon platform
- `0x1001eaf5` If variant amusement_fakir_balloon of amusement_fakir
- `0x1001eb5a` Action amusement_platform.crash.amusement_fakir_balloon
- `0x1001ebc3` If variant amusement_seesaw_shovel of amusement_seesaw
- `0x1001ebee` Action crash
- `0x1001ec55` Shout amusement_seesaw
- `0x1001ec9b` Set 6
- `0x1001eccb` Shout 3
- `0x1001ed11` Set 6
- `0x1001ed55` Action repair
- `0x1001eec1` Icon 268560597 60 amusement_platform platform
- `0x1001eeff` GoTo amusement_platform
- `0x1001ef48` If variant amusement_fakir_balloon of amusement_fakir
- `0x1001efac` Action play

## in_c2 (Level209)

- `0x1001f12a` If variant 20 of holy_cow_cow_open
- `0x1001f19a` Action holy_cow_crap.crap
- `0x1001f259` If variant holy_cow_cow_open of holy_cow_cow
- `0x1001f2e9` Action standup.holy_cow_cow
- `0x1001f5ac` Icon 16 dressingroom
- `0x1001f5ea` GoTo bazar_dressing_room
- `0x1001f771` Icon fakirshop
- `0x1001f7af` GoTo bazar_shop
- `0x1001f7dc` Action bazar_shop.0.1
- `0x1001f910` Icon 16
- `0x1001f961` If variant holy_cow_cow_open of holy_cow_cow
- `0x1001f992` GoTo ?
- `0x1001f9d1` Action neighbor.lookaround
- `0x1001fa1d` Action ride
- `0x1001fa88` Shout holy_cow_cow_open
- `0x1001face` Set 6
- `0x1001fb12` Action repair
- `0x1001fea1` Icon 2
- `0x1001fef2` If variant bazar_icecream_machine_dirt of bazar_icecream_machine
- `0x1001ff23` GoTo ?
- `0x1001ff5f` Action take
- `0x1001ffc9` Shout bazar_icecream_machine_dirt
- `0x1002000f` Set 2
- `0x10020053` Action repair
- `0x1002016f` Icon 1 bazar_icecream_machine bazar_icecream_machine_dirt coals
- `0x100201c0` If variant coal_area_hot_coal of coal_area_coal
- `0x10020203` If variant coal_area_trough_fuel of coal_area_trough
- `0x10020234` GoTo ?
- `0x10020313` Action walk_fuel.walk.walk_hot.coal_area_hot_coal
- `0x10020463` Action walk.walk
- `0x1002058b` Shout 2
- `0x100205d1` Set 6
- `0x1002066c` Action coal_area_trough_fuel.repair.coal_area_coal.1
- `0x100206e7` Shout 1
- `0x1002072d` Set 6
- `0x10020851` Icon 1 coal_area_coal slippers
- `0x100208cb` If tricked tadj_mahal_shoe_mat
- `0x10020944` Action tadj_mahal_shoe_mat_empty.take.tadj_mahal_shoe_mat_empty.tadj_mahal
- `0x1002099c` If variant tadj_mahal_gully_open of tadj_mahal_gully
- `0x100209fc` Action tadj_mahal_shoe_mat_coal.burn.tadj_mahal_shoe_mat_empty.tadj_mahal
- `0x10020a48` Action jump
- `0x10020aee` Shout tadj_mahal_shoe_mat_coal
- `0x10020b0e` Shout ?
- `0x10020b54` Set 6
- `0x10020c0e` Icon tadj_mahal
- `0x10020cbd` Icon 268568582 120 tadj_mahal_curtain tadj_mahal
- `0x10020cfb` GoTo tadj_mahal_shoe_mat_empty
- `0x10020d8d` Action tadj_mahal_shoe_mat.tadj_mahal_shoe_mat.tadj_mahal
- `0x10020e89` Icon tadj_mahal_curtain fakir
- `0x10020eda` If variant fire_fakir_groove_fuel of fire_fakir_groove
- `0x10020f0b` GoTo ?
- `0x10020f3a` Action fire_fakir_fakir.spit
- `0x10020ff8` Action fire_fakir_groove_fuel.burn.fire_fakir_groove_fuel.fire_fakir_fakir
- `0x1002103a` Shout ?
- `0x10021080` Set 6
- `0x100210c7` Action fire_fakir_groove_fuel.repair
- `0x1002116f` Action fire_fakir_groove.burn.fire_fakir_groove_fuel.fire_fakir_groove

## in_b2 (Level210)

- `0x10017ddf` Action beachleft_poolvalve_help.flush.pool_pool_empty.pool
- `0x10017fbf` GoTo neighbor
- `0x1001800a` If tricked help
- `0x100182ce` GoTo bar_elefant
- `0x10018301` If tricked bar_bat
- `0x10018356` Action bar_elefant.dogattack_bat.bar_bat.disappear
- `0x100183e4` Action fifi.fall.bar_bat
- `0x1001843e` Action bar_elefant.dogattack
- `0x100186cd` Icon pool_deckchair 0 4 neighbor
- `0x1001870b` GoTo pool_deckchair
- `0x10018783` Action order.neighbor.pool_deckchair
- `0x1001881b` Icon ?
- `0x100189cb` GoTo pool_deckchair
- `0x10018aba` Icon neighbor beachleft_deckchair_guarded 4 neighbor
- `0x10018b5f` Action callneighbor
- `0x10018c56` Icon deckchair
- `0x10018d21` Icon 268536195 240 pool_deckchair pool_deckchair
- `0x10018dbe` Icon pool_deckchair 1 4 m_hurt_n
- `0x10018fdf` Action wakeup.4.beachleft_deckchair_guarded
- `0x100190ae` GoTo beachleft_deckchair_guarded
- `0x10019169` Icon beachleft_deckchair_guarded mother
- `0x1001921b` If tricked beachleft_deckchair_guarded
- `0x1001929a` GoTo pool_deckchair
- `0x100192ef` Icon m_hurt_n
- `0x100195e7` Icon 2
- `0x10019693` Icon 268537674 120 beachleft_deckchair_guarded deckchair
- `0x100196e4` If variant beachleft_deckchair_hedgehog of beachleft_deckchair
- `0x10019717` GoTo ?
- `0x10019820` If tricked beachleft_pole_damaged
- `0x1001984e` Action electrify
- `0x100198d0` Set 6
- `0x1001990e` Shout 1
- `0x10019971` Set 6
- `0x100199ae` Shout ?
- `0x10019a5b` Action repair.beachleft_deckchair_hedgehog
- `0x10019b6b` Icon 2 beachleft_deckchair fifi
- `0x10019bbc` If variant pool_divingboard_oil of pool_divingboard
- `0x10019bed` GoTo ?
- `0x10019c85` Action pool_fifi_sleep.pool_fifi_sleep.pool_dogbasket
- `0x10019cb9` If tricked pool_bone
- `0x10019e29` Icon fifi
- `0x10019e67` GoTo bar_elefant
- `0x10019eec` If tricked help
- `0x10019f48` Action fifi.take1
- `0x1001a09d` Icon help elephant
- `0x1001a0e2` GoTo bar_elefant
- `0x1001a216` Action fifi.put1.fifi
- `0x1001a259` If tricked bar_bat
- `0x1001a2e5` Action neighbor.fifi_bat.4
- `0x1001a3c2` Icon 1 262144 m_hurt_n
- `0x1001a40c` Shout 0
- `0x1001a50c` Icon 4 turban
- `0x1001a55f` If variant beachright_turbanshop_hedgehog of beachright_turbanshop_octopus
- `0x1001a5d1` GoTo ?
- `0x1001a702` Action fifi.put3.fifi
- `0x1001a74e` Action try_turban
- `0x1001a7b9` Shout beachright_turbanshop_octopus
- `0x1001a7ff` Set 6
- `0x1001a843` Action repair
- `0x1001a8e2` Shout 1
- `0x1001a928` Set 6
- `0x1001a9c3` Action fifi.take3.beachright_turbanshop.1
- `0x1001ab13` Icon 20 fifi
- `0x1001ab64` If variant pool_fifi_bone of pool_fifi_sleep
- `0x1001ab95` GoTo ?
- `0x1001aca1` Action take.269350848.pool_fifi_sleep.pool_bone
- `0x1001ad8f` Icon fifi
- `0x1001adcf` GoTo pool_fifi_bone
- `0x1001ae0e` Action pool_fifi_bone.take_bone
- `0x1001af1a` Icon 2 pool_fifi_sleep pool_fifi_bone fifi
- `0x1001af6b` If variant pool_fifi_bone of pool_fifi_sleep
- `0x1001af9c` GoTo ?
- `0x1001afe2` Action tickle
- `0x1001b073` If variant pool_fifi_bone of pool_divingboard_oil
- `0x1001b0e2` If variant pool_divingboard_oil of pool_pool_empty
- `0x1001b17a` Action fall_empty.pool_pool_empty.8.1
- `0x1001b27c` Shout 8
- `0x1001b2d2` Action fall_water
- `0x1001b3d4` Shout 8
- `0x1001b438` Action fall
- `0x1001b47e` Set 6
- `0x1001b613` If tricked beachleft_bra
- `0x1001b69e` Action beachleft_shower_guarded.takebra.beachleft_bra_guarded.beachleft
- `0x1001b943` Action beachleft_shower_guarded.putbra.beachleft_bra_guarded.beachleft
- `0x1001ba8c` If variant 120 of beachleft_shower_guarded
- `0x1001bac1` GoTo ?
- `0x1001bc51` If tricked beachleft_mat_olga_guarded
- `0x1001bd44` If variant beachleft_mat_olga of beachleft_mat_olga_guarded
- `0x1001bd78` GoTo ?
- `0x1001bf4e` If tricked bazar_snake

## ship3 (Level211)

- `0x1002f37a` If tricked topright_handbag
- `0x1002f3e3` If tricked fifi
- `0x1002f412` Room topright woody
- `0x1002f5b6` GoTo 16
- `0x1002f5e3` Action shout.0.0
- `0x1002f884` GoTo topright_deckchair
- `0x1002f9b4` Icon 16 diving neighbor
- `0x1002f9fd` If variant bottomright_diving_manip of bottomright_diving
- `0x1002fa2e` GoTo ?
- `0x1002fa81` Action bottomright_diving.bottomright_diving
- `0x1002fafc` Action bottomright_diving_manip
- `0x1002fb3f` Shout 1
- `0x1002fb85` Set 2
- `0x1002fbd4` Action bottomright_diving_manip.repair
- `0x1002fcf9` Icon bottomright_diving bottomright_diving_manip phone neighbor
- `0x1002fd33` GoTo cabin_phone
- `0x1002fd66` If tricked kid_manip
- `0x1002fd93` Action cabin_phone.crash
- `0x1002fdd6` Shout 1
- `0x1002fdfe` Action cabin_phone
- `0x1002fe40` Shout ?
- `0x1002fee3` Set 3 topleft_phone topleft_phone_manip 2
- `0x10030293` Icon ring cabin_phone lifevest neighbor
- `0x100302dc` If variant bottomleft_lifevest_manip of bottomleft_lifevest
- `0x1003030d` GoTo ?
- `0x10030360` Action bottomleft_lifevest.bottomleft_lifevest
- `0x100303db` Action bottomleft_lifevest_manip
- `0x1003041e` Shout 1
- `0x10030464` Set 2
- `0x100304b3` Action bottomleft_lifevest_manip.repair
- `0x1003071d` If tricked bottomleft_boat_gone
- `0x10030752` Icon boat neighbor
- `0x1003079b` If variant bottomleft_boat_manip of bottomleft_boat
- `0x100307cc` GoTo ?
- `0x100309cd` Icon bottomleft_boat_gone bottomleft_boat_manip fishing neighbor
- `0x10030a16` If variant topleft_rod_manip of topleft_rod
- `0x10030a47` GoTo ?
- `0x10030a9a` Action topleft_rod.topleft_rod
- `0x10030bd6` Icon 1 2 toilet neighbor
- `0x10030c0a` GoTo topleft_wcsign_manip
- `0x10030c4c` Action topleft_wcsign_manip.repair.0.0
- `0x10030d49` Icon topleft_wcsign topleft_wcsign_manip o_hurt_n neighbor
- `0x10030dfd` Icon 1 2 toilet neighbor
- `0x10030e2b` If tricked topleft_wcsign_manip
- `0x10030e70` GoTo 269353656
- `0x10030ed7` Action topleft_wcleft.puke.topleft_wcleft
- `0x10030f1a` Shout 1
- `0x100310f3` Icon fear neighbor candy neighbor
- `0x10031134` If variant topleft_dish_manip of topleft_dish
- `0x10031165` GoTo ?
- `0x100311b8` Action topleft_dish.topleft_dish
- `0x1003127e` Action topleft_dish_manip.2
- `0x100315d8` GoTo topleft_wcright
- `0x1003161a` Action topleft_wcright.enter.0.0
- `0x100316c5` GoTo ?
- `0x100317b6` GoTo topleft_reling
- `0x100317e3` Action topleft_reling.look.0.1
- `0x10031919` Action topleft_wcright.puke.268637824
- `0x10031a2f` Action topleft_wcright.leave.bonbons.goup
- `0x10031b5d` Icon 16 o_hurt_n neighbor
- `0x10031ba1` Icon gong neighbor
- `0x10031e57` Icon 2 gong neighbor
- `0x10031e9a` If variant wallleft_gong_manip of wallleft_gong
- `0x10031fbe` Action 6.wallleft_gong_manip.wallleft_elvis
- `0x10032084` Icon headbanding neighbor
- `0x100320c7` If variant groundleft_headbanging_manip of groundleft_headbanging
- `0x100320fb` GoTo ?
- `0x10032137` Action ?
- `0x100321a2` Shout groundleft_headbanging_manip
- `0x100321e8` Set 6
- `0x1003222c` Action repair
- `0x10032334` Icon 1 groundleft_headbanging rickshaw neighbor
- `0x10032377` If variant groundleft_rickshaw_manip of groundleft_rickshaw
- `0x100323aa` GoTo ?
- `0x100323d6` Action ?
- `0x10032544` Icon 6 rickshaw neighbor
- `0x10032579` GoTo groundleft_rickshaw_manip
- `0x100325b8` Action groundleft_rickshaw_manip.repair
- `0x100326b1` Icon groundleft_rickshaw groundleft_rickshaw_manip jade neighbor
- `0x100326f4` If variant groundright_jade_manip of groundright_jade
- `0x10032737` If variant groundright_vase_manip of groundright_vase
- `0x1003276b` GoTo ?
- `0x100327f3` Action groundright_jadedummy.look.look.groundright_jade
- `0x100328b6` Action crash_long.crash_long.groundright_vase_manip
- `0x100328f9` Shout 2
- `0x10032940` Action crash.crash
- `0x10032982` Shout ?
- `0x100329c8` Set 6
- `0x10032a0c` Action repair
- `0x10032ba9` Icon 2 groundright_vase rickshaw neighbor
- `0x10032be6` Shout 0
- `0x10032cc1` Icon 6 hotdog neighbor
- `0x10032d04` If variant wallright_hotdogshop_manip of wallright_hotdogshop
- `0x10032d38` GoTo ?
- `0x10032d77` Action neighbor.lookaround
- `0x10032dc3` Action ?
- `0x10032e2e` Shout wallright_hotdogshop_manip
- `0x10032e74` Set 6
- `0x10032f8c` Icon 1 wallright_hotdogshop gong neighbor
- `0x10032fcf` If variant wallleft_gong_manip of wallleft_gong
- `0x10033065` Shout wallleft_gong_manip
- `0x100330ec` Action repair.6
- `0x10033362` If variant 20 of groundleft_rickshaw_manip
- `0x10033711` Icon 16 bike neighbor

## me_c1 (Level212)

- `0x10034c3b` If tricked topright_throne_half
- `0x10034c60` If tricked topright_throne_half_2
- `0x10034c85` If tricked topright_throne_full
- `0x10034caa` If tricked topright_throne_half_right
- `0x10034ccb` If tricked topright_wheel
- `0x10034d2c` If tricked topright_wheel_turning
- `0x10034e34` If tricked bottomright_parrot_manip
- `0x10034e5b` If tricked bottomright_parrot_shit
- `0x10034e9c` Action bottomright_parrot_manip
- `0x10035081` Icon whip mother
- `0x100350b2` GoTo midright_statue_hideout
- `0x100350df` Action midright_statue_hideout.0.1
- `0x10035241` Icon bull mother
- `0x10035272` GoTo midleft_red_bull
- `0x1003529f` Action midleft_red_bull.0.1
- `0x100353c2` Icon 16 cliff neighbor
- `0x100353f5` GoTo bottomright_cliff
- `0x1003543e` If variant bottomright_parrot_manip of bottomright_parrot
- `0x10035534` Action bottomright_cliff.enter.neighbor.5
- `0x10035577` If tricked bottomright_parrot_shit
- `0x10035597` If tricked bottomright_boat
- `0x100355c8` Action bottomright_parrot_shit.crash
- `0x100355ed` Action bottomright_cliff
- `0x1003570d` Action bottomright_boat.crash.269354160.bottomright_parrot
- `0x10035732` Action bottomright_water
- `0x10035883` Shout 3
- `0x100358c9` Set 2
- `0x10035a4a` Shout 5
- `0x10035cc7` Icon 2 bullride neighbor
- `0x10035d0a` If variant bottomleft_bullride_manip of bottomleft_bullride
- `0x10035d3e` GoTo ?
- `0x10035d7a` Action ?
- `0x10035de5` If tricked bottomleft_coins
- `0x10035e87` Shout bottomleft
- `0x10035ecd` Set 6
- `0x10035f11` Action repair
- `0x10036038` If variant bottomleft_bullride of midleft_bank_manip
- `0x10036094` GoTo midleft_bank_manip
- `0x10036170` Icon 1 midleft_bank neighbor
- `0x1003619b` If tricked midleft_bank_manip
- `0x10036277` Action midleft_red_bull.crash.midleft_red_bull.wakeup
- `0x100362bd` Shout 1
- `0x10036303` Set 6
- `0x100364c0` If variant midleft_red_bull of midleft_bank_manip
- `0x100364f4` GoTo ?
- `0x10036515` Icon neighbor
- `0x1003656f` Icon 268656954 60 bank neighbor
- `0x100365d0` Icon cigars neighbor
- `0x10036613` If variant midleft_cigars_manip of midleft_cigars
- `0x10036647` GoTo ?
- `0x10036683` Action ?
- `0x100366ed` Shout midleft_cigars_manip
- `0x10036733` Set 6
- `0x10036834` Icon 1 midleft_cigars whip neighbor
- `0x10036877` If variant midright_whip_manip of midright_whip
- `0x100368ab` GoTo ?
- `0x10036906` If tricked midright_spikes_open
- `0x10036934` Action crash
- `0x10036977` Shout 2
- `0x100369bd` Set 6
- `0x100369e8` Action ?
- `0x10036a2a` Shout ?
- `0x10036a70` Set 6
- `0x10036ab7` Action midright_whip_manip.repair
- `0x10036b38` Action midright_whip_manip.midright_whip.2
- `0x10036bec` Icon throne neighbor
- `0x10036c1f` GoTo topright_hands
- `0x10036c42` If tricked topright_throne_half
- `0x10036c62` If tricked topright_throne_half_2
- `0x10036c82` If tricked topright_throne_half_right
- `0x10036c9d` If tricked topright_throne_full
- `0x10036cd8` Action neighbor.lookaround
- `0x10036d42` Action topright_hands
- `0x10036d87` Shout ?
- `0x10036dcd` Set 6
- `0x10036e14` Action topright_hands.repair
- `0x10036ee8` Action topright_hands.topright_ruby.topright
- `0x10036f18` Action topright_hands.miss
- `0x10036f5d` Shout ?
- `0x10036fa3` Set 6
- `0x10036fea` Action topright_hands.repair
- `0x1003732a` Icon 16 water mother

## me_c2 (Level213)

- `0x1003735b` GoTo bottomright_water
- `0x100374e0` Icon throne mother
- `0x10037511` GoTo topright_flowers
- `0x10037656` Icon 16 washingtub neighbor
- `0x10037687` GoTo midleft_washingtub_manip
- `0x10037a6c` Icon washingtub neighbor
- `0x10037aaf` If variant midleft_washingtub_manip of midleft_washingtub
- `0x10037ae3` GoTo ?
- `0x10037c0a` Icon 1 2 bullride_olga neighbor
- `0x10037c6b` Icon bullride_olga neighbor
- `0x10037c9c` GoTo bottomleft_bullride_controls_manip
- `0x10037d72` Icon bottomleft_bullride_controls bottomleft_bullride_controls_manip o_hurt_n neighbor
- `0x10037e20` Icon 0 2 bullride_olga neighbor
- `0x10037e63` If variant bottomleft_bullride_controls_manip of bottomleft_bullride_controls
- `0x10037e96` GoTo ?
- `0x100380d5` Icon bull pinata neighbor
- `0x1003812a` If variant bottomleft_pinata_manip of bottomleft_pinata
- `0x1003815d` GoTo ?
- `0x10038258` Icon 1 2 o_hurt_n neighbor
- `0x1003831e` Icon 1 2 picnic neighbor
- `0x10038339` If tricked bottomright_picnic
- `0x1003835c` If tricked bottomright_picnic_manip
- `0x100383af` If variant bottomright_picnic_manip of bottomright_picnic
- `0x100383e3` GoTo ?
- `0x100385de` Icon fear neighbor tortilla neighbor
- `0x10038627` If variant bottomright_tortilla_sharp_tequila of bottomright_tortilla_tequila
- `0x1003865c` GoTo ?
- `0x1003887b` Icon bottomright_tortilla_tequila 2 carnivore neighbor
- `0x100388bf` If variant topright_carnivore_bigmanip of topright_carnivore_big
- `0x100388f4` GoTo ?
- `0x10038a48` Icon 1 2 limberwall neighbor
- `0x10038a7b` GoTo midleft_limberwall
- `0x10038a9e` If tricked midleft_bull_manip
- `0x10038e4d` GoTo bottomright_water
- `0x100390bb` GoTo bottomleft_bullride_olga
- `0x10039102` If tricked bottomleft_bullride_controls_manip
- `0x10039221` If variant neighbor of 268669043
- `0x10039348` If variant bottomright_water2 of bottomright_water2
- `0x1003938a` GoTo ?

## ship4 (Level214)

- `0x100396aa` If variant neighbor of woody
- `0x10039a08` If tricked bridge_steering_captain
- `0x10039a56` If variant bridge_grog_guarded of bridge_grog_manip
- `0x10039caa` If tricked bridge_steering_captain
- `0x10039d56` If tricked bridge_steering_captain
- `0x10039d85` Action bridge_steering_captain.sleep.0.1
- `0x10039eb5` Icon 16 deckchair
- `0x10039f7c` Icon 0 awake topright_deckchair water
- `0x10039fba` GoTo bottomright_reling
- `0x10039fe7` Action bottomright_reling.0.1
- `0x1003a106` Icon deckchair
- `0x1003a144` GoTo topright_deckchair
- `0x1003a264` Icon 268672820 600 topright_deckchair m_hurt_n
- `0x1003a452` Icon 16 o_hurt_n
- `0x1003a4db` Icon m_hurt_n
- `0x1003a55e` Icon fishbox
- `0x1003a5b7` If variant bottomright_hatch_open_manip of bottomright_hatch_closed_manip
- `0x1003a5e8` GoTo ?
- `0x1003aade` Icon 2 pistol
- `0x1003ab2f` If variant bottomleft_pistol_manip of bottomleft_pistol
- `0x1003ab62` GoTo ?
- `0x1003ae3b` Icon wait pistol
- `0x1003ae79` GoTo bottomleft_pistol_manip
- `0x1003af61` Icon 1 bottomleft_pistol bottomleft_pistol_manip steering
- `0x1003afb5` If variant bridge_steering_captain of bridge_steering_manip
- `0x1003afe7` GoTo ?
- `0x1003b0fe` Icon bridge_steering_manip 2 6 pistol
- `0x1003b13c` GoTo bottomleft_pistol_ground
- `0x1003b204` Icon bottomleft_pistol_ground bottomleft_pistol_ground steering
- `0x1003b255` If variant topright_bridge of topright_door_closed
- `0x1003b288` GoTo ?
- `0x1003b371` Icon topright_door_closed m_hurt_n
- `0x1003b436` Icon 262144 0 4 bouquet
- `0x1003b487` If variant topleft_bouquet_manip of topleft_bouquet
- `0x1003b4cc` GoTo ?
- `0x1003b6c0` Icon olga o_hurt_n
- `0x1003b786` Icon 262144 1 6 shipshower
- `0x1003b7d9` If variant bottomleft_shipshower_guarded of bottomleft_shipshower
- `0x1003b80d` GoTo bottomleft_shipshower
- `0x1003b890` If tricked bottomleft_washbucket_manip
- `0x1003bad9` Icon bottomleft_washbucket o_hurt_n
- `0x1003bd37` If variant 20 of bottomleft_shipshower_guarded
- `0x1003bd68` GoTo ?
- `0x1003c1f5` If variant flowers of 2
- `0x1003c229` GoTo ?
- `0x1003c2e7` GoTo topleft_pillar
- `0x1003c323` Action wait.0.0
- `0x1003c430` Action wait.0.0.flowers
- `0x1003d1e1` Action 0.0.20
- `0x1003d41e` Icon hit_woody
- `0x1003df74` Icon sfx_verybig1.wav alarm
- `0x1003e078` Action search.1

## unattributed

- `0x100032eb` Action leave
- `0x10003754` Action enter
- `0x100043f4` Action 8
- `0x10004d51` Action failed
- `0x1000594b` Action decline
- `0x100063b8` Action respawn.0.0
- `0x10006558` Action 0.0.269359840.fear3
- `0x10006821` Action enter.4.1.320
- `0x10006a77` Action leave.1.269136360
- `0x1000711b` Action fight.fear3_loop.12.fear1_loop
- `0x1000a93a` Action decline.0.1.woody
- `0x1000b78b` Action open.8192
- `0x1000c092` Action surprise.32
- `0x1000c185` Action take.0.8.1
- `0x1000c2d6` Action give.0.declinetext.alreadyininv
- `0x1000c33b` Action surprise.0
- `0x1000d7e3` Action 11
- `0x1000e91c` Icon neighbor neighbor mother mother
- `0x1000e9b3` GoTo 1
- `0x1000ea71` GoTo ?
- `0x1000eb7b` Action fight.0.0
- `0x1000f001` Action 0
- `0x1000fb9b` If tricked ?
- `0x1000fbca` If tricked ?
- `0x1000fbed` If tricked ?
- `0x1000fc10` If tricked ?
- `0x1000ff0c` Shout ?
- `0x1000ff79` Set 
- `0x1001378c` Action start

