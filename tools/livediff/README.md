# Track A — diffing the port against the running original

The port is checked three ways. `tests/invariants.py` watches our own
loop for states the original cannot produce; `tools/csdiff` runs the
game's own bytecode against ours one method at a time. This directory
is the third: the **whole original game, running**, with its state read
out frame by frame so a plan can be replayed on both sides and the two
traces diffed.

## Why it is feasible at all

Three facts, all checked against the shipped apk:

- **the apk carries an x86 build** (`lib/x86/libunity.so`, `libmain.so`,
  `libmono.so`) — an x86_64 host runs the game natively, with no ARM
  translation anywhere. There is no arm64 build, only `armeabi-v7a`
  and `x86`.
- **it is Mono, not IL2CPP** — `libmono.so` sits next to the player, so
  Frida reaches `Assembly-CSharp`'s methods by name (`probe.js`); no
  address reversing, and the same class and field names the port cites
  in its comments.
- **no root, no kernel modules, no compositor** are needed on the host:
  QEMU with KVM (`/dev/kvm` is world-writable), a user-mode network and
  a serial console are enough. That ruled out Waydroid, which wants a
  NixOS rebuild and a Wayland session.

## The machine

`vm.sh` builds and drives it: it fetches an Android-x86 ISO, repacks the
initrd with the properties this harness needs, installs unattended
(`AUTO_INSTALL=force` answers every installer dialog), and boots with
`-kernel`/`-initrd` so the kernel command line stays in our hands.

Hard-won details, all encoded in the script:

| what | why |
|---|---|
| Android-x86 **7.1**, 32-bit | the game is Unity **5.3.4f1** (March 2016). On Android 9 its player quits with "Your hardware does not support this application" before it even dlopens `libunity.so` — a decade of linker and namespace changes in between. On 7.1 it gets past that (see the open question below). |
| `SETUPWIZARD=0` + `ro.adb.secure=0` in the initrd | the VM comes up ready: no wizard, no adb key prompt, root adbd on TCP. The stock init already appends `ro.setupwizard.mode` there. |
| the address goes on `wifi_eth` | Android-x86 renames the NIC and parks a carrier-less `wlan0` shim on top; an address on `wlan0` sends nothing. |
| `ip rule add ... lookup main` | netd's policy rules never consult the main table, so even a correct route is ignored and inbound connections are never answered. |
| adb on port **6666** | on 5555 the host's adb mistakes the guest for an emulator and holds it `offline` forever. |
| `svc power stayon true` | a sleeping screen pauses Unity: the process idles at 0% CPU and logs nothing. |
| `frida-server -l 0.0.0.0` | it binds loopback by default, which QEMU's forward cannot reach. |

Frida runs on the developer's machine and talks to the guest through an
ssh tunnel to the forwarded port (client and server versions must match
exactly).

## The plan for the diff itself

- **pin `Time.deltaTime` to 1/60.** The port's recorder already runs a
  fixed 60 Hz step (`runtime/record.py`), so with the original's clock
  pinned the two advance in identical quanta and the emulator's speed
  stops mattering.
- **feed input by frame number,** not by `adb input tap`: the same click
  script both sides, replacing the player's input read.
- **dump state in `record.py`'s schema** — Woody's position, state and
  animation, the routines, the game counters — so the existing tooling
  diffs the two streams and names the first frame that disagrees.

## The graphics-buffer wall, and how it fell

Android-x86 under plain QEMU gets its own system up (SurfaceFlinger
draws through virgl on the host GPU, or through SwiftShader) but never
lets an *app process* map a graphics buffer, so the player dies asking
for its surface:

| guest | app-side failure |
|---|---|
| 9.0, SwiftShader | `graphics.mapper@2.0-impl.so` — "not accessible for the namespace" (Treble keeps vendor HALs away from apps) |
| 7.1, virtio-gpu + virgl | `gralloc.gbm.so` — `libdrm.so` not found inside the app |
| 7.1, SwiftShader | `Gralloc1On0Adapter: gralloc0 register failed`, then the game stops |

The AOSP emulator has none of that: its goldfish gralloc is built for
virtual machines. On API 25 x86 the game runs — Unity logs its GL
extension list, the THQ Nordic card and the title screen come up, and
`vm.sh`'s Android-x86 route is kept only as the record of what did not
work. `emulator.sh` is the working recipe.

