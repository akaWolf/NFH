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

## Clicking, and the clock the click is on

`sweep.py clicks-live` / `clicks-port` add one click to the opening:
the first `take` of the level's plan, tapped on both sides. The first
pass tapped "level frame 720" on both, and every Season 1 row came out
diverged from 5.3 s to the click — because the two sides count level
time differently: the original's frames run from the load and include
the title cards (about 500 frames), the port's recorder skipped the
cards with a click and counted from play. Season 2 hid the same offset
behind the differ's alignment on the first move — there Woody's first
move *is* the click. Two things fixed it. `record_app.py --cards` plays
the cards out, so the port's clock runs from the load too (IntroCards
takes its times from the same data; the first move lands on frame 500
on both sides). And the original's tap does not land on the frame it
was asked for — frida, ssh and adb put it a second or two later — so
`state.js` reports the frame `Woody.ProcessMoveInput` (Woody.cs:702)
ran, run.py files it in `tap.json`, and the port side, recorded second,
clicks on exactly that frame. The bench itself now lives in
`~/nfh-bench` on its host (the host wipes `/tmp` nightly); `shell.nix`
carries the port's Python environment.

## What one click showed

With the clock settled (the cards played on both sides, the port
clicking on the frame `Woody.ProcessMoveInput` ran, the differ
anchoring Woody on that frame and the neighbour on his first move),
the click sweep — the first `take` of every level's plan, on the
level's frame ~800 — comes out like this: Woody's reply to the click
matches the original on all 28 levels, to the frame on 27 of them
(Level206 both sides ignore the click; Level214's HatchFish is inactive
at load, so `first_take` skips to an item `GameObject.Find` can see),
and the neighbour's rows are the opening table's.

