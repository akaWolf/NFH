# src/ — the decompiled game assemblies (generated, not stored)

This directory holds the C# decompilation of the game's own code
(`Assembly-CSharp`, `Assembly-CSharp-firstpass`, `CoreFramework`) — the
project's source of truth: every line of `runtime/` cites it by file and
line. It is **not stored in the repository** (it is THQ Nordic's code,
decompiled from the user's own copy of the game) — regenerate it locally:

```sh
tools/extract.sh /tmp/nfh-data          # unpack the apk/obb (once)
NFH_DATA=/tmp/nfh-data tools/decompile.sh
```

## The decompiler version is pinned

`tools/decompile.sh` pins **ilspycmd 11.0.0.9375**. The pin matters:
`runtime/` carries thousands of line-number citations
(`Pawn.cs:1378`, `Woody.cs:729`, ...) into exactly the text this ILSpy
version emits. A different ILSpy release shifts the line numbering and
silently degrades every citation, so:

- regenerate with the pinned version only (the script installs it);
- do not re-run the decompilation gratuitously — treat the generated
  tree as read-only reference material.
