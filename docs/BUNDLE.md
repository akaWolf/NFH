# Neighbours from Hell — the desktop port

A source port of the mobile Unity remaster (Season 1 "At Home" and
Season 2 "On Vacation") rebuilt against the game's own decompiled code.

## Running

1. Put the game's data next to the `nfh` executable — either form works:
   - the Season 1 `.apk` **and** its `main.*.obb`,
   - or the `.xapk` (the APKPure wrapper holds both),
   - Season 2's `.xapk` (or apk+obb) too, if you have it — optional.
   The game data is **not** distributed with this port; it is extracted
   from your own copy on the first start.
2. Start `nfh` (double-click, or from a terminal to watch the one-time
   extraction — it takes a few minutes and produces `textures/`,
   `audio/`, `strings/`, `fonts/` beside the executable).
3. Play. Season 1 is required (it carries the menu); without Season 2 its
   episodes stay unplayable.

## Controls

- **Left click** — walk, use items, all menu buttons
- **Esc** — in-game menu (pause), skip the splash / title cards
- **Tab** — sneak; **1–9** — pick an inventory slot
- Fullscreen: OPTIONS → the FULLSCREEN checkbox

Settings and progress live in `~/.local/share/nfh/prefs.json`
(`NFH_PREFS` overrides the path; `NFH_ASSETS` points at an asset
directory somewhere else).

## Source

Built from the NFH port repository — see its README for the project
layout, the parity-audit reports and the test suites.
