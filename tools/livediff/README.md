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
BridgeRail. Against the port recorded from the same start:

| | |
|---|---|
| frames compared | 3511 |
| mean distance | 0.0036 |
| identical (<=0.002) | the first 963 frames (16.05 s) |
| segments over 0.02 | 3, the longest 72 frames at 0.023, one frame at 0.30 |

What is left is timing at the action boundaries: the port is one to
three frames ahead of the original at each hand-over, and the positions
between them agree. `frames.js` reads the original's own order — inside
a frame each `ActionManager.Update` runs, `Pawn.ProcessMovement` moves,
and a finished action advances (`AdvanceToNextAction`, `StartAction`)
only after that, so the next walk starts on the following frame. The
port's `World.tick` already ticks pawns before routines, which is why
the gap is frames rather than shape.

## Reading the original's state

`state.js` reads by name through Mono's C API (`libmono.so` exports
`mono_class_from_name`, `mono_class_get_field_from_name`,
`mono_field_get_offset`, `mono_runtime_invoke`). Two things it took a
while to learn: `GameObject.GetComponent` is overloaded, and the
by-arity lookup returns the `Type` overload, which crashes on a string —
`mono_method_desc_search_in_class` with `:GetComponent(string)` picks
the right one; and anything that calls into the engine has to run on
the player's thread, which the hook on `GameInfo.Update` provides.
