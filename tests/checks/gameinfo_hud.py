"""gameinfo_hud — the GameInfo / HUD / animation-model checks of the final
audit (docs/audit/verified/gameinfo_hud.md). Each guards one fixed
divergence and fails on the pre-fix code.

Most scenarios need the real viewer loop (the HUD draws, the virtual mouse
hovers, the clicks go through HUD.CheckClick), so they drive
runtime/record.py's Recorder in-process — the same 60 Hz loop the moment
suite records — and poke the exact state the original's method reads
(GameInfo's counters, the clock, the inventory) where no script line can.
"""
import os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, 'runtime'))
os.environ.setdefault('SDL_VIDEODRIVER', 'offscreen')

from record import Recorder, DT, WIDTH, HEIGHT      # noqa: E402

_N = [0]


def drive(level, seconds, outdir, at=(), each=None):
    """the real headless viewer loop for `seconds`; `at` is a list of
    (time, fn(v, t)) fired once when the clock passes the time, `each` a
    fn(v, t) run every tick before it (returning True stops the run)"""
    _N[0] += 1
    out = os.path.join(outdir, 'drive%02d' % _N[0])
    os.makedirs(out, exist_ok=True)
    rec = Recorder(os.path.join(ROOT, level), out, script=None,
                   seconds=seconds, fps=0)
    rec._next_shot = 0.0
    rec._shot_i = 0
    fired = set()
    t = 0.0
    while t < seconds + 1e-9:
        for i, (tt, fn) in enumerate(at):
            if i not in fired and t + 1e-9 >= tt:
                fired.add(i)
                fn(rec.v, t)
        if each is not None and each(rec.v, t):
            break
        rec.tick(t)
        t += DT
    rec.log.close()
    return rec.v


def item(v, name):
    return next(i for i in v.level.items.values() if i.name == name)


def screen_of(v, x, y):
    return v.cam.world_to_screen(x, y, WIDTH, HEIGHT)


def click_world(v, x, y):
    return v.handle_click(*screen_of(v, x, y))


def click_item(v, it):
    return v.handle_click(*screen_of(v, it.collider[0], it.collider[1]))


def hover_item(v, it):
    """park the recorder's virtual mouse on the item's collider centre"""
    sx, sy = screen_of(v, it.collider[0], it.collider[1])
    v.virtual_mouse[0], v.virtual_mouse[1] = sx, sy


