# PC reference measurements

The PC games' neighbour routine, read off the 100 % walkthrough videos
without touching the game: the PC HUD's top-left thought bubble shows the
neighbour's CURRENT activity (coffee cup, deck chair, watering can …), so
its icon per second is his action sequence — camera-independent, unlike
tracking his sprite (the PC view pans and he is often off-screen).

- `bubble.py <video> <start> <dur> <x0> <y0> <w> <h> <out_prefix> [fps] [T]`
  crops the bubble per frame, clusters the crops greedily (24×24 RGB, L2
  threshold T≈900), writes `<prefix>.json` (t, cluster), `<prefix>_icons.png`
  (one exemplar per cluster) and prints the run-length sequence. Crops used:
  Badinfos 720p Season 1 `10 568 120 70`, Badinfos 720p NFH2 `15 548 150 65`.
- `episodes_s1.json`, `episodes_nfh2.json`: episode start/end in the two
  Badinfos videos (from ffmpeg scene cuts + the episode-selection cards).
- `laps_table.py`: the cluster→activity labels (read by eye from the icon
  sheets), the PC sequences, the lap periods, and the mobile side from the
  port's recordings (`tests/run_tricks.py` state.jsonl: the neighbour's
  `using` items) — writes the detail file behind `docs/PC_LAPS_DETAIL.md`.

Videos live outside the repo in `~/nfh-bench/pcref` (see its README.txt;
`yt-dlp -4` from pcnew). Results: `docs/PC_LAPS.md`.
- `laps_natural.py [--plans <dir>] [--idle <dir>] [level ...]`: the neighbour's
  natural lap (no trick fired) — writes 28 wait-only plans for the harness,
  then pairs the idle recordings' actions with PC_LAPS_DETAIL's bubble spans
  by name (docs/PC_LAPS.md, "Natural laps").
- `amounts.py <video> [episode ...]`: the NFH2 trick amounts — the gauge's
  jumps per second, each labelled with the bubble activity of that second
  (PC_LAPS_DETAIL.md) and scaled to the full bar, beside the level's mobile
  AngerAmounts (the overlays in levels/pc).
- `gauge.py <video> <start> <dur>`: the PC NFH2 anger gauge (the bar at the
  left of the 720p frame) as fill % per second — its jumps are the tricks'
  amounts, its plateaus the decay (~0.4 %/s).
- `lives2.py <video> <start> <dur> <x0> <y0> <w> <h> <prefix> [T] [white|red]`: the
  PC NFH2 lives counter (top right) binarized and clustered per second — a
  cluster change is a lost life; used to find the catches in a let's play.
- `thermo.py [video]`: the Season 1 thermometer (the neighbour's anger meter,
  bottom-left): the mercury column at 10 Hz per episode, its full holds and
  full-to-empty durations. The mercury drains at 8.3–12.9 %/s per level (E01
  ≈ 6.1) — a drawing rate the PC overlays carry as PCThermometerDrain; the
  tick meter behind it is the data's 4.23 %/s (docs/PC_FIDELITY.md §7).
- `gamedata.py <gamedata.bnd> list|cat|grep|tags …`: the PC original's data archive
  (a plain ZIP of XML and TGA: the seasons' level folders with their level.xml,
  the animations) — the PC side as data, once a copy of the game is at hand;
  everything else here reads the PC off video.
