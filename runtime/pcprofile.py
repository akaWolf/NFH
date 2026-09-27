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
    (`component`), the GameObject's name (`object`) or the component's own
    fields (`match`), and optionally the item's zone (`zone`); `set` updates
    fields, `append` extends list fields, `anim` + `anim_set` retunes one
    animation of an ItemAnimationController by Name. A Season 2 level takes
    levels/pc/Season2.overlay.json's patches first (tools/pcref/
    pc_respawn_s2.py: Woody's landing). Returns the number of components
    touched."""
    global SEASON2
    SEASON2 = os.path.basename(level.path or '').startswith('Level2')
    n = 0
    if SEASON2:
        # (a level without a Mother leaves her patch unmatched: no warnings)
        n += _apply_file(level, os.path.join(ROOT, 'levels', 'pc', 'Season2.overlay.json'),
                         warn=False)
    p = overlay_path(level.path)
    if not os.path.exists(p):
        return n
    return n + _apply_file(level, p)


def _apply_file(level, p, warn=True):
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
            if 'match' in op:
                if any(d.get(k) != v for k, v in op['match'].items()):
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
        if hit == 0 and warn:
            import sys
            # a patch that touched nothing is a wrong object/component name
            # (the Season 2 neighbour's GameObject is "Rottweiler2", not
            # "Rottweiler"): say so, per patch, instead of applying silently
            print('pcprofile: overlay %s: patch %s matched nothing' % (
                os.path.basename(p), json.dumps({k: op[k] for k in ('object', 'component', 'zone', 'match') if k in op})), file=sys.stderr)
    if n == 0 and warn:
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


# The Season 1 shout after a trick, read from game.exe (fcn.0047bd00,
# docs/PC_ROUTINES.md "The fire's tail"): the fire scores, then plays one
# clip on the neighbour — shout2_extra when the trick was a bonus (the rage
# current above zero as it fired), else by the points and the step's index:
# 5 or fewer shout0_light or shout2, 10 or fewer shout0_medium or shout2,
# more shout0 or shout2, the second of each pair at index 1 (the tables at
# 0x51b584, 0x51b590, 0x51b598, 0x51b5a0); a step carrying flag 2 plays
# none (the tub's hair, the dirty towel, the bath candy, the fuel beer …).
# The fire plays it as an ACTION step on the neighbour (0x47bf7d over
# fcn.00477f60, the name from those tables), so it lasts the action record's
# time as Loader.dll stores it: time="auto" over generic/anims.xml's oneshot
# (92, 25, 45, 26 and 26 frames) less one (0x1000a9e6-0x1000aa05), at 12 a
# second. The mobile's AngryHard plays at the pace that lasts the PC clip
# (World.play_angry); the profile carries the index and the flag per item as
# PCShoutIndex and PCShoutSkip (tools/pcref/pc_reactions.py from
# tools/pcref/fire_sites.py).
# The ACTION step lasts the time + 2: its start (fcn.004772f0 returns not
# done, 0x477ad6), its timer's time + 1 updates (0x47e500, the first on the
# tick after the push), the step ended in the timer's last tick and the next
# one pushed with the run-now flag 0, starting on the tick after
# (tools/pcref/lap_model.py job_ticks).
S1_SHOUT_TICKS = {'shout2_extra': 93, 'shout0_light': 26, 'shout0_medium': 46,
                  'shout0': 27, 'shout2': 27}
# The fire is itself a step of the stand's list (vtable 0x4e5944, update
# 0x47bd00): its first update fires — the score, the rage, the face, the
# jingle — builds a list of its own (fcn.00476770) and pushes it with the
# run-now flag 0 (0x47c015-0x47c031), returning not done; the list's first
# update only pushes its first element (the sequence update 0x476530, the
# run-now flag 0 again), so that element starts two ticks after the fire.
# The list: the step's own clip where it has one (the five- and four-argument
# steps' +0x18: the fall, the shock, the explode), then — unless flag 2 —
# the `shout` icon message (fcn.004618b0 wrapped by fcn.0047c640: an instant
# step, one tick) and the shout ACTION, then — unless flag 1 — a StopMsg
# (fcn.0047c6c0 with fcn.0047bc90, which sets the actor's +0x8a, the level's
# end check; one tick). The step ends with its list, and the stand's next
# step starts on the tick after: flags 0 and no clip of its own, the shout
# starts three ticks after the fire and the next step four after its end.
S1_FIRE_LEAD_TICKS = 2           # the fire's own tick and its list's first update
# The profile's waits and paced clips are whole PC ticks (1/12 s), counted down
# in the frame's steps: k/12 s less 5k steps of 1/60 s leaves a float residue
# (+1e-17 in doubles, ~1e-8 in the clips' floats) that cost one frame more on
# most k — a frame a wait, some 0.1-0.3 s over a chain of reactions. A wait
# ends once what is left is below this.
TIMER_EPS = 1e-6
S1_FIRE_ICON_TICKS = 1           # the `shout` icon message before the shout
S1_FIRE_STOP_TICKS = 1           # the StopMsg after it


def s1_shout_clip(points, bonus, index=0, skip=False):
    """the PC clip name the fire plays, or None"""
    if skip or points <= 0:
        return None
    if bonus:
        return 'shout2_extra'
    if index:
        return 'shout2'
    if points <= 5:
        return 'shout0_light'
    if points <= 10:
        return 'shout0_medium'
    return 'shout0'


def s1_shout_seconds(points, bonus, index=0, skip=False):
    """the PC shout's seconds after a trick, 0 when the step plays none"""
    clip = s1_shout_clip(points, bonus, index, skip)
    return S1_SHOUT_TICKS[clip] / float(S1_TICK_HZ) if clip else 0.0


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