def run(record, check, outdir):
    ok = True
    os.makedirs(outdir, exist_ok=True)

    # -- D1 + D3: TimeUp keeps Won (GameInfo.cs:241-249, 373-390, 438-465);
    #    GameEnded waits for the finish pose (cs:343-345, HUD.cs:731) -------
    seen = {}
    jingles = []

    def arm(v, t):
        g = v.world.game
        g.completed = g.winning
        g.won = True
        g.time_seconds = 1.5
        v.world._play_jingle = lambda key: jingles.append(key)

    def watch(v, t):
        g = v.world.game
        if g.time_up and 'timeup' not in seen:
            seen['timeup'] = t
        if g.ending and v.woody.anim.anim.name == 'WinGame':
            seen['pose_ended_flag'] = g.ended if 'pose_ended_flag' not in seen \
                else seen['pose_ended_flag'] or g.ended
        if g.ended and 'ended' not in seen:
            seen['ended'] = t
        return 'ended' in seen and t > seen['ended'] + 0.5
    v = drive('levels/s1/Level101.json', 12.0, outdir, at=[(4.0, arm)],
              each=watch)
    g = v.world.game
    ok &= check('gameinfo: TimeUp keeps Won -> success jingle',
                g.time_up and g.won and jingles == ['success'], jingles)
    ok &= check('gameinfo: TimeUp keeps Won -> a Won rating band',
                g.rating in ('PASSED', 'GOOD', 'EXCELLENT'), g.rating)
    ok &= check('gameinfo: GameEnded only after the finish pose',
                'timeup' in seen and 'ended' in seen
                and seen['ended'] - seen['timeup'] > 1.5, seen)
    ok &= check('gameinfo: Woody stands Down after the pose (PrevAnimState)',
                v.woody.anim.anim.name == 'Stand_Down', v.woody.anim.anim.name)

    # -- D2: GameEnding from the first all-tricks frame; the clock and the
    #    HUD freeze for the 2.5 s coroutine, Woody's clicks stay live
    #    (GameInfo.cs:212, 226-231, 292-302; Woody.cs:637) -----------------
    seen = {}

    def last_trick(v, t):
        g = v.world.game
        g.completed = g.total
        g.won = True
        seen['clock'] = g.time_seconds

    def click_wait(v, t):
        seen['ending_at_click'] = v.world.game.ending
        seen['clock_at_click'] = v.world.game.time_seconds
        seen['click'] = click_world(v, v.woody.sprite.x - 1.5, v.woody.sprite.y)
        seen['x0'] = v.woody.sprite.x
        seen['tip'] = v.hud.tooltip

    def moved(v, t):
        seen['x1'] = v.woody.sprite.x
        seen['pose'] = v.woody.anim.anim.name

    def watch2(v, t):
        g = v.world.game
        if g.ending and 'ending' not in seen:
            seen['ending'] = t
        if v.woody.anim.anim.name == 'WinGame' and 'win' not in seen:
            seen['win'] = t
        return 'win' in seen and t > seen['win'] + 0.2
    v = drive('levels/s1/Level101.json', 12.0, outdir,
              at=[(4.0, last_trick), (4.5, click_wait), (6.0, moved)],
              each=watch2)
    ok &= check('gameinfo: GameEnding set on the all-tricks frame',
                'ending' in seen and seen['ending'] < 4.1, seen.get('ending'))
    ok &= check('gameinfo: the clock freezes during the win wait',
                seen.get('clock_at_click') == seen.get('clock')
                and abs(v.world.game.time_seconds - seen['clock']) < 1e-6,
                (seen.get('clock'), v.world.game.time_seconds))
    ok &= check('gameinfo: PlayWinAnimations after the 2.5 s coroutine',
                'win' in seen and 6.4 < seen['win'] < 6.7, seen.get('win'))
    ok &= check('gameinfo: Woody still walks during the wait (Frozen later)',
                seen.get('click') == 'world' and seen.get('x1', 0) < seen.get('x0', 0) - 0.3
                and v.woody.frozen, (seen.get('click'), seen.get('x0'), seen.get('x1')))
    ok &= check('hud: the unlatched tooltip clears once GameEnding',
                seen.get('tip') is None, seen.get('tip'))

    # -- D4: FinishAnimationEnded disables the sleep bars (GameInfo.cs:346,
    #    535-541; ProgressBar.cs:303-307) — L109's bed bar ------------------
    seen = {}

    def each3(v, t):
        w = v.world
        g = w.game
        bar = next((pb for pb in w.progress_bars if pb.visible), None)
        if bar is not None and 'armed' not in seen:
            seen['armed'] = t
            seen['bar'] = bar
            g.time_seconds = 1.5          # the clock runs out mid-sleep
        if g.ended and 'ended' not in seen:
            seen['ended'] = t
        return 'ended' in seen and t > seen['ended'] + 0.3
    v = drive('levels/s1/Level109.json', 60.0, outdir, each=each3)
    bar = seen.get('bar')
    rott = v.world.pawns['Rottweiler']
    ok &= check('gameinfo: a sleep bar was up when the clock ran out',
                bar is not None and 'ended' in seen, seen.get('armed'))
    ok &= check('gameinfo: DisableAllProgressBars at FinishAnimationEnded',
                bar is not None and bar.disabled and not bar.visible
                and not rott.is_sleeping and not rott.hud_disable_think,
                None if bar is None else (bar.disabled, bar.visible,
                                          rott.is_sleeping))

    # -- D5 + D7 + D17: every non-icon click promotes/drops the used
    #    inventory (HUD.cs:1319-1322, Woody.cs:1062-1073) and latches the
    #    tooltip (UpdateTooltip, cs:1062-1075); the cursor/hover read
    #    CurrentInventory only (MouseCursor.cs:189-198, 362-373) ------------
    seen = {}

    def take(v, t):
        click_item(v, item(v, 'Drawer'))

    def select_and_hover(v, t):
        v.world.inventory.select(0)                  # the icon click
        hover_item(v, item(v, 'Microwave'))

    def hover_state(v, t):
        seen['hover_tip'] = v.hud.tooltip
        seen['hover_cursor'] = v.hud.cursor_tex
        seen['tip_state'] = v.hud.tooltip_state

    def promote(v, t):
        seen['promote'] = click_item(v, item(v, 'Microwave'))
        inv = v.world.inventory
        seen['after_promote'] = (inv.used is not None, inv.current is None,
                                 v.hud.colored_tooltip, v.hud.tooltip)

    def promoted_frame(v, t):
        seen['cursor_used'] = v.hud.cursor_tex
        seen['tip_used'] = v.hud.tooltip

    def bare_click(v, t):
        seen['bare'] = click_world(v, v.woody.sprite.x + 0.5, v.woody.sprite.y)
        seen['used_after_bare'] = v.world.inventory.used
        seen['colored_after_bare'] = v.hud.colored_tooltip
    v = drive('levels/s1/Level101.json', 15.0, outdir,
              at=[(4.0, take), (9.0, select_and_hover), (10.5, hover_state),
                  (10.6, promote), (10.7, promoted_frame), (11.5, bare_click)])
    inv = v.world.inventory
    ok &= check('hud: the icon stage speaks "Use X with <hover>"',
                inv.items and isinstance(seen.get('hover_tip'), str)
                and seen['hover_tip'].startswith('Use ') and ' with ' in seen['hover_tip']
                and not seen['hover_tip'].endswith(v.hud.woody_strings['empty_use']),
                seen.get('hover_tip'))
    ok &= check('hud: the icon stage shows the use-inventory cursor',
                seen.get('hover_cursor') == v.level.mouse_cursor['use_inv'],
                seen.get('hover_cursor'))
    ok &= check('hud: the world click promotes Current -> Used and latches',
                seen.get('after_promote', (False,))[0]
                and seen['after_promote'][1] and seen['after_promote'][2],
                seen.get('after_promote'))
    ok &= check('hud: after the promotion the cursor reads Current only',
                seen.get('cursor_used') != v.level.mouse_cursor['use_inv'],
                seen.get('cursor_used'))
    ok &= check('hud: a click with nothing selected drops UsedInventory',
                seen.get('used_after_bare') is None, seen.get('used_after_bare'))

    # -- D7 alone: a bare-handed tap on an item latches its line -----------
    seen = {}

    def hover_bare(v, t):
        hover_item(v, item(v, 'Microwave'))

    def tap(v, t):
        click_item(v, item(v, 'Microwave'))
        seen['colored'] = v.hud.colored_tooltip
        seen['tip'] = v.hud.tooltip
        # the hover moves away: a latched line stays put
        v.virtual_mouse[0], v.virtual_mouse[1] = 30.0, 30.0

    def later(v, t):
        seen['still'] = (v.hud.colored_tooltip, v.hud.tooltip)
    v = drive('levels/s1/Level101.json', 5.5, outdir,
              at=[(4.0, hover_bare), (4.6, tap), (5.0, later)])
    ok &= check('hud: a bare tap on an item latches the colored line',
                seen.get('colored') and seen.get('tip')
                and seen.get('still') == (True, seen.get('tip')), seen)

    # -- D6 + D18: the pressed icon's line is hover-aware and gated; an
    #    unselected icon under the cursor speaks "Use X with nothing"
    #    (HUD.cs:942-967) -------------------------------------------------
    seen = {}
    icon_rect = {}

    def take2(v, t):
        click_item(v, item(v, 'Drawer'))
        icon_rect['r'] = v.hud._inventory_rects()[0]

    def sel_hover(v, t):
        v.world.inventory.select(0)
        hover_item(v, item(v, 'Microwave'))

    def read_pressed(v, t):
        seen['pressed_tip'] = v.hud.tooltip

    def unselect_hover_icon(v, t):
        v.world.inventory.select(-1)
        r = icon_rect['r']
        v.virtual_mouse[0], v.virtual_mouse[1] = r[0] + r[2] / 2, r[1] + r[3] / 2

    def read_icon(v, t):
        seen['icon_tip'] = v.hud.tooltip
    v = drive('levels/s1/Level101.json', 12.5, outdir,
              at=[(4.0, take2), (9.0, sel_hover), (10.0, read_pressed),
                  (10.5, unselect_hover_icon), (12.0, read_icon)])
    ws = v.hud.woody_strings
    ok &= check('hud: the pressed icon line names the hovered item',
                isinstance(seen.get('pressed_tip'), str)
                and seen['pressed_tip'].startswith(ws['use'])
                and not seen['pressed_tip'].endswith(ws['empty_use']),
                seen.get('pressed_tip'))
    ok &= check('hud: an unselected icon under the cursor speaks "with nothing"',
                isinstance(seen.get('icon_tip'), str)
                and seen['icon_tip'].endswith(ws['empty_use']), seen.get('icon_tip'))

    # -- D10: OnInventoryAdded scrolls to the newest item ------------------
    v = drive('levels/s1/Level101.json', 0.5, outdir)
    v.world.inventory.add([{'type': 'IT_X%d' % i, 'use_count': 1, 'name': ''}
                           for i in range(6)])
    ok &= check('hud: OnInventoryAdded pages to the newest item',
                v.hud.displayed_begin == 6 - len(v.hud._inventory_rects()),
                v.hud.displayed_begin)

    # -- D9: a bare single (NoNo) ends on StandDown, not the facing --------
    seen = {}

    def walk_left(v, t):
        click_world(v, v.woody.sprite.x - 1.0, v.woody.sprite.y)

    def nono(v, t):
        seen['before'] = v.woody.anim.anim.name
        v.woody.anim.play_single('NoNo')

    def after(v, t):
        seen['after'] = v.woody.anim.anim.name
    v = drive('levels/s1/Level101.json', 9.0, outdir,
              at=[(4.0, walk_left), (6.0, nono), (8.5, after)])
    ok &= check('anim: a bare single stands Down (PrevAnimState default)',
                seen.get('before') == 'Stand_Left' and seen.get('after') == 'Stand_Down',
                seen)

    # -- D14: no detection before ActionManager.CurrentAction exists -------
    v = drive('levels/s1/Level101.json', 0.5, outdir)
    w = v.world
    rott = w.pawns['Rottweiler']
    woody = w.woody
    woody.zone = rott.zone
    woody.sprite.x, woody.sprite.y = rott.sprite.x + 0.5, rott.sprite.y
    woody.hiding = False
    woody.is_warping = False
    early = w.can_rottweiler_see_woody()
    for r in w.routines:
        r.delay_start = 0.0
        r.started = True                   # the first StartAction happened
    late = w.can_rottweiler_see_woody()
    ok &= check('gameinfo: detection needs CurrentAction (DelayStart)',
                not early and late, (early, late))

    # -- D13: Door.Unlock leaves the zone graph alone ----------------------
    # L101's locked doors are decorative (no LinkTo): give one a link to a
    # door of another zone, unlock it, and the graph must stay as built
    v = drive('levels/s1/Level101.json', 0.5, outdir)
    lv = v.level
    locked = next(d for d in lv.doors if d.locked)
    other = next(d for d in lv.doors if d.zone != locked.zone and not d.locked)
    locked.link_to = other.pid
    before = {z: list(es) for z, es in lv.graph.items()}
    v.world.unlock_door(locked)
    ok &= check('zones: Door.Unlock adds no path edge (ZoneController.Start)',
                not locked.locked and lv.graph == before
                and all(d is not locked for _z, d in lv.graph.get(locked.zone, [])),
                (locked.name, other.name))

    # -- D15: the angry meter repaints at 10 Hz ------------------------------
    v = drive('levels/s1/Level101.json', 1.0, outdir)
    rott = v.world.pawns['Rottweiler']
    rott.angry_meter = 40.0
    v.draw()
    first = v.hud._angry_rects
    rott.angry_meter = 80.0
    v.draw()                               # same Time.time: the cache holds
    held = v.hud._angry_rects
    v.world.tick(0.11)
    v.draw()
    moved = v.hud._angry_rects
    ok &= check('hud: DrawAngryMeter recomputes at most every 0.1 s',
                first is not None and held == first and moved != first,
                (first, held, moved))

    # -- D20: forcewin is GameInfo.ForceWinGame (WinImmediate, rating 100) --
    seen = {}

    def fw(v, t):
        v.world.game.force_win()

    def watch4(v, t):
        if v.woody.anim.anim.name == 'WinGame' and 'win' not in seen:
            seen['win'] = t
        return v.world.game.ended
    v = drive('levels/s1/Level101.json', 12.0, outdir, at=[(4.0, fw)],
              each=watch4)
    ok &= check('gameinfo: ForceWinGame plays the win at once, rating 100',
                'win' in seen and seen['win'] < 4.1 and v.world.game.rating == 'EXCELLENT'
                and v.world.game.final_viewer_rating == 100,
                (seen.get('win'), v.world.game.rating))

    # -- B: the finish arriving mid-door-pass waits for the arrival
    #    (Woody.cs:1104-1111, 490-493) — never a hidden WinGame ------------
    seen = {}

    def go_far(v, t):
        # the front door: click the neighbouring zone's floor
        w = v.world
        zones = [z for z in v.level.zones if w.woody.zone is None
                 or z.pid != w.woody.zone.pid]
        z = zones[0]
        click_world(v, (z.play_left + z.play_right) / 2.0, z.ty + z.height_delta + 0.2)

    def watch5(v, t):
        wd = v.woody
        if wd.is_warping and 'fw' not in seen:
            seen['fw'] = t
            v.world.game.force_win()
        if wd.anim.anim.name == 'WinGame':
            seen.setdefault('win_frames', []).append((round(t, 2), wd.sprite.hidden, wd.is_warping))
        if v.world.game.ended:
            seen['ended'] = t
            return True
        return False
    v = drive('levels/s1/Level101.json', 20.0, outdir, at=[(4.0, go_far)],
              each=watch5)
    frames = seen.get('win_frames', [])
    ok &= check('finish: deferred through the door pass, played visible',
                'fw' in seen and frames and all(not h and not wp for _t, h, wp in frames)
                and 'ended' in seen, (seen.get('fw'), frames[:3], seen.get('ended')))

    # -- B: hiding — the finish waits for the leave animation ---------------
    seen = {}

    def hide(v, t):
        click_item(v, item(v, 'Wardrobe'))

    def watch6(v, t):
        wd = v.woody
        if wd.hiding and wd.anim.anim.name != 'Hide_In' and 'fw' not in seen:
            seen['fw'] = t
            v.world.game.force_win()
        if 'fw' in seen:
            seen.setdefault('anims', []).append(wd.anim.anim.name)
        if v.world.game.ended:
            seen['ended'] = t
            return True
        return False
    v = drive('levels/s1/Level101.json', 25.0, outdir, at=[(4.0, hide)],
              each=watch6)
    anims = seen.get('anims', [])
    order = [a for i, a in enumerate(anims) if i == 0 or anims[i - 1] != a]
    ok &= check('finish: hiding -> Hide_Out first, then the win pose',
                'ended' in seen and 'Hide_Out' in order and 'WinGame' in order
                and order.index('Hide_Out') < order.index('WinGame'),
                (seen.get('fw'), order[:6], seen.get('ended')))

    # -- D8 guard: Level205's mutex handshake keeps cycling; a Level101 door
    #    pass completes with Woody visible on the far side -----------------
    seen = {'states': set()}

    def watch7(v, t):
        for r in v.world.routines:
            seen['states'].add((r.role, r.state, r.item.name if r.item else None))
        return False
    # the first mat use ends at ~20 s (the neighbour's parked lap: Olga's
    # use runs hidden and its end springs him — README, Level205), so
    # the second item shows up only past that
    v = drive('levels/s2/Level205.json', 40.0, outdir, each=watch7)
    olga = [s for s in seen['states'] if s[0] == 'Olga']
    rott = [s for s in seen['states'] if s[0] == 'Rottweiler']
    ok &= check('routine: Level205 cycles both routines (D8 guard)',
                len({s[2] for s in olga}) >= 2 and len({s[2] for s in rott}) >= 2,
                (sorted(olga), sorted(rott)))
    seen = {}

    def watch8(v, t):
        wd = v.woody
        if wd.is_warping:
            seen['warped'] = True
        if seen.get('warped') and not wd.is_warping and not wd.sprite.hidden:
            seen['arrived'] = (t, wd.zone.name if wd.zone else None)
            return True
        return False
    v = drive('levels/s1/Level101.json', 12.0, outdir, at=[(4.0, go_far)],
              each=watch8)
    ok &= check('pawn: Level101 door pass completes visible (D8 guard)',
                'arrived' in seen, seen)

    # -- X2: every pawn controller refreshes once per frame — a 10 fps pawn
    #    animation steps every 0.1 s (AnimationControllerBase.cs:102-142,
    #    172-189), not every 0.05 s -----------------------------------------
    from scene import Level
    from world import World
    lv = Level(os.path.join(ROOT, 'levels/s1/Level101.json'))
    w = World(lv)
    for role in ('Woody', 'Rottweiler'):
        w.spawn_pawn(role)
    w.woody = w.pawns['Woody']
    w.start_routines()
    w._entrance_timer = None               # no entrance walk in the way
    wd = w.woody
    wd.anim.play_single('Hello')           # frames 15..22 at 10 fps
    steps = []
    t = 0.0
    for _ in range(90):
        w.tick(DT)
        t += DT
        if not steps or steps[-1][1] != wd.anim.frame:
            steps.append((round(t, 3), wd.anim.frame))
        if wd.anim.anim.name != 'Hello':
            break
    gaps = [round(b[0] - a[0], 3) for a, b in zip(steps[1:], steps[2:])]
    ok &= check('anim: a pawn animation steps at its FrameRate (one tick)',
                gaps and all(abs(g - 0.1) < 0.02 for g in gaps), (steps, gaps))

    # -- X3: UsePattern with an empty Pattern (AnimationInstance.cs:66-76,
    #    186-234): a single ends on its first step, a looping one holds
    #    sheet frame 0 — Woody's PutEel on Level202 --------------------------
    lv = Level(os.path.join(ROOT, 'levels/s2/Level202.json'))
    w = World(lv)
    for role in ('Woody', 'Rottweiler', 'Olga', 'Mother', 'Kid'):
        w.spawn_pawn(role)
    w.woody = w.pawns['Woody']
    w.start_routines()
    w._entrance_timer = None
    wd = w.woody
    a = next(x for x in wd.sprite.anims if x.name == 'PutEel')
    wd.anim.play_single('PutEel')
    w.tick(DT)
    ended_at_once = wd.anim.anim.name != 'PutEel'
    wd.anim.play_looping('PutEel')
    frames = set()
    for _ in range(40):
        w.tick(DT)
        frames.add(wd.sprite.cur_frame)
    ok &= check('anim: an empty-pattern single ends on its first step',
                a.empty_pattern and ended_at_once, (a.empty_pattern, wd.anim.anim.name))
    ok &= check('anim: an empty-pattern loop holds sheet frame 0',
                wd.anim.anim.name == 'PutEel' and frames == {0}, frames)

    # -- X6: a pattern animation draws Pattern[index] unclamped
    #    (AnimationInstance.cs:228-234) — L209 FireFakir's 127-entry idle
    #    ships EndFrame 0 and must still animate ------------------------------
    lv = Level(os.path.join(ROOT, 'levels/s2/Level209.json'))
    w = World(lv)
    for role in ('Woody', 'Rottweiler', 'Olga', 'Mother', 'Kid'):
        w.spawn_pawn(role)
    w.woody = w.pawns['Woody']
    w.start_routines()
    ff = next(i for i in lv.items.values() if i.name == 'FireFakir')
    p = w.players[id(ff.sprite)]
    a = p.anim
    drawn = set()
    for _ in range(int(3.0 / DT)):
        w.tick(DT)
        if p.anim is a:
            drawn.add(ff.sprite.cur_frame)
    ok &= check('anim: a pattern animation draws Pattern[index], not <= EndFrame',
                a.pattern and a.end < max(a.pattern) and len(drawn) > 3
                and max(drawn) > a.end, (a.name, a.end, sorted(drawn)[:12]))
    return ok