Getting Google's prebuilts to run on NixOS took one more trick: there is
no FHS loader, `nix-ld` is not enabled on the machine used, `steam-run`'s
sandbox hides the SDK's own directory, and pulling the emulator into the
nix store took the root filesystem to 96% — so `emulator.sh patch`
rewrites the interpreter and rpath of every prebuilt ELF in place, and
everything stays in `/tmp`.

## Where this stands

Proven end to end: the emulator boots headless and unattended, the game
and its 402 MB OBB install, the original runs, and Frida — on the
developer's machine, through an ssh tunnel — spawns it, injects into the
32-bit process and resolves its managed side by name. `state.js` walks
libmono to `Assembly-CSharp`, finds `GameInfo` and reads its field
offsets out of the live runtime (`CompletedTricksCount` at 172,
`TotalTricksCount` at 164, `FinalViewerRating` at 232), then arms a hook
on `GameInfo.Update`.

`run.py --attach` rides the running game (frida names the process by its
application label, so the package is looked up among the applications),
which is what the menus require: `GameInfo.Update` only ticks inside a
level, and the game has to be walked from its title card through the
episode map first.

## The first numbers

Driven into Level201 and recorded at 60 Hz, the original reports
`TotalTricksCount` 4 and puts Woody at **(2.190, -2.209)** — the exact
`start_location` in `levels/s2/Level201.json`, which is the first
confirmation that the export is faithful to what the game actually
loads.

## The first two fixes

With `Time.deltaTime` pinned to 1/60 (`state.js` replaces the property's
JIT-compiled getter) the two sides step in the same quanta, and a click
on the SoapChest could be compared frame for frame. It found two
departures, both settled against the decompile:

1. **A climb ignored the urgent-move pair.** The original picks
   `RunningDoorForceMagnitude` while `InUrgentMove` in the door climb
   (Pawn.cs:1404-1411), the descent (cs:1430-1437) and the climb to an
   item (cs:1771-1778); the port used `DoorForceMagnitude` in all three.
   Woody runs whenever he is not sneaking, and his two magnitudes are
   0.8 and 1.6, so every approach ran at half speed: 0.0133 a frame
   against the original's 0.0265.

2. **Velocity is a field, and the position integrates it after
   WalkOnPath.** `ProcessMovement` (cs:855-880) runs `WalkOnPath` — which
   may snap the x onto the target and switch the move — and only then
   adds `Velocity * dt * Speed`. Nothing zeroes the velocity when
   `MoveToItem` or `MoveToDoor` first takes over (only `TakeNextStep`,
   cs:1052, and `TryUseItem`, cs:1795, do), so the walk's last velocity
   lands once more on the frame a climb begins. That is where the
   original's 3.417 came from: snapped to 3.384, then one more walk
   step; the climb runs on `(0, 1.6)` and leaves x alone; `TryUseItem`
   clears `MovingUp`, and the next `MoveToItem` snaps x onto the target
   again (cs:1735-1738). The port integrated inside each branch and never
   carried a velocity; it now keeps `Pawn.velocity` across frames and
   integrates after the state machine, exactly in the original's order.

