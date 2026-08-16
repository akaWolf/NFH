# pass5_video — frame-by-frame numeric comparison against the reference footage

Reference: `/tmp/nfh-ref/mobile1.mp4` (mobile walkthrough of the Unity
remaster, 640×360, 30 fps CFR, 1027.3 s, 30819 frames). Port: the working
tree at 2026-08-18 23:07–23:20 MSK (commit dca965a + uncommitted `runtime/`
edits, `world.py`/`scene.py`/`viewer.py` mtime 23:03–23:06), recorded with
`runtime/record.py` at 60 Hz (`--fps=0`, `state.jsonl` every tick).
Intermediate frames, strips, trackers and recordings live in
`/tmp/nfh-ref/pass5/` (`vid.py` frame decoder, `strip.py` labelled contact
strips, `track.py` median-background blob tracker, `aud.py` audio NCC
locator, `analyze.py` the speed fits, `rec_ext.py` the recorder with
`game.ended`/the neighbour's x added, `rec/{idle160,woody40,catch,hello5}`
the port runs, `s_*.png` the per-frame strips cited below).

`/tmp/nfh-ref/s1walk.mp4` (1629 s) is the 2003 PC original (classic HUD,
different engine) — not the source of truth, not used.

## 1. Coverage map (mobile1.mp4)

Coarse grid: one tile every 10 s in `/tmp/nfh-ref/pass5/cov/sheet_01..03.jpg`
(timestamps burned in); the 1 fps screen-type scan
(`analyze` cell in the transcript) and the visual read give:

| t (mm:ss)      | frames        | content |
|----------------|---------------|---------|
| 0:00–0:09      | 0–270         | title screen ("Touch to continue") |
| 0:09–0:15      | 270–450       | main menu |
| 0:15–0:21      | 450–630       | title cards (Intro101) |
| 0:21–1:08      | 630–2040      | **Intro101** (director messages: scrolling, sending Woody, the front door) |
| 1:08–1:15      | 2040–2250     | score screen (EXCELLENT 1/1) |
| 1:15–1:27      | 2250–2610     | episode selection, title cards "Onwards and Upwards" |
| 1:27–3:08      | 2610–5640     | **Intro102** (marker/picture, the neighbour's anger, "?!") |
| 3:08–3:17      | 5640–5910     | loading, title cards "Expert Moves" |
| 3:17–4:44      | 5910–8520     | **Intro103** (sneak button, wardrobe, marbles) |
| 4:44–4:51      | 8520–8745     | score screen, episode selection ("The First Trick"), loading |
| 4:51.5         | 8745          | **Level101 scene load** (company logo over the house, HUD clock 05:00) |
| 4:59.4         | 8983          | **Level101 in-game start** (`IntroAnimation.StartGame`; see §2) |
| 4:59–7:44      | 8983–13660    | **Level101** — entrance, drawer, bathroom cabinet, wardrobe, superglue on binoculars (10700), fridge/egg → microwave (10970), coin #1 at 11317, sofa cushion (11420), 4/4 tricks |
| 7:44–7:50      | 13660–13800   | score screen (4/4, 99 %), episode selection |
| 7:50–7:58      | 13800–14040   | title cards "TV Afternoon" |
| 7:58–12:55     | 14040–23250   | **Level102** (6/6 tricks) |
| 12:55–13:07    | 23250–23610   | score (EXCELLENT 6/6 100 %), episodes, title cards "Birthday Surprises" |
| 13:07–14:24    | 23610–25950   | **Level103, attempt 1** — Woody caught at the fridge (25642), FAILED board at 25939 |
| 14:24–14:34    | 25950–26240   | loading, title cards |
| 14:34–17:03    | 26240–30580   | **Level103, attempt 2** (6/6, EXCELLENT at 17:04) |
| 17:04–17:07    | 30580–30819   | score screen, loading, end |

Not in the footage: Level104–114 (so **no Level109 sleep bar**), Season 2,
any 30 s idle (no boredom poses), no sneaking segment long enough to fit,
no alerter flinch (Level101 has none; the L103 flinch is fused with the
catch).

## 2. Anchors, artifacts and conventions

- **Scale.** 360 px = 6 world units (orthographic size 3.0 in every playable
  scene) → **60 px/unit** in the reference, 100 px/unit in the port
  (800×600). Speeds are given in units/s; "screen fraction" = units/s ÷ 6
  (screen heights per second — the aspect-free number; the widths differ:
  10.67 units in the 16:9 crop, 8 in the port). Position resolution: 1 px =
  0.017 u; the trackers' fit residuals are 0.012–0.029 u.
- **In-game start S.** `IntroAnimation.DoIntroLogic` (IntroAnimation.cs:255-276)
  waits 2.0+0.9+1.5+1.5+0.7+0.69+0.5 = **7.79 s** (Level101's serialized
  stage times) then `StartGame` sets `CanStart` (Woody, Rottweiler), plays
  `PlayEntranceMusic`, snaps the camera. Four independent anchors put S at
  **frame 8983 (299.433 s)**: (a) the entrance sound `levelstart.wav` onset
  at 299.637 in the audio minus the recording's A/V offset (0.201 s, see
  below) = 299.436; (b) Woody's first run frame at 8998 = S+15 (the 0.5 s
  `EntranceTimer`, Woody.cs:223-229); (c) the HUD clock flips 04:59→04:58 at
  9013 = S+30 (`(int)TimeSeconds`, HUD.cs:1124; decrement from S+1,
  GameInfo.cs:237-243); (d) the neighbour's first Walk frame at 9030 = S+47
  (`DelayStart` 1.5 s = 45–46 frames + one Update→OnGUI frame,
  Rottweiler.cs:916-925). Scene load (video) is 8745 = 291.500 s, so
  load→StartGame = 7.93 s (7.79 + the seven `WaitForSeconds` latencies).
  Port time t maps to reference frame `8983 + 30·t`.
