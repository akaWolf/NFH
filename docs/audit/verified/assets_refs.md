# assets_refs — verified (asset-name resolution, pass-6 back-references)

Claims received: 4 (pass-4 F9–F12) + 8 (pass-6 (c)) + 8 (pass-6 (d)) + 2
(pass-6 (a)/(b) marker groups) + 1 (coordinator: past-the-end frames / wrap
mode) = **23**.
CONFIRMED-FIXED **14** (F9, F10, wrap+HideItem, d5, the 8 (c) references, 2
marker groups) · CONFIRMED-DOCUMENTED **5** (d1, d2, d3, d4, d7) · REFUTED
**1** (F11; plus the wrap claim's "20 idles" scope) · already-documented
**3** (F12, d6, d8).

Everything below was re-verified against `src/Assembly-CSharp` and the level
data by this instance (the previous instance's Part A landing included);
`tests/checks/assets_refs.py` (32 checks, ~4 s, no recording) guards it.

## Part A — the landing (verified, kept)

### F9 (HIGH, FIXED) — animation sheets resolved like `Resources.Load`
- C#: `AnimationInstance.LoadTexture` (AnimationInstance.cs:130-143):
  `SheetTexture = Resources.Load(basePath + TextureFileName)`, callers pass
  `BaseAnimationPath` verbatim (ItemAnimationController.cs:14-27,
  PawnAnimationController.cs:139-147, 205-208). `Resources.Load` indexes the
  ResourceManager container in `globalgamemanagers` (class 147; lower-cased
  path → PPtr, `tools/extract_gui.py container()` walks it) — case-insensitive,
  a multimap whose first entry answers a duplicated path.
- Port before: `Anim.sheet = basename(path)`, so the TextureCache's flat name
  lookup landed 23 Season-2 references (18 level/sheet pairs) on a same-named
  twin. After: `tools/export_level.py resolve_sheet_textures` resolves each
  path through the container into the extraction's collision-numbered PNG
  name and stores it as `SheetTexture`; `runtime/scene.py Anim.__init__`
  (lines 34-47) reads it, falling back to the basename for old exports.
- Numbers (both seasons re-derived): 12374 sheet references — S1 5869
  (5709 same as basename, 0 renamed, 160 null), S2 6505 (6385 same, 118
  renamed: 23 collision-numbered + 95 case-only, 2 null). The 23:
  L201 ms_0000~7; L202 ms_0000~8, sub_takeshark~2, sub_takesub~2; L204
  jade~2; L206 F_Fifi~2 x6, F_Jump~2; L207 bucket~2; L208 statue~2; L211
  phone~2; L212 bar~2, bull~2; L213 bull~3, controls~2, picnic~2,
  tortilla~2; L214 mat~2, pistol~2. The case-only 95 were already found by
  the cache's case-insensitive table.
- Container duplicates: 7 paths in S1, 9 in S2 (bar_left_hnonly, bar_mid,
  bar_mid_hnonly, mutter_dis_001, progress_back, progress_front,
  abrechnungsscreen; S2 adds n_answer_phone and n_bull_back_crash, each a
  Texture2D followed by its pattern TextAsset) — the Texture2D entry is
  first in every one, so `(Texture)Resources.Load` never hits a cast failure.
- Render-verified headless (camera parked on the sprite): L212 LiveBull now
  the black bull in its pen (bull~2 1011x356) instead of a blown-up corner
  of the 109x72 bubble icon; L213 LiveBull bull~3; L202 Rocks the 512x256
  rocks instead of L211's 1402x980 deck rail squeezed into a strip; L201 /
  L211 unchanged. Old-vs-new pairs in /tmp/as/pair_l202.png, pair_l213.png.
- Level diffs contain only the intended keys (structural diff of all 37
  files vs HEAD): SheetTexture added 12374 (10254 Pawn + 2120 Item
  controllers); ItemTipIcon → `{'texture'}` 469 (TrickItem 282, SearchItem
  185, Drawing 1, Rake 1); FenceTextures 8 (4 levels); MusicPlayer clip
  PPtrs → `{'clip'}` 456; Rottweiler MediumLaughs/BigLaughs 180; hud-section
  textures renamed 153 (AlternateBackground bar_mid~2 x14, MainBackground
  bar_mid_HNonly~2 x31, MotherHUDProgressFull Mutter_dis_001~2 x15,
  NewScoreboard abrechnungsscreen~2 x31, RottweilerOnlyBackground
  bar_left_HNonly~2 x31, TrickCameraBackground camera~2 x31) + WhistlingSound
  clip x31; quads texture names 22 (numbered or sanitised: ms_0000~3/~9/~2/
  ~10, workbench_ms~2, book_ms~2, open_0000~2, `trashcan_me (2)` →
  `trashcan_me__2_` ...); Camera (35) and AudioSource (250) component data
  from `tools/scene.py r_camera / r_audiosource`. Nothing else changed.
- The null sheets (162): the port keeps the animation (`scene.py:1884`
  filters on `sheet_path`, not `sheet`) and `render.draw_sprite` draws
  nothing for `sheet is None`; the AnimPlayer still advances and fires frame
  sounds. C#: `LoadTexture` logs "could not load" and keeps the instance;
  `OnGUI` (AnimationControllerBase.cs:177-188) still calls `Refresh()` for
  a null sheet — the else-branch exists for the async loader
  (`LoadTextureAsync`, cs:151-162), so a null `SheetTexture` never stalls an
  animation. Assumption recorded: `Graphics.DrawTexture(rect, null, ...)`
  draws nothing rather than throwing (if it threw, `Refresh` would abort
  before advancing and the async-loading items would freeze on every level
  load — the design implies it does not). Which strips: S1's
  `Textures/Items/Door/Back/Mother/M_appear|M_disappear` on DoorBack01-03
  of L101-L114 (160; the file lives at `textures/items/doornfh2/`; S1 has
  no Mother pawn, so `MotherDoorBackEnter/Leave` never play) and L213
  BoatPicnic's `BoatPicnic/boat_unmount|boat_rent` (2; the files live under
  `boatrent/`; no code path plays that item's UseNormal/Extra1). Old port
  drew textures/s1/M_appear.png (424x644) for the S1 strips — dead data
  either way.

### F10 (MEDIUM, FIXED) — Texture2D / AudioClip PPtrs carry the extraction's number
`_resolve_asset_ref` (tools/export_level.py:262-286): class 28 → the
collision-numbered PNG name via `_extract_texture_names()` (the exact
numbering loop of `extract_textures.py`: `m_Name` sanitised, `~N` on
repeats in `serialized_files()` order); class 83 → the WAV name via
`_extract_audio_names()`. Verified on disk: `bar_left_HNonly~2` is the
145x127 the HUD rect wants, `Mutter_dis_001~2` the S2 mother face. Quads
go through `_quad_texture` (renderer → material → `_MainTex` PPtr → the same
table). Check: `F10:` lines.

### F11 (LOW) — REFUTED
The two frame-sound names that collide in the audio extraction
(`but_hover1`, `na_slip_up1`; 208 S1 / 443 S2 distinct FileNames checked
against 14 / 23 collision families) extract to byte-identical twins
(md5 07aa5dc3… and 990f3a7a… for both files); `audio_out._load`'s flat
lookup is exact. The other two "families" (na2_scared1, na2_shout3pool)
are format variants of one clip (.fsb + the fsb_to_ogg output). Check:
`audio twins:` lines.

### F12 (LOW) — already documented
`viewer.texture_dirs` docstring: the season order is fixed once per
session by any s2 path (93 shared names differ between the seasons).

## Coordinator item — a frame past its sheet is drawn by the texture's wrap mode (CONFIRMED-FIXED, claim's scope corrected)
- C#: `DrawAnimation` (AnimationControllerBase.cs:153-170) builds the source
  rect from `CurrentFrame` with no bounds check: `y = 1 - (frame/cols+1)/rows`
  drops below 0 once `frame >= cols*rows`; `Refresh` (cs:102-141) keeps
  advancing a Single that ended with nothing set after it (`ReachedEndFrame`
  is `CurrentFrame > EndFrame`, AnimationInstance.cs:197-204;
  `StopSingleAnimation` cs:218-249 finds no sequence, the delegate returns
  false, `SwitchToStandAnimation` is empty on item controllers) — so the
  out-of-range rect is sampled by `Texture2D.m_TextureSettings.m_WrapMode`
  (Repeat wraps V modulo 1: the row wraps; Clamp pins V to 0: the texture's
  bottom edge row stretched over the cell). Pattern animations park on the
  last entry instead (`UpdateCurrentFrame` cs:228-234). Port before:
  `draw_sprite` returned False for `row >= rows` — the sprite vanished.
- Scope, corrected: the coordinator's "20 items on L207 carry a 1x1 idle
  played as a Single" is not what the data says — those items have
  `UseAnimationType=true` and idle `Type=Looping`, so `PlayItemAnimation`
  → `PlayAnimationDirectly` (TrickItem.cs:1018-1039) loops them (frame 0
  forever); over all 31 scenes 218 item idles are played looping, 1 as a
  bare range that runs past (L202 Rake). What actually vanished was
  **L207's BeachChair (HideItem)**: 23614 past-the-end draws in one trick
  run — a port bug, not the wrap: `HideItem.InternalUse` (HideItem.cs:42)
  and `Leave` (cs:75-78) use `PlayAnimationDirectly`, the port used
  `play_single` (world.py `Pawn.hide`/`unhide`), forcing the Looping
  `beach_chair` idle into a Single that ran past its 1x1 sheet after 1 s.
  Fixed to `play_directly` (2 lines). Genuine past-the-end draws that
  remain in a run: `W_Take_Down` (TakeDownNFH2, 4x3, frame 12 for one
  period), i.e. every Single a delegate accepts without switching.
- Fix: `tools/texture.py read_texture2d` parses `m_WrapMode` (the fourth
  m_TextureSettings field, line 59-60; `Texture.wrap`, `wrap_name`);
  `tools/extract_textures.py` writes `wrap.json` `{png name: 'repeat'|
  'clamp'}` next to the PNGs with the same collision numbering
  (`--wrap-only` rewrites just the sidecar; `run.sh` runs it for an old
  extraction); `runtime/render.py TextureCache` loads each directory's
  wrap.json (`wrap_mode(name)`), `draw_sprite` emulates: Repeat → `row %=
  rows`; Clamp → SDL src rect `(col*tw/cols, th-1, tw/cols, 1)` (the last
  PNG row: `texture.decode` flips Unity's bottom-up rows); no index → draws
  nothing as before. Counts (`wrap.json`, every readable Texture2D): S1
  1253 clamp / 325 repeat; S2 1743 clamp / 692 repeat. beach_chair,
  W_Take_Down, W_put_eel, fridge_open, bull~2, S1 ms_0000: repeat; board,
  towel, bull (icon), W_Door_Back_Enter, Sofa_ms, S2 ms_0000: clamp.
- Checks: `wrap.json: beach_chair Repeat, board Clamp`, `past-end Repeat:
  frame 7 of a 1x1 -> frame 0` (src (0,0,256,256)), `past-end Clamp: frame
  3 of a 1x1 -> the last PNG row` (src (0,63,128,1)), `HideItem.Leave:
  beach chair idle loops` (mode looping, frame 0 after 3 s — 'single' /
  frame 3 on the old code).

## Part B — pass-6 back-references

### (c) unreferenced game logic — 8 defs, all now referenced (verified line by line)
| def | reference (verified) | state |
|---|---|---|
| world.py `Pawn.goto` / `goto_zone` | Pawn.MoveToLocation cs:394-421, MoveToGoal cs:428-441/450-455, InternalMoveToGoal cs:475-486, ConstructLocationPath cs:545-552, BuildPathToTarget cs:729, AdjustEndMoveInZoneArea Helpers.cs:125-136 | already carried (previous instance) — verified |
| `Pawn._face_towards` | Pawn.cs:1109 (`WasMovingLeft`), 1173-1179 (Walk_Right/Left) | carried — verified |
| `Pawn.walk_speed_scale` | Pawn.cs:869-880 (Speed / SpeedSneaking under SneakFlag; 0.65 at cs:204) | carried — verified |
| `Pawn._door_anims` | Woody.cs:452-463, Rottweiler.cs:363-373, Mother.cs:63-73, Olga.cs:94-104, Door.cs:85-139, Pawn.cs:1615-1635 | carried — verified |
| `Pawn._leave_played` | Door.cs:180-195 (OnAnimationEnded *Leave cases), Pawn.cs:1682-1688 | carried — verified |
| `World.start_routines` | ActionManager.StartFirstAction cs:103-110; callers Rottweiler.cs:927, Mother.cs:83, Olga.cs:36 | carried — verified |
| `World._score` | GameInfo.CalculateScore cs:392-431, called from FinishGame cs:370; AngryCountTicks cs:396-398/416, NFH2Path cs:394 | **added** |
| scene.py `Level.zone_at` | Pawn.cs:403-404, 698-701; overlap census re-derived: 10 pairs (L208/L209 Zone05 over Zone03/04 by 1.73/1.87, L210 Zone03/04 0.53, L213 0.02/0.08, intros 0.12); every zone box z=-0.525, depth 2 | carried — verified |

### (d) claimed equivalences
1. **`_build_graph` "Exactly ZoneController.Start()" — CONFIRMED-DOCUMENTED** (docstring already
   corrected by the previous instance; refined here). ZoneController.cs:16-27
   keeps `(!Locked || TemporalLock)`; the port drops `d.locked`. Data: 22
   TemporalLock doors, 20 also Locked, all in s1/Intro101-103; **0 in the 28
   playable levels**. In the intros the original keeps the edge but
   `GetDoorBetweenZones` demands `!Locked` (Helpers.cs:194-205) so
   `LinkNodes` returns false (cs:245-248) → null path; the port has no edge →
   None — the same result for every ordered zone pair of the three intros
   (Intro101/102: 0 routes; Intro103: only Zone02<->Zone03, unlocked in
   both). Not changed: a faithful fix needs the edge AND the LinkNodes
   refusal, two places, for zero observable effect. Also `disabled`
   (DisableOnStart, Door.cs:64-67): only L214's DoorBack pair Zone03<->Zone05,
   no other route joins them → equivalent whichever Start() runs first.
   Checks: `TemporalLock doors: only s1/Intro101-103`, `IntroNNN: routes
   only through unlocked doors`.
2. **`find_path` BFS vs Helpers.GetShortestPath — CONFIRMED-DOCUMENTED.**
   Script (a faithful Dijkstra port: costs, strict relaxation, list.Remove,
   sort, `zone = list[0]`) over every level and every ordered pair: 786
   reachable pairs, LENGTH equal on all 786; 720 have a unique shortest
   route (every S1 pair, Intro103), 66 have two (S2: 4 per 4-zone level, 6
   per 5-zone level — the opposite corners of the 4-cycles). On those 66 the
   four plausible tie-breaks (stable/reversed sort x scene/reversed zone
   order) agree with the port's pick on 19, 20, 44 and 47 pairs — never all:
   the original's choice hangs on `FindGameObjectsWithTag` order and Mono's
   unstable `List.Sort` (Unity 5.3's classic qsort) — not recoverable. No
   parallel doors between any zone pair. Check: `find_path: 786 reachable
   pairs, length == Dijkstra on all`.
3. **hud font sizing — CONFIRMED, flagged (hud.py not mine).** The pass-6
   formula is wrong: `LevelDataGUIRenderer.CalculateFontSize` (cs:177-183)
   is `((W/1024)+(H/768))*10 - adjust` (`DefaultWidth`/`DefaultHeight`
   are private fields initialised to 1024/768, cs:150-152; the same in
   Control.cs:88-90) and `CalculateFontSizeDescription` (cs:185-191) is
   `W/1024*13 - adjust`. HUD.Start (HUD.cs:335-342) sets: Description 10 @
   800x600 (13 @ 1024x768), Tooltip/ColoredTooltip/Score/ScoreHover 13 (18),
   Rating 15 (20), Time/TimeShadow 18 (23). The port (hud.py:209-240) opens
   the style's face at the size baked in the asset name x H/600: TimeStyle
   acmesa22 → 22 (28 @ 1024x768), TooltipStyle bluehigh18 (S1) / bluehigh16
   (S2) → 18/16 (23/20). So the port's text runs ~20-25 % large and scales
   by height only (at 1920x1080 the original gives 32/35, the port 32/39).
   Fix recipe for the hud owner: keep the face from the asset name, size it
   `int((W/1024 + H/768)*10) - adjust` per HUD.cs:335-342 (Description
   `int(W/1024*13)`), and drop the `(\d+)$` regex — Unity ignores the baked
   size once `fontSize` is set.
4. **`_style_font` size-from-name — CONFIRMED heuristic**, same flag as 3.
5. **`set_tricked_object_hidden` collider toggle — CONFIRMED-FIXED** (landed
   by the previous instance, verified): TrickItem.cs:400-410 flips the
   overlay's Renderer and, for `IsGroundTrick`, its BoxCollider; the port
   sets `clickable` on every Item whose GO is the overlay (`viewer._hit_at`
   honours it). Data: 95 tricked overlays all carry a Renderer; all 57
   ground tricks carry a BoxCollider (107 GroundItem colliders shipped
   disabled), so the C# guards are vacuous here. Check: `ground trick:`.
6. `set_active` — accepted as documented (pass 6).
7. **`_hit_at` "exactly as Physics.Raycast" — CONFIRMED-DOCUMENTED** (near-face
   ordering landed by the previous instance; numbers re-derived from the
   port's own colliders): the ray starts at `ScreenToWorldPoint(mouse)`
   (Woody.cs:708) and runs along camera forward (Pawn.cs:403); the hit
   distance is the collider's NEAR face `z - dz` (`Level._world_box`), and
   of the 667 XY-overlapping item/door collider pairs 113 order differently
   by centre than by near face (L103 Candle -2.01 over Microwave -4.0, a
   ToiletPaper -4.5 over its DoorRight01 -4.02 …). Ties keep scene order
   (PhysX's choice between coincident faces is unspecified). Zone boxes ride
   the same ray (near face -1.525): only 13 shallow colliders overlapped by a
   zone in XY sit behind it (Fence1-3 of L208/209/212/213 at -0.447,
   L214 MotherWait at -0.5), all shipped disabled and never enabled by any
   code path (docstring's "14 incl. DictatorPhoto" corrected: L203's
   DictatorPhoto is above every zone box). Checks: `raycast:` lines.
8. `world.tick(min(dt, 0.1))` — already carries the "viewer decision"
   marker (viewer.py run loop).

### (a)/(b) markers
Added: render.py `Camera` class docstring, `TextureCache.missing`,
`draw_zone_overlay`; scene.py the "helpers: accessors over the export
format" section comment (`_o/_go_of/_transform/_component/_active`).
Already marked (previous instance / others): scene.py `frame_at` ("port
scaffolding"), the loaders (`_add_zone/_add_door/_add_item/_find_game_info`
"loader:"), lookups (`zone_by_pid` …), viewer `_print_state`, `screenshot`,
`texture_dirs`; audio_out `audio_dirs`, `SoundBank`; record.py by its module
docstring. Not touched: hud.py `_tex/_blit/_measure` (another agent's file
— flag).

## Same-class sweep
- Every other Texture2D consumer resolves through `_resolve_asset_ref`
  (numbered) or by container path (bubbles `BUBBLE_BASES`, HUD faces
  `HUD.LoadTextures` paths → extract_gui's path-named files) — no other bare
  `m_Name` lookup remains; the raw objects still hold their PPtrs (GUIStyle
  backgrounds, menu Controls) but nothing in runtime/ reads them by name.
- Frame sounds stay bare names (identical twins, F11); MusicPlayer / laugh /
  whistle clips are numbered.
- `PlayAnimationDirectly` vs forced `play_single`: swept HideItem (fixed);
  the general `PlayItemAnimation` port (`play_item_anim`) already branches on
  UseAnimationType — see the flag on Single-typed idles below.

## README additions (runtime/README.md)

**Asset names.** Every texture and clip the runtime draws is named after the
file the extraction wrote, and the extraction numbers repeated `m_Name`s
`name~2`, `name~3` in serialized-file order. PPtr fields resolve through the
pointer in the exporter; animation sheets are `Resources.Load` strings and are
resolved through the ResourceManager container into `SheetTexture` (null when
the container has no such path — S1's Mother door strips, L213 BoatPicnic's
boat_rent/boat_unmount: the original loads nothing there either, the
animation still runs and draws nothing). Details and counts: tools/README.md
"Asset names", docs/audit/verified/assets_refs.md.

**A frame past its sheet.** `AnimationControllerBase.DrawAnimation` never
checks `CurrentFrame` against the sheet; a Single that ends with nothing set
after it keeps advancing, and `Graphics.DrawTexture` samples the out-of-range
source rect by the texture's wrap mode — Repeat wraps the row back onto the
sheet, Clamp smears the texture's bottom edge row over the cell. `draw_sprite`
emulates both from `textures/<season>/wrap.json` (each PNG's `m_WrapMode`,
written by `tools/extract_textures.py`; `--wrap-only` refreshes an old
extraction; without it such a frame draws nothing). S1 1253 clamp / 325
repeat, S2 1743 / 692.

**Zone graph and paths.** The graph is `ZoneController.Start()` minus the
`|| TemporalLock` arm: 22 TemporalLock doors exist, all in the three S1 intros
(20 of them Locked), none in the 28 playable levels; there `LinkNodes` refuses
the Locked door anyway, so every intro zone pair yields the same null path.
`find_path` is a BFS: the route LENGTH equals `Helpers.GetShortestPath` on all
786 reachable ordered zone pairs; 66 S2 pairs (the opposite corners of the
4-cycles) have two shortest routes and the original's pick depends on
`FindGameObjectsWithTag` order plus Mono's unstable `List.Sort` — the port
takes the first door in scene order.

**Click raycast.** `_hit_at` orders items and doors by the near face of their
world box (`z - dz`), which is what `Physics.Raycast`'s hit distance ranks;
113 of the 667 XY-overlapping collider pairs would order differently by
centre. Zone boxes (near face -1.525) are not in the ray; the 13 shallow
disabled colliders that would lose to them never enable.

**Reference shorthand.** Comments cite the original three ways: the full
`File.cs:NN-MM`; the short `cs:NN` — the file is the one named by the enclosing
class/def docstring (world.py 600+, behaviors.py 260+, scene.py 100+ uses); or
by member name (`AnimationInstance.SetStartFrame`). A grep for `\.cs:\d`
alone undercounts by an order of magnitude.

## Coordinator flags
1. **hud.py font sizes** (d3/d4): see (d)3 — the fix is per-style
   `int((W/1024+H/768)*10) - adjust` (HUD.cs:335-342), not the asset-name
   size; hud.py's `_tex/_blit/_measure` also want "SDL plotting" markers.
2. **Single-typed idles played directly** (items/anim area): the port's
   AnimPlayer starts every sprite in mode 'looping'; for the 2 items whose
   `IdleNormal` instance is `Type=Single` without InfiniteLoop and is played
   by `PlayAnimationDirectly` (UseAnimationType) — L205 SandSculpture
   (288-entry pattern, 8 fps: the original builds the sculpture once in 36 s
   and freezes on the last entry; the port rebuilds it every 36 s) and L208
   Snake (96-entry pattern, HoldOnLastFrame: once, then frame 19; the port
   loops every 12 s) — the port diverges. Chili (L109) is DontPlayIdleOnStart,
   AngryElephant/ParrotLedge are InfiniteLoop (loop in both).
3. **`Graphics.DrawTexture(null)`**: the port assumes it draws nothing and
   `Refresh` continues (the async-loader design implies it); cannot be
   verified from the decompile.
4. **`_hit_at` docstring** now cites this report for the numbers.
5. Two S2 levels' trick plans (L207 CrayFish `take` after the dexterity
   unlock) failed in my probe run — dexterity area, unrelated to these
   changes (they failed identically before the wrap change).
