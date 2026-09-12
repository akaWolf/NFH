"""The PC-experience profile (docs/PC_FIDELITY.md): the default since
2026-09-09; NFH_PROFILE=mobile (or --profile=mobile) selects the
mobile-parity runtime, which stays untouched. This module is the one
switch the profile hangs off — a data overlay applied after the
mobile level loads (levels/pc/<Level>.overlay.json) and the rule switches
the world reads through is_pc(). Every overlay entry carries a "source"
(the PC guide / video the deviation comes from), the profile's counterpart
of the runtime's `cs:` citations."""
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def is_pc():
    """read live, not at import: the harness sets the env after its imports"""
    return os.environ.get('NFH_PROFILE', 'pc') != 'mobile'


def overlay_path(level_path):
    name = os.path.basename(level_path).replace('.json', '.overlay.json')
    return os.path.join(ROOT, 'levels', 'pc', name)


def apply_overlay(level):
    """patch level.objs in place. An entry matches components by type
    (`component`), the GameObject's name (`object`) and optionally the item's
    zone (`zone`); `set` updates fields, `append` extends list fields, `anim`
    + `anim_set` retunes one animation of an ItemAnimationController by
    Name. Returns the number of components touched."""
    p = overlay_path(level.path)
    if not os.path.exists(p):
        return 0
    ov = json.load(open(p, encoding='utf-8'))
    n = 0
    for op in ov.get('patches', []):
        hit = 0
        for pid, o in level.objs.items():
            if o.get('type') != op.get('component'):
                continue
            d = o.get('data') or {}
            if 'owner' in op:
                # an ActionManager is addressed by its Owner pawn
                if (d.get('Owner') or {}).get('name') != op['owner']:
                    continue
            else:
                goname = (d.get('m_GameObject') or {}).get('name')
                if goname is None:
                    go = level._go_of(o)
                    goname = ((level._o(go) or {}).get('data') or {}).get('name')
                if goname != op.get('object'):
                    continue
            if op.get('zone') and (d.get('Zone') or {}).get('name') != op['zone']:
                continue
            if 'set' in op:
                d.update(op['set']); n += 1; hit += 1
            if 'append' in op:
                for k, v in op['append'].items():
                    d.setdefault(k, []).extend(v)
                n += 1; hit += 1
            if 'anim' in op:
                for a in d.get('Animations') or []:
                    if a.get('Name') == op['anim']:
                        a.update(op.get('anim_set') or {}); n += 1; hit += 1
            if 'actions_by_index' in op:
                # rebuild an ActionManager's list from the mobile list's
                # indices (duplicates allowed): the PC order of a lap where
                # the same item has several distinct actions (Level104's
                # two ApplePie entries — the fridge and the eat)
                acts = d.get('Actions') or []
                new = [acts[i] for i in op['actions_by_index'] if 0 <= i < len(acts)]
                if new:
                    d['Actions'] = new; n += 1; hit += 1
            if 'actions' in op:
                # rebuild an ActionManager's list from item names, the
                # entries reused (duplicates allowed): the PC order of a lap
                acts = d.get('Actions') or []
                by_name = {}
                for a in acts:
                    nm = (a.get('Item') or {}).get('name')
                    by_name.setdefault(nm, a)
                new = []
                for nm in op['actions']:
                    if nm in by_name:
                        new.append(by_name[nm])
                if new:
                    d['Actions'] = new; n += 1; hit += 1
        if hit == 0:
            import sys
            # a patch that touched nothing is a wrong object/component name
            # (the Season 2 neighbour's GameObject is "Rottweiler2", not
            # "Rottweiler"): say so, per patch, instead of applying silently
            print('pcprofile: overlay %s: patch %s matched nothing' % (
                os.path.basename(p), json.dumps({k: op[k] for k in ('object', 'component', 'owner', 'zone') if k in op})), file=sys.stderr)
    if n == 0:
        import sys
        print('pcprofile: overlay %s matched nothing' % os.path.basename(p), file=sys.stderr)
    return n


# The PC's pass rule (leveldata.xml of the Season 1 game, "minquota"; the
# manual: an episode is a SUCCESS once the minimum viewer rating is reached):
# the same numbers the mobile Entry scene carries as MinRatings, but the
# mobile wins a level on its WinningTricksCount and grades the rating after.
S1_MIN_RATING = {101: 50, 102: 55, 103: 60, 104: 65, 105: 70, 106: 75, 107: 60,
                 108: 65, 109: 70, 110: 75, 111: 60, 112: 65, 113: 70, 114: 75}


def min_rating(level_name):
    """the PC minquota for a Season 1 level name ('Level106'), else None"""
    try:
        return S1_MIN_RATING.get(int(str(level_name)[-3:]))
    except ValueError:
        return None


