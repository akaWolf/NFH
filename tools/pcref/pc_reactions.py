"""The Season 1 trick step's own data, per item, into the levels/pc overlays
(2026-09-22): what game.exe does around a trick, read per fire site by
tools/pcref/trick_branches.py (the level class's case chain simulated with
the trick in place: the stand's DoActions before the fire, the five-argument
step's own clip, the actions after it, the repair or clean) and decoded by
tools/pcref/fire_sites.py (the shout's index and the flags). The keys:

  PCShoutIndex        1 = the cold shout is shout2 (the step's index ≠ 0)
  PCShoutSkip         flag 2: the step plays no shout
  PCUseSecondsTricked the tricked stand's seconds: the actions before the
                      fire, the step's own clip, the actions after it
  PCFireAt            the second of that stand at which the step fires when
                      a clip or more actions follow the fire (0 = on arrival)
  PCFixSeconds        the repair or clean after the fire (0 = the PC plays
                      none, the mobile's fix clips are dropped)
  PCSurpriseSeconds   a walk-by's clip before its fire: the doubletake
                      (its ACTION step, 16 ticks), the skate's fall out of
                      the window, the electric shock
  PCFireBefore        the fire before that clip (the slips, the trap)
  PCSlipSeconds       a slip's fall, slip1/slip3 (31 frames)
  PCGrabSeconds       a fixing tool's take (the mobile's grab), and at the
  PCFixUseSeconds     target the use after the repair (the mobile's redo of
  PCReturnSeconds     the fixing use; 0 = the case plays none) and the give on
                      the way back (0 = the case keeps the tool: no walk back);
  PCToolUseSeconds    a sound tool's use at the target; the tool's tricked
                      use there is PCUseSecondsTricked
  PCRunTo             the case runs to the object (the gait's run, RUNTO):
                      101/102's antenna shout, 110's extinguisher fetch and
                      113's valves — whose station is the switch alone
                      (FIXRUN: PCGrabSeconds; the use and the return none)
  PCAlignX            a look walk-by (the picture, the toilet, the
                      microwave, 111's board): CreateGoToObjXJob before the
                      doubletake (fcn.0047a4a0: the tricked object's hotspot
                      x at the actor's own y)
  PCFixPoint          the tricked object's `neighbor` hotspot [x, y, room],
                      where the repair walks first when he does not stand
                      on it (fcn.0047ae70 over isActorAtObject, fcn.0047aa90)
                      — the look walk-bys and the trap

The seconds are objects.xml's `time` ticks or the clip's frames at 12 a
second. The pairing mobile item -> PC object is the TABLE below, by hand
from the levels' TrickItems and tricks.xml; the notes name the sites whose
stand the tool cannot cut by itself (a station shared by two tricks, the
normal use that follows a repair). An item not in it keeps the mobile clips.

    python3 tools/pcref/pc_reactions.py [--write] [106 110 ...]
    python3 tools/pcref/pc_reactions.py --runs-s2     # RUNTO_S2 into the Season 2 overlays
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import trick_branches as TB   # noqa: E402

ROOT = os.path.dirname(os.path.dirname(HERE))
FPS = 12.0
SLIP = 31 / FPS          # slip1 / slip3
DOUBLETAKE = 15 / FPS    # doubletake3, the one of the pair that plays

# the register-valued index and flags of the sites whose call passes a
# register: the level fiber's prologue constant (fire_sites.py --fibers,
# read 2026-09-22; docs/PC_ROUTINES.md "The fire's tail")
REG = {'lir/stickybook': (1, 0), 'lir/bathcandy': (0, 3), 'toi/tub_hair': (0, 3), 'toi/dirtytowel': (0, 3),
       'bal/fuelbeer': (0, 3), 'kit/laxativebeer': (0, 3), 'kit/candlebox_boom': (1, 0),
       'toi/aftershave_glue': (1, 0), 'toi/grease_exchanged': (1, 0), 'anc/stinkflower': (0, 3),
       'bed/medalbox_rat': (0, 3), 'bed/stickyhat': (1, 0), 'bal/dove_free': (0, 0), 'anc/deadflower': (0, 0),
       'wor/book_replaced': (0, 0), 'kit/skate': (0, 3)}


def use(pc, site=None, before=None, after=None, fix=None, own=None, prime=None, fixwalk=False):
    """a station use: the tool's stand, or the listed (object, action) parts
    (`own`: the five-argument step's clip where the site passes its actor in a
    register; `prime`: the part the mobile's prime leg plays when tricked;
    `fixwalk`: the case walks to `fix`'s hotspot before its repair)"""
    return dict(pc=pc, kind='use', site=site, before=before, after=after, fix=fix, own=own, prime=prime,
                fixwalk=fixwalk)


def wb(pc, site=None, fix=None):
    """a walk-by: doubletake3, the fire, the shout, the clean (fcn.0047d520's handlers)"""
    return dict(pc=pc, kind='wb', site=site, fix=fix)


def tool(pc, back=None, use=None, site=None):
    """a fixing tool's case (the mobile's RoutineActionUseFixingItem chain): the
    take at the tool is the grab (inside the stand's cut or just before the walk
    to the target), the rest of the stand before the fire with the step's own clip
    the tricked use at the target, the actions after the repair the redo's use (0:
    the case has none), `use` = (object, action) the sound tool's action at the
    target, `back`'s give after the walk back the return (none: the case keeps
    the tool, no walk back)"""
    return dict(pc=pc, kind='tool', site=site, back=back, use=use)


TABLE = {
    101: {'Microwave': wb('kit/microwavedirty'), 'Television': use('lir/twistedantenna'),
          'Binoculars': use('kit/binoculars_glue'), 'Sofa': use('lir/sofa_fartbag')},
    102: {'Microwave': wb('kit/microwavedirty'), 'Toilet': wb('toi/toiletstuffed'), 'Television': use('lir/twistedantenna'),
          'Sofa': use('lir/sofa_broken'), 'Beer': use('kit/laxativebeer')},
    103: {'MumPicture': wb('anc/mum_smeared'), 'Toilet': wb('toi/toiletstuffed'), 'Microwave': wb('kit/microwavedirty'),
          # the cake is one PC station (Level_Mail's case 4) the mobile plays
          # as a prime leg and a use: tricked, put_tnt and light_tnt, then
          # celebrate_boom and the fire
          'Candle': use('kit/candlebox_boom'),
          'BirthdayCake': use('kit/candlebox_boom', before=[('kit/cake', 'celebrate_boom')],
                              prime=[('kit/cake', 'put_tnt'), ('kit/cake', 'light_tnt')]),
          'LetterBox': use('anc/mailbox_trap')},
    104: {'MumPicture': wb('anc/mum_smeared'), 'Toilet': wb('toi/toiletstuffed'), 'Microwave': use('kit/microwavedirty'),
          'WhippedCream': use('kit/foamcream'),
          # the basin stand serves both tricks: each item takes its own action
          'SinkAftershave': use('toi/aftershave_glue', before=[('toi/basin', 'shave_glue')], after=[]),
          'AfterShave': use('toi/aftershave_glue', before=[('toi/basin', 'shave_glue')], after=[]),
          'SinkDeodrant': use('toi/grease_exchanged', before=[('toi/basin', 'grow_hair')], after=[]),
          'Deodrant': use('toi/grease_exchanged', before=[('toi/basin', 'grow_hair')], after=[])},
    105: {'MumPicture': wb('anc/mum_smeared'), 'Toilet': wb('toi/toiletstuffed'), 'Microwave': wb('kit/microwavedirty'),
          'Piano': use('lir/scoresmeared'),
          'Football': use('kit/bowlingball'), 'PlantStink': use('anc/stinkflower'), 'Phone': use('anc/phone')},
    106: {'MumPicture': wb('anc/mum_smeared'), 'Toilet': wb('toi/toiletstuffed'), 'Microwave': wb('kit/microwavedirty'),
          'Pudding': use('kit/foambottle'), 'PhotoAlbum': use('lir/stickybook'), 'Candy': use('lir/bathcandy'),
          'BathTub': use('toi/tub_hair'), 'Towel': use('toi/dirtytowel')},
    107: {# the stool's stand is the potter's wheel's: the seat, the cry, the hurt
          # and the repair are the chair's, the potting after it the wheel's use
          'DieselChair': use('kit/stool_pins', after=[]),
          # Level_Art's case 9 tricked: potter_fast, the LEAVE of the wheel
          # (its ENTER is the DieselChair's visit), the fire, a GoTo to
          # kit/potterswheel_fast's own hotspot (0x45814a — 630/420, the
          # wheel's 490/415) and its repair (fixwalk: PCFixPoint)
          'DieselGenerator': use('kit/potterswheel_fast', fix='kit/potterswheel_fast', fixwalk=True,
                                 before=[('kit/potterswheel_fast', 'potter_fast'),
                                         ('kit/potterswheel_fast', 'leave')]),
          'MumStatueFootStool': use('lir/footstool_unlocked'), 'Camera': use('bed/camera_flashy'), 'Dove': use('bal/dove_free')},
    108: {'Shezlong': use('bal/foldingchair_pins'), 'ToothBrush': use('toi/shoebrushset'), 'CoffeeMaker': use('kit/coffeebox_soil'),
          'SunLotion': use('bal/suncream_sweet'), 'Plant': use('anc/deadflower')},
    109: {'AlarmClock': use('bed/cactusclock'), 'PigMilk': use('kit/babybottle_nitro'), 'Bed': use('bed/bed_pins'),
          # the chili's stand plays the chips' trick: CornChips pays it
          # (RoutineActionUse.GetTrickedItem, World._pc_trick_item)
          'Chili': use('kit/cookiebox_hot'), 'CornChips': use('kit/cookiebox_hot'),
          'Teeth': use('bed/teeth_tabasco'), 'Pig': wb('anc/pigout')},
    110: {'BBQ': use('bal/fuelbeer'),
          # case 9: take the extinguisher, go to the burning barbecue, extinguish_explo,
          # repair_extinguisher, extinguish, the fire, the barbecue's repair — the
          # extinguisher is not taken back
          'FireExtinguisher': tool('bed/extinguisher_knotted', use=('bal/barbecue_burn', 'extinguish')),
          'CarnivorPlantSpray': use('bal/growspray'),
          'SteakChair': use('lir/chair_pins'), 'SteakWine': use('lir/vinegar')},
    111: {# the machines' give is the mobile's prime leg (PCUseSeconds' first
          # visit, tools/pcref/pc_durations.py): the tricked use is the rest
          'Drier': use('bas/tumbledrier_smashed', before=[('bas/tumbledrier_smashed', 'dry')]),
          'WashingMachine': use('bas/washingmachine_wine', before=[('bas/washingmachine_wine', 'wash'),
                                                                   ('bas/washingmachine_wine', 'get_clothes')]),
          'FishTank': use('wor/fishfood_soap'), 'Airer': use('bal/clothes_food'), 'Iron': wb('bed/ironingboard_burn'),
          # case 22: take the vacuum, go to the carpet, vacuum_hole, the fire before
          # vacuum_explode, repair, vacuum2, back to lir/vacuum and give — the carpet
          # (Neutral) only sends him, the glued vacuum is the tool that pays
          'Vacuum': tool('lir/vacuum_hole', back='lir/vacuum', use=('lir/dirtycarpet', 'vacuum'))},
    112: {'Weights': use('bas/barbell_sawed'), 'GroundSkates': wb('kit/skate'), 'FishTank': use('wor/fishfood_steroid'),
          'Yoga': use('wor/book_replaced'), 'YogaBook': use('wor/book_replaced'), 'Trampoline': use('bed/trampoline_elastic'),
          'Rope': use('anc/skippingrope_knotted'), 'Bicycle': use('lir/hometrainer_tonged'), 'ChestExpander': use('bas/expander_elastic')},
    113: {'ValveHot': use('kit/heater_hot'), 'ChairAssembly': use('lir/stoolkit_pain'), 'ChairAssemblyBook': use('lir/stoolkit_pain'),
          'Sink': use('toi/basin_flooded'), 'ValveMain': use('toi/basin_flooded'), 'FuseBox': use('anc/fuse'),
          'Ladder': use('wor/ladder_cut'), 'AngleGrinder': use('bal/anglegrinder_manipulated')},
    114: {# the hat stand serves the medal box and the hat (Level_Hunter's cases
          # 22-24): the take and takehat (the Hat's first visit), the medals or
          # the rat's dance (the five-argument step fires first, then
          # `ratdance`), the rip and the sticky hat's fire or the putback, the
          # give (the Hat's second visit) — each visit takes its own part; the
          # take and takehat, played at the Hat's first visit, are no part of
          # the tricked visits
          'MedalBox': use('bed/medalbox_rat', before=[], own=[('neighbor', 'ratdance')], after=[]),
          'Hat': use('bed/stickyhat', before=[('neighbor', 'riphat')]),
          'Gramaphone': use('lir/phono_nail'), 'Polish': use('kit/blackpolish'), 'Horn': use('bal/balloonhorn'),
          'Pipe': use('lir/tabacbox_explosive'), 'Shotgun': use('bas/gun_loaded')},
}
# the fixing runs whose tool is the valve itself: Level_DIY's case 5 sets the run
# gait when the basin flooded (game.exe 0x452a1c) and case 6 switches the main
# valve off (bas/valve_on.switch_off, 0x452afe; the valve Woody opened); case 9
# runs to the heat valve after the hot heater's vent (0x452497) and case 10
# switches it off (bas/heatvalve_on.switch_off, 0x45256a) — then the lap goes on
FIXRUN = {113: {'ValveMain': ('bas/valve_on', 'switch_off'), 'ValveHot': ('bas/heatvalve_on', 'switch_off')}}
# the objects the level class runs to — the gait set to 2 before the GoTo
# (runtime/pcprofile.py GAIT_PX_PER_TICK): the twisted antenna's shout (101
# 0x4710e3, 102 0x46fe74 — the mobile's Television notice run), the
# extinguisher's fetch after the fuel beer and the way back to the burning
# barbecue (110 case 8 0x45fffe, reset in case 9 0x460339 — the mobile's
# fixing chain), the valves of FIXRUN
RUNTO = {101: ('Television',), 102: ('Television',), 110: ('FireExtinguisher',),
         113: ('ValveMain', 'ValveHot')}
# Season 2 (GameLogic.dll): a level script sets the actor's gait (+0x3c) to 2
# before the walk — the co-actor's run to the neighbour after his crash (the
# mobile's hit-pawn of the item's PawnToAffectWhenTricked): 201's Olga at the
# damaged buffet (0x1002ad27), 204's at the rickshaw (0x10033486), 205's at
# the table tennis (0x1002637e), 206's Mother to the ramp on the rabbit's
# crash (0x1002bbd1), 207's Olga to the destroyed sand castle to lift him
# (0x10017606), 210's Mother from her deck chair when Fifi falls off the
# elephant the bat tricked (fifi's `fall`, behavior="crash" on the mother:
# her script's handler, vtable 0x100aca38 slot 4, 0x10018e15 -> 0x10018d76,
# the write 0x10018dd9),
# 214's Olga after the shower and the bouquet (0x1003c035, one handler) and
# its Mother after the pistol (0x1003a27f) — each a gait write then
# fcn.1000eb19's walk to "neighbor"; and 211's neighbour to the ringing cabin
# phone (0x1002fd04, the mobile's alarm)
RUNTO_S2 = {201: ('Buffet',), 204: ('PullKart',), 205: ('TabbleTennis',), 206: ('LaunchPad',),
            207: ('SandCastle',), 210: ('Elephant',), 211: ('CabinPhone',),
            214: ('Shower', 'Bouquet', 'Pistol')}
# the tricked stations whose shout and repair the PC plays back at the item
# after a run (PCTrickReturn, the station's next visit): 205's nailed skis —
# after the ride the script runs him back to the ski (0x10024fde: gait 2),
# where he pants (`pant`), shouts (fcn.1000f977) and repairs it (0x1002512d)
# before the lap goes on (0x10024929); the neighbour's actions, by name
RETURN_S2 = {205: {'WaterSkiis': ('pant',)}}
# the generic handlers: every soap, banana and marbles slip (the fire first,
# one fall clip, index 1; the soap's fcn.0047ddc0 without a clean, the
# marbles' and the banana's with one, SLIP_CLEAN) and the electric trap
# (bas/electrotrap: the fire first, the shock clip, index 1, its repair)
SLIP_NAMES = ('Ground', 'GroundMarbles')
TRAP_NAMES = ('ElectricTrap',)
# the fall's list after the five-argument step: the marbles (fcn.0047b6a0,
# 0x47b838) and the banana (fcn.0047d0e0, 0x47d26c) push the neighbour's
# `clean` of the floor object — 47 ticks the marbles, 11 or 23 the banana by
# its room — before its removal (fcn.0047b610); the soap's (fcn.0047ddc0)
# has none. The mobile's floor item is named Ground (soap, banana) or
# GroundMarbles; the banana's is Ground on the levels whose trigger.xml has
# banana_on_floor
SLIP_CLEAN = {'GroundMarbles': 'marbles'}
BANANA_LEVELS = (107, 108, 109, 110)

KEYS = ('PCShoutIndex', 'PCShoutSkip', 'PCFixSeconds', 'PCUseSecondsTricked', 'PCFireAt', 'PCFireBefore',
        'PCSlipSeconds', 'PCSurpriseSeconds', 'PCGrabSeconds', 'PCFixUseSeconds', 'PCToolUseSeconds',
        'PCReturnSeconds', 'PCRunTo', 'PCTrickReturn', 'PCAlignX', 'PCFixPoint', 'PCBreathSeconds',
        'PCShoutAfter', 'PCPrimeSecondsTricked')


def slip_cleans(n, item, floor, lv):
    """[(zone, seconds)] of the `clean` of `<room>/<floor>` in each zone the
    mobile has the item in (the zone's PC room from the overlay's PCWalkRoom),
    in the mobile file's order"""
    d = json.load(open(os.path.join(ROOT, 'levels/s1/Level%d.json' % n)))
    ov = json.load(open(os.path.join(ROOT, 'levels/pc/Level%d.overlay.json' % n)))
    rooms = {e['object']: e['set']['PCWalkRoom']['room'] for e in ov.get('patches', [])
             if e.get('component') == 'Zone' and 'PCWalkRoom' in (e.get('set') or {})}
    out = []
    for o in d['objects'].values():
        dd = o.get('data') or {}
        if o.get('type') != 'TrickItem' or (dd.get('m_GameObject') or {}).get('name') != item:
            continue
        zone = (dd.get('Zone') or {}).get('name')
        room = rooms.get(zone)
        v = lv.action('%s/%s' % (room, floor), 'clean') if room else None
        if v is not None and zone not in [z for z, _ in out]:
            out.append((zone, v))
    return out


def fix_point(n, obj):
    """the repair's walk target: fcn.0047ae70 asks isActorAtObject (fcn.0047aa90:
    the same room and the actor's point equal to the tricked object's `neighbor`
    hotspot, fcn.00445aa0) and else goes there first (fcn.0044ac80 to that
    object, x and y) — the tricked object, the helper's fourth argument, in
    every Season 1 reaction (the picture 0x47d6f7, the microwave, the toilet
    0x47dbef, the trap 0x47b584, 111's board 0x45495b); [x, y, room]"""
    import lap_model
    p = lap_model.Level(n).object_point(obj)
    return [p[1], p[2], p[0]] if p else None

_ROWS = None
_LEVELS = None


def rows():
    global _ROWS, _LEVELS
    if _ROWS is None:
        _LEVELS = {n: TB.Level(n) for n in TB.LEVEL_DIR}
        _ROWS = TB.analyse(_LEVELS)
        for r in _ROWS:
            r['summary'] = TB.summarise(r, _LEVELS.get(r['level']) or _LEVELS[106])
    return _ROWS


def site_of(n, pc, site=None, kind='use'):
    """the fire site's row for the level: its own class's, else — for a
    walk-by — the generic handler's (no case chain, fcn.0047d520's family),
    else any of that name"""
    cands = [r for r in rows() if r['name'] == pc and (site is None or r['addr'] == site)]
    own = [r for r in cands if r['level'] == n]
    if own:
        return own[0]
    if kind == 'wb':
        handlers = [r for r in cands if not r.get('group')]
        if handlers:
            return handlers[0]
    if cands:
        return cands[0]
    raise KeyError('%d: no fire site of %s' % (n, pc))


def trick_items(n):
    """the level's trick items, and the ones the mobile uses again after the
    fix (ReuseAfterFix: Rottweiler.cs:707-714 — the PC's actions after the
    fire at those stands are that normal use, which the mobile's redo plays
    at the pace of PCUseSeconds, so they stay out of PCUseSecondsTricked).
    An item the TABLE names is one too whatever its mobile score: 109's
    CornChips pays 0 on the mobile and the chips' 15 under the profile"""
    d = json.load(open(os.path.join(ROOT, 'levels/s1/Level%d.json' % n)))
    out = []; reuse = set()
    for o in d['objects'].values():
        if o.get('type') != 'TrickItem' or not (o['data'].get('TrickScore')
                                                 or o['data']['m_GameObject']['name'] in TABLE.get(n, {})):
            continue
        out.append(o['data']['m_GameObject']['name'])
        if o['data'].get('ReuseAfterFix'):
            reuse.add(o['data']['m_GameObject']['name'])
    return out, reuse


def _sum(lv, parts):
    s = 0.0
    for obj, name in parts:
        v = lv.action(obj, name)
        if v is None:
            raise KeyError('%s.%s' % (obj, name))
        s += v
    return s


def index_flags(row):
    a = row['args']
    idx, fl = (a[1] if len(a) > 1 else 0), (a[2] if len(a) > 2 else 0)
    if not isinstance(idx, int) or not isinstance(fl, int):
        idx, fl = REG[row['name']]
    return (1 if idx else 0), fl


def specs(n):
    """item -> {key: value} for the level"""
    lv = _LEVELS[n] if _LEVELS else None
    rows()
    lv = _LEVELS[n]
    out = {}
    names, reuse = trick_items(n)
    for name in names:
        base = name.split('@')[0]
        keys = {}
        if base in SLIP_NAMES:
            keys = {'PCShoutIndex': 1, 'PCFixSeconds': 0.0, 'PCFireBefore': True, 'PCSlipSeconds': round(SLIP, 3)}
            floor = SLIP_CLEAN.get(base) or ('groundbanana' if n in BANANA_LEVELS else None)
            if floor:
                # the clean of the floor object in each of the item's rooms:
                # the level's first as the item's, another as its zone's
                cleans = slip_cleans(n, base, floor, lv)
                if cleans:
                    first = cleans[0][1]
                    keys['PCFixSeconds'] = round(first, 3)
                    for zone, v in cleans[1:]:
                        if v != first:
                            out['%s@%s' % (name, zone)] = {'PCFixSeconds': round(v, 3)}
        elif base in TRAP_NAMES:
            row = site_of(n, 'bas/electrotrap')
            shock = lv.action('neighbor', 'electroshock')
            keys = {'PCShoutIndex': 1, 'PCFireBefore': True, 'PCSurpriseSeconds': round(shock, 3),
                    'PCFixSeconds': round(lv.fix('bas/electrotrap')[1], 3)}
            pt = fix_point(n, 'bas/electrotrap')
            if pt and keys['PCFixSeconds']:
                keys['PCFixPoint'] = pt
        else:
            spec = TABLE.get(n, {}).get(base)
            if spec is None:
                continue
            row = site_of(n, spec['pc'], spec.get('site'), spec['kind'])
            sm = row['summary']
            idx, fl = index_flags(row)
            if idx:
                keys['PCShoutIndex'] = 1
            if fl & 2:
                keys['PCShoutSkip'] = True
            before = _sum(lv, spec['before']) if spec.get('before') is not None else sum(v for _, v in sm['before'])
            after = _sum(lv, spec['after']) if spec.get('after') is not None else sum(v for _, v in sm['after'])
            if base in reuse:
                after = 0.0         # the mobile's redo of the normal use (ReuseAfterFix)
            own = _sum(lv, spec['own']) if spec.get('own') is not None \
                else ((sm['own'][1] or 0.0) if sm['own'] else 0.0)
            if spec.get('fix') is not None:
                fix = lv.fix(spec['fix'])[1]
            else:
                fix = sum(v for _, v in sm['fixes'])
            if sm['unknown'] and spec.get('before') is None:
                print('   %s: unresolved %s' % (name, ', '.join(sm['unknown'])), file=sys.stderr)
            if spec['kind'] == 'wb':
                if row['kind'] == 'OBJ2' and sm['before'] and base == 'GroundSkates':
                    # the skate: the fall out of the window, then the fire
                    keys['PCSurpriseSeconds'] = round(before, 3)
                    keys['PCFixSeconds'] = round(fix + after, 3)
                    # the list's tail after the run back in (Level_Fitness,
                    # 0x46349f and 0x463507): `wheeze`, then an explicit
                    # `shout2` (the UTF-16 name at 0x4e3d54) — the step
                    # itself shouts nothing (flags 3)
                    keys['PCBreathSeconds'] = round(_sum(lv, [('neighbor', 'wheeze')]), 3)
                    keys['PCShoutAfter'] = round(_sum(lv, [('neighbor', 'shout2')]), 3)
                elif base == 'Pig':
                    # the pig's stand: the fire on arrival, the catch after it
                    keys['PCFixSeconds'] = round(fix + after, 3)
                else:
                    # the look (fcn.0047d520 and its kin): CreateGoToObjXJob
                    # (fcn.0047a4a0 — the object's hotspot x at the actor's own
                    # y), the doubletake as an ACTION step (time + 2), the fire,
                    # the shout, the repair with its walk (fix_point)
                    keys['PCSurpriseSeconds'] = round(lv.action('neighbor', 'doubletake3') or DOUBLETAKE, 3)
                    keys['PCFixSeconds'] = round(fix + own + after, 3)
                    keys['PCAlignX'] = True
                    pt = fix_point(n, spec['pc'])
                    if pt:
                        keys['PCFixPoint'] = pt
            elif spec['kind'] == 'tool':
                inside = sum(v for a, v in sm['before'] if a.startswith(spec['pc'] + '.'))
                grab = inside or _sum(lv, [(spec['pc'], 'take')])
                keys['PCGrabSeconds'] = round(grab, 3)
                keys['PCUseSecondsTricked'] = round(before - inside + own, 3)
                keys['PCFireAt'] = round(before - inside, 3)
                keys['PCFixSeconds'] = round(fix, 3)
                keys['PCFixUseSeconds'] = round(after, 3)
                if fix and sm.get('repair'):
                    pt = fix_point(n, sm['repair'])
                    if pt:
                        keys['PCFixPoint'] = pt
                if spec.get('use'):
                    keys['PCToolUseSeconds'] = round(_sum(lv, [spec['use']]), 3)
                keys['PCReturnSeconds'] = round(_sum(lv, [(spec['back'], 'give')]), 3) \
                    if spec.get('back') else 0.0
            else:
                total = before + own + after
                keys['PCFixSeconds'] = round(fix, 3)
                keys['PCUseSecondsTricked'] = round(total, 3)
                if spec.get('prime'):
                    keys['PCPrimeSecondsTricked'] = round(_sum(lv, spec['prime']), 3)
                if fix and sm.get('repair') and spec.get('fix') is None:
                    # the repair helper's walk to the tricked object when he
                    # does not stand on it (fix_point)
                    pt = fix_point(n, sm['repair'])
                    if pt:
                        keys['PCFixPoint'] = pt
                elif fix and spec.get('fixwalk'):
                    pt = fix_point(n, spec['fix'])
                    if pt:
                        keys['PCFixPoint'] = pt
                if own + after > 0 or total == 0:
                    # the fire before the step's own clip or more actions,
                    # or on arrival when the stand plays nothing before it
                    keys['PCFireAt'] = round(before, 3)
        if base in RUNTO.get(n, ()):
            keys['PCRunTo'] = True
            # the run ends on the object's hotspot: the repair does not walk
            keys.pop('PCFixPoint', None)
        run = FIXRUN.get(n, {}).get(base)
        if run is not None:
            keys['PCGrabSeconds'] = round(_sum(lv, [run]), 3)
            keys['PCToolUseSeconds'] = 0.0
            keys['PCReturnSeconds'] = 0.0
        out[name] = keys
    return out


def _strip_key(patches, key):
    """drop `key` from this writer's own patches, the TrickItem ones (_set_key's):
    an Alerter's PCSurpriseSeconds is tools/pcref/pc_durations.py's (ALERTERS)"""
    out = []
    for e in patches:
        st = e.get('set')
        if e.get('component') == 'TrickItem' and isinstance(st, dict) and key in st:
            st = dict(st); del st[key]
            if not st:
                continue
            e = dict(e); e['set'] = st
        out.append(e)
    return out


def _set_key(patches, item, key, value):
    """`item` may name one zone's instance, `Name@ZoneNN` (a patch with `zone`)"""
    base, _, zone = item.partition('@')
    for e in patches:
        if e.get('object') == base and e.get('component') == 'TrickItem' and isinstance(e.get('set'), dict) \
                and (e.get('zone') or '') == zone:
            e['set'][key] = value; return
    p = {'object': base, 'component': 'TrickItem'}
    if zone:
        p['zone'] = zone
    p['set'] = {key: value}
    patches.append(p)


def write(n, sp):
    """the keys set in place — a patch keeps its other keys and its place, a key
    no longer wanted is dropped (and a patch left empty), the new ones added;
    a patch another writer sourced (tools/pcref/pc_durations.py's SEARCHES and
    ALERTERS) is not this writer's"""
    p = os.path.join(ROOT, 'levels/pc/Level%d.overlay.json' % n)
    ov = json.load(open(p)) if os.path.exists(p) else {'source': '', 'patches': []}
    want = {(item, k): v for item, keys in sp.items() for k, v in keys.items()}
    patches = []
    for e in ov.get('patches', []):
        st = e.get('set')
        if e.get('component') == 'TrickItem' and isinstance(st, dict) \
                and 'pc_durations.py' not in (e.get('source') or ''):
            who = e.get('object') + ('@' + e['zone'] if e.get('zone') else '')
            for k in [k for k in st if k in KEYS]:
                v = want.pop((who, k), None)
                if v is None:
                    del st[k]
                else:
                    st[k] = v
            if not st:
                continue
        patches.append(e)
    for (item, k), v in want.items():
        _set_key(patches, item, k, v)
    ov['patches'] = patches
    src = ov.get('source', '')
    note = ("The Season 1 trick step's data per item (tools/pcref/pc_reactions.py over tools/pcref/trick_branches.py: "
            "game.exe's level class simulated with the trick in place, docs/PC_ROUTINES.md \"The fire's tail\"): "
            "PCShoutIndex/PCShoutSkip the step's shout, PCUseSecondsTricked the tricked stand's actions with the "
            "step's own clip, PCFireAt the second of it at which the step fires, PCFixSeconds the repair or clean "
            "after the fire, PCSurpriseSeconds/PCFireBefore/PCSlipSeconds the walk-bys', slips' and trap's clip and fire.")
    if 'trick_branches.py' not in src:
        ov['source'] = (src + ' ' if src else '') + note
    json.dump(ov, open(p, 'w'), ensure_ascii=False, indent=1); open(p, 'a').write('\n')


def write_runs_s2():
    """RUNTO_S2's PCRunTo and RETURN_S2's PCTrickReturn into the Season 2
    overlays (those keys alone)"""
    import lap_model_s2
    for n in sorted(set(RUNTO_S2) | set(RETURN_S2)):
        p = os.path.join(ROOT, 'levels/pc/Level%d.overlay.json' % n)
        ov = json.load(open(p))
        items = RUNTO_S2.get(n, ())
        want = {(item, 'PCRunTo'): True for item in items}
        d = lap_model_s2.Data(n) if n in RETURN_S2 else None
        for item, acts in RETURN_S2.get(n, {}).items():
            ticks = sum(d.action_ticks('neighbor', a) or 0 for a in acts)
            want[(item, 'PCTrickReturn')] = {'pant': round(ticks / FPS, 2)}
            print('== Level%d PCTrickReturn %s: pant %.2f s' % (n, item, ticks / FPS))
        # the keys set in place (a patch's other keys and order kept), the
        # ones no longer wanted dropped, the new ones added
        patches = ov.get('patches', [])
        for e in patches:
            st = e.get('set') or {}
            for key in ('PCRunTo', 'PCTrickReturn'):
                if key in st and e.get('component') == 'TrickItem':
                    v = want.pop((e['object'], key), None)
                    if v is None:
                        st.pop(key)
                    else:
                        st[key] = v
        patches = [e for e in patches if e.get('set') != {}]
        for (item, key), v in want.items():
            _set_key(patches, item, key, v)
        ov['patches'] = patches
        json.dump(ov, open(p, 'w'), ensure_ascii=False, indent=1); open(p, 'a').write('\n')
        print('== Level%d PCRunTo %s' % (n, ', '.join(items)))


def main(argv):
    do_write = '--write' in argv
    if '--runs-s2' in argv:
        write_runs_s2()
        return
    levels = [int(a) for a in argv if a.isdigit()] or sorted(TB.LEVEL_DIR)
    for n in levels:
        sp = specs(n)
        print('== Level%d' % n)
        for item, keys in sp.items():
            print('   %-22s %s' % (item, ' '.join('%s=%s' % (k, v) for k, v in keys.items())))
        if do_write:
            write(n, sp)
            print('   written')


if __name__ == '__main__':
    main(sys.argv[1:])
