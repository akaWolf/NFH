"""sprite_model: the item-controller sprite model (docs/audit/verified/
sprite_model.md).

An ItemAnimationController exists from Awake with CurrentAnimation == null
(AnimationControllerBase.cs:13) and OnGUI draws / refreshes nothing until
the first SetAnimation (cs:172-189, 350-371); Item.Start's plays are what
give it a pose (Item.cs:677-719, TrickItem.cs:214-217, SearchItem.cs:91-107,
HideItem.cs:24-30). The port used to build NO sprite for a controller whose
serialized resting pose was NONE (every S2 SearchItem, the ElectricTraps,
L111's WashingMachine, L114's Gramaphone...), so their played strips never
showed and their AnimPlayer hooks never fired; and every idle it did build
started looping regardless of the item's PlayItemAnimation dispatch
(TrickItem.cs:1018-1050). Guards here: the sprite exists with current None,
the load-time plays run through play_item_anim / search_play / play_directly,
`current is None` draws and ticks nothing (SetObjectHidden(false) included),
the AnimPlayer readers survive a None animation, and the L202 RubbishBin
shows Rubbish_Empty after the take.
"""
import glob, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, 'runtime'))

from record import Recorder, DT     # noqa: E402

TRICK_KINDS = ('TrickItem', 'Drawing', 'Rake', 'Toilet', 'Television')


def _rec(level, outdir, name):
    os.environ.setdefault('SDL_VIDEODRIVER', 'offscreen')
    return Recorder(os.path.join(ROOT, level), os.path.join(outdir, name),
                    script=None, seconds=1e9, fps=0)


def _advance(rec, t, seconds, stop=None):
    end = t + seconds
    while t < end:
        rec.tick(t)
        t += DT
        if stop is not None and stop():
            break
    return t


def _world(level):
    from scene import Level
    from world import World
    L = Level(os.path.join(ROOT, level))
    return L, World(L)


def _item(L, name, kind=None):
    return next(i for i in L.items.values()
                if i.name == name and (kind is None or i.kind == kind))


def _player(w, it):
    return w.players.get(id(it.sprite)) if it.sprite else None


def _guard(check, name, fn):
    try:
        return fn()
    except Exception as e:                # noqa: BLE001
        return check(name, False, '%s: %s' % (type(e).__name__, e))


def _controller_census():
    """(season -> (active item controllers with a loadable sheet, of them
    with a sprite)) over every exported level"""
    from scene import Level
    out = {}
    for p in sorted(glob.glob(os.path.join(ROOT, 'levels', 's*', '*.json'))):
        L = Level(p)
        season = os.path.basename(os.path.dirname(p))
        have = {s.go for s in L.sprites if s.kind == 'ItemAnimationController'}
        tot = got = 0
        for o in L.objs.values():
            if o['type'] != 'ItemAnimationController' or 'data' not in o:
                continue
            go = L._go_of(o)
            if not L._transform(go) or not L._active(go):
                continue
            if not any(a.get('SheetTexture')
                       for a in (o['data'].get('Animations') or [])):
                continue
            tot += 1
            got += go in have
        a, b = out.get(season, (0, 0))
        out[season] = (a + tot, b + got)
    return out


