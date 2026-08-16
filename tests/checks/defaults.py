"""Pass-4 'silent defaults' (docs/audit/verified/defaults.md): a port default
must equal the C# field initializer, and an `or` fallback must never replace
a legitimately falsy serialized value the original uses as-is. Data-level:
the port's Item / Door / Anim specs are built from minimal dicts and from
every shipped level and compared with the C# initializers and the raw JSON.
"""
import glob, json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, 'runtime'))


def _item(d):
    from scene import Item
    return Item('x', 1, 'TrickItem', 0.0, 0.0, None, 0.0, 0.0, d)


def _door(d):
    from scene import Door
    return Door('x', 1, 0.0, 0.0, None, None, False, 'DT_Normal', d)


def _anim(**kw):
    from scene import Anim
    d = {'Name': 'X', 'TextureFileName': 'X', 'SheetColumns': 4,
         'SheetRows': 4, 'StartFrame': 0, 'EndFrame': 3, 'FrameRate': 8.0,
         'OriginalWidth': 100.0, 'OriginalHeight': 100.0, 'UsePattern': False,
         'Pattern': [], 'Type': 'Single'}
    d.update(kw)
    return Anim(d, '')


def _close(a, b):
    return abs(a - b) < 1e-6


def run(record, check, outdir):
    from scene import Level
    ok = True

    # -- the field-absent path returns the C# initializer -------------------
    it = _item({})
    ok &= check('defaults: Item.UseDistance = 0.03f',
                _close(it.use_distance, 0.03), it.use_distance)      # Item.cs:246
    ok &= check('defaults: Item.ItemUseHeight = 0.01f',
                _close(it.item_use_height, 0.01), it.item_use_height)  # Item.cs:220
    ok &= check('defaults: Item.AngerAmount = 20',
                it.anger_amount == 20, it.anger_amount)               # Item.cs:392
    ok &= check('defaults: Item.Passable = true', it.passable is True)   # cs:432
    ok &= check('defaults: Item.CanUse = true', it.can_use is True)      # cs:314
    ok &= check('defaults: Item.TipIconDimentions = 0.7f',
                _close(it.tip_dimensions, 0.7), it.tip_dimensions)   # Item.cs:236
    ok &= check('defaults: Item.CauseAlarmInterval = 2f',
                _close(it.cause_alarm_interval, 2.0))                # Item.cs:326
    ok &= check('defaults: Alerter.AlerterDelay = 1f',
                _close(it.alerter_delay, 1.0))                       # Alerter.cs:24
    ok &= check('defaults: Item.ItemTipIconDepth = ItemsFront',
                it.tip_icon_depth == 24)                             # Item.cs:230
    d = _door({})
    ok &= check('defaults: Door inherits the Item radii',
                _close(d.use_distance, 0.03) and _close(d.item_use_height, 0.01))
    ok &= check('defaults: Door carries CanUse/DontUseOn/WoodyDeltaUseHeight',
                getattr(d, 'can_use', None) is True
                and getattr(d, 'dont_use_on', 1) is None
                and getattr(d, 'woody_delta_use_height', None) == 0.0
                and getattr(d, 'use_woody_extra', None) is False)

    # -- a serialized falsy value survives (the `or` trap) ------------------
    it0 = _item({'ItemUseHeight': 0.0, 'UseDistance': 0.0, 'AngerAmount': 0,
                 'Passable': False, 'CanUse': False, 'TipIconDimentions': 0.0,
                 'CauseAlarmInterval': 0.0, 'AlerterDelay': 0.0})
    ok &= check('defaults: Item keeps serialized 0 / false',
                it0.item_use_height == 0.0 and it0.use_distance == 0.0
                and it0.anger_amount == 0 and it0.passable is False
                and it0.can_use is False and it0.tip_dimensions == 0.0
                and it0.cause_alarm_interval == 0.0 and it0.alerter_delay == 0.0,
                (it0.item_use_height, it0.use_distance, it0.anger_amount,
                 it0.tip_dimensions))
    d0 = _door({'ItemUseHeight': 0.0, 'UseDistance': 0.0, 'CanUse': False,
                'WoodyDeltaUseHeight': 0.3, 'UseWoodyExtraDeltaHeight': True,
                'DontUseOn': {'path': 77}})
    ok &= check('defaults: Door keeps serialized 0 / false and its widenings',
                d0.item_use_height == 0.0 and d0.use_distance == 0.0
                and getattr(d0, 'can_use', None) is False
                and _close(getattr(d0, 'woody_delta_use_height', 0.0), 0.3)
                and getattr(d0, 'use_woody_extra', None) is True
                and getattr(d0, 'dont_use_on', None) == 77)

    # -- AnimationInstance.UsePattern gates Pattern (cs:66-76, 186-234) ------
    a = _anim(UsePattern=False, Pattern=[39, 38, 37], StartFrame=15, EndFrame=16)
    ok &= check('defaults: Pattern ignored while UsePattern is false',
                a.pattern is None and a.frame_at(0.0) == 15
                and a.frame_at(1.0 / 8.0) == 16, a.pattern)
    a = _anim(UsePattern=True, Pattern=[5, 6, 7])
    ok &= check('defaults: Pattern honoured with UsePattern',
                a.pattern == [5, 6, 7] and a.frame_at(0.0) == 5)

    # -- the shipped data: the port equals the raw JSON field-for-field ------
    bad_items = bad_doors = bad_anims = bad_acts = 0
    n_items = n_anims = n_acts = 0
    for path in sorted(glob.glob(os.path.join(ROOT, 'levels', 's*', '*.json'))):
        raw = json.load(open(path))
        objs = raw['objects']
        L = Level(path)
        for pid, it in L.items.items():
            rd = objs[str(pid)]['data']
            n_items += 1
            if it.item_use_height != rd['ItemUseHeight'] \
                    or it.use_distance != rd['UseDistance'] \
                    or it.anger_amount != rd['AngerAmount'] \
                    or it.tip_dimensions != rd['TipIconDimentions'] \
                    or it.passable != rd['Passable'] or it.can_use != rd['CanUse']:
                bad_items += 1
        for dr in L.doors:
            rd = objs[str(dr.pid)]['data']
            if dr.item_use_height != rd['ItemUseHeight'] \
                    or dr.use_distance != rd['UseDistance'] \
                    or getattr(dr, 'woody_delta_use_height', None) \
                    != rd['WoodyDeltaUseHeight'] \
                    or getattr(dr, 'can_use', None) != rd['CanUse']:
                bad_doors += 1
        # every sprite's Anim against its controller's serialized instance
        ctrls = {}
        for pid, o in objs.items():
            if o.get('type') in ('ItemAnimationController',
                                 'PawnAnimationController') and 'data' in o:
                go = (o['data'].get('m_GameObject') or {}).get('path')
                ctrls[(o['type'], go)] = o['data'].get('Animations') or []
        for s in L.sprites:
            src = ctrls.get((s.kind, s.go))
            if src is None:
                continue
            for an in s.anims:
                if an.src_index is None or an.src_index >= len(src):
                    continue
                ra = src[an.src_index]
                n_anims += 1
                want = (ra.get('Pattern') or None) if ra.get('UsePattern') else None
                if an.pattern != want or an.fps != ra['FrameRate'] \
                        or an.start != ra['StartFrame'] or an.end != ra['EndFrame']:
                    bad_anims += 1
        # RoutineAction.MaximumPawnDistanceToAction raw (RoutineAction.cs:25)
        raw_zero = 0
        for pid, o in objs.items():
            if o.get('type') == 'ActionManager' and 'data' in o:
                raw_zero += sum(1 for x in (o['data'].get('Actions') or [])
                                if x.get('MaximumPawnDistanceToAction') == 0.0)
        port_zero = sum(1 for r in L.routines for x in r['actions']
                        if x['max_distance'] == 0.0)
        n_acts += raw_zero
        if raw_zero != port_zero:
            bad_acts += 1
    ok &= check('defaults: shipped Items keep their radii/anger/flags',
                bad_items == 0 and n_items > 500, (bad_items, n_items))
    ok &= check('defaults: shipped Doors keep radii/WoodyDeltaUseHeight',
                bad_doors == 0, bad_doors)
    ok &= check('defaults: shipped Anims: Pattern only with UsePattern',
                bad_anims == 0 and n_anims > 10000, (bad_anims, n_anims))
    ok &= check('defaults: routine actions keep a 0 MaximumPawnDistance',
                bad_acts == 0 and n_acts > 0, (bad_acts, n_acts))

    # -- World.InvUsed is an honest field (Item.cs:628) ---------------------
    try:
        from world import World
        w = World(Level(os.path.join(ROOT, 'levels', 's1', 'Level101.json')))
        ok &= check('defaults: World._dex_inv_used declared',
                    '_dex_inv_used' in vars(w) and w._dex_inv_used is None)
    except Exception as e:                    # a headless World must build
        ok &= check('defaults: World builds headless', False, e)
    return ok
