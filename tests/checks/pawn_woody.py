"""Pawn / Woody checks (docs/audit/verified/pawn_woody.md): the S2 sneak
override, the dexterity retry, the held-transition wait, the door-at-once
arms, the per-role door strips (and the S2 door sprites), the Hide_In
click drop, the sneak portal strips, the stand-switch clears, the last-step
restamp, the SeeAlerter Frozen gate, the door refusal without a bubble and
the DonePassing / pause click gates.

Most of these need state a script cannot set (a dexterity win, a claimed
transition pair, a frozen Woody), so they drive the headless Viewer directly
with the recorder's 60 Hz step; the S2 sneak crash is a plain script.
"""
import os, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, 'runtime'))

DT = 1.0 / 60.0


def _viewer(level):
    os.environ.setdefault('SDL_VIDEODRIVER', 'offscreen')
    from viewer import Viewer
    return Viewer([os.path.join(ROOT, level)], headless=True)


def _run(v, seconds, stop=None):
    """the recorder's tick without the drawing: world tick + the stored
    click replay; returns the seconds elapsed (early on stop())"""
    w = v.world
    wd = v.woody
    n = int(seconds / DT)
    for i in range(n):
        v._frame_dt = DT
        w.tick(DT)
        if wd is not None and wd.stored_input is not None \
                and not wd.input_locked and not wd.anim.blocking \
                and not wd.is_warping and not w.game.ending:
            click, wd.stored_input = wd.stored_input, None
            v.world_click(*click)
        if stop is not None and stop():
            return (i + 1) * DT
    return seconds


def _guard(check, name, fn):
    """one check body; an exception is a failure of that check alone"""
    try:
        return fn()
    except Exception as e:                # noqa: BLE001
        return check(name, False, '%s: %s' % (type(e).__name__, e))


