# The PC oracle: the original running under Wine, traced and driven

The PC originals (NFH1 game.exe, NFH2 game.exe + GameLogic.dll — the Steam
builds, byte-identical to the r2 dumps' binaries) run on this machine under
Wine on an Xvfb, and a gdb attached through Wine's own `winedbg --gdb`
proxy traces the game logic tick by tick and injects the player's inputs.
Every number the port's PC profile claims can then be checked against the
real thing without reading videos.

## Pieces

- `wdbg.py <nfh1|nfh2> <gdb python script> [timeout]` — the driver: Xvfb
  `:97` (800x600, the game fullscreen; windowed 1024x768 scaled the cursor
  x by 0.75 and rendered greyscale), `wineserver -p`, `winedbg --gdb
  --no-start --port 33333 <Z:\ path of game.exe>` (WDBG_CMD), the nix gdb
  (`gdb-result`, `nix-build '<nixpkgs>' -A gdb`) running the script, and
  `clicks.sh` alongside (WDBG_CLICKS: `x y wait` clicks in game
  coordinates, `key <name> wait`, `move x,y wait`, `sync 0 wait` — waits
  for the level's first tick, written by the script to
  `~/nfh-bench/wine/logs/level_started`). Hard cleanup at the end. The
  game dirs are `~/nfh-bench/wine/nfh2game` (bin + data; gamedata.bnd is a
  plain zip, repacked with `unlockall` on VK_KEY_U and `levelshot` on L in
  shortcuts.xml), the prefix `~/nfh-bench/wine/nfh`; `gameopts.py nfh2
  screen.fullscreen=true …` edits the UTF-16 gameoptions.xml in the
  prefix's Documents/JoWooD/NFH2 (loggamelogic=true keeps the game's own
  input log, below).