def run(record, check, outdir):
    ok = True

    # -- every active item controller with a loadable sheet is a sprite ----
    def census():
        c = _controller_census()
        return check('sprite: every active item controller is a sprite '
                     '(s1 %d/%d, s2 %d/%d)' % (c['s1'][1], c['s1'][0],
                                               c['s2'][1], c['s2'][0]),
                     all(a == b for a, b in c.values()), c)
    ok &= _guard(check, 'sprite census', census)

    # -- L202 RubbishBin: FullAnimation at load, through search_play's
    #    Looping dispatch (SearchItem.cs:68-89, 106) ------------------------
    def rubbish_load():
        L, w = _world('levels/s2/Level202.json')
        it = _item(L, 'RubbishBin')
        p = _player(w, it)
        return check('L202 RubbishBin: Rubbish_Full looping at load',
                     p is not None and p.anim is not None
                     and p.anim.name == 'N2TrickItemIdleNormal'
                     and p.anim.sheet == 'Rubbish_Full' and p.mode == 'looping'
                     and not it.sprite.hidden,
                     (p and p.anim and p.anim.name, p and p.mode))
    ok &= _guard(check, 'L202 RubbishBin: load', rubbish_load)

    # -- L109 Chili: the one DontPlayIdleOnStart item (TrickItem.cs:214)
    #    shares its controller with the Alerter twin on the same object, and
    #    Alerter.Start's SleepSequence (Alerter.cs:48) is the pose — the old
    #    hide-at-load + reveal-on-play stand-in is gone --------------------
    def chili():
        L, w = _world('levels/s1/Level109.json')
        it = _item(L, 'Chili', 'TrickItem')
        al = _item(L, 'Chili', 'Alerter')
        p = _player(w, it)
        return check('L109 Chili: the shared controller shows the sleep loop',
                     p is not None and it.sprite is al.sprite
                     and it.dont_play_idle_on_start and p.anim is not None
                     and p.anim.name == 'ChiliSleepLoop'
                     and not it.sprite.hidden,
                     (p and p.anim and p.anim.name, it.sprite and it.sprite.hidden))
    ok &= _guard(check, 'L109 Chili', chili)

    # -- current None is not Hidden: SetObjectHidden(false) on a controller
    #    that has no CurrentAnimation draws nothing (OnGUI, cs:177-188), and
    #    the None-safe readers hold; the first play sets the animation -----
    def none_not_hidden():
        L, w = _world('levels/s1/Level111.json')
        it = _item(L, 'WashingMachine')
        p = _player(w, it)
        r = check('L111 WashingMachine: no CurrentAnimation at load',
                  p is not None and p.anim is None and it.sprite.current is None
                  and it.sprite.cur_frame is None,
                  (p and p.anim, it.sprite and it.sprite.hidden))
        if p is None:
            return r
        w.set_object_hidden(it, False)          # Item.cs:1984-1995
        for _ in range(30):
            p.tick(1.0 / 60.0)
        r &= check('L111 WashingMachine: SetObjectHidden(false) draws nothing',
                   not it.sprite.hidden and p.anim is None
                   and it.sprite.cur_frame is None
                   and not p.blocking and not p.waiting()
                   and p.current_index() == 0)
        w.play_item_anim(it, 'WasherRed')
        r &= check('L111 WashingMachine: the first play sets the animation',
                   p.anim is not None and p.anim.name == 'WasherRed'
                   and it.sprite.cur_frame is not None
                   and p.mode == 'looping',                # Type Looping
                   (p.anim and p.anim.name, p.mode))
        return r
    ok &= _guard(check, 'current None vs Hidden', none_not_hidden)

    # -- L111 ElectricTrap / WashingMachine, L114 Gramaphone: idle NONE with
    #    HideWhenNotAnimating (hidden AND no animation at load); the tricked
    #    idle / the use strip / the primed pose bring them up ---------------
    def l111():
        L, w = _world('levels/s1/Level111.json')
        trap = _item(L, 'ElectricTrap')
        wm = _item(L, 'WashingMachine')
        pt, pw = _player(w, trap), _player(w, wm)
        r = check('L111 ElectricTrap/WashingMachine: sprites, no animation, hidden',
                  pt is not None and pw is not None and pt.anim is None
                  and pw.anim is None and trap.sprite.hidden and wm.sprite.hidden,
                  (pt and pt.anim, pw and pw.anim))
        if pt is None or pw is None:
            return r
        trap.tricked = True
        w._return_to_idle(trap)                 # TrickItem.cs:697-720
        r &= check('L111 ElectricTrap: the trick shows the spark loop',
                   pt.anim is not None and pt.anim.name == 'ElectricTrap'
                   and not trap.sprite.hidden and pt.mode == 'looping',
                   (pt.anim and pt.anim.name, trap.sprite.hidden, pt.mode))
        w.play_use_item_anim(wm)                # TrickItem.cs:982-994
        r &= check('L111 WashingMachine: the use plays WasherLoop',
                   pw.anim is not None and pw.anim.name == 'WasherLoop'
                   and not wm.sprite.hidden,
                   (pw.anim and pw.anim.name, wm.sprite.hidden))
        return r
    ok &= _guard(check, 'L111 items', l111)

    def l114():
        L, w = _world('levels/s1/Level114.json')
        g = _item(L, 'Gramaphone')
        p = _player(w, g)
        r = check('L114 Gramaphone: sprite, no animation at load',
                  p is not None and p.anim is None and g.sprite.hidden,
                  (p and p.anim, g.sprite and g.sprite.hidden))
        if p is None:
            return r
        g.primed = True
        w._play_primed_animation(g)             # TrickItem.cs:483-493
        r &= check('L114 Gramaphone: primed -> GramaphoneOpen',
                   p.anim is not None and p.anim.name == 'GramaphoneOpen'
                   and not g.sprite.hidden, p.anim and p.anim.name)
        w.play_use_item_anim(g)
        r &= check('L114 Gramaphone: use -> GramaphonePlay',
                   p.anim is not None and p.anim.name == 'GramaphonePlay',
                   p.anim and p.anim.name)
        return r
    ok &= _guard(check, 'L114 Gramaphone', l114)

    # -- L107 Drawing: Drawing.Start hides the controller (Drawing.cs:20)
    #    over a null CurrentAnimation; RottweilerUse unhides and plays
    #    Drawing1 (cs:53-54) ---------------------------------------------------
    def drawing():
        L, w = _world('levels/s1/Level107.json')
        it = _item(L, 'Drawing')
        p = _player(w, it)
        r = check('L107 Drawing: sprite hidden, no animation at load',
                  p is not None and p.anim is None and it.sprite.hidden
                  and p.has('Drawing1') and p.has('DrawingSmeared'),
                  (p and p.anim, it.sprite and it.sprite.hidden))
        if p is None:
            return r
        it.sprite.hidden = False                # Drawing.cs:53
        w.play_item_anim(it, 'Drawing1')        # Drawing.cs:54
        r &= check('L107 Drawing: RottweilerUse shows Drawing1',
                   p.anim is not None and p.anim.name == 'Drawing1'
                   and not it.sprite.hidden, p.anim and p.anim.name)
        return r
    ok &= _guard(check, 'L107 Drawing', drawing)

    # -- Animating=false (TrickItem.cs:1020): PlayItemAnimation never runs,
    #    so L113 Aquarium / L107 MumStatueDummy / L206 DogFifi keep no
    #    CurrentAnimation ---------------------------------------------------
    def not_animating():
        r = True
        for lv, name in (('levels/s1/Level113.json', 'Aquarium'),
                         ('levels/s1/Level107.json', 'MumStatueDummy'),
                         ('levels/s2/Level206.json', 'DogFifi')):
            L, w = _world(lv)
            it = _item(L, name)
            p = _player(w, it)
            r &= check('%s: Animating=false -> no animation' % name,
                       p is not None and p.anim is None
                       and it.sprite.cur_frame is None,
                       (p and p.anim and p.anim.name))
        return r
    ok &= _guard(check, 'Animating=false items', not_animating)

    # -- the load-time dispatch: PlayAnimationDirectly keeps the serialized
    #    Type (AnimationControllerBase.cs:326-329, 350-358): L205's
    #    SandSculpture and L208's Snake carry Single-typed idles — played
    #    once, then parked (the pattern's last entry / HoldOnLastFrame) —
    #    while L202's Rake (a TrickItem subclass) gets its Looping idle ------
    def dispatch():
        L, w = _world('levels/s2/Level205.json')
        sc = _item(L, 'SandSculpture')
        p = _player(w, sc)
        # C_build: a 288-entry pattern at 8 fps — 36 s of build-up, frames
        # 0..7 for 4.5 s each, then parked on 7 (the finished sculpture)
        seen = set()
        for _ in range(40 * 60):
            p.tick(1.0 / 60.0)
            seen.add(sc.sprite.cur_frame)
        a = p.anim
        r = check('L205 SandSculpture: Single idle plays once (36 s), parks on frame 7',
                  p.mode == 'single' and a is not None and a.pattern
                  and sc.sprite.cur_frame == a.pattern[-1] == 7
                  and p.pat_idx >= len(a.pattern) and seen == set(range(8)),
                  (p.mode, sc.sprite.cur_frame, p.pat_idx, sorted(seen)))
        L, w = _world('levels/s2/Level208.json')
        sn = _item(L, 'Snake')
        p = _player(w, sn)
        for _ in range(600):
            p.tick(1.0 / 60.0)
        a = p.anim
        r &= check('L208 Snake: Single hold idle parks (no loop)',
                   p.mode == 'single' and a is not None and a.hold
                   and sn.sprite.cur_frame == a.pattern[-1],
                   (p.mode, sn.sprite.cur_frame))
        L, w = _world('levels/s2/Level202.json')
        rk = _item(L, 'Rake')
        p = _player(w, rk)
        r &= check('L202 Rake (TrickItem subclass): idle looping',
                   p is not None and p.anim is not None
                   and p.anim.name == 'N2TrickItemIdleNormal'
                   and p.mode == 'looping', p and p.anim and p.anim.name)
        return r
    ok &= _guard(check, 'load-time dispatch', dispatch)

    # -- the IgnoreIdleAnimation DoorBacks (Door.cs:209-223): the controller
    #    stays enabled with no CurrentAnimation at load; the pass strip is
    #    the first play, and its end disables the controller (hidden) ------
    def doorbacks():
        L, w = _world('levels/s2/Level211.json')
        ds = [d for d in L.doors if d.ignore_idle and d.sprite is not None]
        r = check('L211 IgnoreIdleAnimation doors: no animation, not hidden',
                  bool(ds) and all(d.sprite.anim is None
                                   and not d.sprite.sprite.hidden for d in ds),
                  [(d.name, d.sprite.anim and d.sprite.anim.name,
                    d.sprite.sprite.hidden) for d in ds])
        return r
    ok &= _guard(check, 'IgnoreIdleAnimation doors', doorbacks)

    # -- render: draw_sprite draws nothing for current None ----------------
    def render_none():
        try:
            import sdl2
            from render import TextureCache, Camera, draw_sprite
            from viewer import texture_dirs
            if sdl2.SDL_Init(sdl2.SDL_INIT_VIDEO) != 0:
                return check('render: current None draws nothing', True,
                             'no SDL')
            win = sdl2.SDL_CreateWindow(b'checks', 0, 0, 64, 64,
                                        sdl2.SDL_WINDOW_HIDDEN)
            rnd = sdl2.SDL_CreateRenderer(win, -1, 0)
            cache = TextureCache(rnd, texture_dirs(['levels/s1/x']))
        except Exception as e:            # noqa: BLE001
            return check('render: current None draws nothing', True,
                         'no SDL (%s)' % e)
        L, w = _world('levels/s1/Level111.json')
        wm = _item(L, 'WashingMachine')
        s = wm.sprite
        s.hidden = False
        drew = draw_sprite(rnd, cache, Camera(), s, s.anims[0], 0.0, 800, 600)
        return check('render: current None draws nothing', drew is False, drew)
    ok &= _guard(check, 'render current None', render_none)

    # -- live: the L202 RubbishBin take leaves Rubbish_Empty on screen
    #    (SearchItem.OnFinishAnimationCompelted, cs:114-119) ---------------
    def rubbish_take():
        rec = _rec('levels/s2/Level202.json', outdir, 'rubbish')
        w = rec.v.world
        it = next(i for i in rec.v.level.items.values() if i.name == 'RubbishBin')
        p = w.players.get(id(it.sprite)) if it.sprite else None
        if p is None:
            return check('L202 RubbishBin: take -> Rubbish_Empty', False,
                         'no sprite')
        t = _advance(rec, 0.0, 5.0)
        pos = rec._screen_of_item('RubbishBin')
        rec.v.handle_click(*pos)
        n0 = len(w.inventory.items)
        t = _advance(rec, t, 20.0, stop=lambda: len(w.inventory.items) != n0)
        t = _advance(rec, t, 1.0)
        return check('L202 RubbishBin: take -> Rubbish_Empty',
                     len(w.inventory.items) != n0 and p.anim is not None
                     and p.anim.name == 'N2TrickItemUseNormal'
                     and p.anim.sheet == 'Rubbish_Empty'
                     and not it.sprite.hidden and it.sprite.cur_frame is not None,
                     (len(w.inventory.items), p.anim and p.anim.name))
    ok &= _guard(check, 'L202 RubbishBin: take', rubbish_take)
    return ok


if __name__ == '__main__':
    def _check(name, cond, detail=''):
        print('%-60s %s %s' % (name, 'ok' if cond else 'FAIL',
                               detail if not cond else ''))
        return cond
    import tempfile
    sys.exit(0 if run(None, _check, tempfile.mkdtemp(prefix='nfh-sprite-'))
             else 1)