def run(record, check, outdir):
    ok = True

    # -- 1. the S2 sneak toggle + a click used to crash the walk (no Walk_*
    #       strips on the S2 sheet): StartMoveToLocation's NFH2 override
    #       (Woody.cs:717-720) and ToggleSneak's gate (cs:1151-1163) ------
    def sneak_s2():
        try:
            st = record('levels/s2/Level201.json',
                        os.path.join(outdir, 'sneak_s2'),
                        'wait 4\nfollow on\nkey sneak\nclickworld 5.2 -2.26\n'
                        'wait 2\n', 6)
        except subprocess.CalledProcessError as e:
            return check('pawn: S2 sneak click survives', False,
                         'record.py died: %s' % e)
        r = check('pawn: S2 sneak click survives', True)
        r &= check('pawn: S2 never sneaks',
                   not any(s['woody']['sneak'] for s in st))
        r &= check('pawn: S2 sneak click still walks',
                   st[-1]['woody']['x'] > st[0]['woody']['x'] + 0.3,
                   '%s -> %s' % (st[0]['woody']['x'], st[-1]['woody']['x']))
        return r
    ok &= _guard(check, 'pawn: S2 sneak click survives', sneak_s2)

    # -- 2. the dexterity retry (Woody.cs:218-222): the frame after the win
    #       TryUseItem re-runs and CanWoodyUse's DexterityDone branch drops
    #       InDexterity/DexterityDone and spends the unlocker ---------------
    def dex_retry():
        v = _viewer('levels/s2/Level202.json')
        w, wd = v.world, v.woody
        it = next(i for i in v.level.items.values() if i.name == 'CrayFish')
        _run(v, 6)
        w.inventory.add([{'type': 'IT2_Reed', 'use_count': 0, 'name': 'REED',
                          'desc': '', 'wrong_zone': '', 'long': False}])
        w.inventory.select(0)
        w.inventory.promote()
        w.woody_click(it.x, it.y, it, None)
        t = _run(v, 40, lambda: w.is_dexterity_on)
        r = check('pawn: dexterity arms', w.is_dexterity_on, 'after %.1fs' % t)
        if not w.is_dexterity_on:
            return r
        ds = next(d for d in w.dex_states.values() if d.enabled)
        ds._win()
        _run(v, 1)
        r &= check('pawn: dexterity win retries the use',
                   not wd.dexterity_done and not wd.in_dexterity,
                   'done=%s in_dex=%s' % (wd.dexterity_done, wd.in_dexterity))
        r &= check('pawn: the retry spends the unlocker',
                   not w.inventory.has('IT2_Reed'))
        _run(v, 8)
        # the take rides CanWoodyUse's post-'done' path: the two dexterity
        # arms fall through to the tail past the refusal cluster
        # (Item.cs:1462-1474, 1704-1730 — World._can_woody_use_tail)
        r &= check('pawn: dexterity take landed',
                   w.inventory.has('IT2_Crayfish'),
                   [e['type'] for e in w.inventory.items])
        return r
    ok &= _guard(check, 'pawn: dexterity arms', dex_retry)

    # -- 3. a transition pair held by another pawn parks Woody standing on
    #       the first approach (TransitionEnter before the claim,
    #       Pawn.cs:1004/1014, 1022-1027) ---------------------------------
    def transition_wait():
        v = _viewer('levels/s2/Level201.json')
        w, wd = v.world, v.woody
        rott = w.pawns['Rottweiler']
        _run(v, 6)
        trans = [d for d in v.level.doors
                 if d.zone == wd.zone.pid and d.is_transition and d.complex_move
                 and d.nfh2_stairs]
        d = trans[0]
        other = v.level.door_by_pid(d.link_to)
        d.passing_nfh2 = rott
        other.passing_nfh2 = rott
        dest = v.level.zone_by_pid(other.zone)
        start_zone = wd.zone.pid
        w.woody_click(dest.x, dest.ty, None, None)
        _run(v, 12)
        r = check('pawn: held transition parks Woody',
                  wd.zone.pid == start_zone
                  and wd.anim.anim.name.startswith('Stand'),
                  'zone %s anim %s' % (wd.zone.name, wd.anim.anim.name))
        d.passing_nfh2 = None
        other.passing_nfh2 = None
        t = _run(v, 15, lambda: wd.zone.pid == other.zone)
        r &= check('pawn: the release lets him through',
                   wd.zone.pid == other.zone, 'after %.1fs' % t)
        return r
    ok &= _guard(check, 'pawn: held transition parks Woody', transition_wait)

    # -- 4. ShouldExitDoorNow's general arm (Woody.cs:777-780, Pawn.cs:768-
    #       779): standing on the door he came through, a far-zone click
    #       passes at once from the doorway — no walk down and re-climb ---
    def door_at_once():
        v = _viewer('levels/s1/Level101.json')
        w, wd = v.world, v.woody
        _run(v, 6)
        d = next(x for x in v.level.doors if x.zone == wd.zone.pid
                 and x.should_walk_up and not x.locked)
        other = v.level.door_by_pid(d.link_to)
        w.woody_click(d.x, d.y, None, d)
        _run(v, 30, lambda: wd.zone.pid == other.zone and wd.state == wd.IDLE)
        r = check('pawn: arrives on the far doorway',
                  wd.at_door_location and wd.last_exit_door is other
                  and wd.sprite.y > wd.floor_y() + 0.3)
        back = v.level.zone_by_pid(d.zone)
        y0 = wd.sprite.y
        w.woody_click(back.x, back.ty, None, None)
        t = _run(v, 5, lambda: wd.is_warping)
        r &= check('pawn: far click passes the door at once',
                   wd.is_warping and t < 0.2
                   and abs(wd.sprite.y - y0) < 0.1,
                   'warping=%s after %.2fs, y %.2f -> %.2f'
                   % (wd.is_warping, t, y0, wd.sprite.y))
        return r
    ok &= _guard(check, 'pawn: far click passes the door at once',
                 door_at_once)

    # -- 5. the door strips per pawn class (Door.cs:85-139; Mother.cs:63-73)
    #       and the S2 DoorBack controllers (IdleAnimation NONE +
    #       IgnoreIdleAnimation) existing as sprites with no
    #       CurrentAnimation — Door.Start's ReturnToIdleAnimation is skipped
    #       (Door.cs:211), the controller stays enabled and draws nothing
    #       until the first pass strip (sprite_model: current None, not
    #       Hidden) --------------------------------------------------------
    def door_roles():
        v = _viewer('levels/s2/Level213.json')
        w = v.world
        mother = w.pawns.get('Mother')
        d = next(x for x in v.level.doors if x.name == 'DoorBack')
        r = check('pawn: S2 DoorBack has its pass sprite',
                  d.sprite is not None and d.sprite.anim is None
                  and not d.sprite.sprite.hidden)
        r &= check('pawn: Mother gets her own door strips',
                   mother is not None and mother._door_anims(d)
                   == ('MotherDoorBackLeave', 'MotherDoorBackEnter'),
                   mother._door_anims(d) if mother else None)
        olga = w.pawns.get('Olga')
        r &= check('pawn: Olga gets her (NONE) strips',
                   olga is not None and olga._door_anims(d) == (None, None))
        return r
    ok &= _guard(check, 'pawn: Mother gets her own door strips', door_roles)

    # -- 6. a click during the literal Hide_In dive is dropped, not stored
    #       (Woody.cs:642-651) ---------------------------------------------
    def hide_in_drop():
        from viewer import WIDTH, HEIGHT
        v = _viewer('levels/s1/Level101.json')
        w, wd = v.world, v.woody
        it = next(i for i in v.level.items.values() if i.name == 'Wardrobe')
        _run(v, 6)
        w.woody_click(it.x, it.y, it, None)
        _run(v, 30, lambda: wd.hiding)
        r = check('pawn: wardrobe hides', wd.hiding
                  and wd.anim.anim.name == 'Hide_In')
        v.cam.x, v.cam.y = wd.sprite.x, wd.sprite.y
        sx, sy = v.cam.world_to_screen(wd.sprite.x - 1.5, wd.floor_y(),
                                       WIDTH, HEIGHT)
        res = v.handle_click(sx, sy)
        r &= check('pawn: click during Hide_In is dropped',
                   res == 'hide-in' and wd.stored_input is None, res)
        _run(v, 4)
        r &= check('pawn: he stays hidden after Hide_In', wd.hiding)
        return r
    ok &= _guard(check, 'pawn: click during Hide_In is dropped', hide_in_drop)

    # -- 7. sneaking climbs with the PortalSneak strips (Woody.cs:952-968),
    #       the stand switch clears the NFH2 tracker (PawnAnimationController
    #       .cs:86-95), entering the last step restamps and drops the flag
    #       (Pawn.cs:1100-1104), the SeeAlerter Frozen gate (Woody.cs:1040),
    #       the door refusal without a WrongZone bubble (Pawn.cs:615 vs
    #       633-638), the DonePassing and pause click gates (Woody.cs:637,
    #       659-662) ------------------------------------------------------
    def small_ones():
        from viewer import WIDTH, HEIGHT
        v = _viewer('levels/s1/Level107.json')       # has the Chili alerter
        w, wd = v.world, v.woody
        _run(v, 6)
        wd.toggle_sneak()
        r = check('pawn: sneak portal strips',
                  wd.sneaking and wd._portal_up_anim() == 'Walk_Up'
                  and wd._portal_down_anim() == 'Walk_Down',
                  (wd._portal_up_anim(), wd._portal_down_anim()))
        wd.toggle_sneak()
        # the SeeAlerter gate: any alerter, Woody parked in its zone
        al = next(iter(w.alerters.values()), None)
        if al is not None:
            wd.zone = v.level.zone_by_pid(al.item.zone) or wd.zone
            wd.movement_paused = False
            wd.frozen = True
            w.woody_see_alerter(al.item)
            r &= check('pawn: a frozen Woody does not flinch',
                       not wd.movement_paused)
            wd.frozen = False
        # the door refusal: a held source inventory, no bubble
        door = next(x for x in v.level.doors if x.zone == wd.zone.pid
                    and not x.locked)
        w.inventory.used = {'type': 'IT_Key', 'item': 1, 'use_count': 0,
                            'name': 'KEY', 'wrong_zone': 'KEY_WRONGZONE',
                            'long': False}
        w.hud.show_description = False
        w.woody_click(door.x, door.y, None, door)
        r &= check('pawn: door refusal speaks no WrongZone bubble',
                   not w.hud.show_description
                   and wd.anim.anim.name == 'NoNo')
        w.inventory.used = None
        # the pause gate
        w.menu_open = True
        sx, sy = v.cam.world_to_screen(wd.sprite.x + 0.5, wd.floor_y(),
                                       WIDTH, HEIGHT)
        r &= check('pawn: a paused game drops world clicks',
                   v.handle_click(sx, sy) == 'paused')
        w.menu_open = False
        # S2: the stand-switch clears, the last-step restamp, the DonePassing
        # click gate
        v2 = _viewer('levels/s2/Level201.json')
        w2, w2d = v2.world, v2.woody
        _run(v2, 6)
        w2d.done_passing = True
        w2d.go_zone = w2d.zone
        w2d.door_clicked = None
        w2d._stand()
        r &= check('pawn: the stand switch clears DonePassing/GoZone',
                   not w2d.done_passing and w2d.go_zone is None)
        w2d.done_passing = True
        w2d.go_zone = None
        v2.cam.x, v2.cam.y = w2d.sprite.x, w2d.sprite.y
        sx, sy = v2.cam.world_to_screen(w2d.sprite.x + 0.5, w2d.floor_y(),
                                        WIDTH, HEIGHT)
        r &= check('pawn: DonePassing swallows the click',
                   v2.handle_click(sx, sy) == 'passing')
        w2.woody_click(w2d.sprite.x + 0.5, w2d.sprite.y, None, None)
        r &= check('pawn: entering the last step drops DonePassing',
                   not w2d.done_passing and w2d.state == w2d.WALK)
        return r
    ok &= _guard(check, 'pawn: sneak portal strips', small_ones)

    return ok