- `oracle.py` — the gdb script of a level run: breaks at game.exe's level
  session start (0x408014, `call fcn.00407456`) and overwrites the level
  name String ([[ebp+0xc]]+4 = {vtable, begin, end}; the names are all five
  characters: ship1 cn_b1 cn_c2 cn_c1 cn_b2 ship2 in_b1 in_c1 in_c2 in_b2
  ship3 me_c1 me_c2 ship4) with WDBG_LEVEL, so the menu walk is always
  title (300,300), START GAME (283,314), play (745,550); then hooks
  GameLogic.dll (relocated — its base from winedbg's `loads DLL` line):
  the level tick fcn.10044234 (12 a second, no slowdown measured: 12.06/s),
  the path finder fcn.1000a711 (its args[1] is the actor object: +4 name,
  +0x2c x, +0x30 y, +0x40 current animation — read every tick), GoTo
  fcn.1000e3e0, DoAction fcn.10002cd5 (object, action), icon fcn.100422a5
  (actor, icon), behaviour post fcn.1004000a, SHOUT fcn.1000f977; the
  String arguments are decoded on the stack and the calling step's return
  address kept. WDBG_SCRIPT is the input script (`port2script.py`, below);
  WDBG_SECS the trace length. Trace: `~/nfh-bench/wine/logs/oracle_<level>.jsonl`.
- Inputs: GameLogic is driven by messages (Loader.dll's MsgList; the
  game's own log of them is GameLogicLog00.xml in the prefix's Documents
  folder when loggamelogic is on: `<level seed=>`, the setup, `<time
  value=N/>` per tick, the player's `GoToPosMsg room= position="x/0"`,
  `UseObjectMsg name=`, `CombineMsg object= object2=`). The level update's
  loop pops each message at GL 0x10044464 ([ebp-0x14]); `oracle.py` sends
  a dummy floor click (xdotool at WDBG_DUMMY) a tick before a scripted
  input and replaces the dummy's GoToPosMsg there by a message built in
  scratch memory (VirtualAlloc through game.exe's import slot 0x452108 —
  gdb inferior calls work through the proxy): UseObjectMsg (vtable
  0x453b2c: +4 name, +8 text, refcount +0x10), CombineMsg (0x453b20: +4
  object, +8 object2, +0xc text, refcount +0x1c), GoToPosMsg (0x453b38: +4
  room, +0xc x, +0x10 y, refcount +0x18); the Strings are {vtable, begin,
  end, +0xc, refcount +0x10} cloned from a live one, refcounts preset to
  0x1000 (the game's release deletes at zero). The tick the game took each
  message at is in its own log.
- Minigames: a combination with `game=` (combine.xml; 9 of them on the PC —
  minigame/*.xml) runs the object's game action (the crayfish's `reed`,
  time 360) while GameLogic's own minigame object scores the player's
  thumb each tick (fcn.100508a1: its distance from the wobbling field's
  middle in a 1000-unit radius — 4 within 200, 3 / 2 / 1 farther, a
  penalty beyond; [this+0x18]) and accumulates it (fcn.10001b2c,
  [this+0x28]) into the progress [this+0x1c] (fcn.100507dd); the action's
  update reads it (fcn.100507f0, 100 = won, 0x10004c63) and plays `failed`
  at the end otherwise. WDBG_MINIGAME=perfect (the default) writes the 4
  at the scoring's join 0x10050a1a: a perfect player, the game's length a
  property of the data; `100` writes 100 before every read from the
  WDBG_MINIGAME_TICKS-th (36) on. Either way the item is taken by the
  combination itself (the port's `take` after its `unlock` is no PC input,
  oracle2plan.py adds it). Unplayed, the crayfish's game ran 208 ticks to
  `failed`, not the action's 360.
- `port2script.py <level> <run dir>` — the port's clicks.json (frames at 60
  a second) as the oracle's script: an item click = UseObjectMsg on the
  item's PC object (the overlay's PCApproach Woody `obj`), with an
  inventory type = CombineMsg (IT2_X -> x), a floor click = GoToPosMsg in
  the zone's PC room at pc_room_x; a take after an unlock stays a plain
  use; one message a tick.
- `oracle.py` with WDBG_PLAN=<port plan> WDBG_LEVELNUM=<n> runs the port's
  plan itself (`planrun.sh <n> <level> <secs> <tag>` wraps it; pcmap.py maps
  the legs: the item's PC object, a combination's target and minigame from
  combine.xml, a trick item's bare `use`, the neighbour's station object,
  the zone's room — the guarded / container / ground variants of a name
  are one family); the conditions are read off the trace: a take / use /
  usewith waits for Woody standing (ms0-3, or the `smile` he keeps after a
  trick's action until the next command), injects, and is done when an
  action on the object's family has run and he stands again (or declined:
  `woody decline`); park waits for his arrival in the zone's room (x range
  and floor); whenusing X for the neighbour's next action on X's station;
  await for a record paid since the item's trick; wait / until for the
  clock; a leg times out at 120 s; a take right after the item's unlock is
  done if the unlock's take happened (the PC's combination takes the item);
  `walk x y` goes to the point's zone on its PC room (pcgeo.py: the port's
  loader and overlay give the zones' walking limits, runtime/world.py
  pc_room_x the x); `usewith Ground@Zone IT_X [x=]` is a floor trick (the
  CombineMsg of the zone's room object with the item at the drop's x);
  (NFH1's GUI, game.exe fcn.004077a0 @ 0x407ae6 — a floor hit with an
  item in hand: the message carries the item at +4, the room's name at
  +8 and the click's x/y at +0x10/+0x14; the room at +4 was declined,
  the `house` background object there crashed the game, as does any
  combine on an object not placed yet — a variant before its trick);
  `whenin Role Zone` waits for the pawn in the zone's room; `activated X`
  is three seconds (the PC has no inactive objects); a tool-less `unlock`
  is the GUI's own click on a `game` object — a CombineMsg with a NULL
  second object (game.exe fcn.00408161 @ 0x40828a), which starts the
  minigame (a UseObjectMsg of the object only walks him there, one of its
  `_container` crashes GameLogic); an item's PC inventory name comes
  from combine.xml's ingredient on the object's family (IT_Wcpaper is
  level_mail's `toiletpaper`). The gate: a take / use / usewith / park /
  walk waits until no catcher stands in the target's room, none walks
  (mg*/mr*) and none is in a door pass (no state) — the port's gate reads
  its routine's ETAs instead (tests/run_tricks.py gate_open); a leg the
  plan marks `!` runs ungated, as the port runs it. WDBG_USETEXT sets the
  UseObjectMsg's text field (a probe; the GUI's own is the action's label
  or NULL for flag-2 objects — the game ignores it on takes and uses).
  Batches: `planbatch.sh <secs> <levels>` (S2) and `s1plan.sh <secs>
  <levels>` (S1) take TAG=<tag> for the runs' file names (default
  planrun) — never edit a running .sh (sh reads it incrementally: the
  TAG edit broke both running batches with a syntax error).
  The legs' outcomes go to `oracle_<level>_legs.json`, the catches
  (`woody fight` / `respawn`) are printed; the game's own log (a new
  GameLogicLogNN.xml per session) then gives the port the same inputs by
  tick (`oracle2plan.py`, `replay.sh <n> <level> <tag>`: the plan, the
  port's run, the comparison). The replay plan now comes from the
  oracle's own trace (`oracle2plan.py <n> <trace.jsonl>`: the `injected`
  events' legs at their ticks, the `sneak` legs from their `leg`
  events) — NFH1 stops writing GameLogicLogNN.xml past 99 files in its
  Documents folder, and every copy after that was a stale session's
  (the gated 106-114 and the first nocatch copies all said level_piano);
  the game's log still serves as a check of what the game accepted.