- **A/V offset (reference artifact).** The audio lags the video by 0.20 s:
  the level scene appears at 8745 (291.500 s) while `MusicPlayer.Start`'s
  clap (`jingle_levelstart`, MusicPlayer.cs:43-51) starts at 291.701 s
  (NCC 0.996); the entrance sound gives 0.204. Audio→audio intervals are
  exact; audio→video times are corrected by −0.20 s.
- **Frame pacing (reference artifact).** The recording is CFR 30 but the
  game/recorder dropped frames: runs of identical frames (e.g. 8990–8993,
  9028–9029, about every other frame in 9013–9033) and a 5-frame hitch at
  8989–8993 during the camera snap. Durations are read from the first
  changed frame, so the resolution is 1–2 frames (±0.03–0.07 s); the HUD
  clock flips exactly every 30 frames over the whole level (9013+30k), so
  the video's time base is real time.
- **Duration tolerance** ±0.07 s (two 30-fps frames) unless the row's
  measurement resolution is stated wider (both ends uncertain ⇒ ±0.1 s).
- **Animation timing rule** (both sides): a single animation shows frame 0
  for one render frame then each following frame 1/FrameRate
  (`animationTime = 0` in InitializeCurrentAnimation, then `+= 1/FrameRate`
  after every advance, AnimationControllerBase.cs:102-150, 380); a
  sequence element after the first shows frame 0 for a full 1/FrameRate
  because ResetAnimationTime runs after PlayNextSequenceAnimation. So a
  first element lasts (N−1)/fps, later ones N/fps; the port's AnimPlayer
  (world.py:260-295 `tick`) does the same and adds one 60 Hz tick per switch.

## 3. Measured quantities

Ref = reference, Port = `state.jsonl` of the named run. Port t=0 is the
StartGame equivalent (CanStart at t=0, EntranceTimer from t=0).

