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
- `gauge.py <video> <start> <dur>`: the PC NFH2 anger gauge (the bar at the
  left of the 720p frame) as fill % per second — its jumps are the tricks'
  amounts, its plateaus the decay (~0.4 %/s).
- `lives2.py <video> <start> <dur> <x0> <y0> <w> <h> <prefix> [T] [white|red]`: the
  PC NFH2 lives counter (top right) binarized and clustered per second — a
  cluster change is a lost life; used to find the catches in a let's play.