def s1_rage_at(amount, ticks):
    """(current, hold) at the end of the level tick `ticks` after the fire's —
    the fire in the actors' pass (0x43b2f5), the level state's tick after it
    in the same game tick (0x43b2fc): the hold 59 as the fire's tick ends"""
    return max(0, amount - max(0, ticks - 59)), max(0, 59 - ticks)


def s1_rage_before(amount, gap):
    """the current a fire `gap` ticks after the last one finds — its tick's
    actors' pass comes before its level tick: the state at the end of the
    tick before; the +3 is paid iff it is above zero (gap <= amount + 59)"""
    return s1_rage_at(amount, gap - 1)[0] if gap > 0 else amount


def s1_ticks(seconds):
    """the port's seconds between two events as the PC's whole ticks: the
    nearest (the PC runs every step on the 12 Hz tick, the port on its 60 Hz
    frames — a step's end falls up to a frame late)"""
    return int(seconds * S1_TICK_HZ + 0.5)


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


# The Season 2 neighbour's reaction to a trick, read from GameLogic.dll: the
# level script's SHOUT (fcn.1000f977) — its last parameter, the step's
# constant (PCShout, tools/pcref/lap_model_s2.py code_stays_tricked), picks
# the neighbour's action from one of four tables the DLL's static
# initializers fill (0x1007b54b-0x1007b61d): 0 [shout2_light] (0x100df45c),
# 1 [shout2, shout2] (0x100df434), 2 [shout2_hard x3] (0x100df450), 3
# [shout2_high] (0x100df41c), any other level none; before them it always
# picks one of [freakout1, freakout2, freakout3] (0x100df43c,
# 0x1000f998-0x1000f9b0), which the SHOUT element (vtable 0x100ab99c, update
# 0x1000d751) plays instead once the level's status byte +0x28 is set: the
# trick credit fcn.1000140b sets it as the rage reaches 100 000
# (0x10001500) and the level tick (0x10044710-0x100447f1) never clears it,
# so every shout after the gauge's first overflow is a freakout. Each draw
# is the level's random(n) (fcn.10040141), the freakout's first. The
# actions (generic/objects.xml) play the neighbour's animations of their
# names — shout2_light the shout2 one — time="auto" over generic/anims.xml's
# oneshots (shout2 26 frames, shout2_hard 85, shout2_high 26, freakout1 37,
# freakout2 38, freakout3 63), which Loader.dll stores less one. The SHOUT
# element's first update pushes the action's DoActions job in front of
# itself (fcn.10049216) and returns 0 (0x1000d8a2), the job runs the
# Loader's time + 2 ticks from the tick after, and the element's next update
# returns 1 (0x1000d8a6): the reaction lasts the time + 4 — shout2 29,
# shout2_hard 88, shout2_high 29, freakout1 40, freakout2 41, freakout3 66
# (the element ticks of tools/pcref/lap_model_s2.py). Where the model reaches no
# SHOUT the trick record's `laugh` stands in for the level (PCLaugh); the
# mobile's tantrum is its own AngryEasyUp + AngryHard clips (~7.6 s), paced
# to the PC clip under the profile (World.play_angry).
S2_SHOUT_TICKS = {0: (29,), 1: (29, 29), 2: (88, 88, 88), 3: (29,)}
S2_FREAKOUT_TICKS = (40, 41, 66)


