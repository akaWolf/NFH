#!/usr/bin/env python3
"""The Season 2 mini-games of the PC original into the levels/pc overlays.

    python3 tools/pcref/pc_minigames.py            # print the pairs
    python3 tools/pcref/pc_minigames.py --write    # PCMinigameTicks / PCMinigameLevels into the overlays

The PC has them (the earlier "PC has none" of docs/PC_FIDELITY.md 2.6 is
withdrawn, 2026-09-23): every Season 2 level has one object flagged `game`
in its objects.xml whose Woody action — the hairpin, the reed, the tongs, the
air pump, the brailer, the rasp, the crowbar, the beehive, the shards, or a
bare `use` — carries a `time` of 240, 270 or 360, beside a `failed` action
(the game_failed clip, behaviour `run` on the neighbour). GameLogic.dll runs
the action as the game: the DoAction step (fcn.10001b2c) advances its elapsed
count each level tick not by 1 but by the game's rate (fcn.100507d9, +0x18),
clamps it at the action's `time` and hands the game its progress, elapsed x
100 / time (fcn.100507dd, which latches +0x50 from 10 on); the game object
(vtable 0x100b1a7c, fcn.100508a1 once a level tick) sets the rate from the
thumb's distance to the field's middle in 1/10 px — under 200 it is 4, under
400 3, under 600 2, under 800 1, beyond it 0, or once latched
-(progress x 4 / 10) held in -40..-4 — and leaves it at 0 over its first
three ticks. The action ends when the elapsed count reaches `time` (the
use_object step's check, progress == 100 at 0x10004c68: the object's action)
or drops below 0 (the `failed` action). A thumb held in the middle so takes
3 + ceil(time / 4) level ticks.

The game's wobble comes from the level's combine.xml: the combination that
takes the game object as an ingredient names the game's xml (`game=`, the
field, the alarm field, the tool as the thumb) and a `startlevel` and an
`endlevel` — 1..4 to 3..7 — that the level parser hands the object (the
setter fcn.100452d7 from the object message's +0x14/+0x18, 0x10048b74) and
the use_object step hands the game (fcn.10004353: the object's +0x28/+0x2c
as doubles to fcn.10041735 and the constructor fcn.100507f4, +0x40/+0x48).
fcn.100508a1 grows a factor from startlevel to endlevel with the progress
(min(progress, 90) / 90) and pushes the mouse each tick by three sinusoids of
it (PCMinigameLevels; DexterityState._pc_tick). A lost game plays the object's
`failed` action (PCMinigameFailed, its behavioractor): the neighbour's `run`
on eleven levels; on 203 Olga's `shout`, her shout_chinese whose own
behaviour is the neighbour's `run` (cn_c2's olga actor; PCMinigameFailedClip:
the port's Olga plays her Shout for the clip's 69 frames, then her
EatChinese); on 201's tutorial
toolbox `run` on `aux`, the level's invisible dummy at 0/0 (ship1/level.xml),
and on 212's spikes and 213's pinata no behaviour at all — nobody comes.
The use_object step pushes the `failed` DoActions job in front of itself
(fcn.10002cd5 and fcn.10049216's push_front, 0x10004d51-0x10004d69) on the
tick after the game's end, and the job posts its behaviour as it ends
(state 2, fcn.1004000a at 0x10002708): Woody's game_failed, 9 frames, the
Loader's time 8, the post 10 ticks after the job's first update
(PCMinigameFailedTicks); Olga's shout likewise 70 ticks after hers.

Woody plays the game where the use put him: the object's `woody` hotspot
(its level.xml position plus the hotspot offset), which is off the room's
floor line on thirteen of the fourteen levels — 24 px above it on 204's
dispenser — and the field's middle is 150 px above that point (the
`minigame` hotspot of generic/objects.xml, read into the game's middle and
the create message by fcn.10049e01 from the actor's +0x2c/+0x30).
PCMinigameLift is that point's height above the floor line (the room's
path1 y), which the port adds to its walking line: the remaster keeps
Woody's point on the line and draws him up by the clip's offset.

The pairing mobile dexterity item -> PC game object is by hand (the items'
DexterityUnlocker against the objects' actions). 214's shards round is the
PC's bottomright/hatch_closed — the hatch his first fall leaves closed — and
the mobile's Hatch, whose Dexterity his first Fix sets (Item.HatchFixBehavior,
Item.cs:2550-2579): its data carries Dexterity false.
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import canon  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(HERE))
# level -> (mobile dexterity item, PC game object, its Woody action)
PAIRS = {
    201: ('ToolBox', 'bottomright/toolbox', 'hairpin'),
    202: ('CrayFish', 'beachleft/crayfish', 'reed'),
    203: ('OlgaBag', 'groundright/olgahandbag', 'use'),
    204: ('ToyDispenser', 'wallleft/toy_o_mat', 'use'),
    205: ('DuckCage', 'shop/duckcage', 'use'),
    206: ('DentureAdhesive', 'topleft/kukidentomat', 'use'),
    207: ('CrayFish', 'beachright/crayfish', 'bbqtongs'),
    208: ('Mouse', 'altar/rat', 'use'),
    209: ('Coal', 'coal_area/coal', 'air_pump'),
    210: ('ToolBelt', 'beachleft/toolbelt', 'brailer'),
    211: ('LifeBoat', 'bottomleft/boat', 'rasp'),
    212: ('WhipStonePlate', 'midright/spikes', 'crowbar'),
    213: ('Pinata', 'bottomleft/pinata', 'beehive'),
    214: ('Hatch', 'bottomright/hatch_closed', 'shards'),
}
# the items whose Dexterity a behaviour sets at run time (not in the data)
FIX_DEXTERITY = {214}


def action_time(n, obj, act):
    folder = canon.pc_level(n)['folder']
    s = canon.read('%s/nfh2/x/%s/objects.xml' % (canon.ROOT, folder))
    m = re.search(r'<object name="%s"[^>]*>(.*?)</object>' % re.escape(obj), s, re.S)
    if m is None or '<flag name="game"' not in m.group(1):
        raise KeyError('%d: no game object %s' % (n, obj))
    a = re.search(r'<action name="%s" actor="woody"[^>]*time="(\d+)"' % re.escape(act), m.group(1))
    if a is None:
        raise KeyError('%d: %s has no timed %s' % (n, obj, act))
    return int(a.group(1))


# the PC's actor animations the port's sprites play under another name
CLIPS = {('olga', 'shout_chinese'): 'Shout', ('olga', 'eat_chinese'): 'EatChinese'}


def failed_clip(n, obj):
    """the clip a lost game's behaviour plays on its actor when that is not
    the neighbour's own `run`: the actor's level record's action named after
    the behaviour — 203's olga `shout`: shout_chinese, 69 frames at 12 a
    second, then eat_chinese; its own behaviour, the neighbour's `run`, is
    posted as its job ends, `ticks` after its first update — as {role, clip,
    secs, then, ticks}, None elsewhere"""
    folder = canon.pc_level(n)['folder']
    s = canon.read('%s/nfh2/x/%s/objects.xml' % (canon.ROOT, folder))
    m = re.search(r'<object name="%s"[^>]*>(.*?)</object>' % re.escape(obj), s, re.S)
    a = re.search(r'<action name="failed"([^>]*)>', m.group(1), re.S)
    at = dict(re.findall(r'(\w+)="([^"]*)"', a.group(1))) if a else {}
    actor, beh = at.get('behavioractor'), at.get('behavior')
    if not actor or actor in ('neighbor', 'aux') or not beh:
        return None
    r = re.search(r'<actor name="%s"[^>]*>(.*?)</actor>' % re.escape(actor), s, re.S)
    b = re.search(r'<action name="%s" actor="%s"([^>]*)>' % (re.escape(beh), re.escape(actor)),
                  r.group(1)) if r else None
    if b is None:
        return None
    ba = dict(re.findall(r'(\w+)="([^"]*)"', b.group(1)))
    import lap_model_s2
    frames = lap_model_s2.Data(n).frames.get((actor, ba.get('actoranim')))
    if not frames:
        return None
    role = {'olga': 'Olga', 'mother': 'Mother'}[actor]
    return {'role': role, 'clip': CLIPS[(actor, ba['actoranim'])],
            'secs': round(frames / 12.0, 4),
            'then': CLIPS.get((actor, ba.get('actornextanim'))),
            'ticks': lap_model_s2.Data(n).job_ticks(actor, beh, actor)}


def failed_ticks(n, obj):
    """the ticks of the object's `failed` action as GameLogic.dll runs it:
    its DoActions job from its first update to the one that posts its
    behaviour (lap_model_s2.Data.job_ticks: the Loader's time + 2) — Woody's
    game_failed, 9 frames, on all fourteen (205's duck cage's `ms` is a
    loop, 179 frames, and counts for nothing)"""
    import lap_model_s2
    return lap_model_s2.Data(n).job_ticks(obj, 'failed', 'woody')


def failed_actor(n, obj):
    """whom the game object's `failed` action sends: its behavioractor, '' for
    none (212's spikes, 213's pinata)"""
    folder = canon.pc_level(n)['folder']
    s = canon.read('%s/nfh2/x/%s/objects.xml' % (canon.ROOT, folder))
    m = re.search(r'<object name="%s"[^>]*>(.*?)</object>' % re.escape(obj), s, re.S)
    a = re.search(r'<action name="failed"([^>]*)>', m.group(1), re.S)
    b = re.search(r'behavioractor="(\w+)"', a.group(1)) if a else None
    return b.group(1) if b else ''


def game_lift(n, obj):
    """the height in level px of Woody's place for the game — the object's
    `woody` hotspot, its level.xml position plus the offset — above the
    floor line (path1's y) of the room it stands in"""
    folder = canon.pc_level(n)['folder']
    X = '%s/nfh2/x/%s' % (canon.ROOT, folder)
    ob = canon.read(X + '/objects.xml')
    lv = canon.read(X + '/level.xml')
    m = re.search(r'<object name="%s"[^>]*>(.*?)</object>' % re.escape(obj), ob, re.S)
    h = re.search(r'<hotspot name="woody" offset="(-?\d+)/(-?\d+)"', m.group(1))
    for rm in re.finditer(r'<room name="\w+" offset="([^"]+)" path1="([^"]+)" path2="[^"]+">(.*?)</room>',
                          lv, re.S):
        p = re.search(r'<object name="%s"[^>]*position="(-?\d+)/(-?\d+)"' % re.escape(obj), rm.group(3))
        if p is None:
            continue
        if rm.group(1) != '0/0':
            raise KeyError('%d: room offset %s' % (n, rm.group(1)))
        floor = int(rm.group(2).split('/')[1])
        return floor - (int(p.group(2)) + int(h.group(2)))
    raise KeyError('%d: %s placed in no room' % (n, obj))


def game_levels(n, obj):
    """the startlevel / endlevel of the combination that plays obj's game"""
    folder = canon.pc_level(n)['folder']
    s = canon.read('%s/nfh2/x/%s/combine.xml' % (canon.ROOT, folder))
    for m in re.finditer(r'<combination([^>]*)>(.*?)</combination>', s, re.S):
        a = dict(re.findall(r'(\w+)="([^"]*)"', m.group(1)))
        if 'game' in a and re.search(r'<ingredient name="%s"' % re.escape(obj), m.group(2)):
            return int(a['startlevel']), int(a['endlevel'])
    raise KeyError('%d: no game combination on %s' % (n, obj))


def item_kind(n, name):
    d = json.load(open('%s/levels/s2/Level%d.json' % (ROOT, n)))['objects']
    for o in d.values():
        dd = o.get('data') or {}
        if o['type'] in ('TrickItem', 'Item', 'SearchItem') \
                and (dd.get('Dexterity') or n in FIX_DEXTERITY) \
                and (dd.get('m_GameObject') or {}).get('name') == name:
            return o['type']
    return None


def main(argv):
    write = '--write' in argv
    for n, (item, obj, act) in sorted(PAIRS.items()):
        t = action_time(n, obj, act)
        lo, hi = game_levels(n, obj)
        fa = failed_actor(n, obj)
        fc = failed_clip(n, obj)
        ft = failed_ticks(n, obj)
        kind = item_kind(n, item)
        lift = game_lift(n, obj)
        print('%d %-16s %-12s <- %s.%s time %d: %d ticks held, levels %d..%d, failed %d ticks -> %s%s, lift %d' % (
            n, item, kind, obj, act, t, 3 + -(-t // 4), lo, hi, ft, fa,
            (' (%s %s %.2f s, %d ticks)' % (fc['role'], fc['clip'], fc['secs'], fc['ticks'])) if fc else '',
            lift))
        if not write or kind is None:
            continue
        p = '%s/levels/pc/Level%d.overlay.json' % (ROOT, n)
        ov = json.load(open(p))
        patches = ov.get('patches', [])
        # the keys rewritten in place: in the patch that holds them, else the
        # item's first patch, else a new one (a patch they shared with another
        # writer's keys keeps those)
        e = next((e for e in patches if isinstance(e.get('set'), dict)
                  and 'PCMinigameTicks' in e['set']), None) \
            or next((e for e in patches if e.get('object') == item and e.get('component') == kind
                     and isinstance(e.get('set'), dict)), None)
        if e is None:
            e = {'object': item, 'component': kind, 'set': {}}
            patches.append(e)
        e['set'].pop('PCMinigameFailedClip', None)
        e['set']['PCMinigameTicks'] = t
        e['set']['PCMinigameLevels'] = [lo, hi]
        e['set']['PCMinigameFailed'] = fa
        e['set']['PCMinigameFailedTicks'] = ft
        e['set']['PCMinigameLift'] = lift
        if fc:
            e['set']['PCMinigameFailedClip'] = fc
        ov['patches'] = patches
        note = (" The mini-game (tools/pcref/pc_minigames.py): PCMinigameTicks = the `time` of the"
                " game object's Woody action in objects.xml, PCMinigameLevels = the startlevel and"
                " endlevel of its combine.xml combination (the wobble's range), PCMinigameFailed = the"
                " behavioractor of its `failed` action (the actor a lost game sends running),"
                " PCMinigameFailedTicks = that action's ticks from its job's first update to the one that"
                " posts its behaviour (the Loader's time + 2),"
                " PCMinigameFailedClip = the clip that actor's behaviour plays first when it is not the"
                " neighbour (203's Olga shouts, 69 frames, and her shout's own behaviour, his run, is"
                " posted as her shout's job ends, its `ticks`),"
                " PCMinigameLift = the height in level px of Woody's place for the game (the object's"
                " `woody` hotspot) above its room's floor line, the field's middle 150 px above it.")
        src = ov.get('source', '')
        i = src.find(' The mini-game (tools/pcref/pc_minigames.py)')
        if i >= 0:
            j = src.find(' The ', i + 1)
            src = src[:i] + (src[j:] if j >= 0 else '')
        ov['source'] = src + note
        json.dump(ov, open(p, 'w'), ensure_ascii=False, indent=1)
        open(p, 'a').write('\n')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
