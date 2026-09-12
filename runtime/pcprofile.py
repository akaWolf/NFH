"""The PC-experience profile (docs/PC_FIDELITY.md): the default since
2026-09-09; NFH_PROFILE=mobile (or --profile=mobile) selects the
mobile-parity runtime, which stays untouched. This module is the one
switch the profile hangs off — a data overlay applied after the
mobile level loads (levels/pc/<Level>.overlay.json) and the rule switches
the world reads through is_pc(). Every overlay entry carries a "source"
(the PC guide / video the deviation comes from), the profile's counterpart
of the runtime's `cs:` citations."""
import json
import math
import os
import re

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
    global SEASON2
    SEASON2 = os.path.basename(level.path or '').startswith('Level2')
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



# -- the walk (docs/PC_VERIFICATION.md "the walking speed", "the lap's timing") -----------
# generic/objects.xml <speed> records of each actor: px a tick along the floor (the facing 1/3
# gaits) and up or down the room (facing 0/2), one axis a tick — fcn.0047c7f0 adds the record
# of the facing animation to the coordinate on every tick of the walk fiber fcn.00475b30
# (0x476148), 12 ticks a second. The mobile scene is 96 px a unit (the house of 101: the
# living room's 586 px path against the 6.8 u zone less the collider's margin, the hall
# 740/8.4, the kitchen 412/5.1; the neighbour's start 504 px against -1.75 u within 9 px;
# Season 2's scenes 93-100 px a unit by the actors' starts of 208 and 201's bridge-to-rail
# span) — one figure serves both seasons. Checked by tools/pcref/lap_model.py: nine Season 1
# laps within 12 % of the PC video.
PX_PER_UNIT = 96.0
TICKS_PER_SECOND = 12.0
WALK_PX_PER_TICK = {
    # role: (along the floor, up or down the room, up or down the stairs — Season 2's stair
    # gaits; Season 1 has no stairs to walk)
    'Rottweiler': (8, 3, 5),       # neighbor mg1 8 / mg0 3, stair1 8 / stair0 5
    'Mother': (8, 3, 5),           # the same records on mother and olga (Season 2)
    'Olga': (8, 3, 5),
    'Woody': (17, 6, 6),           # woody mg1 17 / mg0 6, stair1 17 / stair0 6
    'Woody_sneak': (5, 2, 2),      # sn1 5 / sn0 2 (no stair record: the room's)
}


def rule(name):
    """the diagnostics' switch: NFH_PC_RULES=walk,doors,sight,durations names the PC rules to keep,
    the others fall back to the mobile's (all on when unset) — for bisecting a plan"""
    keep = os.environ.get('NFH_PC_RULES')
    return keep is None or name in keep.split(',')


def walk_speed(role, sneaking, vx, vy, climbing=False, stairs=False):
    """The multiplier of the pawn's Velocity that moves it at the PC's pace, divided by the
    velocity's own length (the mobile's force). A plain walk moves at the floor record whatever
    its direction: the PC walks along the room's path and steps a tick or two off it to a
    hotspot, while the mobile scene's depth offsets to its items are the remaster's own (the
    axis-by-axis mix over them made the Season 2 laps 20-30 % longer than the PC video's). A door
    approach — the pawn's DOOR_CLIMB / DESCEND states, the PC's ~50 px up to a back door and down
    from its twin — moves at the room's vertical record (`climbing`), or at Season 2's stair
    record on its stairs (`stairs`); tools/pcref/lap_model.py checks those climbs against the
    video. None for a pawn without a record (the Kid keeps the mobile's)."""
    rec = WALK_PX_PER_TICK.get('Woody_sneak' if (role == 'Woody' and sneaking) else role)
    n = math.hypot(vx, vy)
    if rec is None or n == 0.0 or not rule('walk'):
        return None
    h, v, st = (r * TICKS_PER_SECOND / PX_PER_UNIT for r in rec)
    pace = (st if stairs else v) if climbing else h
    return pace / n


