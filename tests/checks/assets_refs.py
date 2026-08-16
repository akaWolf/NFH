"""assets_refs: asset-name resolution (docs/audit/verified/assets_refs.md).

Guards F9 (animation sheets resolved through the ResourceManager container
into the extraction's collision-numbered PNGs — bull~2 instead of the 109x72
bubble icon), F10 (Texture2D PPtrs numbered the same way in the HUD/
ProgressBar sections), the null-sheet handling (a Resources path the
original cannot load keeps its animation but draws nothing), the season
order of the clip search path, and TrickItem.SetTrickedObjectHidden's
collider toggle. The pass-6 back-reference items ride along: the zone
graph vs ZoneController.Start (TemporalLock), find_path's length vs a
faithful Helpers.GetShortestPath, the click raycast's near-face ordering,
and the frame-sound name twins. Everything here is data-level plus an SDL
offscreen TextureCache resolution, so it needs no recording.
"""
import glob, hashlib, json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, 'runtime'))

# (level, GameObject name, animation, expected SheetTexture, expected PNG
#  size, whether the port builds a sprite for it — SearchItems (FifiHarpoon,
#  IceBucket) get none today and Washbucket's object ships inactive, so those
#  three are asserted on the JSON only)
SHEETS = [
    ('levels/s2/Level212.json', 'LiveBull', 'N2TrickItemIdleNormal', 'bull~2', (1011, 356), True),
    ('levels/s2/Level213.json', 'LiveBull', 'N2TrickItemIdleNormal', 'bull~3', (1059, 310), True),
    ('levels/s2/Level202.json', 'Rocks', None, 'ms_0000~8', (512, 256), True),
    ('levels/s2/Level206.json', 'FifiHarpoon', 'N2TrickItemExtra1', 'F_Jump~2', (780, 549), False),
    # one name, two sheets: the fork resolves per level
    ('levels/s2/Level207.json', 'IceBucket', 'N2TrickItemIdleNormal', 'bucket~2', (64, 32), False),
    ('levels/s2/Level214.json', 'Washbucket', 'N2TrickItemIdleNormal', 'bucket', (128, 128), False),
    ('levels/s2/Level213.json', 'MechanicalBullControls', 'N2TrickItemIdleNormal', 'controls~2', (64, 64), True),
    ('levels/s2/Level214.json', 'CaptainControls', 'N2TrickItemIdleNormal', 'controls', (256, 128), True),
]


def _anim_json(level, go_name, anim_name):
    d = json.load(open(os.path.join(ROOT, level)))
    for o in d['objects'].values():
        dd = o.get('data')
        if o['type'] != 'ItemAnimationController' or not isinstance(dd, dict):
            continue
        if (dd.get('m_GameObject') or {}).get('name') != go_name:
            continue
        for a in dd.get('Animations') or []:
            if anim_name is None or a.get('Name') == anim_name:
                return a
    return None


def _sprite_anim(level, go_name, anim_name):
    from scene import Level
    L = Level(os.path.join(ROOT, level))
    for s in L.sprites:
        if s.name != go_name:
            continue
        for a in s.anims:
            if anim_name is None or a.name == anim_name:
                return L, s, a
    return L, None, None


def _open_cache(level_paths):
    """an offscreen SDL renderer + the viewer's TextureCache, or None"""
    os.environ.setdefault('SDL_VIDEODRIVER', 'offscreen')
    try:
        import sdl2
        from render import TextureCache
        from viewer import texture_dirs
        if sdl2.SDL_Init(sdl2.SDL_INIT_VIDEO) != 0:
            return None, None
        win = sdl2.SDL_CreateWindow(b'checks', 0, 0, 64, 64,
                                    sdl2.SDL_WINDOW_HIDDEN)
        rnd = sdl2.SDL_CreateRenderer(win, -1, 0)
        if not rnd:
            return None, None
        return TextureCache(rnd, texture_dirs(level_paths)), rnd
    except Exception:
        return None, None


