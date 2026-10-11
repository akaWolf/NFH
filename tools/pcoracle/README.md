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
- `port2script.py <level> <run dir>` — the port's clicks.json (frames at 60
  a second) as the oracle's script: an item click = UseObjectMsg on the
  item's PC object (the overlay's PCApproach Woody `obj`), with an
  inventory type = CombineMsg (IT2_X -> x), a floor click = GoToPosMsg in
  the zone's PC room at pc_room_x; a take after an unlock stays a plain
  use; one message a tick.
- `cmp_run.py <trace> <run dir>` — the two sides on one clock: the PC's
  station actions, icon changes, posts, SHOUTs and inputs against the
  port's routine transitions, think icon, trick count and clicks.
- `cmp_idle.py` — the same for an idle lap (`runtime/record.py`,
  NFH_PROFILE=pc).
- `trace_*.py`, `inject*.py`, `test_call.py`, `smoke_gdb.py` — the
  experiments the above grew from (kept for their hook recipes).

## What was found on the way

frida cannot do this on Wine (the 32-bit helper segfaults inspecting the
process, the gadget crashes inside it); native gdb on the process blocks
Wine's start (wineserver uses ptrace itself); `winedbg --gdb` is the way.
`LOADING DATA` takes the level's setup messages through the loop, so the
message hooks are armed at tick 20. The windowed mode's cursor scaling and
greyscale come from the 32-bit window on a 24-bit Xvfb; fullscreen 800x600
is clean. The game's own replay (`createGameLogicFromLogFile`) exists but
its trigger (the session's log name, fcn.004037b6 case 4) was not found —
the injection above replaces it.