# -- the door transit (docs/PC_VERIFICATION.md "door transit") ----------------------------
# Every door of Season 1 is a <door> of the level's objects.xml with two actions per actor:
# `enter` on the near door, `leave` on the far one, each `time` ticks long, the same figures
# on every door of a type across the 14 levels — the neighbour 19 + 19 through a side door
# and 11 + 22 through a back door, Woody 15 + 23 (right), 18 + 24 (left), 9 + 25 (back).
# game.exe composes the pair as one step list (fcn.00478030 over fcn.00477ed0: the near
# door's `enter`, then the far door's `leave`), and the PC video of 110 measures the
# bedroom-to-living-room back door at ~3 s from the neighbour's arrival at the door to his
# step out below — the sum — so the two clips run one after the other through a flat door
# too, where the mobile fires both at once (Door.cs, Pawn._begin_transit). The actor is
# placed at the far door's hotspot for the `leave` and its room pointer follows the
# placement (fcn.00448d70), so the room changes at the far clip's START; the mobile warps
# at its end. The mobile strips keep their frames (the neighbour's far back-door strip has
# 13 where the PC's has 23) and play at the rate that lasts the PC's ticks; in Season 2,
# whose doors are not <door> objects, they run a frame a tick as before.
DOOR_CLIP_FPS = 12.0
DOOR_CLIP = re.compile(r'^(Woody|Rottweiler|Mother|Olga|Kid)Door(Left|Right|Back)(Enter|Leave)$')
DOOR_TICKS = {                    # (the near door's `enter`, the far door's `leave`)
    ('Rottweiler', 'Back'): (11, 22), ('Rottweiler', 'Left'): (19, 19), ('Rottweiler', 'Right'): (19, 19),
    ('Woody', 'Back'): (9, 25), ('Woody', 'Left'): (18, 24), ('Woody', 'Right'): (15, 23),
}
SEASON2 = False                   # apply_overlay sets it from the level's name


def door_ticks(role, side, nfh2=None):
    """(near, far) ticks of a pawn's Season 1 door pass; None off the rule, in
    Season 2, and for the pawns without <door> actions (the Mother, Olga)"""
    if not is_pc() or not rule('doors') or (SEASON2 if nfh2 is None else nfh2):
        return None
    return DOOR_TICKS.get((role, side))


def clip_fps(name, fps, frames=0):
    """the rate a door strip plays at: the one that lasts its PC action's ticks
    (Season 1, the neighbour and Woody), else a frame a tick"""
    m = DOOR_CLIP.match(name or '')
    if not m or not rule('doors'):
        return fps
    t = door_ticks(m.group(1), m.group(2))
    if t is None or not frames:
        return DOOR_CLIP_FPS
    return frames * TICKS_PER_SECOND / t[0 if m.group(3) == 'Leave' else 1]


def doors_sequential(nfh2=False):
    """a flat door's Leave -> Enter run one after the other, as the walk-up's do"""
    return rule('doors') and not nfh2


def door_warp_early(nfh2=False):
    """the far door places the pawn — and flips its zone — at its clip's start"""
    return rule('doors') and not nfh2


# -- the catch on sight (docs/PC_VERIFICATION.md "caught on sight", "a busy neighbour") ----
# game.exe: level state 3 when Woody and the neighbour hold the same room object
# ([actor+0x1c], set at the placement and at the door warp through fcn.00448d70's room
# lookup), neither carries flag 4 — inside an object with the hideout flags 0x140: Woody's
# hideouts, the neighbour's `neighbor_hideout` bed of 109 (fcn.004737a0 at 0x473951) — and
# the +0x78 byte is clear, which it always is. No busy, sleeping or blocking-animation window
# (the mobile's IgnoreWoodyWhenUse, IsSleeping and Blocking clauses are the remaster's). The
# neighbour asleep in his hideout is woken by noise 1 in his room: a walking Woody's speed
# record carries noise 1, a sneaking one 0 (generic/objects.xml).
SEES_WHILE_BUSY = True


def sees_while_busy(nfh2=False):
    """Season 1 only: GameLogic.dll's watch predicate (fcn.1003f573) reads mode bits whose meaning is
    still open, so Season 2 keeps the mobile's busy windows until they are read"""
    return SEES_WHILE_BUSY and not nfh2 and rule('sight')
