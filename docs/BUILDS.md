# Builds on disk, and which one this project targets

Three artifacts of *Neighbours from Hell: Season 1* (`com.nordigames.nfh`) are
kept here. They are **not** interchangeable: one of them is the only version that
can be reverse engineered with the tooling in `tools/`.

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

## Conclusion

**1.5.5 is the base for this project, and it is the last Mono build.** That is
why it yields 33.9k lines of readable C# and byte-exact level data, and why
1.5.14 cannot replace it.

1.5.14 is worth keeping only as a source of newer content or assets in modern
texture formats. Reading it needs a SerializedFile v22 parser — installing
UnityPy would be cheaper than extending `unityser.py`.
