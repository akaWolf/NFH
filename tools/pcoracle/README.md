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
  done if the unlock's take happened (the PC's combination takes the item).
  The legs' outcomes go to `oracle_<level>_legs.json`, the catches
  (`woody fight` / `respawn`) are printed; the game's own log (a new
  GameLogicLogNN.xml per session) then gives the port the same inputs by
  tick (`oracle2plan.py`, `replay.sh <n> <level> <tag>`: the plan, the
  port's run, the comparison).
- `cmp_run.py <trace> <run dir>` — the two sides on one clock: the PC's
  station actions, icon changes, posts, SHOUTs and inputs against the
  port's routine transitions, think icon, trick count and clicks.
- `cmp_pairs.py <trace> <run dir> [--segments=<secs>]` — the same, paired:
  the inputs (equal by construction), the bubble (the PC's icon changes
  against the port's think changes, matched by value in order), the
  stations (STATION_CLIPS: the PC action on a room/object family -> the
  port's clip), the records paid, the catches — each pair with the port
  minus the PC in seconds and a mean per kind; `--segments` lists the
  neighbour's animation changes on both sides (the port's sprite x is the
  mobile station's, not the PC hotspot the walk timing leaves from).
- `cmp_idle.py` — the same for an idle lap (`runtime/record.py`,
  NFH_PROFILE=pc).
- `s1_smoke.py` (`s1smoke.sh <level folder> <secs> [clicks]`) — NFH1's
  game.exe under the same harness: the game logic is in game.exe (no
  GameLogic.dll; the same Loader.dll messages and GameLogicLog): the level
  factory fcn.00439fe0 picks the level class by name (tutorial_1,
  level_peep...), the GameLogic constructor fcn.0043ab40 calls it; the
  script calls are __fastcall-ish — DoAction fcn.00477f60 (ecx object, edx
  action), GoTo fcn.00479da0 (edx object), SetIcon fcn.00437f70 (ecx); the
  per-tick `<time>` log is written at 0x450c40. The menu walk: the title
  (400,300), START GAME (414,313), tutorial_1 (65,116), play (750,555) —
  NFH1 runs 800x600 fullscreen by default.
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
hook): before it the plan runner takes him as standing.

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