def _dijkstra(graph, zone_order, s, t):
    """Helpers.GetShortestPath (Helpers.cs:158-192) with its data flow kept:
    Cost/Previous per zone, strict relaxation (num < Cost), list.Remove,
    list.Sort at equal cost (a stable sort here — the original's Mono sort
    is not, so only the LENGTH is asserted), zone = list[0]. Returns the
    zone sequence start..t or None."""
    INF = 1000.0
    cost = {z: INF for z in zone_order}
    prev = {z: None for z in zone_order}
    lst = list(zone_order)
    cost[s] = 0.0
    zone = s
    while zone is not None:
        for nb, _door in graph.get(zone, ()):
            num = cost[zone] + 1.0
            if num < cost[nb]:
                cost[nb] = num
                prev[nb] = zone
        lst.remove(zone)
        if zone == t:
            path = [t]
            n = t
            while prev[n] is not None and prev[n] != s:
                n = prev[n]
                path.append(n)
            path.append(s)
            path.reverse()
            return path
        lst.sort(key=lambda z: cost[z])
        if not lst:
            return None
        zone = lst[0]
        if cost[zone] >= INF:
            return None
    return None


def _overlap_centre(a, b):
    """the centre of two collider boxes' XY overlap, or None"""
    x0 = max(a[0] - a[2] / 2, b[0] - b[2] / 2)
    x1 = min(a[0] + a[2] / 2, b[0] + b[2] / 2)
    y0 = max(a[1] - a[3] / 2, b[1] - b[3] / 2)
    y1 = min(a[1] + a[3] / 2, b[1] + b[3] / 2)
    if x0 < x1 and y0 < y1:
        return (x0 + x1) / 2, (y0 + y1) / 2
    return None


def _sheet_census():
    """(total sheet references, [(level, sheet path) with SheetTexture
    None]) over every exported level"""
    total, nulls = 0, []
    for p in sorted(glob.glob(os.path.join(ROOT, 'levels', 's*', '*.json'))):
        d = json.load(open(p))
        for o in d['objects'].values():
            dd = o.get('data')
            if not isinstance(dd, dict) or 'BaseAnimationPath' not in dd \
                    or not isinstance(dd.get('Animations'), list):
                continue
            base = dd.get('BaseAnimationPath') or ''
            for a in dd['Animations']:
                if not isinstance(a, dict) or 'TextureFileName' not in a:
                    continue
                total += 1
                if a.get('SheetTexture') is None:
                    nulls.append((os.path.basename(p),
                                  base + (a.get('TextureFileName') or '')))
    return total, nulls