def s2_reaction_seconds(level, rng, full=False):
    """the seconds of the PC neighbour's SHOUT at this level (the trick
    record's laugh level where the model reaches no SHOUT): the level's
    action, or, once the gauge has overflowed (`full`), the freakout the
    SHOUT picked first"""
    freak = S2_FREAKOUT_TICKS[rng.randrange(len(S2_FREAKOUT_TICKS))]
    table = S2_SHOUT_TICKS[min(max(int(level), 0), 3)]
    pick = table[rng.randrange(len(table))]
    return (freak if full else pick) / float(S2_TICK_HZ)


def s2_rage_tick(meter, decay_per_tick):
    """one 1/12 s tick of the Season 2 gauge: the meter less the decay, not below zero"""
    return max(0.0, meter - decay_per_tick / 1000.0)


# The Season 2 mini-game, read from GameLogic.dll (docs/PC_FIDELITY.md 2.6):
# the game object (vtable 0x100b1a7c, constructor fcn.100507f4, run once a
# level tick with the mouse by fcn.100508a1 from 0x1004482b) measures the
# thumb from the field's middle in 1/10 px, (mouse - middle) x 10000 / 1000
# with each axis held in -1000..1000 and the pair then to a radius of 1000.
# Its first three ticks move the mouse back onto the middle and leave the
# rate at the constructor's 0; after them it rates the distance and pushes
# the mouse by three sinusoids — amplitudes 20, 10, 5 (0x100b1ff0), 0.064774,
# -0.146118 and 0.369593 rad a tick (0x100cc838), the y's a quarter turn
# ahead (0x100b2010, the binary's pi/4), a phase wrapped once above 6.283078
# (0x100b2020) — times a factor that grows from the combination's startlevel
# to its endlevel with the progress, min(progress, 90) / 90 (0x100b2028;
# combine.xml through the object's +0x28/+0x2c, tools/pcref/pc_minigames.py);
# the constructor starts each phase at rand(8) quarter turns. The level tick
# then moves the mouse by the push (0x100448c6-0x100448db) and draws the
# alarm field while the rate is negative (0x10044880).
S2_GAME_AMPS = (20.0, 10.0, 5.0)
# The field's middle is Woody's `minigame` hotspot (generic/objects.xml:
# woody's <hotspot name="minigame" offset="0/-150"/>): the use_object step
# (fcn.10041735) reads it as the actor's +0x2c/+0x30 plus the offset
# (fcn.10049e01) into the game's middle (the constructor's +0xc/+0x10) and
# the create message (vtable 0x100b1444, slot 79 of the GFX visitor: its
# +0xc/+0x10); GFXEngine makes the field round it (0x1000aa80 -> fcn.10004b00
# -> fcn.1000fb30: +0x24/+0x28), scrolls the camera to hold it at (400, 256),
# the middle of the 800 x 512 scene, within the level (0x1000ab08-0x1000ab7e)
# and puts the mouse on it. Its px are the level's (the PC draws the scene
# 1:1), PX_PER_UNIT to the port's unit.
S2_GAME_HOTSPOT = (0, -150)
# The game's progress bar: every minigame/<tool>.xml (all fifteen alike)
# has <progressbar vertical="true" front="gui/ingame/minigame_progress_
# front.tga" offset="28/28"/>, drawn from the field's corner (fcn.1000fcf0,
# slot 9 of the game's +4): the front 28 px in on each side — the field's
# disk inside its ring (the 138 px field's ring at 26-27 and 110-111) —
# its rows from the bottom up to the progress.
S2_GAME_BAR = (28, 28)
S2_GAME_FREQS = (0.064774, -0.14611809302325582, 0.36959282352941175)
S2_GAME_QUARTER = 0.78538475
S2_GAME_TWO_PI = 6.283078


def s2_game_offset(ox, oy):
    """(mouse - middle) in whole px -> the game's displacement in 1/10 px, each axis held"""
    return max(-1000, min(1000, ox * 10)), max(-1000, min(1000, oy * 10))


def _s2_game_radius(dx, dy):
    """the pair held to a radius of 1000, truncated (fcn.100508a1, 0x10050963 / 0x10050acd)"""
    d2 = dx * dx + dy * dy
    if d2 > 1000000:
        r = math.sqrt(d2)
        return int(dx * 1000 / r), int(dy * 1000 / r)
    return dx, dy


def s2_game_thumb(dx, dy, ticks):
    """the pair the state message carries (the game's +4/+8, 0x10044864-0x1004486f, sent
    before the push): each axis held, past the first three ticks the pair to the radius
    (fcn.100508a1 writes it back at 0x1005097f / 0x1005099a)"""
    return (dx, dy) if ticks < 4 else _s2_game_radius(dx, dy)


