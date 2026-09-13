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
  PCSurpriseSeconds   a walk-by's clip before its fire: doubletake3 (15
                      frames), the skate's fall out of the window, the
                      electric shock
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

The seconds are objects.xml's `time` ticks or the clip's frames at 12 a
second. The pairing mobile item -> PC object is the TABLE below, by hand
from the levels' TrickItems and tricks.xml; the notes name the sites whose
stand the tool cannot cut by itself (a station shared by two tricks, the
normal use that follows a repair). An item not in it keeps the mobile clips.

    python3 tools/pcref/pc_reactions.py [--write] [106 110 ...]
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


def use(pc, site=None, before=None, after=None, fix=None):
    """a station use: the tool's stand, or the listed (object, action) parts"""
    return dict(pc=pc, kind='use', site=site, before=before, after=after, fix=fix)


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
          'Candle': use('kit/candlebox_boom'), 'BirthdayCake': use('kit/candlebox_boom'), 'LetterBox': use('anc/mailbox_trap')},
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
          'DieselGenerator': use('kit/potterswheel_fast', fix='kit/potterswheel_fast'),
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
    114: {# the hat stand serves the medal box and the hat: the box's take and
          # the hat's takehat lead to the rat's dance or the medals; the sticky
          # hat's rip follows the medals — each item takes its own part
          'MedalBox': use('bed/medalbox_rat'),
          'Hat': use('bed/stickyhat', before=[('neighbor', 'takehat'), ('neighbor', 'riphat')]),
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
# the generic handlers: every soap, banana and marbles slip (fcn.0047ddc0: the
# fire first, one fall clip, no clean, index 1) and the electric trap
# (bas/electrotrap: the fire first, the shock clip, index 1, its repair)
SLIP_NAMES = ('Ground', 'GroundMarbles')
TRAP_NAMES = ('ElectricTrap',)

KEYS = ('PCShoutIndex', 'PCShoutSkip', 'PCFixSeconds', 'PCUseSecondsTricked', 'PCFireAt', 'PCFireBefore',
        'PCSlipSeconds', 'PCSurpriseSeconds', 'PCGrabSeconds', 'PCFixUseSeconds', 'PCToolUseSeconds',
        'PCReturnSeconds', 'PCRunTo')

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
        elif base in TRAP_NAMES:
            row = site_of(n, 'bas/electrotrap')
            shock = lv.action('neighbor', 'electroshock')
            keys = {'PCShoutIndex': 1, 'PCFireBefore': True, 'PCSurpriseSeconds': round(shock, 3),
                    'PCFixSeconds': round(lv.fix('bas/electrotrap')[1], 3)}
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
            own = (sm['own'][1] or 0.0) if sm['own'] else 0.0
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
                elif base == 'Pig':
                    # the pig's stand: the fire on arrival, the catch after it
                    keys['PCFixSeconds'] = round(fix + after, 3)
                else:
                    keys['PCSurpriseSeconds'] = round(DOUBLETAKE, 3)
                    keys['PCFixSeconds'] = round(fix + own + after, 3)
            elif spec['kind'] == 'tool':
                inside = sum(v for a, v in sm['before'] if a.startswith(spec['pc'] + '.'))
                grab = inside or _sum(lv, [(spec['pc'], 'take')])
                keys['PCGrabSeconds'] = round(grab, 3)
                keys['PCUseSecondsTricked'] = round(before - inside + own, 3)
                keys['PCFireAt'] = round(before - inside, 3)
                keys['PCFixSeconds'] = round(fix, 3)
                keys['PCFixUseSeconds'] = round(after, 3)
                if spec.get('use'):
                    keys['PCToolUseSeconds'] = round(_sum(lv, [spec['use']]), 3)
                keys['PCReturnSeconds'] = round(_sum(lv, [(spec['back'], 'give')]), 3) \
                    if spec.get('back') else 0.0
            else:
                total = before + own + after
                keys['PCFixSeconds'] = round(fix, 3)
                keys['PCUseSecondsTricked'] = round(total, 3)
                if own + after > 0 or total == 0:
                    # the fire before the step's own clip or more actions,
                    # or on arrival when the stand plays nothing before it
                    keys['PCFireAt'] = round(before, 3)
        if base in RUNTO.get(n, ()):
            keys['PCRunTo'] = True
        run = FIXRUN.get(n, {}).get(base)
        if run is not None:
            keys['PCGrabSeconds'] = round(_sum(lv, [run]), 3)
            keys['PCToolUseSeconds'] = 0.0
            keys['PCReturnSeconds'] = 0.0
        out[name] = keys
    return out


def _strip_key(patches, key):
    out = []
    for e in patches:
        st = e.get('set')
        if isinstance(st, dict) and key in st:
            st = dict(st); del st[key]
            if not st:
                continue
            e = dict(e); e['set'] = st
        out.append(e)
    return out


def _set_key(patches, item, key, value):
    for e in patches:
        if e.get('object') == item and e.get('component') == 'TrickItem' and isinstance(e.get('set'), dict):
            e['set'][key] = value; return
    patches.append({'object': item, 'component': 'TrickItem', 'set': {key: value}})


def write(n, sp):
    p = os.path.join(ROOT, 'levels/pc/Level%d.overlay.json' % n)
    ov = json.load(open(p)) if os.path.exists(p) else {'source': '', 'patches': []}
    patches = ov.get('patches', [])
    for k in KEYS:
        patches = _strip_key(patches, k)
    for item, keys in sp.items():
        for k, v in keys.items():
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


def main(argv):
    do_write = '--write' in argv
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