- `cmp_run.py <trace> <run dir>` — the two sides on one clock: the PC's
  station actions, icon changes, posts, SHOUTs and inputs against the
  port's routine transitions, think icon, trick count and clicks.
- `cmp_pairs.py <trace> <run dir> [--segments=<secs>] [--role=Olga]` —
  the same, paired: the inputs (equal by construction), the bubble (the
  PC's icon changes against the port's think changes, matched by value in
  order), the stations (STATION_CLIPS: the PC action on a room/object
  family -> the port's clip), the records paid, the catches — each pair
  with the port minus the PC in seconds and a mean per kind; `--segments`
  adds the actor's animation changes on both sides (the port's sprite x is
  the mobile station's, not the PC hotspot the walk timing leaves from),
  the walks and stays as blocks, the station-to-station legs (the action
  starts: free of the stay / walk boundary — the PC's action starts two
  ticks after the arrival, the port's clip at once), and the visits (the
  neighbour's GoTo targets against the port's routine items, by the
  overlay's PCApproach — the lap's order, not its timing).
- `exit_ticks.py <trace> [role]` and `pc_depart_ticks.py <n> <trace>
  [--write]` — the ticks an actor stands between a station's last
  animation and its next walk's first move (the step dispatch: the next
  step the tick the action ends or the one after, the mover's first move
  two ticks after the GoTo), per station into the overlay's PCDepartTicks
  (per role) and PCStart `depart` (the level's start); a catch's fight is
  no exit. The stands are the PC's absolute ones and over-correct a level
  whose station seconds (the video-paired PCUseSeconds / PCClipSeconds)
  carry them already — 205's legs paired within a tick before any were
  written and ran 0.6 s per 100 s late after: `calib_depart.py <n> <trace>
  <port run without them> [--write | --strip]` settles them as the net
  ticks each leg lacks (the port's replay with NFH_NO_DEPART=1 against the
  trace, station action start to action start, the deficit written on the
  station the leg leaves; the port long -> 0; no paired leg -> 0), or
  strips every departure key of a level whose bubble drifts under 0.1 s
  per 100 s without them — `calib.sh <n> <tag>` runs the whole settlement
  (the replay without, the decision, the replay with, the pairing). The
  walks' targets are the actor's own `goto` records: the trace's `actor`
  records name the objects (the path finder's registration), and an older
  trace is attributed by the rooms the walks end in against the targets'
  (207's Olga polls her mat's GoTo every tick and out-voted the neighbour
  by coincidence before).
  `pc_clips_from_trace.py <n> <trace> [--write]` — a station's
  PCClipSeconds re-measured where its clips are the actor's own animations
  (202's sea), each from its animation's first tick to the next's, the
  last to the walk less the exit's ticks; a waited-on clip keeps its value.
- `idlebatch.sh <secs> <levels>` runs the levels' idle laps one after
  another (Woody at his start — the catches in 203-205 and 208 spoil the
  lap); `parkbatch.sh <secs> <levels>` the laps with Woody parked
  (~/nfh-bench/plans/park/LevelN.txt: the port's auto park zone, then a
  wait) as plan runs, each replayed by the port to the clock (UNTIL) and
  paired (runs/replayN_park/pairs.txt); `s1parkbatch.sh` the same on NFH1
  through `s1planrun.sh` (the menu walk, the NFH1 log). The port's safe
  zone is not the PC's on 204, 207-209 (the PC lap or the respawn puts him
  in the neighbour's room): WDBG_NOCATCH=1 stubs the mode-1 trigger
  predicate fcn.1003f573 (`xor eax, eax; ret 0x10` at the first tick —
  tools/pcref/pc_catch_s2.py) for an idle lap with Woody uncatchable. When
  the ticks stall six seconds the watchdog takes a screenshot
  (stall_<level>.xwd: Season 1's FAILED screen — a catch ends a Season 1
  level, Woody's `fear` is the catch; its idle laps park him in the hall's
  wardrobe (`use Wardrobe`, ~/nfh-bench/plans/park/Level1NN.txt) where the
  lap crosses the port's park zone). The port's
  state.jsonl cadence is NFH_STATE_EVERY (10 = 6 Hz; the replays 5 = 12 Hz).
- `cmp_idle.py` — the same for an idle lap (`runtime/record.py`,
  NFH_PROFILE=pc).
- `s1_smoke.py` / `s1_probe.py` (`S1SCRIPT=s1_probe.py s1smoke.sh <level
  folder> <secs> [clicks]`) — NFH1's game.exe under the same harness: the
  game logic is in game.exe (no GameLogic.dll; the same Loader.dll
  messages and GameLogicLog, off by default — `gameopts.py nfh1
  system.loggamelogic=true`). The level's name String is on the stack of
  the session start fcn.00406970 (word 13 — the menu's level button name:
  tutorial_1 for the first), patched there (in place when the lengths
  agree, else into VirtualAlloc'd scratch — the IAT slot 0x4dc0f8 — with
  the String's begin / end repointed); the per-object factory fcn.00439fe0
  then compares it with the level class names (fcn.00413840 at 0x43a2da:
  `level_peep` ...). The level tick is the GameLogic update's call of the
  level update, 0x43b2f5 -> fcn.00439cd0 (12.1 a second measured); the
  update's message loop pops each input message and has it accepted by
  the logger (0x43b18d) and the handler (0x43b1a3 / 0x43b1bd: `call
  [edx+8]`, ecx = the message) — GoToPosMsg vtable 0x4e79fc (+4 room, +0xc
  x, +0x10 y, +0x18 refcount). The script calls take their Strings on the
  stack as GameLogic.dll's: DoAction fcn.00477f60 ([esp+8] object, [esp+0xc]
  action), SetIcon fcn.00437f70 ([esp+4] icon, ecx the actor object); the
  mover's update is fcn.0047cb50 (ecx = the mover: +0xc / +0x10 the
  target). The menu walk: the title (400,300), START GAME (414,313),
  tutorial_1 (65,116), play (750,555) — NFH1 runs 800x600 fullscreen by
  default. A catch stops the level ticks (the cutscene): a probe's floor
  clicks keep Woody out of the neighbour's room.
- A second instance: WDBG_DISPLAY=:96 WDBG_PORT=33334
  WDBG_PREFIX=~/nfh-bench/wine/nfh1pfx WDBG_LOGS=~/nfh-bench/wine/logs1
  (`wineboot -u` makes the prefix; the game's first start writes its
  gameoptions.xml) runs beside the first — `idlebatch.sh <secs> <levels>`
  runs the idle laps of Season 2 levels one after another on the first.
- `trace_*.py`, `inject*.py`, `test_call.py`, `smoke_gdb.py` — the
  experiments the above grew from (kept for their hook recipes).

## What was found on the way

frida cannot do this on Wine (the 32-bit helper segfaults inspecting the
process, the gadget crashes inside it); native gdb on the process blocks
Wine's start (wineserver uses ptrace itself); `winedbg --gdb` is the way.
`LOADING DATA` takes the level's setup messages through the loop, so the
message hooks are armed at the first tick, not before; winedbg's proxy
garbles a memory write past 32 bytes (16 a packet, read back); xdotool's
instant click falls between two of the game's 12 Hz mouse polls every
other time (the button is held 0.2 s); a Windows path in WDBG_CMD is split
on blanks, not by shlex (the backslashes). The windowed mode's cursor
scaling and greyscale come from the 32-bit window on a 24-bit Xvfb;
fullscreen 800x600 is clean. The game's own replay
(`createGameLogicFromLogFile`) exists but its trigger (the session's log
name, fcn.004037b6 case 4) was not found — the injection above replaces it.
Wine rewrites its processes' argv to the Windows paths, and once the
wineserver is gone `wineserver -k9` reaches none of them: wdbg.py's cleanup
kills every process whose environment names the prefix (475 of them had
piled up from the earlier runs, one game.exe spinning for three hours).
Woody is in the trace's `actors` from his first walk on (the path finder
hook): before it the plan runner takes him as standing. 201 (the
tutorial) runs fcn.10044234 once and then waits for the tutorial's own
inputs (the level clock runs, the actors stand): the idle and parked
batches skip it — its plan's `tutorial` legs are the port's scripted ones. The cleanup's
prefix match is the whole NUL-terminated variable: ~/nfh-bench/wine/nfh is
a prefix of the second instance's ~/nfh-bench/wine/nfh1pfx, and the first
instance's cleanup killed the second's run once. A dummy click that hits
no floor sends no message: the Tick hook re-clicks the next point of
WDBG_DUMMIES while a step stays pending.

## What the first plan run found (202, 2026-10-02)

The port's replay of the PC's inputs (replay202_planrun3): the inputs
within 0.25 s (the first click 1.0 s against the PC's 0.75); the bubble
0.9-1.0 s a lap earlier in the port, growing: mat -0.02, beer -0.08,
goswim -0.19, the sea's blank -0.66, bridge -0.86, the next mat -0.88 ...
the fifth mat -3.90 — by which the port's neighbour reaches the lap-5 mat
before Woody's crayfish is placed (the PC's placed it, then caught him at
318 s; the port's usewith failed and was retried). Lap 1 by segment (PC /
port): the mat's leave to the walk 0.83 / 1.33 s; the walk mat -> shore
4.59 / 3.65 (the PC walks down from the mat's hotspot, 27 px in 0.84 s,
then right, then down to the shore; the port right then down); WaitSea
5.83 / 5.64; EnterSea 3.17 / 3.15; SeeSub to LeaveSea 8.25 / 7.97; the
sea -> rail 16.16 / 16.10 (the port stands 3.3 s at the stairs' foot and
climbs faster: the same sum). The lap-1 drift is these: -0.5 at the shore,
-0.28 in the sea, -0.1 the rest.

- `station_positions.py <n> <trace>` — where the PC neighbour stands as
  each station's action starts (the mode over his visits) against the
  overlay's PCApproach x / px, px read against the floor line of the
  level.xml room that places the object (pc_walks_s2's frame; 203's
  melons stand in groundleft, its toilet up in wallleft); a deviation of
  10 px is flagged, an action played from elsewhere flags too (204's jade
  `look`). 2026-10-03: every station of the fourteen runs matched but
  208's tricked elephant (`xt` 192 now).
- `WDBG_BARS=1` — the oracle logs a timed stay's bar (fcn.1000b154's
  object: its count every 60 ticks, its starts and falls): 214's Mother in
  her chair, 600 ticks, standing still through the neighbour's reaction
  scenes. `WDBG_GATES=addr,…` reads a step's `test al` after a call (206's
  director's pillows gate). The port's own diagnostics: NFH_LOOP_LOG (the
  once-ignore targets), NFH_DEPART_LOG (the departure records), NFH_PASS_LOG
  / NFH_CLAIM_LOG (passes, door waits).
- `jumps_report.py <pairs.txt...> [--jump=2]` — where a replay's drift
  jumps: the bubble pairs read as port-minus-PC offsets, a step of two
  seconds or more between two bubbles names the visit between them (its
  tricked reaction or the walk on) — the per-station to-do list of a
  tricked lap (205's eel: the PC's 9.25 s against the port's 21.3).
- `tricked_visits.py <n> <trace> [--write]` — the tricked visits of a
  Season 2 run measured: per trick record paid, the neighbour's stand
  around the credit (the station, the actions posted, the SHOUT level,
  the animations with their lengths, the credit's second) next to the
  item's PCUseSecondsTricked / PCCreditAt / PCShout / PCFixSeconds /
  PCShoutTail; `--write` puts the measure into the overlay where it
  differs by three ticks or more (a simple model only — not a pair, a
  linked or a compound flow; a tail under a second and a repair the
  model stands out elsewhere are left).
- `WDBG_NOCATCH=1` on NFH1 (s1_oracle.py): Woody uncatchable — the state
  function's rooms test (fcn.00436bb0: the two room objects equal, the
  neighbour's pause byte +0x78 clear, no flag 4 on either, fcn.0043c2b0)
  stores its `seen` byte at 0x436d2c; five NOPs there, and a breakpoint on
  them logs `wouldcatch` events (once a second) — a plan runs its whole
  length and every would-be catch is in the trace. `catch_report.py <n>
  <trace> <port run dir>` lines a run's catches up with the port's replay
  (the rooms of Woody and the catchers over the seconds before, whether the
  port's Woody shares a room with a catcher then); the replay must run to
  the trace's end (replay.sh UNTIL=<secs>) or the port's state is frozen at
  its last leg; the port's replay of an uncatchable run takes NFH_NO_CATCH=1
  (runtime/world.py _catch: the catch logged as `WOULD CATCH t= by` once a
  second and not played — a harness switch like NFH_NO_DEPART).

## What the plan batches found (2026-10-03 03:00)

Blind, the plans end in early catches on the original (212 at 7 s, 214 at
11 s, each Season 1 level once — a Season 1 catch ends the level): the
plans carry the port's timing and the port's predictive gate. The 206
runs never get past the lesson: the runner skips the `tutorial` leg and
the director's gates (the bag held, the pillows manipulated, the pipe
entered: TutorialPC206's b51c/b434/b28c) have not all passed on the
oracle — the neighbour waits for her second call at (550, 340) in her
room, and a probe of the Mother's sight there was his catch (2026-10-03,
the `msg` hook on fcn.100101f3 logs the director's boxes since, and
`WDBG_GATES=0x1002b4b5` the director's pillows gate). The gate failed
because the runner's next input came inside Woody's `inflate` (an `auto`
action, 37 frames) and cancelled the placement of pillows_manip at the
job's end — the two-second pose rule had taken the leg as done. The
runners wait an action's own ticks out now (PCMap.woody_ticks: time="N"
+ 2, `auto` through lap_model_s2.Data.action_ticks); a leg's `wait` is
no longer needed for that. The Season 2 runner's gate reads a catcher's
blindness off the actor's own flag word (+0x14, the `flags` field of the
tick's actors; flag 4 the hideout state the predicate skips — 206's
Mother asleep in her chair, which is no hideout object): the 206 plan
runs 18 of 18 legs since (nocatch3), its one timeout the kukidentomat:
a `game` object (objects.xml's flag) whose `use` action is the game's own
clip — the runner had sent a UseObjectMsg, which only walks Woody to it;
the GUI's click on a `game` object is the minigame's CombineMsg with no
second object (game.exe fcn.00408161 @ 0x40828a), which the runners send
for any `game` object now (PCMap.games: 206's kukidentomat, 205's duck
cage, 214's closed hatch). The runner's
live-state gate (above) keeps Woody out of a catcher's room but cannot
leave a room before the catcher arrives — 101's `park! Zone01` right after
the binoculars (101 s): the PC neighbour leaves the sofa at 100 s and is in
the kitchen 6.9 s later for the microwave's clean, the gated Woody waited
for him to stop walking and was caught standing. The port's replay of the
run (replay.sh, `s1gatedreplay.sh` on the bench) is where its neighbour is
at that second. 203's handbag and 205's duck cage: see the unlock note
above (the first run's "modal minigame" was the container use's SIGSEGV).