def s2_thumb_corner(x, y, field, thumb):
    """GFXEngine's thumb setter (fcn.1000fa00, from fcn.10003b90 on the state message):
    the thumb's corner in the field, (x + 1000) x (field - thumb) / 2000 each axis,
    truncated — the radius's reach puts the thumb's edge on the field's"""
    def cdiv(p):
        q = abs(p) // 2000
        return q if p >= 0 else -q
    return (cdiv((x + 1000) * (field[0] - thumb[0])),
            cdiv((y + 1000) * (field[1] - thumb[1])))


def s2_game_rate(dx, dy, progress, latched):
    """the rate of a tick past the first three (0x1005099d-0x10050a17): by the squared
    distance before the radius, 4 under 200, 3 under 400, 2 under 600, 1 under 800, beyond
    it 0 or, once the progress has latched at 10, -(progress x 4 / 10) held in -40..-4"""
    d2 = dx * dx + dy * dy
    if d2 < 40000:
        return 4
    if d2 < 160000:
        return 3
    if d2 < 360000:
        return 2
    if d2 < 640000:
        return 1
    if latched:
        return max(-40, min(-4, int(-progress * 4 / 10)))
    return 0


def s2_game_push(dx, dy, progress, levels, phases):
    """the mouse push of a tick past the first three, in whole px (0x10050a1a-0x10050b35):
    the wobble added to the displacement held to the radius, less the displacement, over
    ten; `phases` advance in place"""
    dx, dy = _s2_game_radius(dx, dy)
    lo, hi = levels
    factor = (hi - lo) * min(progress, 90) * (1.0 / 90.0) + lo
    sx = sy = 0.0
    for i, (amp, freq) in enumerate(zip(S2_GAME_AMPS, S2_GAME_FREQS)):
        ph = phases[i]
        sx += math.sin(ph) * factor * amp
        sy += math.cos(ph + S2_GAME_QUARTER) * factor * amp
        ph += freq
        if ph > S2_GAME_TWO_PI:
            ph -= S2_GAME_TWO_PI
        phases[i] = ph
    vx, vy = _s2_game_radius(dx + int(sx), dy + int(sy))
    return int((vx - dx) * 1000 / 10000), int((vy - dy) * 1000 / 10000)

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


# The Season 1 jingles: fcn.00437de0 posts its message on every change of
# the level state to 2..5 (the tick, 0x439dd6-0x439df3), and the level
# classes' slot 43 (0x440d40, vtables 0x4e07b8 / 0x4e1638) plays the jingle
# of the table at 0x440fbc by the state less 2 (0x440f23-0x440f34): 2 caught
# after the beating and 4 time's up `jingle_failed`, 3 the catch on sight
# `jingle_caught`, 5 success `jingle_success_normal` — the perfect one is
# never played. A catch plays two: the caught one as it happens, then the
# failed or the success one when the beating's state 1 turns 2 or 5.
S1_JINGLES = {2: 'failed', 3: 'caught', 4: 'failed', 5: 'success'}


def s1_jingles(nfh2=False):
    """Season 1 under the profile: the PC's jingle table"""
    return is_pc() and not nfh2


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
# The neighbour's gaits, Season 1: the actor's +0x38 indexes the facing tables 0x51b5f0 /
# 0x51b648 (0 mg, 1 sn, 2 mr, 3 mrwc, 4 mgbowling1 in both, 5 skate1 in both, 6 piewalk) and
# fcn.0047c7f0 moves him by that record. The level class sets it before a GoTo and back to 0
# at the next case — directly (+0x38) or by a step (fcn.0045f6b0, the value at +4, run by
# 0x479660): the run (2, and 3 on the toilet runs — ebx = 3 from the classes' prologues) on
# every level's `noise` case (the pets' alarm, 107-114: 0x458e6b, 0x45e43f, 0x46b50e, 0x4615a4,
# 0x4563d3, 0x46508c, 0x454262, 0x46834a), the toilet and first-aid rushes (102 0x470034, 103
# 0x45f3e7, 105 0x46ea8a, 106 0x46d0f5, 108's rinse 0x45d729), the antenna's shout (101
# 0x4710e3, 102 0x46fe74), the extinguisher's fetch and the way back to the burning barbecue
# (110 0x45fffe, reset 0x460339), 113's main valve after the flood and heat valve after the hot
# heater (0x452a1c, 0x452497) and 112's way back in after the skate (0x463335); the skate's
# slide to the window (112 0x46312f, 5) and the bowling ball's carry to the window (105
# 0x46e4d3, 4). generic/objects.xml's mr1 18 / mr0 9 (the mrwc records of level_sofa, bath,
# piano and suntan the same), level_fitness's skate1 18, level_piano's mgbowling1 9.
# Season 2 (GameLogic.dll): the actor's +0x3c indexes 0x100de870 / 0x100de8dc (mg, mg, mr,
# mrwc, mgbowling1, skiwalk, mg_fifi, stair — UTF-16 literals at 0x100ab550-0x100ab5ac); a
# level script sets 2 before a walk (fcn.1000e3e0) and the GoTo step's run flag (+0xd,
# fcn.10007df9: the saved gait restored at its end) does the same — generic/objects.xml's
# neighbor, mother and olga carry mr1 18 / mr0 9, and the stairs keep their stair records.
GAIT_PX_PER_TICK = {
    ('Rottweiler', 'run'): (18, 9),       # (along the floor, up or down the room)
    ('Mother', 'run'): (18, 9),
    ('Olga', 'run'): (18, 9),
    ('Rottweiler', 'bowling'): (9, 9),    # mgbowling1 in both tables
    ('Rottweiler', 'skate'): (18, 18),    # skate1 in both tables
}