# The Season 1 anger rule, read from the PC game.exe (docs/PC_ROUTINES.md,
# "The anger and the bonus"): the level state ticks 12 times a second —
# the same tick counts the clock (leveldata's time=4320 is the 6:00 the HUD
# shows, and the HUD divides the remaining ticks by 12), and the raw
# mercury column holds 5.4-5.8 s after a trick (60 ticks plus the top 3 %)
# and falls 0.7 of the level's angrytime in ticks over the visible tube.
# A trick that pays raises the neighbour's rage current to max(current, its
# angrytime — the level's when the trick has none) and starts a 60-tick
# hold (fcn.00438b90); every tick the hold counts down first, then the
# current, one per tick (fcn.00438a80); the HUD's mercury is current * 100
# / the level's angrytime clipped at 100 (GFXEngine 0x10011460); the bonus,
# +3 on the rating, is paid iff the current is above zero when the next
# trick fires (fcn.0047bd00: fcn.004357e0 returns the current). The values
# are the PC data's, in ticks: PCAngryTime on the Rottweiler is level.xml's
# angrytime, PCAngryTime on an item its tricks.xml angrytime.
S1_TICK_HZ = 12
S1_RAGE_HOLD_TICKS = 60


def s1_rage_fire(current, amount):
    """the trick handler's rage part: the new (current, hold)"""
    return max(current, amount), S1_RAGE_HOLD_TICKS


def s1_rage_tick(current, hold):
    """one 1/12 s tick of the level state: the new (current, hold)"""
    if hold > 0:
        return current, hold - 1
    if current > 0:
        return current - 1, hold
    return current, hold


def s1_rage_percent(current, level_angrytime):
    """the mercury: integer percent of the level's angrytime, clipped"""
    if level_angrytime <= 0:
        return 0
    return min(100, current * 100 // level_angrytime)


# The Season 2 gauge, read from GameLogic.dll (docs/PC_ROUTINES.md): the
# level state ticks 12 times a second too (the HUD clock divides the tick
# count by 12); every tick the rage falls by the level record's `time`
# (leveldata.xml, 30 on every level) and the status goes to the HUD; a trick
# adds tricks.xml's rage; the gauge is 100 000 long (the dialog's range, the
# accounting's flag). In the port's units (1 = 1000 rage) the decay per tick
# is PCRageDecay / 1000.
S2_TICK_HZ = 12


def s2_rage_tick(meter, decay_per_tick):
    """one 1/12 s tick of the Season 2 gauge: the meter less the decay, not below zero"""
    return max(0.0, meter - decay_per_tick / 1000.0)

# The Season 1 result screen, read from the PC binaries (docs/PC_VERIFICATION.md
# "The level's end"). The level state machine (game.exe fcn.00436bb0, run
# every tick from fcn.00439cd0) ends a level with 5 = success once the score
# reaches 100 or every reachable trick has fired (the check runs after each
# trick's reaction, fcn.0045b470 -> fcn.0047bc90), with 4 = time's up when
# the clock runs out below the level's minquota and 5 when at or above it,
# and with 2 = caught after the beating (the level classes' last case sets
# state 1) — unless the score already reaches minquota, which makes a catch
# a 5 as well. The game-over dialog (GFXEngine.dll 0x1000e0f9-0x1000e2b1)
# captions the success flag as `perfect` when the viewer rating is 90 or
# more (0x1000e201: cmp [esp+0x70], 0x5a) and `success` below, the time-up
# flag as `timeover` and everything else as `failed`; generic/strings.xml
# spells them BRILLIANT!, SUCCESS!, TIME'S UP!, FAILED!. The same 90 marks
# the episode `perfect` on the level map (fcn.00437de0 at 0x437ebe writes
# the leveldata state 4 for a score of 90 or more, 3 for one at minquota).
S1_PERFECT_RATING = 90
S1_RESULT = {'brilliant': 'BRILLIANT!', 'success': 'SUCCESS!',
             'timeover': "TIME'S UP!", 'failed': 'FAILED!'}


def s1_perfect(rating):
    """the PC's BRILLIANT / map-perfect threshold for a Season 1 rating"""
    return int(rating) >= S1_PERFECT_RATING


def s1_result(won, time_up, rating):
    """the PC game-over caption for a Season 1 outcome (GFXEngine
    0x1000e113-0x1000e2b1): the success flag first, then time's up, else
    failed — a catch with the quota reached is a success (fcn.00436bb0)"""
    if won:
        return S1_RESULT['brilliant' if s1_perfect(rating) else 'success']
    return S1_RESULT['timeover' if time_up else 'failed']


# The Season 2 result screen (docs/PC_VERIFICATION.md "Season 2"): the
# GameLogic level end hands GUIEngine the status struct (eleven dwords) and
# a failed flag, and the dialog fill at GUIEngine 0x10001536-0x10001652
# captions the `rating` text `failed` when the flag is set, `bonus` when
# the status's collapse byte (+0x28, the gauge overflowed) is set,
# `perfect` when the coins (+0) equal the level's total (+4), else
# `success`; generic/strings.xml spells them FAILURE, COLLAPSE!, GOOD JOB!,
# SUCCESS!. The rows below the caption are the board's coins, lives,
# bonus and time (calculate_score's pc_lines).
S2_RESULT = {'failed': 'FAILURE', 'bonus': 'COLLAPSE!', 'perfect': 'GOOD JOB!',
             'success': 'SUCCESS!'}


def s2_result(won, collapsed, completed, total):
    """the PC game-over caption for a Season 2 outcome (GUIEngine
    0x10001536): failed, then the overflow, then every coin, else success"""
    if not won:
        return S2_RESULT['failed']
    if collapsed:
        return S2_RESULT['bonus']
    if total > 0 and completed >= total:
        return S2_RESULT['perfect']
    return S2_RESULT['success']