After both, the SoapChest walk matches the original on all 50 frames
(mean distance 0.00006, the peak being the trace's third decimal):

| frame | original | port |
|---|---|---|
| 37 | (3.389, -2.259) | (3.389, -2.259) |
| 38 | (3.417, -2.261) | (3.417, -2.261) |
| 39..47 | x 3.417, y rising 0.0267 a frame | same |
| 49 | (3.384, -2.021) | (3.384, -2.021) |

Two details of the same code are deliberately not reproduced, both
invisible: the leave animation of a door does not zero the velocity
either (cs:1615-1626), so the original's hidden, warping pawn keeps
integrating until the far door places it — the port's `DOOR_ANIM`
state does not integrate, and the placement overwrites the position
anyway; and the original repeats the post-use snap on every frame of
the use, which only matters if something moves the x meanwhile, and
nothing in the port does.

## Past the tutorial

Level201 is the tutorial: its first eight seconds are the title cards,
the neighbour stays frozen until the script releases him, and every
item and door is locked until its step. Every other node on the episode
map is locked too, and that lock is not progress: `LevelUnlocker.
CheckUnlockedLevels` (LevelUnlocker.cs:76-86) opens a node only when its
purchase pack is recorded as bought — a PlayerPrefs key,
`nfh.02pack_levels`, written by the store `Purchaser`. The apk on the
bench came from the owner's own purchased copy, but the bench has no
store account to restore the purchase from, so `emulator.sh purchased`
mirrors the owner's entitlement onto it by writing that key. It is for a
copy whose packs were bought, and nothing else.

## Clicking the original by item name

`tap.py <ItemName>` is the emulator side of the port's `clickitem`: Frida
finds the item's GameObject, asks the scene's camera for its screen
point and adb taps it, with Unity's bottom-up screen y flipped against
`Screen.height`. `run.py --tap=<Item>@<seconds>` does the same from
inside the recorder's own session — two Frida clients on one process
crashed the recorder. Three things cost a game process each to learn:
`GameObject.Find` returns a GameObject, so it is `GameObject.get_transform`
(`Component.get_transform` on it reads a field that is not there);
`Camera.main` is null (no MainCamera tag), so the camera is the first of
`Camera.allCameras`; and the session must not be torn down while the
player is still inside the hooked `Update` — a second's grace before
exit. Every pointer is checked before use, because an engine call on a
null object takes the game down with it.

Driving the game to a level (`emulator.sh level`) had its own lessons:
the cross-promotion after launch is the game's own `MoreGamesActivity`,
up within ten seconds, and BACK closes it; a tap that lands on it opens
the store link in the WebView shell — a separate app that then sits on
top of every later launch, so the shell is force-stopped before the game
is started; and BACK on the loading screen finishes the Activity.

## What the tutorial level allows

Level201 locks every item and door the script has not reached
(`ItemsToUnlock`, LevelScriptAction.cs:152): a click on the ToolBox
before the chest does nothing in the original, and `record_app.py` —
the port recorded through the whole application, tutorial layer and
all, in `record.py`'s schema — does nothing either: 2161 frames, no
difference. The chest, the tutorial's first target, walked through the
application matches the original on all 1109 frames of the walk and the
use that follows (mean 0.0000, peak one third-decimal). The original's
first eight seconds in a level are the title cards; the application
skips them, and the differ aligns on the first move.

(The neighbour question from an earlier pass — the port at (-0.325,
1.656) against the original's (-7.33, 1.54) — was `routines[0]`, which
is Olga on this level; the neighbour stands at (-7.33, 1.54) in both.)

## An ordinary episode: Level202's neighbour

With the packs mirrored, Level202 gives the first comparison that is not
the tutorial: 78 seconds of the neighbour's routine with no input at all
— BeerMat, the Rake, the Swimming ring, then a zone transit up to the
BridgeRail. The first pass showed 3511 frames at a mean distance of
0.0036 with a 0.30 spike, and `steps.js` (every `TakeNextStep` of the
original with its new `MoveLocation` and `MinDistToNextMove`) explained
the spike: `BuildPathToItem` (Pawn.cs:811-825) adds the floor step
before an elevated item only when the pawn is not already within 0.1 of
the item's x (`IsAtItemLocation`, cs:827-830), and that step targets
`TargetLocation.x` — the port added it always, at `GetMoveLocation`,
so the neighbour walked to an extra corner and stood a frame there.

After that fix:

| | |
|---|---|
| frames compared | 3511 |
| mean distance | 0.0014 |
| peak | 0.0154 — one walking step |
| identical (<=0.002) | the first 963 frames (16.05 s) |

What is left is one frame at each hand-over, and it comes from the
animation clock rather than from the movement. `frames.js` shows the
original's order inside a frame — `ActionManager.Update`, then
`Pawn.ProcessMovement`, and a finished action advancing only after the
move — which is the order `World.tick` already keeps. `clock.js` then
reads the controller's own `animationTime` and current sheet frame every
frame; against the port's, playing the same use:

| | sequence element lengths, in 60 Hz ticks |
|---|---|
| original | 43, 48, 49, 49, 48, 48, 49 |
| port | 43, 49, 49, 49, 49, 49, 49 |

The original advances a sheet frame every six ticks (0.1 s at 10 fps
against a 1/60 step is exactly six, so the `animationTime <= 0` test
sits on a knife edge) and its leftover drifts, spending 48 ticks on an
element as often as 49; the port always spends 49. Rounding the port's
accumulator to single precision, which is what Unity's `animationTime`
is, does not move it — the two land on the same side of that test — so
the change was dropped rather than kept on a guess. **Open**: an element
runs 0–1 ticks long in the port, which is the whole of the residual
0.0014.

## Both seasons

`NFH_SEASON=1` points the whole set at `com.nordigames.nfh` — the same
launcher Activity, the same prefs layout, its own pack key
(`nfh.01pack_levels`, Purchaser.cs:39) and one extra tap for the
season page that Season 1's menu shows before the episode book.
`NFH_PKG` does the same for `run.py` and `tap.py`.

Level101, recorded the same way — 80 seconds from the play button, no
input beyond it:

| | neighbour | Woody's walk-in |
|---|---|---|
| frames compared | 3511 | 3572 |
| mean distance | 0.0109 | 0.0017 |
| identical (<=0.002) | the first 1167 (19.45 s) | the first 24 |

Both excursions over 0.05 in the neighbour's trace are single frames
where he is mid-warp through a door — 0.89 and 0.91, which is the width
of the warp, taken one frame apart. Woody's entrance is one step to the
level's EntranceLocation in both (`steps.js` with `ROLE = 'Woody'` shows
the original taking no door step at all); the two pause together partway
and resume, 1.5 frames apart. So Season 1 shows the same one-frame phase
as Season 2 and nothing else.

