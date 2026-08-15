# Builds on disk, and which ones this project targets

Artifacts of both seasons are kept here — `com.nordigames.nfh` (Season 1) and
`com.nordigames.nfh2` (Season 2). They are **not** interchangeable. Each season
has exactly one usable version, and it is the *older* one in both cases:

| season | use | avoid |
|---|---|---|
| 1 | **1.5.5** — Mono | 1.5.14 — IL2CPP |
| 2 | **3.2.5** — Mono | 3.2.13 — IL2CPP |

The rule is the same both times: the last Mono build is the last one that can be
reverse engineered. Everything after it is IL2CPP.

## Inventory

| file | size | sha256 |
|---|---|---|
| `neighbours-from-hell-season-1_1.5.5.apk` | 29 797 968 | `6596e68a…8b327` |
| `main.13.com.nordigames.nfh.obb` | 202 262 345 | `5a57acec…f830` |
| `Neighbours+from+Hell_+Season+1_1.5.5_APKPure.xapk` | 232 415 443 | `ab1abd25…b2579` |
| `Neighbours+from+Hell_+Season+1_1.5.14_APKPure.xapk` | 959 328 593 | `328834cf…a4aa` |

Inside the 1.5.5 XAPK:

| entry | sha256 |
|---|---|
| `com.nordigames.nfh.apk` | `395acdda…9982` |
| `Android/obb/…/main.13.….obb` | `5a57acec…f830` |

Inside the 1.5.14 XAPK:

| entry | size | sha256 |
|---|---|---|
| `com.nordigames.nfh.apk` (base) | 32 881 420 | `929024a2…8640` |
| `UnityDataAssetPack.apk` | 913 489 527 | `c6abed2a…2d97` |
| `config.armeabi_v7a.apk` | 12 600 029 | `5d3c7e89…8010` |

## 1.5.5 loose APK vs 1.5.5 XAPK — the same build

The OBB is **byte-identical** between the two (same sha256), and all 94 APK
entries match by CRC, including `classes.dex`, `Assembly-CSharp.dll`,
`AndroidManifest.xml` and `META-INF/*`.

The loose APK is 253 bytes larger. Those bytes are an **APK Signing Block**
(trailing magic `APK Sig Block 42`) holding one pair with id `0x2146444e`, whose
protobuf payload contains:

- sha256 of the XAPK's inner APK (`395acdda…`), at block offset 125
- sha256 of the OBB (`5a57acec…`), at block offset 46
- `versionCode` 13, and a DER ECDSA signature

i.e. a store integrity stamp that references exactly these two files. Removing
the block and rewinding the EOCD central-directory offset by 253 reproduces the
XAPK's inner APK bit for bit:

```
rebuilt : 395acddac57fb31b2c82d11344efb0bfba822b8755c671c9fd3cdf3f41389982
xapk apk: 395acddac57fb31b2c82d11344efb0bfba822b8755c671c9fd3cdf3f41389982
```

So the loose APK is the XAPK's APK plus a distributor stamp, nothing else.

### Signing provenance — unresolved

Both copies carry a v1 (JAR) signature only, with certificate
`subject=O=DefaultCompany, issuer=O=DefaultCompany` — the identity Unity's
auto-generated debug keystore produces.

This is *not* by itself evidence of tampering, and equally not proof of
authenticity: both files come from the same distributor, so they are not
independent sources. Either the publisher shipped with Unity's default keystore,
or both descend from a common repack. Settling it needs a Play-sourced copy,
which we do not have. What *is* established: no modification exists on top of the
base APK beyond the store stamp described above.

## 1.5.14 — a different game engine, not an update to work from

| | 1.5.5 | 1.5.14 |
|---|---|---|
| versionCode | 13 | 28 |
| Unity | 5.3.4f1 | **2022.3.67f2** |
| scripting backend | **Mono** | **IL2CPP** |
| SerializedFile version | 15 (32-bit header) | **22** (64-bit header) |
| minSdk / targetSdk | 10 / 28 | 24 / 36 |
| packaging | APK + OBB | split-APK (AAB) + Play Asset Delivery |
| tamper protection | none | `libpairipcore.so` |

The 1.5.14 base APK contains no managed assemblies at all — instead
`assets/bin/Data/Managed/Metadata/global-metadata.dat` (3.9 MB), with the code in
`lib/armeabi-v7a/libil2cpp.so` (17 MB) inside the ABI split.

**This breaks the entire approach in `tools/`.** That pipeline recovers the
serialization schema from CIL metadata in `Assembly-CSharp.dll`; under IL2CPP
there is no such file. Class and field *names* are still recoverable from
`global-metadata.dat` with Il2CppDumper, but method bodies are compiled ARM
machine code, so `docs/GAMEPLAY.md` could not have been written from this build.

Content is the same game: `level0` plus `level1`…`level19`, 1861 GUID-named
serialized files (vs 1854) and 311 `.resource` (vs 316). No Season 2 scenes in
either. File sizes differ throughout because the data was re-imported by a much
newer Unity, e.g. `level1` is 251 796 bytes against 205 608.

`unityser.py` accepts version 15 only and will refuse these files by design.

Two smaller notes:

- The bundle carries only `config.armeabi_v7a.apk`. APKPure serves splits per
  device profile and targetSdk 36 obliges 64-bit support, so an arm64 split
  almost certainly exists upstream — its absence here proves nothing.
- The base APK declares `requiredSplitTypes` / `base__abi`, so it will not
  install alone; the set needs `adb install-multiple`.
- 1.5.14 adds ad-tracking permissions absent in 1.5.5: `AD_ID`,
  `ACCESS_ADSERVICES_ATTRIBUTION`, `ACCESS_ADSERVICES_TOPICS`.

## Season 2

| file | size | sha256 |
|---|---|---|
| `Neighbours+from+Hell_+Season+2_3.2.5_APKPure.xapk` | 432 060 714 | `744c563d…d6f0` |
| `Neighbours+from+Hell_+Season+2_3.2.13_APKPure.xapk` | 1 998 152 280 | `4202e937…dfc9` |

Inside 3.2.5 (APK + OBB, versionCode 14, minSdk 10 / targetSdk 28 — the same
old-style packaging as 1.5.5):

| entry | sha256 |
|---|---|
| `com.nordigames.nfh2.apk` | `d829656b…400f` |
| `main.14.com.nordigames.nfh2.obb` | `02fc5a3d…5562` |

### 3.2.5 ships the same code as Season 1

`Assembly-CSharp.dll` is 427 520 bytes in both seasons, and the metadata is
identical: **298 TypeDefs, 2092 MethodDefs, 4068 Fields, the same 285 type
names, and the same method and field names in the same order.** It is one source
tree, built twice.

The only differences are in the string heaps:

- the Google Play license public key (per-app, naturally)
- the versionCode literal, `13` vs `14`
- `Application.loadedLevel` in S1 vs `SceneManager.GetActiveScene().buildIndex`
  in S2 — a one-call modernisation
- two debug-log flags, `googleplay.debug.logs` / `moregames.debug.logs`, present
  only in S2

A naive byte diff reports ~87% of the file differing; that is an artifact. The
`#~` stream is 28 bytes longer in S2, so everything downstream shifts and stops
lining up. Structurally the assemblies are the same.

This retroactively explains why the Season 1 binary carries `Level201Behavior`…
`Level213Behavior`, `Olga`, `Mother`, `Kid` and a pile of Season 2 item names
hardcoded in `ActionManager`: there was never a separate Season 2 codebase. The
season is decided entirely by which scenes ship in the OBB.

**`src/` and `docs/GAMEPLAY.md` therefore describe Season 2 as well.**

### 3.2.5 data reads with no changes

```
exact 4726 / 4726 objects across 17 scenes
types covered: 106
```

Same Unity 5.3.4f1, same SerializedFile v15. 17 scenes: `EmptyEntry`, `Entry`,
`Transition`, and `Level201`…`Level214` — 14 playable levels, bringing the two
seasons to 28 between them.

### Where Season 2 differs mechanically

Read from the level data, not from the code — the code is shared:

| | Season 1 | Season 2 |
|---|---|---|
| `Woody.NFH2Path` | false | **true** |
| zone links | `Door` (12–18 per level) | `Transition` (116 total, 8 plain Doors) |
| `Alerter` | 9 | **0** — no sleeping-pet alarm at all |
| `GroundItem` | 107 | **0** |
| `DexterityComponent` | 0 | **15** — the minigame is Season 2 only |
| extra characters | — | `Olga` 11, `Mother` 9, `Kid` 3 |
| `AngryMeterDecay` | 3.70–4.23 | **0.37** — a ~11× wider combo window |
| compound cap | 2–5, tuned per level | 4 everywhere |
| zones per level | 4–9 | 4–5 |

`GameMode` stays `Classic` in both; it is `Woody.NFH2Path` that selects the
Season 2 branches in scoring and anger — see `docs/GAMEPLAY.md` §7, which already
documents both paths.

`Transition` derives from `Door`, so `ZoneController`'s
`GetComponentsInChildren<Door>()` picks it up unchanged. `tools/zonegraph.py`
matched on the exact type name and needed one fix to accept subclasses; with it,
all 14 Season 2 levels come out connected.

### 3.2.13 — IL2CPP, same as 1.5.14

versionCode 27, minSdk 24 / targetSdk 36, Unity **2022.3.67f2**, split-APK with a
1.95 GB `UnityDataAssetPack.apk`, `libil2cpp.so` (21 MB) plus
`global-metadata.dat`, and `libpairipcore.so` tamper protection. No managed
assemblies. Unusable for this project, for exactly the reasons given for 1.5.14.

Its ABI split is `config.arm64_v8a.apk`, where Season 1's bundle carried
`config.armeabi_v7a.apk` — confirming that APKPure serves splits per device
profile and that the absence of an arm64 split in the 1.5.14 bundle meant
nothing.

## Conclusion

**1.5.5 and 3.2.5 are the bases for this project — the last Mono builds of each
season.** They yield 33.9k lines of readable C# (shared between them) and
byte-exact level data. The IL2CPP successors cannot replace either.

The newer builds are worth keeping only as a source of assets in modern texture
formats. Reading them needs a SerializedFile v22 parser — installing UnityPy
would be cheaper than extending `unityser.py`.