def rule(name):
    """the diagnostics' switch: NFH_PC_RULES=walk,doors,sight,durations names the PC rules to keep,
    the others fall back to the mobile's (all on when unset) — for bisecting a plan"""
    keep = os.environ.get('NFH_PC_RULES')
    return keep is None or name in keep.split(',')


def walk_speed(role, sneaking, vx, vy, climbing=False, stairs=False, gait='walk'):
    """The multiplier of the pawn's Velocity that moves it at the PC's pace, divided by the
    velocity's own length (the mobile's force). A plain walk moves at the floor record whatever
    its direction: the PC walks along the room's path and steps a tick or two off it to a
    hotspot, while the mobile scene's depth offsets to its items are the remaster's own (the
    axis-by-axis mix over them made the Season 2 laps 20-30 % longer than the PC video's). A door
    approach — the pawn's DOOR_CLIMB / DESCEND states, the PC's ~50 px up to a back door and down
    from its twin — moves at the room's vertical record (`climbing`), or at Season 2's stair
    record on its stairs (`stairs`); tools/pcref/lap_model.py checks those climbs against the
    video. Another gait of the PC case (`gait`: GAIT_PX_PER_TICK, Season 1 — the run, the
    bowling ball's carry) takes its own records. None for a pawn without a record (the Kid
    keeps the mobile's)."""
    rec = WALK_PX_PER_TICK.get('Woody_sneak' if (role == 'Woody' and sneaking) else role)
    n = math.hypot(vx, vy)
    if rec is None or n == 0.0 or not rule('walk'):
        return None
    h, v, st = (r * TICKS_PER_SECOND / PX_PER_UNIT for r in rec)
    if (role, gait) in GAIT_PX_PER_TICK:
        gh, gv = (r * TICKS_PER_SECOND / PX_PER_UNIT for r in GAIT_PX_PER_TICK[(role, gait)])
        h = gh
        if not stairs:
            v = gv
    pace = (st if stairs else v) if climbing else h
    return pace / n