## Reading the original's state

`state.js` reads by name through Mono's C API (`libmono.so` exports
`mono_class_from_name`, `mono_class_get_field_from_name`,
`mono_field_get_offset`, `mono_runtime_invoke`). Two things it took a
while to learn: `GameObject.GetComponent` is overloaded, and the
by-arity lookup returns the `Type` overload, which crashes on a string —
`mono_method_desc_search_in_class` with `:GetComponent(string)` picks
the right one; and anything that calls into the engine has to run on
the player's thread, which the hook on `GameInfo.Update` provides.

## Every level's opening

With `run.py --load` a level starts by name from inside the running
game, and `sweep.py` records all 28 openings on both sides — 74 seconds
of the original, 60 of the port, no input — and tabulates each level's
neighbour and Woody: frames compared, mean and peak distance, the frames
over 0.05 and where the first of them falls. Season 1's table sorted
itself into four kinds of row.

The first is the one-frame door phase already known from Level202:
Level101/102 show two or three frames over 0.05, each the width of a
warp taken a frame apart.

The second is every walk-up door pass, and it is the original's, not a
bug of the port: `PlayDoorLeaveAnimation` clears `MovingUp` and hides
the pawn (Pawn.cs:1624-1635) but leaves `Velocity` at the climb's
`DoorForceMagnitude`, `MoveToDoor`'s `PortalMove` arm returns without
touching it (cs:1389-1440), and `ProcessMovement` keeps integrating
(cs:855-880) — the hidden neighbour rises 1.7 units through the ceiling
for the three seconds of the leave and enter animations until
`WarpThroughDoor` (cs:1517-1522) puts him at the far door. The port
parks him at the foot. Nothing reads the position meanwhile — the pawn
is hidden, and the camera (`CameraMover`) follows touches, not pawns —
so the differ is the only witness: 193 frames over 0.05 per pass, peak
3.4, in Level103-106, 108, 110-114.

