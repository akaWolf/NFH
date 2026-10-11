#!/usr/bin/env python3
"""The neighbour's station durations from the PC data into the Season 1 overlays.

    python3 tools/pcref/pc_durations.py            # rewrite the PCUseSeconds patches
    python3 tools/pcref/pc_durations.py --show     # print the pairing only

Each PC station of the level class's lap (tools/pcref/lap_model.py: the ICON groups
of the walker's tokens, the DoActions' ticks summed at 12 a second) is paired with the
mobile routine's item that visits it — PAIRS: (mobile item, PC icon, k-th visit of that
icon, and how many consecutive mobile visits share one PC station — or, a tuple of the
station's action names, the mobile visits that split it, one each, a name joined by '+'
summing its actions: 111's machines, the mobile's prime, use and unprime legs, are the
case's give, wash, get_clothes and give, dry, take; 104's basin the shaving chain's six
items, 113's ladder the Ladder's climb and the LadderDrill's drill, touch, climb_down,
114's hat the Hat's take and takehat, the MedalBox's wearmedals, the Hat's putbackhat and
give; each action goes to one visit, in the station's order). The overlay entry
PCUseSeconds carries one value per visit, cycling — every visit counts, the prime and
unprime legs of a toggling station included (Routine._pc_visit_seconds: 111's first
ironing is the give, its second the ironing); RoutineAction._pc_use_seconds plays
the mobile use clips at the pace that lasts it (AnimPlayer.time_scale), or holds a
walk-by stand for it. 106's cycle is two laps (lap_model.CYCLE: the tub filled, then
the bath and the towel).
The walker (tools/pcref/routine_order.py) follows the objects' presence along the lap
(isObjectPresent over level.xml and the switches): 111's second ironing irons the clothes
case 8 gave the board, 113's valve is switched off and on, 114's third phonograph visit
plays the record.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import canon      # noqa: E402
import lap_model  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(HERE))
PAIRS = {
    101: [('Sofa', 'sofa', 0), ('Binoculars', 'binoculars', 0)],
    102: [('Sofa', 'sofa', 0), ('Beer', 'beer', 0)],
    103: [('Candle', 'candle', 0), ('BirthdayCake', 'cake', 0, 2), ('LetterBox', 'mail', 0)],
    # the cream's station ends in the neighbour's own `eat` (his objects.xml record,
    # the mobile's second pie visit, CakeEat); the shaving chain at the basin: the
    # two takes, the shave and the grease, the two gives
    104: [('ApplePie', 'applepie', 0), ('Microwave', 'microwave', 0), ('WhippedCream', 'whippedcream', 0, ('put_cream',)),
          ('ApplePie', 'whippedcream', 0, ('eat',)), ('Deodrant', 'basin', 0, ('take',)), ('AfterShave', 'basin', 0, ('take',)),
          ('SinkAftershave', 'basin', 1, ('shave',)), ('SinkDeodrant', 'basin', 1, ('grease_hair',)),
          ('AfterShave', 'basin', 2, ('give',)), ('Deodrant', 'basin', 2, ('give',))],
    105: [('Piano', 'piano', 0), ('Football', 'football', 0), ('Window', 'football', 1), ('PlantStink', 'flower', 0)],
    # the cycle of two laps (lap_model.CYCLE): the tub filled (the give), then the
    # bath (the shower's enter) and the towel (take_towel, dry, take_towel, the
    # shower's leave) — the mobile's BathTub shown after its first use, hidden
    # after the Towel's
    106: [('PhotoAlbum', 'photo_album', 0), ('Candy', 'candy', 0), ('Pudding', 'milk_bottle', 0), ('BathTub', 'bath', 0),
          ('PhotoAlbum', 'photo_album', 1), ('Candy', 'candy', 1), ('Pudding', 'milk_bottle', 1), ('BathTub', 'bath', 1),
          ('Towel', 'towel', 0)],
    # the painting's case 18 counts its pictures ([this+0x1c] against 3,
    # 0x458bca): the first lap's picture (the easel's SWITCH, the MsgStep,
    # paint1), then paint2, paint3 and the clean with paint1 round (VISIT_LAPS,
    # VISIT_FROM)
    107: [('Drawing', 'painting', 1), ('Camera', 'camera', 0), ('MagnesiumBottle', 'magnesium', 0), ('Camera', 'camera', 1),
          ('DieselChair', 'potterswheel', 0, ('enter',)), ('DieselGenerator', 'potterswheel', 0, ('potter+leave',)),
          ('MumStatueFootStool', 'statue', 1),
          ('Drawing', 'painting', 3), ('Drawing', 'painting', 5), ('Drawing', 'painting', 7)],
    108: [('ToothBrush', 'toothbrush', 0), ('CoffeeMaker', 'coffee', 0), ('Shezlong', 'foldingchair', 0),
          ('WateringCan', 'ewer', 1), ('Plant', 'flower', 0), ('WateringCan', 'ewer', 2)],
    109: [('Teeth', 'teeth', 0), ('Bed', 'sleep', 0), ('AlarmClock', 'alarm_clock', 0), ('Teeth', 'teeth', 1),
          ('PigKeys', 'pig_key', 0), ('PigMilk', 'milk_bottle', 0), ('Pig', 'pig', 1), ('PigMilk', 'milk_bottle', 1),
          ('CornChips', 'cookies', 0), ('Chili', 'parrot', 1), ('PigKeys', 'pig_key', 1)],
    110: [('SteakMeat', 'meatbowl', 0), ('Beer', 'beer', 0), ('BBQ', 'bbq', 0), ('CarnivorPlantSpray', 'plant', 0),
          ('BBQ', 'bbq', 1), ('SteakChair', 'table', 0), ('SteakWine', 'wine', 0)],
    111: [('Detergent', 'detergent', 0), ('WashingMachine', 'washing_machine', 0, ('give', 'wash', 'get_clothes')),
          ('Drier', 'tumble_drier', 0, ('give', 'dry', 'take')), ('Iron', 'ironing', 0), ('Airer', 'laundry_rack', 0),
          ('FishTank', 'aquarium', 0), ('Airer', 'laundry_rack', 1), ('Iron', 'ironing', 1)],
    112: [('YogaBook', 'book', 0), ('FishTank', 'aquarium', 0), ('Yoga', 'yoga_mat', 0), ('YogaBook', 'book', 1),
          ('Trampoline', 'trampoline', 0), ('Bicycle', 'home_trainer', 0), ('Mixer', 'mixer', 0, ('mix', 'drink')),
          ('ChestExpander', 'expander', 0), ('Weights', 'barbell', 0), ('Rope', 'skipping_rope', 0)],
    113: [('ChairAssembly', 'chairkit', 0), ('AngleGrinder', 'powertool', 0), ('ValveMain', 'valve', 0),
          ('Radiator', 'heater', 0), ('Sink', 'basin', 0), ('ValveMain', 'valve', 1), ('FuseBox', 'fuse', 0),
          ('Ladder', 'ladder', 0, ('enter',)), ('LadderDrill', 'ladder', 0, ('drill+touch+climb_down+leave',)),
          ('FuseBox', 'fuse', 1)],
    114: [('Polish', 'polish', 0), ('GoldCup', 'cups', 0), ('Polish', 'polish', 1), ('Pipe', 'smoke', 0),
          ('Gramaphone', 'phonograph', 0), ('CDs', 'records', 0), ('Gramaphone', 'phonograph', 1), ('Pipe', 'smoke', 1),
          ('Gramaphone', 'phonograph', 2), ('Shotgun', 'gun', 0), ('Hat', 'hat', 0, ('take+takehat',)),
          ('MedalBox', 'hat', 0, ('wearmedals',)), ('Hat', 'hat', 0, ('putbackhat+give',)), ('Horn', 'horn', 0)],
}


# the laps a station's visits differ over, past lap_model.CYCLE's: 107's
# painting counter runs four laps round before the walker's state repeats
VISIT_LAPS = {107: 4}
# the visit an item's per-visit lists go round to at their end (PCVisitFrom):
# 107's first lap paints the empty easel, the cycle is the next three laps'
VISIT_FROM = {107: {'Drawing': 1}}


# a case's other arm once another item has been tricked (PCWhenTricked): the
# visit's stand — the list's first update and the action — and the repair's
# after the fire. 107's painting once Woody has cut the dove loose (combine.xml's
# `bal/dove_free` removes `aux`): case 18 paints nonsense on the easel's
# picture (0x458d46-0x458dce), and on the smeared one after its fire with no
# clean (StopMsg, OBJ2 0x458ac4, paint_nonsense 0x458b22)
# 105's window after the bowling ball's kick (once: the next laps kick the
# football again): case 11's list after its GoTo to kit/window — the gait's
# message back, throw_bowling (0x46e591-0x46e63c) — then case 7's DoAction,
# the window's shout (0x46e6ef-0x46e730), the normal visit's whole stay
WHEN_TRICKED = {107: {'Drawing': ('Dove', "the list's first update", [('bal/picture', 'paint_nonsense')],
                                  ('bal/picture_smeared', 'paint_nonsense'), False)},
                105: {'Window': ('Football', "the gait's message back",
                                 [('kit/window', 'throw_bowling'), ('kit/window', 'shout')], None, True)}}


# a hideout the neighbour may leave off his lap: the object's `leave` (the
# Loader's time) as PCLeaveSeconds — 109's bed, left on a noise (the pig
# class's `wakeup`: the LEAVE of bed/bed_sleep at 0x468aff)
LEAVES = {109: [('Bed', 'bed/bed_sleep')]}
# a pet's alarm: the level class's `noise` case runs him to the pet's room, the
# next case plays the neighbour's `search` (fcn.0047a690: the ACTION `search` on
# `neighbor` — e.g. 112's cases 21 and 22, 0x46504a-0x465120) — the Alerter's
# PCSurpriseSeconds, the remaster's Search played at its pace
ALERTERS = (107, 109, 111, 112, 113, 114)
# a room trigger whose case plays the neighbour's `search` before its run: 111's
# dirty carpet — Level_Laundry's case 20 (0x45647f) asserts the carpet dirty and
# pushes the ACTION `search` on him (fcn.00479ba0 at 0x4564ee), case 21 the
# vacuum icon and the walk (0x456502) — the TrickItem's PCSurpriseSeconds, its
# SurpriseFar (the remaster's Search) played at that pace
SEARCHES = {111: ['DirtyCarpet']}
# a container station the neighbour finds emptied by Woody: the case's other
# branch plays his `surprise` (109's key board without its pigkey, Level_Pig's
# case 13, 0x46a109) — the SearchItem's tricked (emptied) visit,
# PCUseSecondsTricked
EMPTIES = {109: ['PigKeys']}


def bubbles(n):
    """(the PC icons' bubbles by name — the icon's gfx in the level's or
    generic objects.xml, spelled as the mobile's bubble of that picture
    where it has one, case aside —, the mobile items' own bubbles by name)"""
    import re
    X = os.path.expanduser('~/nfh-bench/pcref/pc/nfh1/x')
    d = json.load(open(os.path.join(ROOT, 'levels/s1/Level%d.json' % n)))
    mob = {}
    for o in d['objects'].values():
        dd = o.get('data') or {}
        nm = (dd.get('m_GameObject') or {}).get('name')
        bi = dd.get('BubbleIconActivePath') or dd.get('BubbleIconPath')
        if nm and bi:
            mob.setdefault(nm, os.path.splitext(os.path.basename(bi))[0])
    spell = {b.lower(): b for b in mob.values()}
    pc = {}
    for f in (os.path.join(X, 'generic/objects.xml'), os.path.join(X, canon.pc_level(n)['folder'], 'objects.xml')):
        for m in re.finditer(r'<icon name="([^"]+)" gfx="([^"]+)"', open(f, encoding='utf-8', errors='replace').read()):
            b = os.path.splitext(os.path.basename(m.group(2)))[0]
            pc[m.group(1)] = spell.get(b.lower())
    return pc, mob


def pc_stations(n, toks, walks=None, leads=None, enters=None, rooms=None, wrap=True, intros=None,
                empties=None, nexts=None):
    """icon -> [seconds of each visit], and icon -> [[(action, seconds)] of each visit]
    (and into `walks` icon -> [the walk's ticks of each visit: its GOTO's
    moves, doors and no-move ticks, 0 where the case has no GOTO]; into
    `leads` icon -> [the seconds of the leave the next case's walk plays at
    the station's end, after the next ICON — lap_model.WalkLeave — per visit];
    into `enters` icon -> [whether the visit's GOTO is a GOTOENTER, its ENTER
    the GOTO's follow-up — lap_model's 'the GOTO enters' — per visit]; into
    `rooms` icon -> [whether a case of a room's GoTo alone walks before the
    visit's own GOTO — lap_model's 'the room GoTo ends' — per visit])"""
    L = lap_model.Level(n)
    legs = lap_model.model(L, toks[n], steady=False)
    st = lap_model.stations(legs)
    acts = []; lead = []; held = 0.0
    # per station, the seconds of the job-less cases between the case before
    # it — one of no actions: a room's GoTo, a GOTO alone — and its own (101's
    # sofa after the room's GoTo, 107's statue and painting, 109's sleep):
    # the next case runs a tick after each, its walk or its stay later
    # (PCCaseEmpty)
    lost = []
    for kind, text, t in legs:
        if kind == 'icon':
            if held and acts and acts[-1]:
                a, v = acts[-1][-1]; acts[-1][-1] = (a, v + held)
            lost.append(held if (held and acts and not acts[-1]) else 0.0)
            held = 0.0
            acts.append([])
        elif kind == 'action' and text.startswith('step '):
            # a list's instant step (lap_model: its start, a message step, a
            # StopMsg): the stand before the station's next action, the
            # last one's where none follows
            held += t / lap_model.TICK
        elif kind == 'action':
            (acts[-1] if acts else lead).append((text.split()[-1], t / lap_model.TICK + held))
            held = 0.0
    if held:
        tgt = acts[-1] if acts and acts[-1] else lead
        if tgt:
            a, v = tgt[-1]; tgt[-1] = (a, v + held)
    # per station, his animation as the walk after its stay starts (the next
    # station's first walk leg's, lap_model.WalkText: the first move's
    # `start` px needs ms1 / ms3 — PCNextAnim); None with no walk after it
    after = []
    for kind, text, t in legs:
        if kind == 'icon':
            after.append(None)
        elif kind == 'walk' and len(after) >= 2 and after[-2] is None and after[-1] is None \
                and getattr(text, 'anim', None):
            after[-2] = text.anim
    if lead and acts:
        # a steady lap opens inside its first station (lap_model.stations)
        acts.insert(0, acts.pop() + lead)
        lost.insert(0, lost.pop())
        after.insert(0, after.pop())
    ent = []; rgo = []; itr = []
    for kind, text, t in legs:
        if kind == 'icon':
            ent.append(False); rgo.append(False); itr.append(False)
        elif kind == 'intro' and itr:
            itr[-1] = True               # the level's first walk: a GOTO the lap does not time
        elif kind == 'goto' and ent and text == 'the GOTO enters':
            ent[-1] = True
        elif kind == 'goto' and rgo and text == 'the room GoTo ends':
            rgo[-1] = True
    if wrap and len(st) > 1 and st[-1][0].split()[-1] == st[0][0].split()[-1]:
        # (the laps of VISIT_LAPS end inside the cycle, not at its first
        # station: no wrap)
        st[0][1] += st[-1][1]; st[0][2] += st[-1][2]; st = st[:-1]
        acts[0] += acts[-1]; acts = acts[:-1]
        lost[0] += lost[-1]; lost = lost[:-1]
        after = after[:-1]
        if len(ent) > len(st):
            ent[0] = ent[0] or ent[-1]; ent = ent[:-1]
        if len(rgo) > len(st):
            rgo[0] = rgo[0] or rgo[-1]; rgo = rgo[:-1]
    by = {}; parts = {}
    # each station's closing walk leave (the legs' last action of the station)
    closing = []
    cur = None
    for kind, text, t in legs:
        if kind == 'icon':
            closing.append(0.0)
        elif kind == 'action' and closing:
            closing[-1] = t / lap_model.TICK if getattr(text, 'walk_leave', False) else 0.0
    if len(closing) > len(st):
        closing = closing[:len(st)]
    carry = 0; room = False
    for i, ((icon, ta, tw), aa) in enumerate(zip(st, acts)):
        by.setdefault(icon.split()[-1], []).append(ta / lap_model.TICK)
        parts.setdefault(icon.split()[-1], []).append(aa)
        if walks is not None:
            # a case of an ICON and a GOTO alone walks for the next case's
            # visit (109's bed: ICON bed, GOTO bed/bed, then the sleep's case
            # with its ENTER and `sleep`)
            walks.setdefault(icon.split()[-1], []).append(tw + carry)
        if rooms is not None:
            rooms.setdefault(icon.split()[-1], []).append(room)
        # its instant steps and empty cases are no actions (107's statue case,
        # 109's bed: the next case a tick on)
        alone = not aa
        carry = tw if alone else 0
        room = alone and i < len(rgo) and rgo[i]
        if leads is not None:
            leads.setdefault(icon.split()[-1], []).append(closing[i] if i < len(closing) else 0.0)
        if enters is not None:
            enters.setdefault(icon.split()[-1], []).append(ent[i] if i < len(ent) else False)
        if intros is not None:
            intros.setdefault(icon.split()[-1], []).append(itr[i] if i < len(itr) else False)
        if empties is not None:
            empties.setdefault(icon.split()[-1], []).append(lost[i] if i < len(lost) else 0.0)
        if nexts is not None:
            nexts.setdefault(icon.split()[-1], []).append(after[i] if i < len(after) else None)
    if st and (carry or room):
        # the lap's last case walks for its first (101's room GoTo to the
        # living room before the sofa's GOTOENTER)
        first = st[0][0].split()[-1]
        if walks is not None:
            walks[first][0] += carry
        if rooms is not None:
            rooms[first][0] = rooms[first][0] or room
    return by, parts


def item_kind(n, name):
    d = json.load(open('%s/levels/s1/Level%d.json' % (ROOT, n)))['objects']
    for o in d.values():
        dd = o.get('data') or {}
        if o['type'] in ('TrickItem', 'Item', 'SearchItem', 'Drawing', 'Rake', 'Toilet', 'Television') \
                and (dd.get('m_GameObject') or {}).get('name') == name:
            return o['type']
    return None


def main(argv):
    show = '--show' in argv
    toks = lap_model.tokens_of([], os.environ.get('LAP_TOKENS'), {**lap_model.CYCLE, **VISIT_LAPS})
    for n, pairs in sorted(PAIRS.items()):
        if not pairs:
            continue
        walks = {}
        leads = {}
        gents = {}
        grooms = {}
        intros = {}
        emps = {}
        nxs = {}
        by, parts = pc_stations(n, toks, walks, leads, gents, grooms, wrap=n not in VISIT_LAPS, intros=intros,
                                empties=emps, nexts=nxs)
        cempty = {}
        cnext = {}
        # per visit, the PC case's icon (the station's ICON: a visit inside
        # another item's case shows that case's — the mobile its own)
        cicon = {}
        # per visit, the seconds before the stay's end the next case's icon is
        # up: the leave the next case's walk job plays (0x475ce6), after that
        # case's ICON (PCIconLead; the last of a pair's visits)
        icon_leads = {}
        secs = {}
        notes = []
        spent = {}
        # per visit, whether it opens its PC case with the case's own GOTO:
        # the first visit of the case (a split case's later ones, another
        # item's share of it, go on where the first left him) and a case
        # that walks (PCCaseGoto: where the mobile uses the station in
        # place, the GOTO's ticks stand — three with no move,
        # Routine._pc1_inplace_walk)
        cases = {}
        # ... and whether that GOTO is a GOTOENTER (PCCaseEnter: its ENTER
        # starts in the arrival's tick, Pawn._pc1_case), and whether a room's
        # GoTo walks before it in a case of its own (PCCaseRoom: the leg
        # after its door starts the GOTO's walk, Pawn._pc1_marks)
        centers = {}
        crooms = {}
        opened = set()
        # a station split over items: its closing leave, after the next ICON,
        # ends its last item's visit (107's wheel: the generator's, not the
        # chair's)
        last_of = {(pr[1], pr[2]): i for i, pr in enumerate(pairs)}
        for i, pr in enumerate(pairs):
            item, icon, k = pr[0], pr[1], pr[2]
            share = pr[3] if len(pr) > 3 else 1
            vals = by.get(icon, [])
            if k >= len(vals):
                print('%d: no PC station %s #%d for %s' % (n, icon, k, item)); continue
            nv = len(share) if isinstance(share, tuple) else share
            ld = round((leads.get(icon) or [0.0] * (k + 1))[k], 3) \
                if k < len(leads.get(icon) or []) and last_of[(icon, k)] == i else 0.0
            icon_leads.setdefault(item, []).extend([0.0] * (nv - 1) + [ld])
            first = (icon, k) not in opened
            opened.add((icon, k))
            goes = bool((walks.get(icon) or [0] * (k + 1))[k]) or bool((intros.get(icon) or [False] * (k + 1))[k])
            cases.setdefault(item, []).extend([first and goes] + [False] * (nv - 1))
            ge = bool((gents.get(icon) or [False] * (k + 1))[k])
            centers.setdefault(item, []).extend([first and goes and ge] + [False] * (nv - 1))
            gr = bool((grooms.get(icon) or [False] * (k + 1))[k])
            crooms.setdefault(item, []).extend([first and goes and gr] + [False] * (nv - 1))
            em = (emps.get(icon) or [0.0] * (k + 1))[k] if first else 0.0
            cempty.setdefault(item, []).extend([int(round(em * lap_model.TICK))] + [0] * (nv - 1))
            # (the station's last visit: its stay's end is the station's)
            nxa = (nxs.get(icon) or [None] * (k + 1))[k] if last_of[(icon, k)] == i else None
            cnext.setdefault(item, []).extend([None] * (nv - 1) + [nxa])
            cicon.setdefault(item, []).extend([icon] * nv)
            if isinstance(share, tuple):
                # the station split by its actions, one mobile visit each (a
                # name joined by '+' sums its actions into one visit); each of
                # the station's actions goes to one visit, in their order
                aa = parts[icon][k]
                used = spent.setdefault((icon, k), set())
                got = []
                for group in share:
                    tot = 0.0
                    for name in group.split('+'):
                        j = next((j for j, (a, _) in enumerate(aa) if a == name and j not in used), None)
                        if j is None:
                            break
                        used.add(j); tot += aa[j][1]
                    else:
                        got.append(tot)
                        continue
                    print('%d: no action %s at %s#%d for %s' % (n, group, icon, k, item)); break
                else:
                    secs.setdefault(item, []).extend(round(v, 2) for v in got)
                    notes.append('%s <- %s#%d %s' % (item, icon, k, ', '.join(
                        '%s %.2f s' % (a, v) for a, v in zip(share, got))))
                continue
            v = round(vals[k] / share, 2)
            for _ in range(share):
                secs.setdefault(item, []).append(v)
            notes.append('%s <- %s#%d %.1f s%s' % (item, icon, k, vals[k], ' /%d' % share if share > 1 else ''))
        print('%d: %s' % (n, '; '.join(notes)))
        if show:
            continue
        p = '%s/levels/pc/Level%d.overlay.json' % (ROOT, n)
        ov = json.load(open(p)) if os.path.exists(p) else {'source': 'the PC data (tools/pcref)', 'patches': []}
        # in place: an entry keeps its other keys (tools/pcref/pc_reactions.py merges the
        # trick step's into the same object's entry) and its place in the file
        patches = []
        for e in ov.get('patches', []):
            st = e.get('set') or {}
            # a case handler's own visit keeps its hand-read stay (102's and
            # 105's toilets: tools/pcref/pc_reactions.py)
            if 'PCUseSeconds' in st and e.get('object') not in secs and not st.get('PCCaseHandler'):
                st = {k: v for k, v in st.items() if k != 'PCUseSeconds'}
                if not st:
                    continue
                e = dict(e, set=st)
            patches.append(e)
        ov['patches'] = patches
        if n in ALERTERS:
            L = lap_model.Level(n)
            t = L.job_ticks('neighbor', 'search')
            mob = json.load(open('%s/levels/s1/Level%d.json' % (ROOT, n)))['objects']
            pets = sorted({((o.get('data') or {}).get('m_GameObject') or {}).get('name')
                           for o in mob.values() if o.get('type') == 'Alerter'} - {None})
            # the case builds the alarm's list (fcn.0047a690) and pushes it with
            # the run-now flag 0: its first update a tick before the `search`;
            # after it, the pet found in his room, the list's GoTo to the pet
            # (the mobile's run already ends at it) and `shout0_light`
            shout = L.job_ticks('neighbor', 'shout0_light')
            for pet in pets:
                v = round((t + 1) / lap_model.TICK, 3)
                sv = round(shout / lap_model.TICK, 3)
                src = ("the pet's alarm: the level class's `noise` case, then its list (fcn.0047a690: "
                       "pushed with the run-now flag 0) — the neighbour's `search` (generic/objects.xml, "
                       "the Loader's time %d ticks at 12 a second, + 2, + the list's first update) and, "
                       "the pet in his room, `shout0_light` (%d ticks: PCAlarmShoutSeconds; "
                       "tools/pcref/pc_durations.py ALERTERS)" % (t - 2, shout))
                e = next((e for e in ov['patches'] if e.get('object') == pet
                          and 'PCSurpriseSeconds' in (e.get('set') or {}) and e.get('component') == 'Alerter'), None)
                if e is not None:
                    e['set']['PCSurpriseSeconds'] = v
                    e['set']['PCAlarmShoutSeconds'] = sv
                    e['source'] = src
                else:
                    ov['patches'].append({'object': pet, 'component': 'Alerter',
                                          'set': {'PCSurpriseSeconds': v, 'PCAlarmShoutSeconds': sv},
                                          'source': src})
        for item in SEARCHES.get(n, ()):
            t = lap_model.Level(n).job_ticks('neighbor', 'search')
            v = round(t / lap_model.TICK, 3)
            src = ("the room trigger's case: the neighbour's `search` before the run (Level_Laundry's case 20, "
                   "fcn.00479ba0 at 0x4564ee; generic/objects.xml, an ACTION step of %d ticks — the Loader's "
                   "time %d + 2 — at 12 a second, tools/pcref/pc_durations.py SEARCHES)" % (t, t - 2))
            e = next((e for e in ov['patches'] if e.get('object') == item
                      and 'PCSurpriseSeconds' in (e.get('set') or {})), None)
            if e is not None:
                e['set']['PCSurpriseSeconds'] = v
                e['source'] = src
            else:
                ov['patches'].append({'object': item, 'component': item_kind(n, item),
                                      'set': {'PCSurpriseSeconds': v}, 'source': src})
        for item in EMPTIES.get(n, ()):
            t = lap_model.Level(n).job_ticks('neighbor', 'surprise')
            v = round(t / lap_model.TICK, 3)
            src = ("the emptied container's branch: the neighbour's `surprise` (Level_Pig's case 13, 0x46a109; "
                   "generic/objects.xml, an ACTION step of %d ticks — the Loader's time %d + 2 — at 12 a second, "
                   "tools/pcref/pc_durations.py EMPTIES)" % (t, t - 2))
            e = next((e for e in ov['patches'] if e.get('object') == item
                      and 'PCUseSecondsTricked' in (e.get('set') or {})), None)
            if e is not None:
                e['set']['PCUseSecondsTricked'] = v
                e['source'] = src
            else:
                ov['patches'].append({'object': item, 'component': item_kind(n, item),
                                      'set': {'PCUseSecondsTricked': v}, 'source': src})
        for item, obj in LEAVES.get(n, ()):
            t = lap_model.Level(n).job_ticks(obj, 'leave')
            if t is None:
                print('%d: no leave of %s for %s' % (n, obj, item)); continue
            v = round(t / lap_model.TICK, 3)
            src = ("the PC hideout's `leave` (level_%s's objects.xml %s, the Loader's time %d ticks at 12 a "
                   "second, tools/pcref/pc_durations.py LEAVES)" % (canon.pc_level(n)['folder'][6:], obj, t))
            e = next((e for e in ov['patches'] if e.get('object') == item
                      and 'PCLeaveSeconds' in (e.get('set') or {})), None)
            if e is not None:
                e['set']['PCLeaveSeconds'] = v
                e['source'] = src
            else:
                ov['patches'].append({'object': item, 'component': item_kind(n, item),
                                      'set': {'PCLeaveSeconds': v}, 'source': src})
        for item, vals in secs.items():
            kind = item_kind(n, item)
            if kind is None:
                print('%d: no item %s' % (n, item)); continue
            src = ("the PC station's DoActions at 12 ticks a second (level_%s's objects.xml and anims.xml through "
                   "tools/pcref/lap_model.py, paired in tools/pcref/pc_durations.py): %s"
                   % (canon.pc_level(n)['folder'][6:], '; '.join(x for x in notes if x.startswith(item + ' <-'))))
            # a visit the PC plays no action at stays a list ([0.0]): a bare 0
            # reads as no PC seconds (runtime/scene.py)
            v = vals if len(vals) > 1 or not vals[0] else vals[0]
            e = next((e for e in ov['patches'] if e.get('object') == item and e.get('component') == kind
                      and 'PCUseSeconds' in (e.get('set') or {})), None)
            if e is not None:
                e['set']['PCUseSeconds'] = v
                e['source'] = src
            else:
                e = {'object': item, 'component': kind, 'set': {'PCUseSeconds': v}, 'source': src}
                ov['patches'].append(e)
            cg = cases.get(item) or []
            if len(cg) == len(vals):
                # (all false too: the visits inside a case walk none, Pawn._pc1_case)
                e['set']['PCCaseGoto'] = cg if len(cg) > 1 else cg[0]
            else:
                e['set'].pop('PCCaseGoto', None)
            ce = centers.get(item) or []
            if any(ce) and len(ce) == len(vals):
                e['set']['PCCaseEnter'] = ce if len(ce) > 1 else ce[0]
            else:
                e['set'].pop('PCCaseEnter', None)
            cr = crooms.get(item) or []
            if any(cr) and len(cr) == len(vals):
                e['set']['PCCaseRoom'] = cr if len(cr) > 1 else cr[0]
            else:
                e['set'].pop('PCCaseRoom', None)
            il = icon_leads.get(item) or []
            if any(il) and len(il) == len(vals):
                e['set']['PCIconLead'] = il if len(il) > 1 else il[0]
            else:
                e['set'].pop('PCIconLead', None)
            cn = cnext.get(item) or []
            if any(cn) and len(cn) == len(vals):
                e['set']['PCNextAnim'] = cn if len(cn) > 1 else cn[0]
            else:
                e['set'].pop('PCNextAnim', None)
            # the bubble of a visit inside another item's case: that case's
            # icon (PCIcon; set only — 109's bed is a hand patch), where the
            # mobile has the picture (a name only the PC's art has —
            # bubble_bildband, bubble_aquarium — is left to the mobile's)
            ci = cicon.get(item) or []
            pcb, mob = bubbles(n)
            want = [pcb.get(ic) for ic in ci]
            if len(ci) == len(vals) and all(want) and mob.get(item) and any(w != mob[item] for w in want):
                e['set']['PCIcon'] = want if len(set(want)) > 1 else want[0]
            ce2 = cempty.get(item) or []
            if any(ce2) and len(ce2) == len(vals):
                e['set']['PCCaseEmpty'] = ce2 if len(ce2) > 1 else ce2[0]
            else:
                e['set'].pop('PCCaseEmpty', None)
            vf = VISIT_FROM.get(n, {}).get(item)
            if vf:
                e['set']['PCVisitFrom'] = vf
            else:
                e['set'].pop('PCVisitFrom', None)
            wt = WHEN_TRICKED.get(n, {}).get(item)
            if wt:
                other, instant, uses, fix, once = wt
                L = lap_model.Level(n)
                tus = [L.job_ticks(uo, ua) for uo, ua in uses]
                br = {'PCUseSeconds': round((1 + sum(tus)) / lap_model.TICK, 2)}
                text = ' and '.join("%s's %s (%d ticks)" % (uo, ua, t) for (uo, ua), t in zip(uses, tus))
                nf = None
                if fix is not None:
                    fo, fa = fix
                    tf = L.job_ticks(fo, fa)
                    br['PCFixSeconds'] = round(tf / lap_model.TICK, 2)
                    nf = L.next_anim(fo, fa, None)
                    text += ", %s's %s after the fire (%d)" % (fo, fa, tf)
                # his animation after either (the record's next: PCNextAnim
                # as the stay ends, PCPoseAfter after the fire's part)
                nu = None
                for uo, ua in uses:
                    nu = L.next_anim(uo, ua, nu)
                if nu:
                    br['PCNextAnim'] = nu
                if nf:
                    br['PCPoseAfter'] = {'PCFixSeconds': nf}
                if once:
                    br['PCOnce'] = True
                    text += ', once (the visit right after its trick)'
                e['set']['PCWhenTricked'] = {other: br}
                e['source'] += ("; with %s tricked the case's other arm: %s and %s"
                                % (other, instant, text))
            else:
                e['set'].pop('PCWhenTricked', None)
        json.dump(ov, open(p, 'w'), ensure_ascii=False, indent=1); open(p, 'a').write('\n')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
