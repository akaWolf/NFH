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

## Open: the guest's graphics buffers

The player runs on 7.1 where it would not on 9, but the app process
cannot get a graphics buffer in any QEMU configuration tried, and the
game dies once Unity asks for its surface:

| guest | app-side failure |
|---|---|
| 9.0, SwiftShader | `android.hardware.graphics.mapper@2.0-impl.so` — "not accessible for the namespace" (Treble keeps vendor HALs away from apps) |
| 7.1, virtio-gpu + virgl | `gralloc.gbm.so` — `libdrm.so` not found inside the app |
| 7.1, SwiftShader | `Gralloc1On0Adapter: gralloc0 register failed`, then the game stops |

SurfaceFlinger itself is fine in all three (GLES 3.1 through virgl on
the host GPU, or GLES 2.0 through SwiftShader) — it is only the app
process that cannot map buffers. The next thing to try is the AOSP
emulator's own x86 system image (its goldfish gralloc is built for
exactly this) or Waydroid, whose container shares the host's gralloc.

Everything else in the chain is proven and scripted: the machine boots
unattended, adb and a root console are up, the game and its 402 MB OBB
install, and Frida — running on the developer's laptop, through an ssh
tunnel — spawns the game, injects into its 32-bit process and hooks
native code there (that is how the failures above were traced).

`probe.js` is written against that access but has not run yet: it walks
libmono to `Assembly-CSharp`'s `GameInfo`, and libmono is only loaded
once the player itself starts.