The third was a bug, and Level103 showed it plainly. The neighbour comes
down the front stairs while Woody stands at the door; the original
catches him on the frame the door animation ends (18.92 s), the port a
second later, after walking him down to the floor line and 0.5 to the
right. `OnDoorEnterAnimationFinished` ends in `HasNeighborCaughtWoody`
(Pawn.cs:1666-1670) → `HitWoody` → `StartUrgentAction` → `StartAction`,
which walks only when `!IsAtActionLocation` (ActionManager.cs:146-155);
`RoutineActionHitWoody`'s test is the x distance against
`MaximumPawnDistanceToAction` (RoutineActionHitWoody.cs:15-18), which
the levels serialize as 0.8 — so the hit starts where the neighbour
stands, and `OnActionStarted`'s `MoveToEmptySpace` snaps him onto Woody
(then 0.6 off the nearest door: (3.785, -2.059) in both). The port
always walked. Two more things came with it: `HitWoody` stops the
current action first (Rottweiler.cs:1088) and `OnActionStarted` pauses
the movement (RoutineActionHitWoody.cs:27) — the port's neighbour still had the door descent
and the LetterBox use queued, and `MailboxStart` played over
`WhirlWoody`; and the catch check has to close the handler, after
`EndPortalMove` has taken the next step, not precede it. With the three
in place the port's neighbour is at (3.785, -2.059) on the same frame,
`WhirlWoody` on the sheet.

The fourth kind took `pawn.js` — the pawn's own fields every frame,
riding the recorder's session through `run.py --extra`. Level107's
neighbour walks his flat door to `MoveLocation.x = 3.451`, not the
3.427 the level data gives the door; Level111's Woody runs at 6.283,
not 5.913, and starts the pass there, 0.37 short of where the port has
the door. The difference is `Level.cs:186`: at start every zone is
moved to `(x, ZonesY[i], z) + ZoneController.position` — the
controller's offset, which the zone's world position already contains
once, is added a second time, and the zone's children (the doors, the
transitions) move with it: (0.024, -0.049) for Zone06 of the 107-110
house, (0.37, -0.031) for Zone05 of 111-114. The port applies the move
to the zone (scene.py:1627) and leaves the children where the scene
file has them. That is the 0.02-0.37 in every door-related row of the
Season 1 table — the stop before a flat door, the far door's placement,
the entrance — and the first thing to fix: shift each zone's descendant
transforms by the zone's own runtime delta. (The Season 2 table, same
sweep: 201/202/210 clean, 203/206/209/211/212/214 to triage after it.)

With the zone children moved the Season 1 door rows collapse: Level111's
Woody entrance goes from 143 frames over 0.05 to none, its neighbour from
3371 to 275 — and what is left in both levels is the hidden drift during
door passes plus the one-frame phase. The differ now skips the frames
the port's pawn spends inside a pass (`door_anim`, one frame of padding
either side; the recorders log the pawn state as `pstate`), so the
tables show what the screen shows.

Season 2 zones move too — by `ZonesY` alone, up to 1.25 in Level211 —
and the shift took Level206's stairs with it: the neighbour's walk
through the two upper-floor transitions, 751 frames apart before, now
tracks the original to a few hundredths. What the same level showed next
was a bug of another kind: after the Urgent DeckChair action the port's
neighbour ran to the dog (2 units/s, arriving at 28.65 s) where the
original walks (0.9, arriving near 30.3 s). A MoveOnly step is a plain
`MoveToGoal` (RoutineActionMove.cs:76-79), and `MoveToGoal` clears
`InUrgentMove` (Pawn.cs:428-432); the port's MoveOnly branch inherited
the previous action's flag. Two Season 2 plans and one check had been
tuned to the port's old geometry — the neighbour of Level206 parks by
the dog for the next half minute in both games now, and Level211's
fishing rod, no longer under the moved stairs' collider, is an item
click (tests/checks/s2_plans.py F4).

## The animation clock, closed

The one frame per hand-over turned out to be one frame per sheet frame,
and Level109 made it large: the neighbour's Bed use is BedIn and thirty
BedSleep elements, 2 fps, two sheet frames each — 60 ticks apiece in the
original (`clock.js`, every element), 61 in the port — and the alarm
clock woke the port's neighbour 31 frames late, with every use after it
displaced by as much. `animationTime` is a C# float
(AnimationControllerBase.cs:17), Time.deltaTime too: 0.5f minus thirty
0.016666668f lands below zero on the 30th tick, where the same sums in
doubles leave +1e-17 and cost a 31st. `AnimPlayer.tick` now rounds its
accumulator, the frame step and `1f / FrameRate` to single precision
(`_f32`), and BedSleep takes 60. (The 43 of a sequence's first element
was already right: `InitializeCurrentAnimation` zeroes the clock and
the first tick advances at once.)