def run(record, check, outdir):
    ok = True

    # -- F9: the exporter's SheetTexture and the port's Anim.sheet ----------
    cache, _rnd = _open_cache(['levels/s2/x'])
    for level, go, anim, want, size, has_sprite in SHEETS:
        a = _anim_json(level, go, anim)
        ok &= check('sheet %s/%s -> %s (json)' % (os.path.basename(level)[:8], go, want),
                    a is not None and a.get('SheetTexture') == want,
                    a.get('SheetTexture') if a else 'no anim')
        if has_sprite:
            L, s, pa = _sprite_anim(level, go, anim)
            ok &= check('sheet %s/%s -> %s (port)' % (os.path.basename(level)[:8], go, want),
                        pa is not None and pa.sheet == want,
                        pa.sheet if pa else 'no sprite anim')
        if cache is not None:
            entry = cache.get(want)
            ok &= check('sheet %s: cache -> %dx%d file' % (want, size[0], size[1]),
                        entry is not None and (entry[1], entry[2]) == size,
                        (entry[1], entry[2]) if entry else 'missing')

    # -- the null sheet: an unloadable Resources path keeps the animation ---
    L, s, pa = _sprite_anim('levels/s2/Level213.json', 'BoatPicnic',
                            'N2TrickItemUseNormal')
    ok &= check('null sheet: BoatPicnic UseNormal kept, sheet None',
                pa is not None and pa.sheet is None and pa.sheet_path ==
                'Textures/NFH2/Items/BoatPicnic/boat_unmount',
                (pa.sheet, pa.sheet_path) if pa else 'dropped')
    if cache is not None and pa is not None:
        from render import Camera, draw_sprite
        try:
            drew = draw_sprite(_rnd, cache, Camera(), s, pa, 0.0, 800, 600)
            ok &= check('null sheet: draw_sprite draws nothing', drew is False)
        except Exception as e:
            ok &= check('null sheet: draw_sprite draws nothing', False, e)

    # -- F10: Texture2D PPtrs carry the collision number -------------------
    from scene import Level as _Level
    L = _Level(os.path.join(ROOT, 'levels/s2/Level202.json'))
    mh = [b.get('mother_hud') for b in L.progress_bars if b.get('mother_hud')]
    ok &= check('F10: MotherHUDProgressFull -> Mutter_dis_001~2',
                bool(mh) and all(v == 'Mutter_dis_001~2' for v in mh), mh)
    hud = (L.hud or {})
    rob = (hud.get('RottweilerOnlyBackground') or {})
    rob = rob.get('texture') if isinstance(rob, dict) else rob
    ok &= check('F10: RottweilerOnlyBackground -> bar_left_HNonly~2',
                rob == 'bar_left_HNonly~2', rob)
    if cache is not None:
        entry = cache.get('bar_left_HNonly~2')
        rect = hud.get('RottweilerOnlyBackgroundRect') or {}
        ok &= check('F10: bar_left_HNonly~2 is the 145x127 the rect wants',
                    entry is not None and (entry[1], entry[2]) ==
                    (int(rect.get('width', 0)), int(rect.get('height', 0))),
                    (entry[1], entry[2]) if entry else 'missing')

    # -- the clip search path follows the level's season -------------------
    from audio_out import audio_dirs
    d2 = audio_dirs(['levels/s2/Level201.json'])
    d1 = audio_dirs(['levels/s1/Level101.json'])
    ok &= check('audio_dirs: s2 level searches audio/s2 first',
                bool(d2) and d2[0].endswith(os.path.join('audio', 's2')), d2[:1])
    ok &= check('audio_dirs: s1 level searches audio/s1 first',
                bool(d1) and d1[0].endswith(os.path.join('audio', 's1')), d1[:1])

    # -- SetTrickedObjectHidden toggles the ground patch's collider --------
    from world import World
    L = _Level(os.path.join(ROOT, 'levels/s1/Level103.json'))
    w = World(L)
    ground = next((it for it in L.items.values()
                   if it.is_ground_trick and it.tricked_object_go is not None), None)
    patches = [it for it in L.items.values()
               if ground is not None and it.go == ground.tricked_object_go
               and it.collider is not None]
    ok &= check('ground trick: a Ground item with GroundItem patches',
                ground is not None and bool(patches))
    if ground is not None and patches:
        w.set_tricked_object_hidden(ground, True)
        off = all(not p.clickable for p in patches)
        w.set_tricked_object_hidden(ground, False)
        on = all(p.clickable for p in patches)
        ok &= check('ground trick: hidden -> patch not clickable', off)
        ok &= check('ground trick: shown -> patch clickable', on)

    # -- the sheet census: every reference resolved, the 162 nulls are the
    #    two Resources paths neither season's container holds ------------
    total, nulls = _sheet_census()
    ok &= check('sheet census: 12374 references, 162 null',
                total == 12374 and len(nulls) == 162, (total, len(nulls)))
    ok &= check('null sheets: S1 Mother/M_appear|M_disappear + L213 BoatPicnic',
                all(p == 'Textures/Items/Door/Back/Mother/M_appear' or
                    p == 'Textures/Items/Door/Back/Mother/M_disappear' or
                    (lv == 'Level213.json' and p in (
                        'Textures/NFH2/Items/BoatPicnic/boat_rent',
                        'Textures/NFH2/Items/BoatPicnic/boat_unmount'))
                    for lv, p in nulls),
                sorted(set(nulls))[:4])

    # -- d1: the zone graph vs ZoneController.Start (cs:16-27) -------------
    #    TemporalLock lives on 22 intro doors only; the graph is built
    #    without the `|| TemporalLock` arm, which must stay invisible to the
    #    playable levels and yield the original's null path in the intros
    tl_levels = set()
    for p in sorted(glob.glob(os.path.join(ROOT, 'levels', 's*', '*.json'))):
        d = json.load(open(p))
        for o in d['objects'].values():
            dd = o.get('data')
            if o['type'] in ('Door', 'Transition') and isinstance(dd, dict) \
                    and dd.get('TemporalLock'):
                tl_levels.add(os.path.basename(p))
    ok &= check('TemporalLock doors: only s1/Intro101-103',
                tl_levels == {'Intro101.json', 'Intro102.json', 'Intro103.json'},
                sorted(tl_levels))
    for lv in ('Intro101', 'Intro102', 'Intro103'):
        L = _Level(os.path.join(ROOT, 'levels', 's1', lv + '.json'))
        routes = [(L.zone_by_pid(a.pid).name, L.zone_by_pid(b.pid).name)
                  for a in L.zones for b in L.zones
                  if a is not b and L.find_path(a.pid, b.pid) is not None]
        want = [('Zone02', 'Zone03'), ('Zone03', 'Zone02')] \
            if lv == 'Intro103' else []
        ok &= check('%s: routes only through unlocked doors' % lv,
                    sorted(routes) == want, routes)

    # -- d2: find_path's length equals Helpers.GetShortestPath's on every
    #    reachable ordered zone pair (786 of them), and both agree on
    #    reachability -------------------------------------------------------
    pairs = agree = 0
    bad = []
    for p in sorted(glob.glob(os.path.join(ROOT, 'levels', 's*', '*.json'))):
        L = _Level(p)
        order = [z.pid for z in L.zones]
        for s in order:
            for t in order:
                if s == t:
                    continue
                port = L.find_path(s, t)
                ref = _dijkstra(L.graph, order, s, t)
                # BuildPath -> LinkNodes finds no door between two zones
                # while the door object is inactive (L214's DisableOnStart
                # DoorBack pair before the CaptainDoor trick) or Locked
                # (the Intro scenes' TemporalLock edges before the tutorial
                # unlocks them; Helpers.cs:194-205, 243-248): FindPath
                # returns null there
                if ref is not None and any(
                        (d.disabled or d.locked)
                        for a, b in zip(ref, ref[1:])
                        for nb, d in L.graph.get(a, ()) if nb == b):
                    ref = None
                if port is None and ref is None:
                    continue
                pairs += 1
                if port is not None and ref is not None \
                        and len(port) == len(ref) - 1:
                    agree += 1
                elif len(bad) < 5:
                    bad.append((os.path.basename(p), s, t,
                                port and len(port), ref and len(ref) - 1))
    # 784 playable pairs + Intro103's unlocked Zone02<->Zone03; the
    # TemporalLock edges (modelled since the tutorial layer) add only
    # null routes — a path through a locked door is refused on both sides
    ok &= check('find_path: 786 reachable pairs, length == Dijkstra on all',
                pairs == 786 and agree == pairs, (pairs, agree, bad))

    # -- d7: the click raycast orders colliders by their NEAR face --------
    try:
        from viewer import Viewer

        class _Fake:
            pass
        f = _Fake()
        f.level = _Level(os.path.join(ROOT, 'levels/s1/Level103.json'))
        c = next(i for i in f.level.items.values() if i.name == 'Candle')
        m = next(i for i in f.level.items.values() if i.name == 'Microwave')
        pt = _overlap_centre(c.collider, m.collider)
        hit = Viewer._hit_at(f, *pt) if pt else (None, None)
        ok &= check('raycast: L103 Candle/Microwave overlap -> Microwave (near -4.0)',
                    hit[0] is not None and hit[0].name == 'Microwave',
                    hit[0].name if hit[0] else hit)
        f.level = _Level(os.path.join(ROOT, 'levels/s1/Level102.json'))
        tp = next(i for i in f.level.items.values() if i.name == 'ToiletPaper')
        door = next((d for d in f.level.doors if d.name == 'DoorRight01'
                     and d.collider and _overlap_centre(tp.collider, d.collider)),
                    None)
        pt = _overlap_centre(tp.collider, door.collider) if door else None
        hit = Viewer._hit_at(f, *pt) if pt else (None, None)
        ok &= check('raycast: L102 ToiletPaper over DoorRight01 -> the item (near -4.5)',
                    hit[0] is not None and hit[0].name == 'ToiletPaper',
                    (hit[0] and hit[0].name, hit[1] and hit[1].name))
    except Exception as e:
        ok &= check('raycast: near-face ordering', False, e)

    # -- a frame past the sheet: DrawAnimation (AnimationControllerBase.cs:
    #    153-170) draws it by the texture's wrap mode — Repeat wraps the
    #    row, Clamp smears the bottom edge row (the last PNG row) ---------
    if cache is not None:
        from render import Camera, draw_sprite
        import render as _render
        L = _Level(os.path.join(ROOT, 'levels/s2/Level207.json'))
        # an item sprite loads with no CurrentAnimation (Sprite.current
        # None); Item.Start's plays — World.__init__ — give the chair and
        # the board their idle (sprite_model)
        from world import World as _W
        _W(L)
        ok &= check('wrap.json: beach_chair Repeat, board Clamp',
                    cache.wrap_mode('beach_chair') == 'repeat' and
                    cache.wrap_mode('board') == 'clamp',
                    (cache.wrap_mode('beach_chair'), cache.wrap_mode('board')))
        copies = []
        _orig = _render.sdl2.SDL_RenderCopy

        def _rc(rnd, tex, src, dst):
            s = src._obj if hasattr(src, '_obj') else src
            copies.append((s.x, s.y, s.w, s.h) if s else None)
            return _orig(rnd, tex, src, dst)
        for go, fr, want, label in (
                ('BeachChair', 7, (0, 0, 256, 256), 'Repeat: frame 7 of a 1x1 -> frame 0'),
                ('PoolBoard', 3, (0, 63, 128, 1), 'Clamp: frame 3 of a 1x1 -> the last PNG row')):
            s = next((x for x in L.sprites if x.name == go), None)
            if s is None:
                ok &= check('past-end %s' % label, False, 'no sprite'); continue
            s.cur_frame = fr
            a = s.anims[s.current]
            _render.sdl2.SDL_RenderCopy = _rc
            copies.clear()
            try:
                drew = draw_sprite(_rnd, cache, Camera(), s, a, 0.0, 800, 600)
            finally:
                _render.sdl2.SDL_RenderCopy = _orig
            ok &= check('past-end %s' % label,
                        drew and copies == [want], (drew, copies))

    # -- HideItem.Leave/InternalUse play the strips DIRECTLY (HideItem.cs:
    #    42, 77): the L207 beach chair's Looping idle keeps looping after
    #    Woody leaves it, instead of running past its 1x1 sheet ------------
    from world import World as _World
    L = _Level(os.path.join(ROOT, 'levels/s2/Level207.json'))
    w = _World(L)
    for role in ('Woody', 'Rottweiler', 'Olga', 'Mother', 'Kid'):
        w.spawn_pawn(role)
    w.woody = w.pawns.get('Woody')
    w.start_routines()
    chair = next((i for i in L.items.values() if i.name == 'BeachChair'), None)
    p = w.players.get(id(chair.sprite)) if chair is not None and chair.sprite else None
    if p is not None and w.woody is not None:
        w.woody.hide(chair)
        w.woody.unhide()
        for _ in range(180):
            w.tick(1.0 / 60.0)
        ok &= check('HideItem.Leave: beach chair idle loops (PlayAnimationDirectly)',
                    p.mode == 'looping' and chair.sprite.cur_frame == 0,
                    (p.mode, chair.sprite.cur_frame))
    else:
        ok &= check('HideItem.Leave: beach chair idle loops', False, 'no chair/woody')

    # -- F11 (refuted): the two frame-sound names that collide in the
    #    audio extraction are byte-identical twins, so the flat lookup is
    #    exact; skipped when the audio was not extracted -------------------
    for name in ('but_hover1', 'na_slip_up1'):
        a = os.path.join(ROOT, 'audio', 's2', name + '.wav')
        b = os.path.join(ROOT, 'audio', 's2', name + '~2.wav')
        if os.path.exists(a) and os.path.exists(b):
            same = hashlib.md5(open(a, 'rb').read()).digest() == \
                hashlib.md5(open(b, 'rb').read()).digest()
            ok &= check('audio twins: %s == %s~2' % (name, name), same)
    return ok


if __name__ == '__main__':
    def _check(name, cond, detail=''):
        print('%-52s %s %s' % (name, 'ok' if cond else 'FAIL',
                               detail if not cond else ''))
        return cond
    sys.exit(0 if run(None, _check, None) else 1)
