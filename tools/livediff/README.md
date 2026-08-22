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

What is left is the input half: `GameInfo.Update` only ticks inside a
level, so the recorder returns no frames until the game is driven from
its title screen into one. That is the same scripted-input work the diff
needs anyway — the plan above — rather than a new obstacle.