## The hit from 0.8 away

Six levels still showed the same shape after that — 203, 208, 211 and
213 in Season 2, 108 and 113 in Season 1: the original's neighbour
jumps 0.8 units ahead of where the port's still walks, then stands. A
tracer on the ActionManager (`actions.js`: the active, urgent and move
actions every frame) named it: `HitWoody` — the neighbour has caught
Woody at the zone's edge and is walking up to him, and a walk toward a
pawn ends when `RoutineActionMove.Finished` says so, which for a hit is
the x distance to Woody under `MaximumPawnDistanceToAction`
(RoutineActionMove.cs:26-41), 0.8 in the levels' data. The move stops
there, `OnActionStarted` snaps him onto Woody (`MoveToEmptySpace`) and
the hit sequence plays; the port walked the last 0.8. `World.tick` now
carries that test for every walk toward a pawn — the catch and the
Mother's and Olga's `HitPawn` runs, whose `IsAtActionLocation` adds the
zone (RoutineActionHitPawn.cs:13-18) — before the pawns move, where
`ActionManager.Update` reads it. Level213's catch lands on the same
frame as the original's, 16.52 s, at (4.004, -0.800).

Four of the trick plans stopped passing along the way — Level113's
ElectricTrap wait, Level205's statue and glasses, Level206 from the
DentureAdhesive on, Level208's ShoeMachine and cable — and none of them
is a divergence the sweep can see: the plans were written against the
port as it was, and the neighbour they wait for now walks, parks and
catches as the original does (Level206's neighbour, for one, sits by
the dog from 35 s to the end of a two-minute recording on both sides).
They are follow-ups: each wants its legs re-timed against the
original's routine, which `sweep.py` now gives per level.

## Where the sweep stands

After the fixes above, re-recorded on the port side (the original's
recordings are the sweep's originals): frames over 0.05 in the
neighbour's trace outside door passes, the mean distance, and where
the first such frame falls. Woody's rows are clean on every level
(no input past the entrance).

| level | over 0.05 / mean / first | level | over 0.05 / mean / first |
|---|---|---|---|
| Level101 | 0 / 0.0080 /  | Level201 | 0 / 0.0002 /  |
| Level102 | 0 / 0.0073 /  | Level202 | 0 / 0.0014 /  |
| Level103 | 0 / 0.0011 /  | Level203 | 1 / 0.0064 / 58.08 |
| Level104 | 0 / 0.0059 /  | Level204 | 1 / 0.0017 / 30.67 |
| Level105 | 0 / 0.0046 /  | Level205 | 1 / 0.0135 / 25.83 |
| Level106 | 0 / 0.0063 /  | Level206 | 0 / 0.0076 /  |
| Level107 | 665 / 0.0183 / 24.67 | Level207 | 3 / 0.0092 / 17.13 |
| Level108 | 3 / 0.0061 / 9.5 | Level208 | 1 / 0.0032 / 23.98 |
| Level109 | 806 / 0.0205 / 37.45 | Level209 | 2 / 0.0099 / 47.45 |
| Level110 | 3 / 0.0146 / 17.23 | Level210 | 0 / 0.0090 /  |
| Level111 | 0 / 0.0031 /  | Level211 | 2 / 0.0076 / 49.77 |
| Level112 | 84 / 0.0141 / 12.22 | Level212 | 3 / 0.0057 / 5.92 |
| Level113 | 1 / 0.0122 / 51.35 | Level213 | 0 / 0.0023 /  |
| Level114 | 2 / 0.0106 / 21.3 | Level214 | 0 / 0.0095 /  |

What is left is small and of two kinds. The single frames (108, 110,
113, 114, 203-205, 207-209, 211, 212) are the warp-phase frame the
mask's padding does not cover: a pass that ends two frames apart.
Level107 and Level109 carry a lag of two to four frames that starts
at the end of an item use and rides the walk that follows — the
original leaves the alarm clock, the camera, the teeth two frames
before the port does — which is the last of the animation-clock
business (a use's last element, the item's own sequence and the
action's stop within one frame of each other) and reads as 0.03-0.09
for the length of a walk. Both are below what a viewer sees.