# -- the door transit (docs/PC_VERIFICATION.md "door transit") ----------------------------
# Every door of Season 1 is a <door> of the level's objects.xml with two actions per actor:
# `enter` on the near door, `leave` on the far one, each `time` ticks long, the same figures
# on every door of a type across the 14 levels — the neighbour 19 + 19 through a side door
# and 11 + 22 through a back door, Woody 15 + 23 (right), 18 + 24 (left), 9 + 25 (back) —
# but the front door's pair for Woody on twelve of them (anc/fro's `enter` 18, fro/anc's
# `leave` 23 or 25), which the overlays carry per door (Door.pc_door_ticks).
# game.exe's door step (vtable 0x4e5370, update 0x474590 -> fcn.004741e0) places the actor
# at the far door's hotspot — its room pointer follows the placement (fcn.00448d70) — and
# pushes ONE ACTION step (fcn.00478030 over fcn.00477ed0, vtable 0x4e546c) of two entries,
# the near door's `enter` and the far door's `leave`; the ACTION update starts every entry
# in its one pass over them (the loop 0x477391-0x47793c) and times the step by the longest
# (the running max at 0x477785-0x4777ab, less the step's +0x20, which the door step leaves
# at 0): the two clips run at once, the pass lasting the longer, the far `leave` on every
# door — its time + 2 (E14's frames at 197.9-199.4 s and 202.6-204.5 s: the kitchen's side
# door 17-18 ticks, the living room's back door ~23; E10's "~3 s" from the neighbour's
# arrival at the bedroom's back door is the climb to its hotspot, 50 px at 3 a tick, and
# the pass). So a walk-up door's two strips play at once too, where the mobile runs them
# one after the other (Door.cs, Pawn._begin_transit), and the pawn is placed at the far
# door as the pass starts (the mobile warps at its end). The mobile strips keep their
# frames (the neighbour's far back-door strip has 13 where the PC's has 22) and play at the
# rate that lasts the PC's ticks; in Season 2, whose doors are not <door> objects, they
# run a frame a tick as before.
DOOR_CLIP_FPS = 12.0
DOOR_CLIP = re.compile(r'^(Woody|Rottweiler|Mother|Olga|Kid)Door(Left|Right|Back)(Enter|Leave)$')
# each clip lasts its ACTION step, the action's time + 2 (its start and its
# timer's time + 1 updates; tools/pcref/lap_model.py job_ticks)
DOOR_TICKS = {                    # (the near door's `enter`, the far door's `leave`): the
                                  # pass lasts the longer, the far door's on every door
    ('Rottweiler', 'Back'): (13, 24), ('Rottweiler', 'Left'): (21, 21), ('Rottweiler', 'Right'): (21, 21),
    ('Woody', 'Back'): (11, 27), ('Woody', 'Left'): (20, 26), ('Woody', 'Right'): (17, 25),
}
SEASON2 = False                   # apply_overlay sets it from the level's name


def door_ticks(role, side, nfh2=None):
    """(near, far) ticks of a pawn's Season 1 door pass; None off the rule, in
    Season 2, and for the pawns without <door> actions (the Mother, Olga)"""
    if not is_pc() or not rule('doors') or (SEASON2 if nfh2 is None else nfh2):
        return None
    return DOOR_TICKS.get((role, side))