| # | Quantity | Reference value (frames / how) | Port value (run: field) | Tol. | Verdict |
|---|----------|--------------------------------|--------------------------|------|---------|
| 1a | Woody run speed (not sneaking) | **1.99–2.06 u/s** (mean 2.02): least-squares slope of the blob centroid vs t over six static-camera runs — porch 8999–9010: 2.044; hall→drawer 9126–9149: 1.990; hall 9273–9301: 2.041; 9419–9437: 1.999; 9455–9481: 2.002; bathroom 9576–9590: 2.063 (`analyze.py`, `track.py` band y140–215 / 160–236; 119–124 px/s at 60 px/u). = 0.332–0.344 screen-heights/s | **2.000 u/s** (woody40: dx/dt of `woody.x` over 4.8–5.5, 9.9–12.6, 0.55–0.85 s; = 1.25 Speed × 1.6 RunningForceMagnitude, `IsInUrgentMove()=!Sneaking`, Woody.cs:858-861, Pawn.cs:961-975; world.py:653, 1416) = 0.333 screen-heights/s | ±0.03 u/s (fit sd over ≥19 frames) | **within** (the README's "Woody walks at 1.25×0.8 = 1.0" is stale — the code and both measurements say 2.0) |
| 1b | Neighbour walk speed | **0.877 u/s** (fit 9620–9760, sofa→door, 141 frames, cam (−1.667,−1.160), sd 0.029 u) | **0.875 u/s** (catch run: `rott.x` slope 21.5–25.5 s; = 1.25 × 0.7) | ±0.02 | within |
| 1c | Sneak speed | not in the footage (no sneak segment ≥ 1 s with a static camera) | 0.65×0.8 = 0.52 u/s by code | — | n/a |
| 2a | Door transit, Woody, entrance (Zone05 DoorLeft01 → Zone01 DoorRight01): Leave start → far Enter end | **63 frames = 2.100 s** (±0.033): W_Door_Right_Enter sheet frames matched by NCC against the port's 60 px/u renders (`door_enter_frames.npy`; table in transcript): frame 0 at 9011, frames 1–21 at 9012–9073 (3 video frames each = 10 fps; frame 1 two frames, frame 6 five — a hitch), the pawn's own frame from 9074 | **2.117 s** (woody40: `doors_active` WoodyDoorRightEnter 0.883→3.000; = 21×0.1 + 1 tick); the Leave (16 frames 9..24) 0.883→2.400 = 1.517 | ±0.07 | within (Δ 0.017) |
| 2b | Door transit, Woody, hall→bathroom (Zone01 DoorLeft01 → Zone04 DoorRight01) | **63 ± 2 frames = 2.10 s**: 9487 (pawn hides, leave sheet appears — blob 179–200 px) → 9549/9550 (pawn moves left at −4.35 u) | **2.117 s** (woody40: 14.733→16.850) | ±0.1 | within |
| 2c | Door transit, neighbour (Zone02 DoorRight01 → Zone03 DoorLeft01, N_Door_* 20 frames) | **58.5 ± 2 frames = 1.95 s**: 9765 (blob mass 996→2308, the leave sheet) → 9824 (steady 0.87 u/s walk resumes at 523→533 px, 9825–9831; 9817–9823 the enter sheet's standing frames) | **1.917 s** (idle160: RottweilerDoorRightLeave/LeftEnter 26.000→27.917 = 19×0.1 + tick) | ±0.1 | within |
| 2d | Transit start after StartGame (entrance) | **0.933 s** (9011 − 8983) | 0.883 s (woody40) | ±0.07 | within (Δ 0.05; the arrival check `IsAtUseLocation` runs on 0.067 u steps at the phone's 30 fps) |
| 3a | Sofa use sequence SitDown start → SitUp end (SitDown 6@7, SitLoop 11@5, SitRemote 35-entry pattern@8 ×2, SitUp 6@7) | **509.5 ± 1.5 frames = 16.98 s**: SitDown start 9103 (blob change 9102→9103; the sit-down sound 303.776 − 0.201 − 1/7 = 303.432 → 9103.0), SitUp end = first Walk_Right frame 9612/9613 (upper-band tracker: 204.9→208.0 px) | **17.000 s** (idle160: `routines[0].anim` SitDown 3.950 → Walk_Right 20.967; elements 0.717/2.217/4.383/2.217/4.383/2.217/0.867) | ±0.07 | within |
| 3b | same, sound to sound (SitDown frame-1 `na_sitsdown1` → SitUp frame-4 `na_getsup1`) | **16.683 s** (audio NCC peaks 303.776 → 320.459, `aud_events_l101.json`; second lap 351.648 → 368.373 = 16.725) | 16.704 s (port emits at frame-leave: 3.950+1/7 → 20.083+5/7) | ±0.03 | within |
| 4 | Routine lap period, Level101 (sit-down → next sit-down, undisturbed lap) | **47.872 s** (audio: `na_sitsdown1` 303.776 → 351.648); video: SitDown#2 start 351.304 → 10539 → t=51.87 s | **47.900 s** (idle160: SitDown 3.950 → 51.850; walk 5.033 + transit 1.917 + walk 4.883 + PeepLoop 7.217 (73-entry pattern @10) + walk 4.883 + transit 1.917 + walk 5.033 + sit 17.0) | ±0.07 | within (Δ 0.03; the README's "about 35 s" was measured with the fixed double-tick bug) |
| 4b | Lap segments: SitUp end→transit / transit→PeepLoop start / PeepLoop | 5.083±0.05 s (9612.5→9765) / 4.82±0.07 (9824→9969: peep sound 332.491−0.201) / **7.2 s** (peep sounds at pattern 0/38/62: 332.491, 336.245, 338.677 → 10.1 fps; 72 intervals) | 5.033 / 4.883 / 7.217 (idle160) | ±0.07 | within |
| 5 | Routine start delay (DelayStart 1.5 s): StartGame → the neighbour's first Walk frame | **1.567 s** (9030 − 8983; blob 124.5→123.2 px at 9030, static 8994–9029, `s_rott_start_8994_9042.png`) | 1.500 s `state` moving, 1.517 s first Walk frame (idle160) | ±0.07 | within (Δ 0.05 = the original's Update→OnGUI frame; both 1.5 s) |
| 5b | Entrance timer: StartGame → Woody's first run frame | 0.500 s (8998) | 0.500 s (woody40) | ±0.07 | within |
| 6a | Time to the level track (`ingame1_normal`) after scene load / after the clap | **15.02 s** after the clap (audio: 291.701 → 306.720, NCC 0.91) = the 15 s `Invoke("PlayMusic",15f)` of `PlayLevelMusic` (MusicPlayer.cs:71-81) issued from `Level.Start→LoadSettings` (Level.cs:230, 295-297) at load | 15.0 s after **t=0** (world.py:4496-4500, scene.py:1364 `delay = 15.0`, OneTime false in the data; line numbers of the 23:06 working tree) | ±0.07 | see 6b |
| 6b | Time to the level track after StartGame (the port's t=0) | **7.08 s** (audio: 306.720 − 299.637 entrance sound; = 15.02 − 7.93 load→StartGame) | **15.0 s** | ±0.07 | **OUTSIDE (Δ +7.9 s) — port bug: the 15 s is anchored at StartGame instead of scene load** (title cards not modelled); the reference is a first run (OneTime=false is serialized in every scene, so every level load waits 15 s) |
| 6c | Entrance clap (`jingle_levelstart`, 15.0 s) start | at scene load (291.701 audio = 8751; = 7.93 s before StartGame; ends 306.7 = when the track starts) | at t=0 (world.py:4498) | — | **OUTSIDE (shifted +7.9 s)** — same anchor bug |
| 6d | Entrance sound (`levelstart.wav`, 7.78 s, `EntranceSoundSource`) | plays at StartGame (299.637 audio; IntroAnimation.cs:311 → MusicPlayer.PlayEntranceMusic cs:122-130) | **not played** (no `EntranceSound` in scene.py's music dict, no call in world.py) | — | **OUTSIDE — missing sound** |
| 7 | Hello greeting (W_Win frames 15..22 @10 fps, Blocking): first Hello frame → Stand_Down | **21 frames = 0.70 s** (±0.05): pawn's own frame from 9074, crouch/laugh 9075–9095 (`s_hello_9064_9128.png`), Stand_Down at 9096; `wod_laugh1` (Hello frame 0) at 302.752 audio → 302.55 | **0.717 s** to the input unlock (hello5/woody40: Hello 3.033→3.750, frames 15..22), **but Stand_Down only at 3.850**: frame 23 (past EndFrame) is drawn 3.750–3.850 | ±0.07 | duration **within**; the stand switch is 0.083 s late — **port bug (minor)**, see fixes |
| 7b | Hello start after StartGame | 3.067 s (9075) | 3.033 s | ±0.07 | within |
| 8 | Sleep bar timing to the wake-up (Level109) | **not in the footage** | 29 × 1.0 s (tests/run_moments.py) | — | n/a |
| 9 | Coin celebration (HUD `TrickAnim`: 17 frames × 0.08825 s = 1.5 s nominal) | **52 ± 1 frames = 1.73 s**: big coin appears 11317, spins, flies to the top slot, static TrickFull from 11369 (`s_coin_11314_11380.png`); = 17 × 0.1 s because `HUDAnimation.Update` resets `CurrentFrameTime = Times[i]` (no residue carry, HUDAnimation.cs:77-107) so each 0.088 s frame lasts 3 render frames at 30 fps | 1.70 s by the same rule at 60 Hz (hud.py:74-119 `HudAnim.update`: 0.08825 → 6 ticks = 0.1 s per frame; not recorded — needs a completed trick) | ±0.07 | within (rule-identical; not recorded) |
| 10 | Catch → score board (Level103 attempt 1 in the reference; Level101 catch scenario in the port) | **297 ± 1 frames = 9.90–9.93 s**: `jingle_caught` at 854.919 audio → 854.72 → 25642 (dust cloud at 25643), FAILED board at 25939 (`s_catch2_25780_25990.png`) | **9.983 s** (catch run: `game.caught` 27.917 → `game.ended` 37.900; hit set WhirlWoody 0.4 / PunchWoody 3.35 / Whirl 0.5 / ShakeWoody 1.85 / Whirl 0.5 / StompWoody 3.35 + 5 switch ticks) | ±0.1 (different level, the hit set is a random pick — the totals matching to 0.06 s says the same set) | within (Δ 0.06) |
| 11 | HUD clock rate | 1.000 s per displayed second (flips at 9013+30k for the whole level, 30.00 frames apart) | 1.000 s (idle160 `game.time` int flips every 0.9999 s) | — | within |
| 12 | Drawer search (arrival → tooltip cleared = SearchItem close 1.5 s after open) | 9150 → 9205 = **1.83 s** (tooltip yellow-pixel count in the bar, `hud_bottom_9160.png` region) | 5.600 → 7.483 = 1.883 s (woody40 `hud.tooltip` colored→False) | ±0.07 | within (Δ 0.05) |
| 13 | FearShort flinch, boredom poses, sneak, alerter timings | not measurable in this footage (see §1) | — | — | n/a |

Rows measured: 17 (12 quantities + sub-rows); within tolerance: 14;
outside: 6b, 6c, 6d (one root cause + one missing sound) and 7's stand
switch (Δ 0.083 s). Row 10 is a cross-level comparison and is marked so.

### How the reference tracks were made (per row)

- Speeds (1a/1b): `track.py` builds a temporal-median background over a
  static-camera window (cam from the previous instance's mosaic locator,
  `cam_l101.json`, one entry per 3 frames; windows 8994–9306, 9381–9441,
  9450–9510, 9519–9834 are static), thresholds |frame−bg| > 35, takes the
  largest column-run blob in a floor band, converts the centroid with
  `x = cam.x + (sx−320)/60`, and fits x(t) by least squares. The
  centroid wobbles with the walk cycle (fit sd 0.012–0.029 u); the slope is
  unaffected.
- Door frames (2a): the previous instance's `door_enter_frames.npy` (the
  port drawing each W_Door_Right_Enter frame at 480×360 = 60 px/u) aligned
  to the reference by NCC of a static band (offset +80 px, score 0.985),
  then per video frame the best of 22 sheet frames in the door bbox
  (scores 0.966–0.989, idle 0.62–0.87).
- Sounds (3b, 4, 6, 10): `aud.py` normalized cross-correlation of the
  extracted clips (`audio/s1/*.ogg|wav`) against the reference audio
  (22.05 kHz mono); the peaks are the clip starts.
- Tooltip (12): count of yellow pixels in the bar's text region
  (y 306–324, x 140–340).

## 4. Outside tolerance — traces and proposed fixes (no runtime edits made)

### F1 — the level track, the clap and the entrance sound are anchored at StartGame (rows 6b/6c/6d)
- Original: `Level.Start` (Level.cs:217-244) runs at scene load and calls
  `LoadSettings` (cs:230 → cs:295-297) → `MusicPlayer.PlayLevelMusic`
  (MusicPlayer.cs:71-81): first run ⇒ `Invoke("PlayMusic", 15f)`;
  `MusicPlayer.Start` (cs:43-51) plays the `EntranceClap` at the same
  moment. `IntroAnimation.StartAnimation` (cs:86-112, from Level.Start
  cs:236-240) then runs the title cards for Σ stage times = 7.79 s
  (Level101 data: CompanyStaticTime 2.0, CompanyOutGameInTime 0.9, GameTime
  1.5, GameEpisodeInTime 1.5, GameEpisodeTime 0.7, GameEpisodeOutTime 0.69,
  GameOutTime 0.5) before `StartGame` (cs:278-315) sets `CanStart` and
  plays `EntranceSound` through `EntranceSoundSource`
  (`PlayEntranceMusic`, MusicPlayer.cs:122-130 — a separate AudioSource, it overlaps the
  level track for 0.6 s in the reference: entrance sound 299.6–307.4,
  track from 306.7). Reference numbers: clap at load, track at load+15.02 s
  = StartGame+7.08 s, entrance sound at StartGame.
- Port: `World.__init__` (world.py:4496-4500) plays the clap at t=0 and
  arms `_music_timer = level.music['delay']` = 15.0 (scene.py:1364);
  t=0 is the StartGame equivalent (`_entrance_timer` 0.5 s and the routines'
  DelayStart both count from t=0). No EntranceSound at all.
- Fix: export the IntroAnimation stage times (the object is already in the
  level JSON: `IntroAnimation` data — `tools/export_level.py` emits it) and
  in scene.py compute `intro_total = Σ(the seven *Time fields)`; in
  world.py arm `_music_timer = delay − intro_total` (15 − 7.79 = 7.21 s;
  reference 7.08 measured because the seven `WaitForSeconds` add ~0.14 s
  of frame latencies — document that), start the clap at
  `t = −intro_total` (Mix_PlayChannel with a seek/`Mix_FadeInChannelTimed`
  is not available — either skip the first `intro_total` seconds of the
  clip via a pre-cut chunk, or accept and document a 7.79 s later clap),
  and play `EntranceSound` (`mp.get('EntranceSound')` → 'levelstart') at
  t=0 on a second reserved channel (audio_out.py `MUSIC_CHANNEL` is one
  channel; `EntranceSoundSource` needs its own so the track can start under
  it; `StopAllSounds`/`StopEntranceMusic` stop it, MusicPlayer.cs:64-69,
  132-135). Verdict: **port bug** (anchor + missing clip), not a reference
  artifact — the 15.02 s clap→track interval and the 7.08 s StartGame→track
  interval are both audio-domain and exact.

### F2 — the stand switch after a blocking single with a callback (row 7)
- Original: `StopSingleAnimation` (AnimationControllerBase.cs:219-247):
  with no sequence pending, `OnAnimationEnded`/`OnBlockingAnimationEnded`
  run and, when both return false, `SwitchToStandAnimation()` in the same
  Refresh; `Woody.OnBlockingAnimationEnded` returns false in its default arm
  (Woody.cs:343-353) — the reference shows Stand_Down on the frame after
  the Hello's last frame (9096).
- Port: `AnimPlayer._stop_single` (world.py:221-258): `if cb: cb() elif
  stand_hook: ...` — the stand fallback is skipped whenever a callback is
  attached; the sprite keeps `frame = end+1` (W_Win cell 23) for one
  1/FrameRate period (3.750→3.850 in `rec/hello5`, frame logged by
  `rec_ext.py`) until the next expiry re-enters `_stop_single` without a
  callback. Every `play_sequence([...], on_end=...)`/single-with-callback
  path is affected (the Hello, use sequences of Woody's items that end in a
  callback…) by 1/fps of a past-the-end cell.
- Fix: give the callbacks the delegate's boolean contract — after `cb()`
  run the stand hook unless the callback started an animation, a move or a
  finish (the true-returning arms: HasMouseInputStored replay, ShouldPlayFinish,
  the FearShort→FearRepeat loop, Woody.cs:330-353), e.g. compare
  `self.sprite.current`/`self.mode`/the pawn's state before and after `cb()`
  and call `_switch_to_stand` when nothing changed. Verdict: **port bug
  (minor, 0.083 s, one wrong sheet cell)**.

### Documentation to correct (README, not code)
- README "Movement": "Woody walks at 1.25 × 0.8 = 1.0 units per second" —
  the code (Woody.IsInUrgentMove = !Sneaking, Woody.cs:858-861 → the
  Running magnitudes, Pawn.cs:961-975) and both measurements give **2.0 u/s**
  when not sneaking; the port already does this (world.py:653, 1416).
- README "The neighbour's routine": "One lap is about 35 seconds" — it is
  **47.9 s** in both the reference and the current port (35.8 s was the
  double-tick era: sit 8.5 + peep 3.6 instead of 17.0 + 7.2).

## 5. Reference artifacts noted (not port issues)
- A/V offset 0.20 s (audio late) — corrected where audio times were mapped
  to frames.
- Dropped/duplicated frames and a hitch (device pacing); the game's own
  frame rate dipped below 30 (2:1 duplicates in 9013–9033).
- 16:9 crop (10.67 × 6 units per screen vs the port's 8 × 6): screen-width
  fractions differ by 4:3 exactly; the heights agree.
- The touch camera (drags at 9306, 9369, 9439, 9510, 9834, …;
  `SnapToRottweilerImmediate` during the title cards then `SnapToWoody`,
  clamped at MaxX = 1.667) is not comparable with the viewer's camera.
- The mobile tap → the latched tooltip and the move on the same frame
  (9125): no double-tap gate delay was observed in Level101.