One thing it found. After a walk-up door Woody comes down the stairs
at the NEAR door's x in the original — 3.890 in Level101 where the port
had 3.774, -1.551 in Level111 against -1.652 — not at the far door's
exit point. `WalkOnPath`'s else-branch runs `MoveToItem` before
`MoveToDoor` on every frame of the descent as well (Pawn.cs:983), and
its head (cs:1735-1738) snaps x to the step's `TargetLocation.x`, the
near door's, when the walk has crossed it (`HasPassedTarget` against
`WasMovingLeft`) and the door is Passable; `WarpThroughDoor` and
Woody's `DeltaExitLocation` set the y, the snap takes the x back on the
next frame. The port's DESCEND state now does the same. Level101's
Woody then matches to 0.034; Level111's to 0.067 — the residual there
is two frames: the two door animations hand over a frame or two
shorter in the port (Woody is placed at the far door on frame 372 of
the click, the original's on 375), and the alerter's `WaitForSeconds`
delay runs a frame longer in doubles than in floats, so the flinch
(`PlayShortFearAnimation`, Woody.cs:1005) comes two frames early and
Woody stops two running steps short. Both belong to the one-frame
family above.

Two things the recording itself needed on the bench: a stray touch
can cut the title cards short (Level202/204 came out with the
neighbour 100-200 frames ahead), so `state.js` reports the frame
`StartGame` set the neighbour's `CanStart` and a recording whose
intro ended before frame 440 is retried; and the game dies after a few
`LoadLevel` calls in a row on the 2 GB emulator, so a recording with no
frames walks the game back into a level and tries once more.

## The frames a wait takes

The last two frames in Level111 came from timers. `events.js` hooks a
list of the original's methods and reports the frame each ran — the
intro's `StartGame`, Woody's `StartMoveToLocation`, every door
animation's start and end, the alerter's flinch, the routine's action
boundaries — and three intervals came out the same on every run:
StartGame on frame 475 from the load, the entrance walk 30 frames
after it, the flinch 32 frames after the far door placed Woody in the
dog's zone. All three are `WaitForSeconds` or a `-= Time.deltaTime`
countdown, and all three read as: the wait ends on the first frame at
or past its seconds (2.0 s is 120 frames, 0.5 is 30 — a double's
countdown leaves +1e-16 and costs a 31st, hence `WAIT_EPS`), and a
coroutine goes on the frame after its wait ran out — seven waits in
`DoIntroLogic`, 468 + 7 = 475; a coroutine started from an animation's
end (the door's `OnAnimationEnded`, after the frame's coroutine phase)
takes two more, 30 + 2 = 32. `IntroCards`, the entrance timer and the
two `AlerterDelay` countdowns follow that now; the port's StartGame,
entrance, routine start, placements and flinch land within a frame of
the original's, which is the jitter of the recording itself. Level111's
Woody row after the click: 0 frames over 0.05, peak 0.034.

## Replaying a plan on the original

The plans in `tests/plans` are written against the port; the four that
fail (113, 205, 206, 208) and Level213's ninth trick can only be settled by
the original playing the same clicks. The runner now logs every click it
makes — `clicks.json` next to `results.json`: the frame from play (its own
60 Hz clock, StartGame at 0), the item, the inventory entry in Woody's hand
(the port's enum name, `IT_Egg`), the result. `sweep.py replay <Level>`
(`NFH_PLANS` = the runner's `--out`, `NFH_SWEEP` = where to write) plays it
back in three steps.

- `replay-live`: `run.py --taps=clicks.json`. The script waits for
  StartGame (Rottweiler.CanStart, the same frame the sweep anchors on),
  then, for each row, waits for level frame `start + frame`, puts the
  inventory in Woody's hand — `Woody.SetUsedInventory` (Woody.cs:1062)
  with the `InventoryManager.InventoryItems` entry of that `InventoryType`
  (the enum's ordinal, `invtypes.py` reads it off InventoryType.cs) — and
  taps the item through `tap.py` (the camera framed on it first). The tap
  lands some frames after the one asked for (frida, the emulator's input
  queue); `tap.json` keeps both — `planned[].want` and `planned[].at` — and
  the frame Woody.ProcessMoveInput actually ran, in `taps`.
- `replay-port`: the port again, on the original's frames: `record_app.py`
  with a script of `at N` / `select TYPE` / `clickitem Item` per click,
  `N` = the original's first ProcessMoveInput at or after the tap; the
  title cards played so both clocks start at the load.
- `replay-report`: the two sides' `CompletedTricksCount` steps and the
  catch, as level frames.

So the comparison is on the original's timing, not the plan's: a plan
that waited for a routine state on the port becomes fixed frames, and where
the original's neighbour is somewhere else on that frame the click does
something else — which is the divergence to look at, either the port's
routine or the plan.

The first replay, Level206, showed the runner's own gap before any of the
port's: the original dropped every click of the plan's first thirty
seconds — Woody stood at his start until the Pipe click at frame 2515 —
while the port's plan had taken the toy box one second in. Level206 is a
tutorial level: TutorialScriptCameraNFH2206 freezes Woody at its Start
and unfreezes him when the neighbour reaches his fourth in-game action
(cs:76-87), and CheckMouseClick drops a click while `Frozen` (Woody.cs:637).
The port models the script (runtime/tutorial.py, the App builds and ticks
it), and headless with the cards it freezes Woody over frames 475-2201 —
but `tests/run_tricks.py` ran the level in a bare Viewer with a bare
`world.tick`, no tutorial layer, so its clicks went through. The runner
now runs the level in the App (`Driver._enter_level`, `Driver.tick`), the
title cards skipped, as record_app.py does; the plans of the tutorial
levels (102, 103, 201, 206) were written against the runner without it.
`state.js` reads `Woody.Frozen` and the report prints both sides' frozen
windows.

## A Mother's catch, and the flag it does not set

Level208's replay ended on the original at frame 7928 with `GameEnding`
true and `gotCaught` false: a Mother's catch. `gotCaught` is the
neighbour's flag alone — every caller of `OnNeighborCaughtWoody` sets it
first (GameInfo.cs:216-218, Pawn.cs:370-372, 1228-1230) and
`OnMotherCaughtWoody`'s callers do not (cs:222-224) — and the port's
`_catch` set it for either catcher. It sets it for the neighbour only now
and keeps its own `caught_by` for the runner; the report shows the ending
on both sides next to the catch.

## The two clocks meet at StartGame

The original's title cards do not take the same number of frames from
run to run: Level208's StartGame (Rottweiler.CanStart) came at level
frame 464 in one replay and 474 in the click sweep, Level205's and
206's at 473. The port's cards take 474 every time. A port script on the
original's absolute frames is then off by the difference for the whole
run — Level208's neighbour left his platform at 1584 on the original and
1596 on the port, 10 of the 12 frames the cards. The replay's port
script clicks at `at +N` from the port's own StartGame (record_app.py
tracks the cards' end) and the report counts both sides' frames from
their StartGame.

## Level201's zone actions never completed

With the runner in the App, Level201's plan stalled at `tutorial 5`: the
LevelScript's action 4 — Woody enters Zone02, UnfreezeNeighbor +
ForceAdvanceAction — never completed although he stood in Zone02. The
action's Zone reference is the Zone component's path (228) and the
pawn's zone carries the GameObject's id (48); the port compared the two
raw ids (the original compares Zone components, Pawn.cs:1592-1595). The
tutorial resolves the reference through the level's component map now
(`zone_by_component`, which the item behaviours already used). Doors and
items were never affected: both are keyed by their component ids.

## Two more things the tap had to wait for

Level208's Balloons tap at frame 604 walked the original's Woody to
x=-0.35 and took nothing, twice, while the click sweep's tap at 720 took
the balloons. The camera log showed why: at 604 CameraMover was still
`Interpolating` the intro's snap to Woody — the camera had looked still
for a hundred frames, but while the flag holds every Update lerps the
transform back toward TargetPosition (cs:355-365), so the framing tap.py
sets on the transform is undone the next frame and the point it read
under the framed camera lands on the floor under the real one. tap.py
waits for the flag to drop, then for three still frames, then frames and
reads.

run.py restarted its level-frame count on any gap of over a second
between frames — the load's gap — and a stall mid-level (the emulator
pausing) restarted it too: Level206's replay burst its last 25 clicks the
moment the count came back small. The reset holds only until StartGame.

## The click box that stayed behind

Level113's Drawer was the first take of every replay and never a take on
the original: Woody walked to x=3.50 and stood, the port climbed and took.
The click sweep's tap at frame 803 had taken it — that tap went to the
GameObject's runtime transform, the replays to the port's collider centre,
and the two are 1.15 apart. Actor.Start moves every actor to
LevelLocations[i] for the level's index; the port moved the actor's use
location and sprite with it and left the BoxCollider where the prefab's
transform serializes it (3.49, -0.46 against the level's 3.45, -1.61). The
collider is on the same transform, so it moves too now — Season 1's
shared prefabs are the ones this reaches: the Drawer (104-106, 108-110,
112-114), the Fridge, the FirstAid, the PinsBoard, the Toilet, by up to
1.15 units; a player's tap in the port landed on air above the drawer.

The injected click (inject.js) showed the same thing without a tap in
between, which is what it is for: the click at the frame asked for, under
the frame's own camera, through Woody.CheckMouseClick's gates
(Woody.cs:637-671) and the HUD's world-click tail (HUD.cs:1320-1322). Its
replies name the gate a click died on — `hud-strip`, `on stairs`,
`stored`, `frozen` — where the port's runner had clicked without one.

## Two routes of equal length

Level205's replay parted at the Banger: the original's Woody went from
the upper-right deck to the lower-left one through Zone04 (the left
stairs), the port's through Zone02 (the right stairs), and the neighbour
found the original's Woody on the way. Both routes are two doors long.
Helpers.GetShortestPath (Helpers.cs:158-192) is a Dijkstra over
ZoneController.Zones whose list is re-sorted by Cost after every step
with ZoneComparer, which returns 0 at equal Cost; the sort is Mono's
classic Array.qsort — the game is Unity 5.3.4f1, its Mono the old mcs
corlib — and that quicksort swaps every pair its two walls meet on,
equal elements included, so a run of equal costs comes out turned
around. The port ran the same Dijkstra with that quicksort, step for
step, over the zones in the scene's order (ZoneController.Zones is
FindGameObjectsWithTag("Zone"), and tools/livediff/zones.js reads the
list off the running original to check the order), and Level205's route
came out through Zone04. The plan suite moved with it: Level208's plan
passes now, Level212's loses three legs to a route its author had not
seen — a plan to re-time, once its replay says the original walks it the
same way.

## An inactive object's click box

Level212's plan lost its crowbar leg under the route change: the runner
clicked the mine's collider centre and the port answered with NoNo. Two
items sit there with the same box — ClosedMine1, the shut mine, and
ClosedMine, the open one that ClosedMine1's priming activates — and the
open one ships with its GameObject inactive. The port skipped the
inactive object's sprite and kept its collider, so the hit test's tie
went to the first in scene order, the open mine, and the crowbar was
refused. An inactive GameObject has no collider in Physics: the loader
now carries the object's active state on the item (`Item.active`), the
box is off until SetActive(true) (`set_active` turns both on), and the
click lands on the shut mine. Fourteen items ship inactive: Level205's
WaterSkiisAux and RocketsBackground, 206's Rabbit, 207's MopedPool,
212's MechanicalBullCoins, ClosedMine, RubyThrone and ParrotCrap, 213's
Wasp, 214's Washbucket, HatchFish, Cloth, BirdDead and CaptainWheel —
the replay's tap.py could never resolve 206's Rabbit before its
activation for the same reason.

The dump, one row per level loaded (zones.js sends a row whenever the
GameInfo instance changes — the first Update after the script loads still
belongs to the level the game was in): on every one of the 27 levels it
reached, ZoneController.Zones is the scene file's order, Zone01…Zone09
as their GameObjects come. Zone.Neighbors' order differs from the port's
door order on most levels (the original's is each zone's child doors as
GetComponentsInChildren walks them), and it does not bear on the route:
every neighbour a zone relaxes gets that zone as Previous, whichever
comes first.

## What the bench itself does under a replay

Two things end replays before their clicks do. The game dies under frida
on a managed null dereference: Mono raises NullReferenceException through
SIGSEGV, frida's handler runs first and faults inside frida-agent (the
tombstone's first frame), and the process is gone — a tap replay of
Level201 lost its session a minute in, the injected replays of Level213
and Level205 stopped at frames 1162 and 8827 with no click near. And the
emulator itself goes: three boots on the afternoon of 2026-09-03 ended
within minutes with a clean shutdown in the emulator log, one after an
hour and nine minutes under load with crashpad's handler in the log. The
emulator is started in its own systemd user scope now — the harness's
background-task kills reach everything in the session's cgroup — and a
run that dies is run again; the sweep's second attempt covers a death
between levels, not one inside a level. Mono's own way out of the
signal-based null check, `MONO_DEBUG=explicit-null-checks`, cannot be
handed to the game: the `wrap.<package>` property is the only door to an
app's environment on the emulator, and with it set the app never starts.
The injected replays (inject.js) lost the game sooner than the tapped
ones — Level213 at frame 1162, Level205 at 8827, against 14,000 to 66,000
frames of tapped replays — so the long replays run through adb taps, the
port replaying the frames the taps landed on.

## Level206, replayed

The plan's clicks — the toy box's eleven tries through the freeze, the
cushion, the sports bag, the hide in the pipe at frame 2922, the harpoon,
the driver's dodges — tapped on the original and clicked on the port at
the frames the taps landed, 46,906 frames of level:

| what | original | port |
|---|---|---|
| LevelScript actions 1, 2, 3, 4 | 1725, 1937, 2581, 11822 | 1727, 1931, 2581, 11822 |
| the neighbour's routine, first loop 1…14 | 12479 … 18514 | 12480 … 18527 |
| the routine's third loop, 4…11 | 24750 … 27870 | 24775 … 27902 |
| the cushion pays | 13706 | 13710 |
| Woody caught | 28176 | 28232 |

The routine drifts by a frame every fifteen seconds or so — the use-end
residual the opening sweep had already measured on 107 and 109 — and
nothing else parts. The plan's own failures on 206 are the plan's: the
Rabbit ships inactive and the plan asked for it before the launch pad's
Fix could activate it.

## What the Season-2 plans taught

The plan runs on 206, 212 and 214 failed on legs the original's code
explains; two of the explanations were port bugs.

- **206, the rabbit.** `IT2_Rabbit` is inventory: `SearchItem.InternalUse`
  hands over every entry of `InventoryItems` (SearchItem.cs:179,
  `Woody.AddInventory`), and the FleaBlanket's list is
  `[IT2_Fleablanket, IT2_Rabbit]`. The Rabbit *item* ships inactive and is
  the rabbit's return for a second launch — `Item.RabbitBehavior`
  (cs:2626-2631) activates it in the LaunchPad's Fix while the pad is
  Tricked. The plan asked for the item before the pad had ever been
  tricked. Reordered: 17/17, the pad and the harpoon pay together at
  224 s, the Rabbit item activates at 242 s.
- **212, the rubies and the coin.** `Item.OnTrickDone` pays an item once
  (`AlreadyTricked`, cs:2148-2152); the throne pair's second coin is the
  linked branch (cs:2123-2146) and wants both halves armed for one sit.
  Woody's ruby on AztecThrone moves the click box to AztecThrone2
  (`ThroneBehavior212`, cs:2450-2469) and his Fix moves it back
  (`FixThroneBehavior`, cs:2471-2477) — so the second ruby goes on before
  he sits, and the second ruby is the WhipStonePlate's: a dexterity
  SearchItem opened with the crowbar (`DexterityUnlocker IT2_Crowbar`,
  `InventoryItems [IT2_Ruby, IT2_Coin]`, and the `WhipStonePlate` name-hack
  in `CanWoodyUse`, cs:1438, lets the round open with a ruby in hand). The
  BoatCoinSlot is nobody's routine item: its coin pays through the
  ParrotLedge's linked visit (`LinkedItemTrick 275`), so the corn waits for
  the coin. The RubyThrone (`ActivateItemAfterFix`) is only the third ruby.
- **214, the fish (port bug).** `Item.ShowObjects` (cs:2668) activates the
  HatchFish only when the Hatch's `Dexterity` is set, and his first Fix is
  what sets it (`HatchFixBehavior`, cs:2560): the fish come out on his
  *second* fall, after Woody's shards round (`DexterityUnlocker
  IT2_Shards`). The port activated them at the first angry — 88 s into the
  run, a lap early. Fixed: `_show_objects` gates on `item.dexterity`.
- **214, the bucket and the cloth (port bug).** `WashbucketBehavior`
  activates the Washbucket on Olga's `OlgaShipShowerSwiffer` pose and the
  Cloth on `OlgaShipShowerIdle` (cs:22-37, `GameObject.SetActive`). The
  port's `Behavior.go_set_active` only unhid the sprite: Olga reached the
  shower at 336 s and played the poses at 341/342 s, the bucket appeared,
  and its click box stayed off — `Item.active`/`clickable` never flipped,
  the plan's `activated Washbucket` timed out at 384 s. Fixed:
  `go_set_active` goes through `World.set_active` for an object that
  carries an Item.

## Season 2 replays: 205, 213, 212

| level | original | port |
|---|---|---|
| 205 routine steps 1…5, second lap | 7612, 8052, 10484, 10956, 11785 | 7614, 8056, 10487, 10960, 11790 |
| 205 the trick, the catch | 10236, 11846 | 10239, 11845 |
| 213 the catch (the plan's own early one) | 639 | 638 |

212 parted at frame 1374 with the same clicks, and the cause is the
bench, not the model: the runner's dodge onto the StatueHidden was tapped
at 1221 and registered ten frames later, while Woody was on the stairs out
of Zone02. The port's Woody topped the stairs at 1226 and turned for the
statue at 1231; the original's reached the top at about 1230, dropped the
click (a click during a transition is not taken, Woody.cs:637-671), kept
walking to the Resin and was caught at 1374 when the neighbour came in
for the Whip. Four frames of walk residual over four hundred, on the
wrong side of a transition's last frame — a hazard of tapping mid-walk,
noted, not fixed. The port replay ran on to the end of its clicks and its
routine kept the original's step frames up to that point (1@447, 2@1048
on both).

## Level201, replayed: four port bugs behind ninety frames

The first tutorial level's replay (the plan's 34 clicks tapped on the
original, replayed on the port at the landed frames) opened with the
neighbour ninety frames late and ended with a different game. Four
things, each fixed per the original's code:

1. **DelayStart under Frozen.** The routine ships Frozen (the LevelScript
   holds the neighbour until its action 2); the port counted the pawn's
   1.5 s DelayStart only after the unfreeze (`Routine.tick` returned on
   `frozen` first), while Rottweiler.Update counts it from CanStart
   regardless of the manager (Rottweiler.cs:916-932) and the unfreeze's
   StartNextAction starts him at once. Freeze start 591 vs the original's
   503; the routine's first step 1340 vs 1249. The detection gates that
   used `delay_start > 0` as "no CurrentAction yet" (GameInfo.cs:189,
   196) read a `started` flag now, set by StartAction and
   StartUrgentAction.
2. **The puddle's teleport, undone.** The WaterPuddle carries
   `TeleportRottweilerOnUse` (−0.26, −0.32): RoutineActionUse.OnActionStarted
   (cs:205-208) stands the neighbour at 3.46 the moment the use starts.
   The port teleported too — and two frames later its deferred MoveToItem
   snap (`_walk_on_path`'s head) read the new x as "passed the target"
   and put him back on the walk target, 3.12. Every later walk started
   0.34 to the left: the DeckRail action +24 frames, the MoveOnly walk
   +51, and the Hold's `ActiveActionIndex = 1` found him still walking
   instead of parked and frozen — the port's neighbour restarted his loop
   at 3690 with the Buffet, the original's waited frozen until the
   script's step 5 (3886). A teleporting use now cancels the pending snap.
3. **The prime leg's teleport.** RottweilerPrime and RottweilerUnprime
   return true (Item.cs:1356, 1370), so the same teleport applies to the
   toggle-prime legs; the port's prime path returned before it (4.32 on
   the second visit instead of 3.46).
4. **Woody.Freeze pauses the walk.** Freeze is `Frozen = true` plus
   `PauseMovement()` (Woody.cs:993-997); the port only set the flag, so a
   frozen Woody finished his walk (to the click's 4.02) while the
   original's stopped at the foot of the stairs (5.12) — and every later
   click started from a different spot. `Pawn.freeze` / `unfreeze` now
   do both, at all fourteen sites.

After all four the replay agrees through both tutorial laps and beyond:
freeze windows (501, 3060) and (3888, 5354) against (503, 3058) and
(3889, 5355), script steps within two frames, the routine's twelve steps
within two, the puddle's payout 4704 against 4702, and Woody's position
frame for frame — the frozen stop at the foot of the stairs, the vanity
bag, the tool box, the buffet, the second soap chest — until 9290. The
split at 9358 is the replay's: the puddle click landed during the empty
chest's take animation, was stored by both, and was replayed against a
camera that had gone back to Woody on the original (a floor point, no
walk) and against the framed item on the port (a walk up the stairs into
the parked neighbour, caught at 9554). A tap while a blocking animation
runs is the same hazard as a tap mid-walk.

## Level113, replayed: a name shared by four items

The first 113 replay parted at the neighbour's second step (1741 on the
original, 3477 on the port) and it was the replay tool: `clickitem
GroundMarbles` picked the first item of that name, and the level has one
per room. The port's Woody carried the marbles to the wrong room, the
neighbour found him on the way and searched instead of grinding. A
`clickitem` carries the click's recorded world point now and takes the
nearest item of the name. Replayed: routine steps 563/564, 1741/1743,
3423/3423, 4400/4387, 5301/5287; the runner's dodge got Woody caught at
5704 on the original and 5701 on the port.

## Level214, replayed: the bench cannot play a dexterity round

The plan's clicks (the carpet, the shards, the bouquet, the pistol, the
cabin) tapped on the original and clicked on the port at the landed
frames, 28,421 frames of level:

| what | original | port |
|---|---|---|
| the neighbour's first lap 1…4 | 476, 1553, 2742, 3678 | 478, 1556, 2746, 3683 |
| the carpet's payout (his first fall) | 5278 | 5284 |
| the shards round (Woody frozen) | 6289–6410 | 6255–6454 |
| second lap 1…4 | 6198, 8468, 9656, 10592 | 6205, 8532, 9721, 10658 |
| Woody caught (the runner's dodges) | 17445 | 17515 |

The lap-two drift of sixty-odd frames is the round's: the tap script
cannot steer the dexterity cursor, so the original's round ran out in
121 frames and the hatch stayed untricked, while the runner won the
port's in 199. Everything the plan does after the fish — the bouquet,
Olga's shower, the cloth, the glass, the bird — has no original to
compare against from this bench; the pistol nap question (the Mother's
tricked-arm MotherSleepLoop and her IsSleeping) is a separate two-click
run.

## Level206, replayed again with the reordered plan

The reordered plan's clicks (the flea blanket before the harpoon and the
pad), 18,072 frames: the neighbour's routine 1…13 of the second lap at
9837 … 14941 on the original against 9838 … 14953 on the port, the
cushion's payout 11064 against 11068. The flea blanket's take landed on
neither side (Woody was still in the pipe; the tap and the click both
un-hid him and went nowhere), so the rabbit never reached the pad on
either, and the original's run ended at 15095 in the denture dexterity
round the bench cannot steer. The pad-and-harpoon path is the port's
plan run alone (17/17) until a replay lands the blanket.

## Level212, replayed with the three-ruby plan

15,204 frames: the neighbour's first five steps at 445, 1046, 1958, 3175,
4266 on the original against 447, 1048, 1960, 3178, 4269 on the port.
Then the spike plate: a dexterity search item, which the tap script
cannot steer — the original's round ran from 4234 to 4579 and lost, and
its game ended at 4691; the runner won the port's in 72 frames and went
on. The rubies, the pair's second coin and the boat slot's coin are the
port's plan run alone (28/28), as 214's fish and 206's rabbit are: every
Season-2 plan that passes through a dexterity round is verified on the
original only up to it.

## Level113's electric trap: the door owns the click

A three-tap run on the original — the cable at 535, the tatter at 1069,
the trap with the cable at 1669 (frames from StartGame): the tatter's
prime played (Woody locked 1608–1758 at the trap's foot), the trap tap
moved nothing, and the neighbour's basement visit caught him at 3225.
The port replays the same three clicks to the same end (caught 3226):
the basement back door's box hides the trap's from the click ray on
both, as the plan's geometry note said. The plan no longer asks for
that coin.

## Level214's pistol nap: not reached, but the regular nap measured

Two short runs on the original (the ammo at 1500, the pistol with the
ammo at 4000 and again at 4300, the deck chair at 5000): Woody walked to
the pistol's foot (1.0, 0.5) and stood, twice, and to the deck chair's
foot (5.1, 0.2) and stood — the first click on a walk-up item from a
walk ends in a stand on the original exactly as the port's first click
does (the runner's second click is what fires the port's use), and a tap
that lands mid-walk is only a re-target. The Mother's IsSleeping flag
(state.js reads it now) went up at 3681 and down at 7158 — her regular
nap, 61.3 s to 119.3 s — against the port's bar window 61.5 s to
119.3 s. The tricked-arm nap after his pistol play stays an open
question; the plan's cabin raid (two legs) waits on it.

## The injector, retired for now

Three injected Drawer clicks on Level113: one stalled Woody at the
drawer's foot with MovingUp set and no take (a tap takes), two killed
the game thirteen frames into the walk. The injector mirrors
Woody.CheckMouseClick including its second ProcessMoveInput when itemAux
is a Door (cs:666-669); whatever it gets wrong there is not worth the
chase while taps land and the pinned clock aligns them. Tap mode is the
reference for every replay above.

The port's side of the same question, probed headlessly (a three-leg plan:
the ammo, the pistol during her first nap, a wait): the regular nap runs
61.4–119.3 s on the MotherSecondUse stamp (indices 1…9 inside the bar's
[0, 10) window, progress 0 → 1); his pistol play at 161 s sends her to
hit him, and her return at 177.7 s is ForceSleepAfterTrick's
MotherExtraUse (MotherSleepBehaviour.cs:85-88, the [2, 11) window):
IsSleeping and the bar from 179.5 s to 237.5 s, a second full nap. The
bar-less MotherSleepLoop seen in the 214 plan run is ForceSleep's tricked
arm (cs:79-82: MotherUseTrickedAnimation, no stamp), reached only when
his play lands while she already sleeps; which stamp the original's bar
reads there is the part still unmeasured.