# Season 2 (GameLogic.dll): a door pair is one step (vtable 0x100ab1b8, fcn.1000340b /
# 0x10003a19) — the walk up to the near door's `<actor>_in`, then the near door's `enter`
# and the far door's `leave` around the placement at `<actor>_out` when the near door has
# an enter action for the actor (fcn.10003647, fcn.10003236), else a movement straight
# from `<actor>_in` to `<actor>_out` (fcn.100037f8 -> fcn.100090bd); the next walk comes
# down from `<actor>_out` to the far floor (fcn.10009177's first waypoint). A movement
# steps one axis a tick at the gait's records (fcn.10009215), each axis run to its
# waypoint ceil(px / record) ticks. The overlays carry each Transition's pass in px of
# the PC scene per pawn (PCPass, tools/pcref/pc_walks_s2.py): `in` and `out` the
# vertical runs off and back onto the floors, `dx`/`dy` the straight movement or
# `enter`/`leave` the two clips.
def s2_pass_ticks(role, gait, p, sneaking=False):
    """the ticks of a Season 2 door pass `p` (a PCPass entry) for the pawn's gait"""
    rec = WALK_PX_PER_TICK.get('Woody_sneak' if (role == 'Woody' and sneaking) else role)
    if rec is None:
        return None
    h, v = rec[0], rec[1]
    if (role, gait) in GAIT_PX_PER_TICK:
        h, v = GAIT_PX_PER_TICK[(role, gait)]

    def run(d, s):
        d = abs(d)
        return -(-d // s) if d else 0
    t = run(p.get('in', 0), v) + run(p.get('out', 0), v)
    if 'enter' in p:
        return t + p['enter'] + p['leave']
    return t + run(p.get('dx', 0), h) + run(p.get('dy', 0), v)


# Season 1 (game.exe, docs/PC_VERIFICATION.md "the walking speed"): a GOTO's walk job
# (vtable 0x4e53d0, update 0x475c80) pushes a mover a leg — to the near door's standing
# point, after the door step from the far door's, at last to the target's hotspot
# (tools/pcref/pc_walks_s1.py) — and a mover (vtable 0x4e59e8, update 0x47cb50) moves one
# axis a tick at the facing's speed record: while x is off the target's, y first goes to
# the room's floor line (the room's point, fcn.0044bac0 on the actor's room, 0x47cbc6-
# 0x47cc9d), then x — its first move `start` px longer when it leaves the standing
# animation (the mover's +0x14 flag and the `ms` test, 0x47ccc6-0x47cd27: generic/
# objects.xml mg1 8 facing right, mg3 10 facing left, the runs' mr1 / mr3 the same) —
# and once x is the target's, y goes to the target's; clamped at the target, found in
# the update of its last move (0x47cf7f-0x47cfac).
S1_START_PX = {           # the first move's extra px, facing right / left (generic/objects.xml)
    'Rottweiler': (8, 10),    # mg1 / mg3, the runs' mr1 / mr3 the same
    'Woody': (12, 12),        # mg1 / mg3
    'Woody_sneak': (2, 2),    # sn1 / sn3
}


def s1_leg_ticks(role, gait, x0, y0, x1, y1, floor, sneaking=False):
    """the ticks of one Season 1 mover from (x0, y0) to (x1, y1), px of the PC scene,
    in a room whose floor line is at `floor`, at the pawn's gait"""
    key = 'Woody_sneak' if (role == 'Woody' and sneaking) else role
    rec = WALK_PX_PER_TICK.get(key)
    if rec is None:
        return None
    h, v = rec[0], rec[1]
    if (role, gait) in GAIT_PX_PER_TICK:
        h, v = GAIT_PX_PER_TICK[(role, gait)]
    t = 0
    standing = True
    if x1 != x0:
        if y0 != floor:
            t += -(-abs(floor - y0) // v)
            y0 = floor
            standing = False
        sp = S1_START_PX.get(key)
        start = sp[0 if x1 > x0 else 1] \
            if standing and sp is not None and (role != 'Rottweiler' or gait in ('walk', 'run')) else 0
        a = abs(x1 - x0)
        t += 1 + (-(-(a - h - start) // h) if a > h + start else 0)
    if y1 != y0:
        t += -(-abs(y1 - y0) // v)
    return t


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


def doors_concurrent(nfh2=None):
    """the near door's `enter` and the far door's `leave` start together, a
    walk-up door's too: one ACTION step of two entries (fcn.004741e0) — Season
    1's (the level's season: the Season 2 pawns but Woody carry no NFH2Path)"""
    return rule('doors') and not (SEASON2 if nfh2 is None else nfh2)


def door_warp_early(nfh2=False):
    """the door step places the pawn at the far door — and flips its zone — as
    the pass starts, before its ACTION step (fcn.004741e0)"""
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
    """Season 1 only: Season 2's catch is GameLogic.dll's watch predicate (s2_sight)"""
    return SEES_WHILE_BUSY and not nfh2 and rule('sight')


# The Season 1 pets (the dog and the parrot share game.exe's class, vtable
# 0x4e3004; its tick fcn.0045bfa0, docs/PC_VERIFICATION.md "The alerters"):
# asleep (2) until a noise of 1 in the room or the whistle wakes it (3: the
# `wakeup` action, the timer set to 72 ticks at 0x45c153), then awake (4): it
# barks while Woody is in its room unhidden, else whines while the
# neighbour is, else idles — the timer counts only there (0x45c45a-0x45c46f)
# and at 0 it falls asleep (1: `fallasleep`, then 2). An action on its queue
# holds the class's step, so the bark and the whine count nothing.
S1_PET_AWAKE_TICKS = 72
# the `wakeup` action of each pet (generic/objects.xml: time auto over
# generic/anims.xml's `wakeup`, a oneshot of 8 frames the dog, 11 the parrot,
# which Loader.dll stores less one — 0x1000a9e6-0x1000aa05 — and its ACTION
# step lasts two more): the first bark — its noise 2 the neighbour's
# `alarm`, the `startle_woody` it posts — comes as it ends (state 3 pushes
# it, state 4 barks on the next free tick)
S1_PET_WAKEUP_TICKS = {'Dog': 9, 'Chili': 12}
# a bark and a whine (generic/objects.xml: the dog's bark1/bark3 time 35
# noise 2 and whine1/whine3 time 23, the parrot's 22 and 29): actions on the
# pet's queue, each holding the class's step to its end — every bark's
# noise 2 the neighbour's `alarm` again, the whine a pose while he is in the
# room; state 4 decides again only as one ends (fcn.0045bfa0). Each is
# (ticks, the remaster's clips it spans): generic/anims.xml's dog bark1 runs
# its 18-frame bark twice in the 35 ticks and poor1 its 12-frame whine twice
# (the remaster's clips are one motion each: the alert pair, two PoorSequence
# clips); the parrot's bark1 is one 22-frame scream (one AlertLeft/Right
# clip), its whine one clip of the remaster's PoorSequence (its idle)
S1_PET_BARK = {'Dog': (37, 2), 'Chili': (24, 1)}      # the steps: the time + 2
S1_PET_WHINE = {'Dog': (25, 2), 'Chili': (31, 1)}


def s1_pets(nfh2=False):
    """Season 1's pets under the profile: the PC class's awake timer and its
    whine at the neighbour (AlerterFSM's PC terms)"""
    return is_pc() and not nfh2 and rule('pets')


# -- the Season 2 catch (docs/PC_VERIFICATION.md "detection", tools/pcref/pc_catch_s2.py) ----
# generic/trigger.xml: the neighbour's and the Mother's `fight` on Woody, position="room"
# type="always" — Loader.dll's trigger parser (0x1000a869-0x1000a936: room 1, nearobj 2,
# house 4; once 0x1000, always 0x2000) into AddObjectTriggerMsg (GameLogic fcn.1004fa5c), the
# level tick's watch walker (fcn.1003fc90) and predicate (fcn.1003f573) under mode 1: both room
# pointers set and equal — none from a pass's `<actor>_in` to its `<actor>_out` (fcn.100037f8,
# fcn.10003647, fcn.10003454) — the target placed (0x20), neither party's flag 4: the enter step
# into a hideout or neighbor_hideout object to the leave step's end (0x100067e9, 0x10006ab7) and
# the level steps' own sets and clears (Item.pc_hideout). No busy, sleep or animation term.
def s2_sight(nfh2=False):
    """the Season 2 catch is the PC's room and flag-4 rule"""
    return nfh2 and rule('sight')


# The Season 2 respawn (docs/PC_VERIFICATION.md "the catch", "the respawn timer"): the catch
# fiber (vtable 0x100ab278, fcn.100061dc) runs on Woody's queue. Case 4 picks the room
# (fcn.10005f58, World._pc_respawn_zone), puts Woody 900 px above the middle of its path
# (0x10006336) and pushes his `respawn` action in front of the fiber (generic/objects.xml: the
# fall of 900 px over its ticks 0-5 and the landing; time auto over the 38 frames of
# generic/anims.xml's `respawn`, 37 by the Loader's rule, a DoActions job of 39 ticks). Case 5,
# once that job is done, clears the catch's flag 0x10000 on Woody and takes the life
# (fcn.10042471): the status' respawn timer gets leveldata.xml's respawntime, 60 ticks
# (0x100424b6), the level update counts it down (0x10044725), and while it runs the `fight`
# and `die` behaviours of generic/trigger.xml refuse Woody (their predicates fcn.1003d526 /
# fcn.1003cd8e read it through fcn.10040123) and GFXEngine draws him outlined (the message of
# 0x10042515 / 0x10044765, visitor slot 80 0x1000ac00: the flag +0x39 of his sprite, which
# draw slot 10 (0x10011c50) turns into four black copies one px off under the frame). On the
# last life (status +0x14 at 1, fcn.1004012a) case 4 skips the fall and case 5 ends the level
# (slot 13 with 0, 0x100424dc).
S2_RESPAWN_ACTION_TICKS = 39
S2_RESPAWN_TICKS = 60
# the `respawn` action's <translation object="true" starttime="0" endtime="5"
# destination="0/900"/> (generic/objects.xml): (start, end, px down), applied by
# the DoActions job on every tick of its count (fcn.100015c4, World._pc_landing_tick)
S2_RESPAWN_FALL = (0, 5, 900)
# the catchers' `fight` on Woody (generic/objects.xml, under Woody's actor): time auto over
# the longer of fight_woody and fly_away_neighbor / fly_away_mother (41 / 44 and 50 / 50
# frames: 43 and 49 by the Loader's rule), a DoActions job of that plus 2 ticks — the
# catch fiber's cases 2-3 wait it out on Woody's fly_away (0x1000647c, 0x10006420) and
# case 4 follows. The animations are the remaster's FightWoody / MotherHitWoody frame
# for frame, a frame a tick (levels/pc/Season2.overlay.json, tools/pcref/pc_respawn_s2.py)
S2_FIGHT_TICKS = {'Rottweiler': 45, 'Mother': 51}


def s2_respawn(nfh2=False):
    """Season 2's respawn is the catch fiber's: the room of fcn.10005f58, the landing, the
    respawn timer"""
    return nfh2 and rule('sight')


def s2_routes(nfh2=False):
    """Season 2's walks between rooms take the PC path finder's route (world.pc_route, the
    GoTo's Dijkstra over the rooms' door hotspots, fcn.1000a421) from wherever they start"""
    return nfh2 and rule('walk')


def gait_speed(role, gait):
    """u/s along the floor of a Season 1 gait record (the skate's slide), None without one"""
    rec = GAIT_PX_PER_TICK.get((role, gait))
    if rec is None or not rule('walk'):
        return None
    return rec[0] * TICKS_PER_SECOND / PX_PER_UNIT
